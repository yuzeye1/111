"""主站（客户端平台）：作品展示 + 派单大厅 + 需求发布 + 实习通道。

主站就是客户端平台本身，页面挂在根路径（/ 与 /index），
接口在 /api/market/* 下；与教育端、创作端共享账号与数据库。
对应功能清单第 26-47 条。
"""
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request

from databaseinit import (Announcement, Application, Artwork, Client, Comment,
                          Course, CourseProgress,
                          CreditLog, Favorite, Feedback, Follow, Internship,
                          Message, OrderApplication, Stage,
                          FEEDBACK_TOKEN_AWARD, InspireCall, Like,
                          Material, Order, OrderRecord, RECHARGE_PACKAGES,
                          RechargeLog, Review, SkillTag, TeachingEval,
                          TIER_CONFIG, TIER_TOKEN_PRICE, User, WorkflowCase,
                          db)
from matching import (aesthetic_avg, match_score, review_avg, stability,
                      user_level)
from utils import current_user, err, login_required, ok

main_bp = Blueprint('main', __name__)


def _level_gate(budget):
    """预算对应的接单门槛（功能清单第 40 条）。"""
    if budget <= 500:
        return 2, 0   # L2+
    if budget <= 2000:
        return 3, 85  # L3+ 且信用分 85+
    return 4, 90      # L4+ 且信用分 90+


def _client_of(user):
    return Client.query.filter_by(user_id=user.id).first()


def _profile_payload(user):
    works = Artwork.query.filter_by(user_id=user.id).order_by(
        Artwork.id.desc()).all()
    evals = TeachingEval.query.filter_by(user_id=user.id).limit(5).all()
    return {
        'user': user.to_dict(brief=True),
        'level': user_level(user),
        'aesthetic_avg': aesthetic_avg(user),
        'review_avg': review_avg(user),
        'stability': stability(user),
        'tags': [t.tag for t in SkillTag.query.filter_by(user_id=user.id).all()],
        'artworks': [a.to_dict() for a in works[:12]],
        'teaching_evals': [e.to_dict() for e in evals],
        'settled_count': Order.query.filter_by(taker_id=user.id,
                                               status='settled').count(),
    }


# ---------- 平台页面 ----------

@main_bp.get('/')
def splash():
    """帧集启动页（新设计稿：动态波纹 + start）。"""
    return render_template('splash.html')


@main_bp.get('/index')
def index():
    """总主页（新需求文档：三大分支入口 + 兴趣社区推送）。"""
    return render_template('index.html')


@main_bp.get('/client/index')
def client_index():
    """客户端主页（新需求文档：波浪通栏 + 六大功能卡）。"""
    return render_template('client/index.html')


@main_bp.get('/client/market')
def client_market():
    """派单大厅（新需求文档：供需双视图 + 筛选 + 卡片流）。"""
    return render_template('client/market.html')


@main_bp.get('/client/match')
def client_match():
    """风格匹配（新需求文档：需求输入 → 设计师匹配列表）。"""
    return render_template('client/match.html')


@main_bp.get('/login')
def login():
    return render_template('login.html')


@main_bp.get('/register')
def register():
    return render_template('register.html')


@main_bp.get('/profile/<int:uid>')
def profile(uid):
    return render_template('profile.html', uid=uid)


# ---------- 个人中心（新设计稿） ----------

@main_bp.get('/me')
def me_center():
    return render_template('me/index.html')


@main_bp.get('/me/recharge')
def me_recharge():
    return render_template('me/recharge.html')


@main_bp.get('/me/favorites')
def me_favorites():
    return render_template('me/favorites.html')


@main_bp.get('/me/settings')
def me_settings():
    return render_template('me/settings.html')


# ---------- 作品展示（第 28-31 条） ----------

@main_bp.get('/api/market/showcase')
def showcase():
    """全站最新作品广场（主站首页作品展示区）。"""
    user = current_user()
    liked_ids = set()
    if user:
        liked_ids = {l.artwork_id for l in Like.query.filter_by(
            user_id=user.id).all()}
    rows = (Artwork.query.filter(Artwork.cover != None)  # noqa: E711
            .order_by(Artwork.id.desc()).limit(12).all())
    items = []
    for a in rows:
        u = User.query.get(a.user_id)
        likes_n = Like.query.filter_by(artwork_id=a.id).count()
        items.append({**a.to_dict(),
                      'author': u.name if u else '',
                      'author_id': a.user_id,
                      'likes': likes_n,
                      'liked': a.id in liked_ids})
    return ok(items)


@main_bp.get('/api/market/profile/<int:uid>')
def public_profile(uid):
    """公开主页：浏览 +1 曝光（第 5 条）。"""
    u = User.query.get(uid)
    if not u:
        return err(404, '用户不存在')
    u.exposure += 1
    db.session.commit()
    return ok(_profile_payload(u))


# ---------- 订单广场（第 26-31、39-41 条） ----------

