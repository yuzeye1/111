"""管理后台（参考 flaskproject.admin，暗色单页 dashboard）。

页面：/admin/login 登录、/admin/ 仪表盘（侧栏 tabs）
接口：/api/admin/*  统一 JWT + is_admin 鉴权（admin_required）
"""
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, redirect, render_template, request, url_for
from flask_jwt_extended import create_access_token

from databaseinit import (Announcement, Artwork, Client, Comment, Feedback,
                          Follow, Material, Message, Order, OrderApplication,
                          OrderRecord, RechargeLog, User, db)
from mailer import check_password_strength, send_admin_notice
from utils import current_user, err, ok

admin_bp = Blueprint('admin', __name__)


# ---------- 鉴权 ----------

def _is_page_request():
    return 'text/html' in (request.headers.get('Accept') or '')


def admin_required(fn):
    """管理员鉴权：页面请求重定向登录页，接口请求返回 401/403 JSON。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            if _is_page_request():
                return redirect(url_for('admin.login_page'))
            return err(401, '请先登录管理后台')
        if not user.is_admin:
            if _is_page_request():
                return redirect(url_for('admin.login_page'))
            return err(403, '需要管理员权限')
        return fn(user, *args, **kwargs)
    return wrapper


def _get_user(uid):
    u = User.query.get(uid)
    if not u:
        return None, err(404, '用户不存在')
    return u, None


# ---------- 页面 ----------

@admin_bp.get('/admin/login')
def login_page():
    return render_template('admin/login.html')


@admin_bp.get('/admin/')
def dashboard():
    """后台仪表盘外壳（与全站一致：页面公开，鉴权在 /api/admin/* 层）。

    JWT 仅存 localStorage、顶层页面导航不带 Authorization 头，故不能在
    页面路由上做服务端守卫；admin.js 首个 API 调用返回 401/403 时跳登录页。
    """
    return render_template('admin/index.html')


# ---------- 登录 ----------

@admin_bp.post('/api/admin/login')
def admin_login():
    data = request.get_json(force=True)
    email = (data.get('email') or '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(data.get('password') or ''):
        return err(401, '邮箱或密码错误')
    if not user.is_admin:
        return err(403, '该账号不是管理员')
    return ok({'token': create_access_token(identity=str(user.id)),
               'user': user.to_dict()}, '登录成功')


# ---------- 概览 ----------

@admin_bp.get('/api/admin/overview')
@admin_required
def overview(user):
    orders_open = Order.query.filter(
        Order.status.in_(['pending', 'accepted', 'delivered'])).count()
    feedback_unrewarded = Feedback.query.filter_by(tokens_awarded=0).count()
    return ok({
        'users': User.query.count(),
        'admins': User.query.filter_by(is_admin=True).count(),
        'students': User.query.filter_by(role='student').count(),
        'clients': User.query.filter_by(role='client').count(),
        'artworks': Artwork.query.count(),
        'materials': Material.query.count(),
        'orders': Order.query.count(),
        'orders_open': orders_open,
        'applications': OrderApplication.query.filter_by(
            status='pending').count(),
        'feedbacks': Feedback.query.count(),
        'feedback_unrewarded': feedback_unrewarded,
        'announcements': Announcement.query.count(),
        'comments': Comment.query.count(),
        'follows': Follow.query.count(),
        'messages': Message.query.count(),
    })


# ---------- 用户管理 ----------

def _admin_user_dict(u):
    return {
        'id': u.id, 'email': u.email, 'name': u.name, 'role': u.role,
        'is_admin': bool(u.is_admin), 'verified': bool(u.verified),
        'credit_score': u.credit_score, 'tokens': u.tokens,
        'banned': bool(u.frozen_until and u.frozen_until > datetime.utcnow()),
        'frozen_until': (u.frozen_until.strftime('%Y-%m-%d')
                         if u.frozen_until else None),
        'created_at': (u.created_at.strftime('%Y-%m-%d')
                       if u.created_at else None),
    }


@admin_bp.get('/api/admin/users')
@admin_required
def user_list(user):
    kw = (request.args.get('kw') or '').strip()
    q = User.query
    if kw:
        like = '%%%s%%' % kw
        q = q.filter(db.or_(User.email.like(like), User.name.like(like)))
    users = q.order_by(User.id).limit(200).all()
    return ok([_admin_user_dict(u) for u in users])


@admin_bp.post('/api/admin/users/<int:uid>/ban')
@admin_required
def user_ban(user, uid):
    u, e = _get_user(uid)
    if e:
        return e
    if u.is_admin:
        return err(400, '不能封禁管理员')
    days = int((request.get_json(force=True) or {}).get('days') or 30)
    u.frozen_until = datetime.utcnow() + timedelta(days=days)
    db.session.add(Message(user_id=u.id, kind='system', title='账号已被限制',
                           content='管理员对你的账号限制接单 %d 天，如有疑问请联系平台。'
                                   % days))
    db.session.commit()
    return ok(None, '已封禁 %d 天' % days)


@admin_bp.post('/api/admin/users/<int:uid>/unban')
@admin_required
def user_unban(user, uid):
    u, e = _get_user(uid)
    if e:
        return e
    u.frozen_until = None
    db.session.add(Message(user_id=u.id, kind='system', title='账号已恢复',
                           content='管理员已解除你的账号限制，可正常接单。'))
    db.session.commit()
    return ok(None, '已解封')


@admin_bp.post('/api/admin/users/<int:uid>/set-admin')
@admin_required
def user_set_admin(user, uid):
    u, e = _get_user(uid)
    if e:
        return e
    u.is_admin = True
    db.session.commit()
    return ok(None, '已设为管理员')


@admin_bp.post('/api/admin/users/<int:uid>/unset-admin')
@admin_required
def user_unset_admin(user, uid):
    u, e = _get_user(uid)
    if e:
        return e
    if u.id == user.id:
        return err(400, '不能撤销自己的管理员权限')
    u.is_admin = False
    db.session.commit()
    return ok(None, '已撤销管理员')


@admin_bp.post('/api/admin/users/<int:uid>/reset-password')
@admin_required
def user_reset_password(user, uid):
    u, e = _get_user(uid)
    if e:
        return e
    password = (request.get_json(force=True) or {}).get('password') or ''
    valid, msg = check_password_strength(password)
    if not valid:
        return err(400, msg)
    u.set_password(password)
    db.session.add(Message(user_id=u.id, kind='system', title='密码已重置',
                           content='管理员重置了你的登录密码，请尽快登录并修改。'))
    db.session.commit()
    return ok(None, '密码已重置')


# ---------- 作品 / 素材 ----------

@admin_bp.get('/api/admin/artworks')
@admin_required
def artwork_list(user):
    items = Artwork.query.order_by(Artwork.id.desc()).limit(200).all()
    out = []
    for a in items:
        d = a.to_dict(brief=True)
        u = User.query.get(a.user_id) if a.user_id else None
        d['user_name'] = u.name if u else '匿名'
        out.append(d)
    return ok(out)


@admin_bp.post('/api/admin/artworks/<int:aid>/moderate')
@admin_required
def artwork_moderate(user, aid):
    a = Artwork.query.get(aid)
    if not a:
        return err(404, '作品不存在')
    data = request.get_json(force=True) or {}
    action = data.get('action')
    if action == 'hide':
        a.visibility = 0
        msg = '作品《%s》已被管理员下架' % (a.title or '')
    elif action == 'restore':
        a.visibility = 2
        msg = '作品《%s》已恢复公开' % (a.title or '')
    else:
        return err(400, '未知操作')
    if a.user_id:
        db.session.add(Message(user_id=a.user_id, kind='system',
                               title='作品状态变更', content=msg))
    db.session.commit()
    return ok({'visibility': a.visibility}, msg)


@admin_bp.get('/api/admin/materials')
@admin_required
def material_list(user):
    items = Material.query.order_by(Material.id).all()
    return ok([m.to_dict() for m in items])


@admin_bp.post('/api/admin/materials/<int:mid>/moderate')
@admin_required
def material_moderate(user, mid):
    m = Material.query.get(mid)
    if not m:
        return err(404, '素材不存在')
    action = (request.get_json(force=True) or {}).get('action')
    if action == 'hide':
        m.hidden = True
        msg = '素材已下架'
    elif action == 'restore':
        m.hidden = False
        msg = '素材已恢复'
    else:
        return err(400, '未知操作')
    db.session.commit()
    return ok(None, msg)


# ---------- 订单 / 仲裁 ----------

@admin_bp.get('/api/admin/orders')
@admin_required
def order_list(user):
    status = (request.args.get('status') or '').strip()
    q = Order.query
    if status:
        q = q.filter_by(status=status)
    orders = q.order_by(Order.id.desc()).limit(200).all()
    out = []
    for o in orders:
        d = o.to_dict()
        c = Client.query.get(o.client_id) if o.client_id else None
        d['client_name'] = (c.company if c else '未知甲方')
        taker = User.query.get(o.taker_id) if o.taker_id else None
        d['taker_name'] = (taker.name if taker else None)
        d['applications'] = OrderApplication.query.filter_by(
            order_id=o.id).count()
        out.append(d)
    return ok(out)


@admin_bp.post('/api/admin/orders/<int:oid>/arbitrate')
@admin_required
def order_arbitrate(user, oid):
    o = Order.query.get(oid)
    if not o:
        return err(404, '订单不存在')
    data = request.get_json(force=True) or {}
    note = (data.get('note') or '').strip()[:200]
    if not note:
        return err(400, '请填写仲裁说明')
    o.status = 'disputed'
    db.session.add(OrderRecord(order_id=o.id, action='arbitrate',
                               actor_id=user.id, note=note))
    # 通知甲方与接单者
    c = Client.query.get(o.client_id) if o.client_id else None
    if c and c.user_id:
        db.session.add(Message(user_id=c.user_id, kind='order',
                               title='订单 #%d 进入仲裁' % o.id,
                               content='平台已介入处理：%s' % note,
                               link='/client/market'))
    if o.taker_id:
        db.session.add(Message(user_id=o.taker_id, kind='order',
                               title='订单 #%d 进入仲裁' % o.id,
                               content='平台已介入处理：%s' % note,
                               link='/me/index'))
    db.session.commit()
    return ok(None, '已标记仲裁并通知双方')


# ---------- 反馈 ----------

@admin_bp.get('/api/admin/feedback')
@admin_required
def feedback_list(user):
    items = Feedback.query.order_by(Feedback.id.desc()).limit(200).all()
    out = []
    for f in items:
        d = f.to_dict()
        u = User.query.get(f.user_id) if f.user_id else None
        d['user_name'] = u.name if u else '匿名'
        d['user_email'] = u.email if u else None
        out.append(d)
    return ok(out)


@admin_bp.post('/api/admin/feedback/<int:fid>/reply')
@admin_required
def feedback_reply(user, fid):
    f = Feedback.query.get(fid)
    if not f:
        return err(404, '反馈不存在')
    data = request.get_json(force=True) or {}
    reply = (data.get('reply') or '').strip()[:200]
    if not reply:
        return err(400, '请填写回复内容')
    award = 0
    u, e = _get_user(f.user_id) if f.user_id else (None, None)
    if u:
        if not f.tokens_awarded:
            award = 5
            f.tokens_awarded = award
            u.tokens += award
            db.session.add(RechargeLog(user_id=u.id, kind='feedback',
                                       tokens=award, amount=0,
                                       note='管理员回复奖励'))
        db.session.add(Message(user_id=u.id, kind='system',
                               title='反馈已回复',
                               content=reply + ('（+%d Token）' % award
                                                if award else '')))
    db.session.commit()
    return ok({'award': award},
              '已回复' + ('，发放 %d Token' % award if award else ''))


# ---------- 公告 ----------

@admin_bp.get('/api/admin/announcements')
@admin_required
def announcement_list(user):
    items = Announcement.query.order_by(
        Announcement.id.desc()).limit(100).all()
    return ok([a.to_dict() for a in items])


@admin_bp.post('/api/admin/announce')
@admin_required
def announce(user):
    data = request.get_json(force=True) or {}
    title = (data.get('title') or '').strip()[:120]
    content = (data.get('content') or '').strip()[:500]
    if not title or not content:
        return err(400, '公告标题与内容不能为空')
    target = data.get('target') or 'all'   # all / user
    uid = data.get('user_id')
    db.session.add(Announcement(title=title, content=content,
                                admin_id=user.id))
    if target == 'user' and uid:
        u, e = _get_user(int(uid))
        if e:
            return e
        targets = [u]
    else:
        targets = User.query.all()
    for t in targets:
        db.session.add(Message(user_id=t.id, kind='system', title=title,
                               content=content[:200], link='/me/index'))
    db.session.commit()
    return ok({'reached': len(targets)}, '公告已下发给 %d 位用户' % len(targets))


# ---------- 邮件通知 ----------

@admin_bp.post('/api/admin/email/send')
@admin_required
def email_send(user):
    data = request.get_json(force=True) or {}
    subject = (data.get('subject') or '').strip()[:120]
    body = (data.get('body') or '').strip()
    if not subject or not body:
        return err(400, '邮件主题与内容不能为空')
    uid = data.get('user_id')
    if uid:
        u, e = _get_user(int(uid))
        if e:
            return e
        recipients = [u]
    else:
        recipients = User.query.filter_by(email_verified=True).all()
    sent, failed = 0, 0
    for r in recipients:
        if not r.email:
            failed += 1
            continue
        try:
            if send_admin_notice(r.email, subject, body):
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    return ok({'sent': sent, 'failed': failed},
              '邮件发送完成：成功 %d，失败 %d' % (sent, failed))