@main_bp.get('/api/market/orders')
def orders():
    """派单大厅：登录后附带个人匹配度，未登录也可浏览（支持筛选）。"""
    user = current_user()
    kw = (request.args.get('kw') or '').strip()
    min_budget = request.args.get('min_budget', type=float)
    max_days = request.args.get('max_days', type=int)
    tag = (request.args.get('tag') or '').strip()
    q = Order.query.filter_by(status='pending')
    if kw:
        q = q.filter(Order.title.contains(kw))
    if min_budget:
        q = q.filter(Order.budget >= min_budget)
    if max_days:
        q = q.filter(Order.days <= max_days)
    rows = q.order_by(Order.id.desc()).limit(50).all()
    # JSON 列在 SQLite 存储为 ASCII 转义文本，contains 匹配不到中文，改为内存过滤
    if tag:
        rows = [o for o in rows if tag in (o.tags or [])]
    items = []
    for o in rows:
        score, detail = (match_score(user, o) if user else (0, None))
        client = Client.query.get(o.client_id)
        items.append({**o.to_dict(),
                      'company': client.company if client else '',
                      'match': score,
                      'match_detail': detail})
    return ok(items)


@main_bp.get('/api/market/orders/<int:oid>')
def order_detail(oid):
    o = Order.query.get(oid)
    if not o:
        return err(404, '订单不存在')
    client = Client.query.get(o.client_id)
    records = OrderRecord.query.filter_by(order_id=oid).order_by(
        OrderRecord.id).all()
    return ok({**o.to_dict(), 'company': client.company if client else '',
               'records': [{'action': r.action, 'note': r.note,
                            'at': r.created_at.strftime('%Y-%m-%d %H:%M')}
                           for r in records]})


@main_bp.post('/api/market/orders/<int:oid>/grab')
@login_required
def grab_order(user, oid):
    o = Order.query.get(oid)
    if not o or o.status != 'pending':
        return err(400, '订单不存在或已被抢')
    need_lv, need_credit = _level_gate(o.budget)
    lv = user_level(user)
    if lv < need_lv:
        return err(403, '该预算档需要 L%d 以上，你当前 L%d。去教育端闯关提升等级'
                    % (need_lv, lv))
    if user.credit_score < need_credit:
        return err(403, '信用分不足：需 %d，当前 %d' % (need_credit,
                                                    user.credit_score))
    if user.credit_score < 60:
        return err(403, '信用分低于 60 已冻结接单，请先完成在途订单修复信用')
    if user.frozen_until and user.frozen_until > datetime.utcnow():
        return err(403, '接单处于冻结期，至 %s'
                    % user.frozen_until.strftime('%Y-%m-%d'))
    o.taker_id = user.id
    o.status = 'accepted'
    db.session.add(OrderRecord(order_id=o.id, action='grab',
                               actor_id=user.id, note='接单成功'))
    db.session.commit()
    return ok(o.to_dict(), '接单成功，请按需求在 %d 天内交付' % o.days)


@main_bp.post('/api/market/orders/<int:oid>/apply')
@login_required
def apply_order(user, oid):
    """报名制：设计师提交报名方案，等待甲方筛选（新需求文档）。"""
    o = Order.query.get(oid)
    if not o or o.status != 'pending':
        return err(400, '订单不存在或已截止报名')
    mine = _client_of(user)
    if mine and o.client_id == mine.id:
        return err(400, '不能报名自己发布的需求')
    need_lv, need_credit = _level_gate(o.budget)
    lv = user_level(user)
    if lv < need_lv:
        return err(403, '该预算档需要 L%d 以上，你当前 L%d。去教育端闯关提升等级'
                    % (need_lv, lv))
    if user.credit_score < need_credit:
        return err(403, '信用分不足：需 %d，当前 %d' % (need_credit,
                                                    user.credit_score))
    if user.credit_score < 60:
        return err(403, '信用分低于 60 已冻结接单，请先完成在途订单修复信用')
    if user.frozen_until and user.frozen_until > datetime.utcnow():
        return err(403, '接单处于冻结期，至 %s'
                    % user.frozen_until.strftime('%Y-%m-%d'))
    if OrderApplication.query.filter_by(order_id=oid, user_id=user.id).first():
        return err(400, '已报名过该需求')
    data = request.get_json(force=True) if request.is_json else {}
    note = (data.get('note') or '')[:400]
    db.session.add(OrderApplication(order_id=oid, user_id=user.id, note=note))
    cl = Client.query.get(o.client_id) if o.client_id else None
    if cl:
        db.session.add(Message(user_id=cl.user_id, kind='order',
                               title='收到新报名：%s' % o.title,
                               content=('%s 提交了报名方案，请在派单大厅筛选。'
                                        % (user.name or '设计师'))[:400],
                               link='/client/market'))
    db.session.commit()
    return ok({'order_id': oid}, '报名成功，等待甲方筛选')


@main_bp.get('/api/market/orders/<int:oid>/applications')
@login_required
def order_applications(user, oid):
    """甲方查看某需求收到的报名列表。"""
    c = _client_of(user)
    o = Order.query.get(oid)
    if not o or not c or o.client_id != c.id:
        return err(403, '无权查看该需求的报名')
    rows = OrderApplication.query.filter_by(order_id=oid).order_by(
        OrderApplication.id.desc()).all()
    return ok({'items': [r.to_dict() for r in rows]})


@main_bp.post('/api/market/orders/<int:oid>/select/<int:app_id>')
@login_required
def select_applicant(user, oid, app_id):
    """甲方选定报名创作者：设 taker + 其余报名置 rejected + 双方消息。"""
    o = Order.query.get(oid)
    c = _client_of(user)
    if not o or not c or o.client_id != c.id:
        return err(403, '无权操作该需求')
    if o.status != 'pending':
        return err(400, '该需求已成交')
    app = OrderApplication.query.get(app_id)
    if not app or app.order_id != oid:
        return err(404, '报名不存在')
    taker = User.query.get(app.user_id)
    o.taker_id = app.user_id
    o.status = 'accepted'
    app.status = 'accepted'
    for other in OrderApplication.query.filter_by(order_id=oid).all():
        if other.id != app.id and other.status == 'pending':
            other.status = 'rejected'
            db.session.add(Message(user_id=other.user_id, kind='order',
                                   title='报名未通过：%s' % o.title,
                                   content='甲方已选定其他创作者，欢迎继续报名其他需求。',
                                   link='/client/market'))
    db.session.add(OrderRecord(order_id=o.id, action='grab',
                               actor_id=app.user_id, note='甲方选定报名方案'))
    db.session.add(Message(user_id=app.user_id, kind='order',
                           title='报名通过：%s' % o.title,
                           content=('甲方已选定你为创作者，请按需求在 %d 天内交付。'
                                    % o.days)[:400],
                           link='/client/market'))
    db.session.commit()
    return ok(o.to_dict(), '已选定 %s，保证金托管中'
              % (taker.name if taker else '创作者'))


@main_bp.get('/api/market/my-orders')
@login_required
def my_orders(user):
    role = request.args.get('role') or 'taker'
    if role == 'client':
        c = _client_of(user)
        if not c:
            return ok({'role': 'client', 'items': []})
        rows = Order.query.filter_by(client_id=c.id).order_by(
            Order.id.desc()).all()
    else:
        role = 'taker'
        rows = Order.query.filter_by(taker_id=user.id).order_by(
            Order.id.desc()).all()
    return ok({'role': role, 'items': [r.to_dict() for r in rows]})


@main_bp.post('/api/market/orders/<int:oid>/deliver')
@login_required
def deliver(user, oid):
    """交付：上传成品，写入作品集并追加曝光（第 24 条）。"""
    o = Order.query.get(oid)
    if not o or o.taker_id != user.id:
        return err(403, '不是你的订单')
    if o.status != 'accepted':
        return err(400, '当前状态不能交付')
    data = request.get_json(force=True)
    o.status = 'delivered'
    art = Artwork(user_id=user.id,
                  title=data.get('title') or o.title,
                  source='order', style_tag=o.type,
                  cover=data.get('cover') or 'grad:linear-gradient(135deg,#75CBD1,#3E5BA3)',
                  note='来自商单《%s》' % o.title)
    db.session.add(art)
    db.session.add(OrderRecord(order_id=o.id, action='deliver',
                               actor_id=user.id, note='交付成品'))
    cl = Client.query.get(o.client_id) if o.client_id else None
    if cl:
        db.session.add(Message(user_id=cl.user_id, kind='order',
                               title='订单已交付：%s' % o.title,
                               content='创作者已交付成品，请及时验收。',
                               link='/client/market'))
    db.session.commit()
    return ok(o.to_dict(), '已交付，等待甲方验收')


@main_bp.post('/api/market/orders/<int:oid>/review')
@login_required
def review_order(user, oid):
    """甲方验收 + 五星评价：好评信用 +2，差评 -5（第 41 条）。"""
    o = Order.query.get(oid)
    if not o:
        return err(404, '订单不存在')
    c = _client_of(user)
    if not c or o.client_id != c.id:
        return err(403, '只有发布方可以验收')
    if o.status != 'delivered':
        return err(400, '订单还未交付')
    data = request.get_json(force=True)
    rating = max(1, min(5, int(data.get('rating') or 5)))
    o.status = 'reviewed'
    db.session.add(Review(order_id=o.id, rating=rating,
                          comment=(data.get('comment') or '')[:300]))
    taker = User.query.get(o.taker_id)
    if taker:
        delta = 2 if rating >= 4 else -5
        taker.credit_score = max(0, taker.credit_score + delta)
        db.session.add(CreditLog(user_id=taker.id, delta=delta,
                                 reason='订单 #%d 验收 %d 星' % (o.id, rating)))
        if rating <= 2 and taker.credit_score < 60:
            # 冻结 7 天（第 41 条）
            taker.frozen_until = datetime.utcnow().replace(
                hour=23, minute=59, second=59) + timedelta(days=7)
    db.session.add(OrderRecord(order_id=o.id, action='review',
                               actor_id=user.id, note='%d 星' % rating))
    if o.taker_id:
        db.session.add(Message(user_id=o.taker_id, kind='order',
                               title='验收完成：%s' % o.title,
                               content=('甲方给出 %d 星评价，信用分%s。'
                                        % (rating, '+2' if rating >= 4 else '-5'))[:400],
                               link='/client/market'))
    db.session.commit()
    return ok(o.to_dict(), '验收完成，结算将在 24h 内完成')


@main_bp.post('/api/market/orders/<int:oid>/settle')
@login_required
def settle(user, oid):
    """结算：平台确认后完成闭环，双方信用 +2。"""
    o = Order.query.get(oid)
    if not o:
        return err(404, '订单不存在')
    c = _client_of(user)
    if not c or o.client_id != c.id:
        return err(403, '只有发布方可以确认结算')
    if o.status != 'reviewed':
        return err(400, '需先完成验收')
    o.status = 'settled'
    taker = User.query.get(o.taker_id)
    if taker:
        taker.credit_score = min(100, taker.credit_score + 2)
        db.session.add(CreditLog(user_id=taker.id, delta=2,
                                 reason='订单 #%d 结算完成' % o.id))
    db.session.add(OrderRecord(order_id=o.id, action='settle',
                               actor_id=user.id, note='结算完成'))
    if o.taker_id:
        db.session.add(Message(user_id=o.taker_id, kind='order',
                               title='结算完成：%s' % o.title,
                               content='保证金已释放，报酬已入账，感谢履约。',
                               link='/client/market'))
    db.session.commit()
    return ok(o.to_dict(), '结算完成，感谢使用')


# ---------- 甲方发布（第 32-38 条） ----------

@main_bp.post('/api/market/orders')
@login_required
def publish_order(user):
    c = _client_of(user)
    if not c:
        return err(403, '请先完成甲方认证（企业/社团）再发布需求')
    data = request.get_json(force=True)
    title = (data.get('title') or '').strip()
    budget = float(data.get('budget') or 0)
    if not title:
        return err(400, '请填写需求标题')
    if budget < 50:
        return err(400, '预算最低 50 元')
    tags = [t for t in (data.get('tags') or []) if t][:5]
    deposit = round(budget * 0.2, 2)
    o = Order(client_id=c.id, title=title, type=data.get('type') or '海报',
              budget=budget, days=int(data.get('days') or 7), tags=tags,
              requirement=(data.get('requirement') or '')[:500],
              deposit=max(deposit, 50))
    db.session.add(o)
    db.session.add(OrderRecord(order_id=o.id, action='publish',
                               actor_id=user.id, note='已托管保证金 %.0f 元'
                               % o.deposit))
    db.session.commit()
    return ok(o.to_dict(),
              '发布成功，已托管 20%% 保证金（%.0f 元），进入派单大厅' % o.deposit)


@main_bp.post('/api/market/client/verify')
@login_required
def client_verify(user):
    """甲方认证：企业 / 社团（第 32 条）。"""
    if _client_of(user):
        return err(400, '你已完成甲方认证')
    data = request.get_json(force=True)
    company = (data.get('company') or '').strip()
    if not company:
        return err(400, '请填写企业/社团名称')
    c = Client(user_id=user.id, company=company,
               kind=data.get('kind') or 'company')
    db.session.add(c)
    user.role = 'client'
    db.session.commit()
    return ok(c.to_dict(), '认证成功，可以发布需求了')


@main_bp.get('/api/market/client/me')
@login_required
def client_me(user):
    return ok(_client_of(user).to_dict() if _client_of(user) else None)


# ---------- 实习通道（第 45-47 条） ----------

@main_bp.get('/api/market/internships')
def internships():
    lv = request.args.get('level', type=int)
    q = Internship.query.filter_by(verified=True)
    if lv:
        q = q.filter(Internship.need_level <= lv)
    rows = q.order_by(Internship.id.desc()).limit(50).all()
    return ok([r.to_dict() for r in rows])


@main_bp.post('/api/market/internships/<int:iid>/apply')
@login_required
def apply_internship(user, iid):
    it = Internship.query.get(iid)
    if not it:
        return err(404, '岗位不存在')
    if Application.query.filter_by(user_id=user.id, internship_id=iid).first():
        return err(400, '已投递过该岗位')
    if user_level(user) < it.need_level:
        return err(403, '该岗位需要 L%d，你当前 L%d'
                    % (it.need_level, user_level(user)))
    db.session.add(Application(user_id=user.id, internship_id=iid))
    db.session.commit()
    return ok({'internship_id': iid,
               'profile': _profile_payload(user)},
               '投递成功，能力档案已随简历发送给企业')


# ---------- 个人总览 ----------

@main_bp.get('/api/market/me/dashboard')
@login_required
def dashboard(user):
    """三平台联动总览：曝光度 / 等级 / 信用 / 空间。"""
    unlock = 500
    return ok({'exposure': user.exposure, 'unlock': unlock,
               'workflow_teaching_open': user.exposure >= unlock,
               'level': user_level(user),
               'credit': user.credit_score,
               'points': user.points,
               'storage_used': user.storage_used,
               'profile': _profile_payload(user)})


# ---------- 金币 Token：钱包 / 充值 / 升级（新设计稿） ----------

@main_bp.get('/api/market/wallet')
def wallet():
    user = current_user()
    if not user:
        return ok({'tokens': 0, 'tier': 0,
                   'tier_config': TIER_CONFIG,
                   'packages': RECHARGE_PACKAGES,
                   'tier_token_price': TIER_TOKEN_PRICE,
                   'logged_in': False})
    return ok({'tokens': user.tokens, 'tier': user.tier,
               'tier_name': TIER_CONFIG[user.tier or 0]['name'],
               'tier_config': TIER_CONFIG,
               'packages': RECHARGE_PACKAGES,
               'tier_token_price': TIER_TOKEN_PRICE,
               'storage_free': TIER_CONFIG[user.tier or 0]['storage_gb'],
               'logged_in': True})


@main_bp.post('/api/market/recharge')
@login_required
def recharge(user):
    """充值 Token（演示支付：直接入账并留痕）。"""
    data = request.get_json(force=True)
    pkg = next((p for p in RECHARGE_PACKAGES if p['id'] == data.get('package')),
               None)
    if not pkg:
        return err(400, '套餐不存在')
    gained = pkg['tokens'] + pkg.get('bonus', 0)
    user.tokens += gained
    log = RechargeLog(user_id=user.id, kind='recharge', tokens=gained,
                      amount=pkg['price'],
                      note='充值 %d Token（含赠 %d）'
                           % (gained, pkg.get('bonus', 0)))
    db.session.add(log)
    db.session.commit()
    return ok({'tokens': user.tokens, 'log': log.to_dict()},
              '充值成功（演示支付），+%d Token' % gained)


@main_bp.post('/api/market/upgrade')
@login_required
def upgrade(user):
    """升级订阅：Token 扣月费开通（新设计稿：升级系统）。"""
    data = request.get_json(force=True)
    tier = int(data.get('tier') or 0)
    if tier not in (1, 2):
        return err(400, '档位不合法')
    if user.tier >= tier:
        return err(400, '你已是 %s 或更高档位' % TIER_CONFIG[user.tier]['name'])
    price = TIER_TOKEN_PRICE[tier]
    if user.tokens < price:
        return err(402, 'Token 不足：需 %d，当前 %d。先去充值'
                    % (price, user.tokens))
    user.tokens -= price
    user.tier = tier
    db.session.add(RechargeLog(user_id=user.id, kind='upgrade', tokens=-price,
                               amount=0,
                               note='订阅 %s / 月' % TIER_CONFIG[tier]['name']))
    db.session.commit()
    return ok({'tokens': user.tokens, 'tier': tier},
              '已开通 %s：空间 %dGB · 灵感每日 %d 次'
              % (TIER_CONFIG[tier]['name'],
                 TIER_CONFIG[tier]['storage_gb'],
                 TIER_CONFIG[tier]['inspire_daily']))


@main_bp.get('/api/market/recharge/records')
@login_required
def recharge_records(user):
    rows = RechargeLog.query.filter_by(user_id=user.id).order_by(
        RechargeLog.id.desc()).limit(30).all()
    return ok([r.to_dict() for r in rows])


@main_bp.post('/api/market/feedback')
@login_required
def submit_feedback(user):
    """反馈送 Token（新设计稿：通用设置页）。"""
    data = request.get_json(force=True)
    content = (data.get('content') or '').strip()
    if len(content) < 10:
        return err(400, '反馈至少写 10 个字')
    if Feedback.query.filter(Feedback.user_id == user.id,
                              Feedback.content == content).first():
        return err(400, '这条反馈已提交过')
    user.tokens += FEEDBACK_TOKEN_AWARD
    db.session.add(Feedback(user_id=user.id, content=content[:500],
                            tokens_awarded=FEEDBACK_TOKEN_AWARD))
    db.session.add(RechargeLog(user_id=user.id, kind='feedback',
                               tokens=FEEDBACK_TOKEN_AWARD, amount=0,
                               note='反馈奖励'))
    db.session.commit()
    return ok({'tokens': user.tokens},
              '反馈已收到，+%d Token 感谢你让帧集更好'
              % FEEDBACK_TOKEN_AWARD)


@main_bp.get('/api/market/feedback/mine')
@login_required
def my_feedback(user):
    """我的反馈记录（设置页问题反馈面板）。"""
    rows = Feedback.query.filter_by(user_id=user.id).order_by(
        Feedback.id.desc()).limit(20).all()
    return ok({'items': [r.to_dict() for r in rows]})


# ---------- 帧集印迹 + 使用分析（新设计稿：个人中心） ----------

@main_bp.get('/api/market/trace')
@login_required
def trace(user):
    """帧集印迹：跨平台行为时间线。"""
    events = []

    def _ev(at, icon, text):
        if at:
            events.append({'at': at.strftime('%Y-%m-%d'), 'icon': icon,
                           'text': text})

    for a in Artwork.query.filter_by(user_id=user.id).order_by(
            Artwork.id.desc()).limit(15).all():
        _ev(a.created_at, '🎨', '上传作品《%s》(%s)'
            % (a.title, a.style_tag or ''))
    for p in CourseProgress.query.filter_by(user_id=user.id).all():
        c = Course.query.get(p.course_id)
        _ev(p.updated_at, '🎓', '闯关《%s》得分 %.1f %s'
            % (c.name if c else '课程', p.score or 0,
               '通关' if p.status == 'passed' else '待重练'))
    for o in Order.query.filter_by(taker_id=user.id).all():
        _ev(o.created_at, '💼', '接下商单《%s》(¥%.0f)' % (o.title, o.budget))
    mats = {m.id: m for m in Material.query.all()}
    for f in Favorite.query.filter_by(user_id=user.id).all():
        m = mats.get(f.material_id)
        _ev(f.created_at, '⭐', '收藏素材《%s》' % (m.title if m else '?'))
    for r in RechargeLog.query.filter_by(user_id=user.id).all():
        _ev(r.created_at, '🪙', r.note + (' +%d' % r.tokens
            if r.tokens > 0 else ' %d' % r.tokens))
    for w in WorkflowCase.query.filter_by(user_id=user.id).all():
        _ev(w.created_at, '🧩', '发布工作流案例《%s》' % w.title)
    for fb in Feedback.query.filter_by(user_id=user.id).all():
        _ev(fb.created_at, '💬', '提交反馈获得 %d Token' % fb.tokens_awarded)
    for ic in InspireCall.query.filter_by(user_id=user.id).all():
        _ev(ic.created_at, '💡', '生成灵感方案：主题「%s」' % ic.theme)

    events.sort(key=lambda e: e['at'], reverse=True)
    return ok(events[:40])


@main_bp.get('/api/market/me/analysis')
@login_required
def me_analysis(user):
    """使用分析 + 年度关键回顾（个人中心）。"""
    works = Artwork.query.filter_by(user_id=user.id).all()
    passed = CourseProgress.query.filter_by(user_id=user.id,
                                            status='passed').count()
    settled = Order.query.filter_by(taker_id=user.id, status='settled').all()
    income = sum(o.budget for o in settled)
    likes_received = Like.query.filter(
        Like.artwork_id.in_([a.id for a in works] or [0])).count()
    fav_n = Favorite.query.filter_by(user_id=user.id).count()
    insp_n = InspireCall.query.filter_by(user_id=user.id).count()

    # 近 12 个月活跃度（作品 + 闯关 + 订单）
    monthly = {}
    stamps = ([a.created_at for a in works]
              + [p.updated_at for p in CourseProgress.query.filter_by(
                  user_id=user.id).all()]
              + [o.created_at for o in Order.query.filter_by(
                  taker_id=user.id).all()])
    now = datetime.utcnow()
    for i in range(11, -1, -1):
        m = (now.year, now.month - i)
        y, mo = m[0], m[1] % 12 or 12
        monthly['%d-%02d' % (y if m[1] > 0 else y - 1, mo)] = 0
    for t in stamps:
        if not t:
            continue
        key = t.strftime('%Y-%m')
        if key in monthly:
            monthly[key] += 1

    best = (CourseProgress.query.filter_by(user_id=user.id)
            .order_by(CourseProgress.score.desc()).first())
    style_count = {}
    for a in works:
        style_count[a.style_tag or '未分类'] = (
            style_count.get(a.style_tag or '未分类', 0) + 1)
    top_style = max(style_count, key=style_count.get) if style_count else None
    first_work = min((a.created_at for a in works if a.created_at),
                     default=None)

    return ok({
        'counts': {'artworks': len(works), 'passed': passed,
                   'settled': len(settled), 'income': round(income, 2),
                   'likes_received': likes_received,
                   'favorites': fav_n, 'inspires': insp_n,
                   'exposure': user.exposure},
        'monthly': monthly,
        'review': {
            'first_work': first_work.strftime('%Y-%m-%d') if first_work else None,
            'best_score': round(best.score, 1) if best else None,
            'top_style': top_style,
            'settled_income': round(income, 2),
        },
    })


# ---------- 工作简历 + 反转身份（新设计稿：客户端） ----------

@main_bp.get('/api/market/resume')
@login_required
def get_resume(user):
    return ok({'resume': user.resume or {},
              'profile': user.to_dict(brief=True),
              'tags': [t.tag for t in SkillTag.query.filter_by(
                  user_id=user.id).all()]})


@main_bp.post('/api/market/resume')
@login_required
def save_resume(user):
    data = request.get_json(force=True)
    user.resume = {
        'bio': (data.get('bio') or '')[:300],
        'skills': [s for s in (data.get('skills') or [])][:10],
        'experience': (data.get('experience') or '')[:800],
        'works_url': (data.get('works_url') or '')[:200],
    }
    db.session.commit()
    return ok(None, '简历已保存，投递实习时会随能力档案一起发送')


@main_bp.post('/api/market/switch-role')
@login_required
def switch_role(user):
    """反转身份：学生 ⇄ 甲方（新设计稿：客户端按钮）。"""
    user.role = 'client' if user.role != 'client' else 'student'
    db.session.commit()
    return ok({'role': user.role},
              '已切换为%s身份' % ('甲方' if user.role == 'client' else '学生'))


# ---------- 作品点赞（新设计稿：收藏/赞） ----------

@main_bp.post('/api/market/artworks/<int:aid>/like')
@login_required
def like_artwork(user, aid):
    a = db.get_or_404(Artwork, aid)
    existed = Like.query.filter_by(user_id=user.id, artwork_id=aid).first()
    if existed:
        db.session.delete(existed)
        db.session.commit()
        return ok({'liked': False,
                   'likes': Like.query.filter_by(artwork_id=aid).count()})
    db.session.add(Like(user_id=user.id, artwork_id=aid))
    db.session.commit()
    return ok({'liked': True,
               'likes': Like.query.filter_by(artwork_id=aid).count()})


@main_bp.get('/api/market/artworks/<int:aid>/like')
def like_state(aid):
    """点赞数 + 当前登录者是否已赞（未登录 liked=False）。"""
    me = current_user()
    liked = bool(me and Like.query.filter_by(user_id=me.id,
                                             artwork_id=aid).first())
    return ok({'liked': liked,
               'likes': Like.query.filter_by(artwork_id=aid).count()})


@main_bp.get('/api/market/likes/mine')
@login_required
def my_likes(user):
    rows = Like.query.filter_by(user_id=user.id).order_by(
        Like.id.desc()).all()
    aids = [r.artwork_id for r in rows]
    arts = {a.id: a for a in Artwork.query.filter(Artwork.id.in_(aids)).all()}
    items = []
    for r in rows:
        a = arts.get(r.artwork_id)
        if a:
            items.append({'id': r.id, 'liked_at':
                          r.created_at.strftime('%Y-%m-%d'),
                          'artwork': a.to_dict()})
    return ok(items)


# ---------- 风格匹配 / 定向邀约（新需求文档：客户端分支） ----------

@main_bp.post('/api/market/match-designers')
def match_designers():
    """按需求标签在设计师库中匹配契合创作者（匹配算法入口，前端只做展示）。"""
    user = current_user()
    data = request.get_json(force=True)
    requirement = (data.get('requirement') or '').strip()
    style = (data.get('style') or '').strip()
    if not requirement:
        return err(400, '请先描述你的设计需求')
    budget = float(data.get('budget') or 0)

    designers = User.query.filter_by(role='student').all()
    items = []
    for d in designers:
        tags = [t.tag for t in SkillTag.query.filter_by(user_id=d.id).all()]
        overlap = len(set(tags) & {style}) if style else 0
        lv = user_level(d)
        est = aesthetic_avg(d)
        score = int(min(99, 40 + overlap * 30 + lv * 6
                        + max(0, (est - 50)) * 0.4
                        + (10 if budget >= 1000 else 0)))
        works = Artwork.query.filter_by(user_id=d.id).order_by(
            Artwork.id.desc()).limit(3).all()
        settled_n = Order.query.filter_by(taker_id=d.id,
                                          status='settled').count()
        items.append({
            'id': d.id, 'name': d.name, 'school': d.school,
            'major': d.major, 'level': lv, 'aesthetic': est,
            'credit': d.credit_score, 'tags': tags,
            'match': score,
            'works': [w.to_dict(brief=True) for w in works],
            'settled': settled_n,
            'schedule': '档期空闲' if settled_n < 2 else '档期较满',
        })
    items.sort(key=lambda x: -x['match'])
    return ok({'items': items[:12], 'total': len(items)})


@main_bp.post('/api/market/invite')
@login_required
def invite_designer(user):
    """定向邀约：甲方 → 设计师消息盒子（新需求文档）。"""
    data = request.get_json(force=True)
    target_id = int(data.get('designer_id') or 0)
    d = User.query.get(target_id)
    if not d:
        return err(404, '设计师不存在')
    if d.id == user.id:
        return err(400, '不能邀约自己')
    msg = Message(user_id=d.id, kind='invite',
                  title='收到来自 %s 的定向邀约' % (user.name or '甲方'),
                  content=(data.get('note') or '希望与你就新项目展开合作，'
                           '请查看派单大厅详情。')[:400],
                  link='/client/market')
    db.session.add(msg)
    db.session.commit()
    return ok(None, '邀约已发送至 %s 的消息盒子' % (d.name or '对方'))


# ---------- 消息盒子（新需求文档：个人中心） ----------

@main_bp.get('/api/market/messages')
@login_required
def my_messages(user):
    rows = Message.query.filter_by(user_id=user.id).order_by(
        Message.id.desc()).limit(50).all()
    unread = Message.query.filter_by(user_id=user.id, is_read=False).count()
    return ok({'items': [r.to_dict() for r in rows], 'unread': unread})


@main_bp.post('/api/market/messages/<int:mid>/read')
@login_required
def read_message(user, mid):
    m = Message.query.get(mid)
    if not m or m.user_id != user.id:
        return err(403, '消息不存在')
    m.is_read = True
    db.session.commit()
    return ok(None)


@main_bp.post('/api/market/messages/read-all')
@login_required
def read_all_messages(user):
    """消息盒子一键全部已读。"""
    rows = Message.query.filter_by(user_id=user.id, is_read=False).all()
    for m in rows:
        m.is_read = True
    db.session.commit()
    return ok(None, '已将 %d 条消息标记为已读' % len(rows))


# ---------- 用户互动：评论 / 关注 / 统计 ----------

@main_bp.get('/api/social/artworks/<int:aid>/comments')
def artwork_comments(aid):
    rows = Comment.query.filter_by(artwork_id=aid).order_by(
        Comment.id.desc()).limit(50).all()
    return ok({'items': [r.to_dict() for r in rows]})


@main_bp.post('/api/social/artworks/<int:aid>/comments')
@login_required
def add_comment(user, aid):
    art = Artwork.query.get(aid)
    if not art:
        return err(404, '作品不存在')
    data = request.get_json(force=True)
    content = (data.get('content') or '').strip()
    if not content:
        return err(400, '评论内容不能为空')
    db.session.add(Comment(user_id=user.id, artwork_id=aid,
                           content=content[:300]))
    if art.user_id and art.user_id != user.id:
        db.session.add(Message(user_id=art.user_id, kind='coop',
                               title='作品收到新评论：%s' % art.title,
                               content=('%s：%s' % (user.name or '有人',
                                                    content))[:400],
                               link='/create/artwork/%d' % aid))
    db.session.commit()
    return ok(None, '评论已发布')


@main_bp.delete('/api/social/artworks/<int:aid>/comments/<int:cid>')
@login_required
def delete_comment(user, aid, cid):
    c = Comment.query.get(cid)
    if not c or c.artwork_id != aid:
        return err(404, '评论不存在')
    if c.user_id != user.id and not user.is_admin:
        return err(403, '只能删除自己的评论')
    db.session.delete(c)
    db.session.commit()
    return ok(None, '评论已删除')


@main_bp.post('/api/social/users/<int:uid>/follow')
@login_required
def toggle_follow(user, uid):
    if uid == user.id:
        return err(400, '不能关注自己')
    target = User.query.get(uid)
    if not target:
        return err(404, '用户不存在')
    row = Follow.query.filter_by(follower_id=user.id,
                                 following_id=uid).first()
    if row:
        db.session.delete(row)
        db.session.commit()
        return ok({'following': False}, '已取消关注')
    db.session.add(Follow(follower_id=user.id, following_id=uid))
    db.session.add(Message(user_id=uid, kind='coop',
                           title='新增粉丝：%s' % (user.name or '有人'),
                           content='关注了你，去看看 TA 的主页吧。',
                           link='/profile/%d' % user.id))
    db.session.commit()
    return ok({'following': True}, '已关注 %s' % (target.name or 'TA'))


@main_bp.get('/api/social/users/<int:uid>/stats')
def user_social_stats(uid):
    """获赞 / 粉丝 / 关注 + 当前登录者是否已关注。"""
    likes_received = db.session.query(db.func.count(Like.id)).join(
        Artwork, Artwork.id == Like.artwork_id).filter(
        Artwork.user_id == uid).scalar() or 0
    fans = Follow.query.filter_by(following_id=uid).count()
    following = Follow.query.filter_by(follower_id=uid).count()
    me = current_user()
    following_me = bool(me and me.id != uid and Follow.query.filter_by(
        follower_id=me.id, following_id=uid).first())
    return ok({'likes_received': likes_received, 'fans': fans,
               'following': following, 'is_following': following_me})


# ---------- 资质证书（新需求文档：闯关通关 + 平台发放） ----------

@main_bp.get('/api/market/me/certificates')
@login_required
def my_certificates(user):
    """证书 = 已通关阶段平台证书 + 平台实习 offer。"""
    certs = []
    stage_ids = sorted({s[0] for s in Stage.query.with_entities(
        Stage.id).all()})
    for sid in stage_ids:
        courses = Course.query.filter_by(stage_id=sid).all()
        passed = CourseProgress.query.filter_by(
            user_id=user.id, status='passed').with_entities(
            CourseProgress.course_id).all()
        passed_ids = {p[0] for p in passed}
        if courses and all(c.id in passed_ids for c in courses):
            s = Stage.query.get(sid)
            certs.append({'kind': 'stage', 'title': '%s %s 通关证书' % (s.code, s.name),
                          'issuer': '帧集 FrameLab 教育端',
                          'at': datetime.utcnow().strftime('%Y-%m-%d')})
    for it in Application.query.filter_by(user_id=user.id).all():
        ins = Internship.query.get(it.internship_id)
        if ins:
            certs.append({'kind': 'offer', 'title': '%s · %s 定向邀约' % (ins.company, ins.title),
                          'issuer': ins.company, 'at':
                          it.created_at.strftime('%Y-%m-%d')})
    return ok(certs)
