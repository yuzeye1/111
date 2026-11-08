"""教育端平台：美学赏析 + 闯关实训。

独立平台，挂在 /edu/ 命名空间下（页面 /edu/index，接口 /edu/api/*），
与主站、创作端共享账号与数据库。
"""
from datetime import date

from flask import Blueprint, redirect, render_template, request, url_for

from aesthetics import WEIGHTS, score_artwork
from databaseinit import (Artwork, COURSE_CHANNELS, Course, CourseNote,
                          CourseProgress, Favorite, Material, Message, Partner,
                          PartnerApply, Stage, TeachingEval, User, db)
from utils import current_user, err, login_required, ok

edu_bp = Blueprint('edu', __name__, url_prefix='/edu')

PAGE_SIZE = 20


# ---------- 平台页面 ----------

@edu_bp.get('/')
@edu_bp.get('/index')
def index():
    return render_template('edu/index.html')


@edu_bp.get('/shelf')
def shelf():
    """帧集优集：书架式素材浏览（新设计稿）。"""
    return render_template('edu/shelf.html')


@edu_bp.get('/course')
def course_index():
    """闯关课堂入口：定位首个已解锁阶段的第一课（视频闯关/作业提交与评测）。"""
    for s in _stage_states(current_user()):
        if s['state'] == 'lock':
            continue
        c = Course.query.filter_by(stage_id=s['stage']['id']).order_by(
            Course.order).first()
        if c:
            return redirect(url_for('edu.course_page', cid=c.id))
    return redirect(url_for('edu.index'))


@edu_bp.get('/course/<int:cid>')
def course_page(cid):
    """教学端详情：视频区 + 关卡分配 + 画板 + 笔记（新设计稿）。"""
    return render_template('edu/course.html', cid=cid)


@edu_bp.get('/cooperation')
def cooperation():
    """教育合作：院校 / 机构 / 大厂青苗（新设计稿）。"""
    return render_template('edu/cooperation.html')


# ---------- 素材库（第 26-30 条） ----------

@edu_bp.get('/api/materials')
def materials():
    q = Material.query.filter(db.or_(Material.hidden.is_(None),
                                     Material.hidden.is_(False)))
    cat = request.args.get('cat')
    style = request.args.get('style')
    kw = request.args.get('kw')
    if cat and cat != '全部':
        q = q.filter_by(cat=cat)
    if style:
        q = q.filter_by(style=style)
    if kw:
        q = q.filter(Material.title.contains(kw))
    page = request.args.get('page', 1, type=int)
    pag = q.order_by(Material.id).paginate(
        page=page, per_page=PAGE_SIZE, error_out=False)
    return ok({'items': [m.to_dict() for m in pag.items],
               'total': pag.total, 'page': page,
               'pages': pag.pages})


@edu_bp.get('/api/materials/<int:mid>')
def material_detail(mid):
    m = db.get_or_404(Material, mid)
    return ok(m.to_dict(with_analysis=True))


@edu_bp.get('/api/compare')
def compare():
    ids = [int(x) for x in request.args.get('ids', '').split(',') if x]
    items = [m.to_dict(with_analysis=True)
             for m in Material.query.filter(Material.id.in_(ids)).all()]
    if len(items) != 2:
        return err(400, '请提供两张素材 id')
    return ok(items)


@edu_bp.post('/api/favorites')
@login_required
def add_favorite(user):
    data = request.get_json(force=True)
    folder = (data.get('folder') or '默认收藏夹').strip()
    folders = {f[0] for f in Favorite.query.filter_by(user_id=user.id)
               .with_entities(Favorite.folder).distinct().all()}
    if folder not in folders and len(folders) >= 8:   # 收藏夹上限 8（第 30 条）
        return err(400, '收藏夹已达上限 8 个，请先整理')
    if not db.get_or_404(Material, data.get('material_id', 0)):
        return err(404, '素材不存在')
    if Favorite.query.filter_by(user_id=user.id,
                                 material_id=data.get('material_id')).first():
        return err(400, '已在收藏夹中')
    f = Favorite(user_id=user.id, material_id=data['material_id'],
                 folder=folder)
    db.session.add(f)
    db.session.commit()
    return ok(f.id, '已加入对标收藏')


@edu_bp.get('/api/favorites')
@login_required
def favorites(user):
    rows = Favorite.query.filter_by(user_id=user.id).all()
    mids = [r.material_id for r in rows]
    mats = {m.id: m for m in Material.query.filter(Material.id.in_(mids)).all()}
    return ok([{'id': r.id, 'folder': r.folder,
                'material_id': r.material_id,
                'material': mats[r.material_id].to_dict()}
               for r in rows if r.material_id in mats])


@edu_bp.post('/api/favorites/remove')
@login_required
def remove_favorite(user):
    """放回书架（新设计稿：选取 / 放回）。"""
    data = request.get_json(force=True)
    f = Favorite.query.filter_by(user_id=user.id,
                                 material_id=data.get('material_id')).first()
    if not f:
        return err(404, '该素材不在你的收藏里')
    db.session.delete(f)
    db.session.commit()
    return ok(None, '已放回书架')


@edu_bp.get('/api/daily')
def daily_push():
    """每日推送分流（第 28 条）：主站推商单风格，教育端推知识点。"""
    user = current_user()
    mats = Material.query.filter(db.or_(Material.hidden.is_(None),
                                        Material.hidden.is_(False))
                                 ).order_by(Material.id).all()
    if not mats:
        return ok({'materials': [], 'client_push': '', 'edu_push': ''})
    base = date.today().toordinal() % len(mats)
    picked = [mats[(base + i) % len(mats)] for i in range(3)]
    client_push = '今日商单风格参考：' + '、'.join(
        m.style for m in picked[:2])
    edu_push = '今日精进方向：'
    if user:
        weak = (CourseProgress.query.filter_by(user_id=user.id)
                .order_by(CourseProgress.updated_at.desc()).first())
        if weak and weak.weak:
            edu_push += ('针对薄弱维度「%s」已为你准备了专项教程'
                         % '、'.join(weak.weak))
        else:
            edu_push += '从 L1 第一关开始你的第一课'
    else:
        edu_push += '登录后按你的薄弱维度定制'
    return ok({'materials': [m.to_dict() for m in picked],
               'client_push': client_push, 'edu_push': edu_push})


# ---------- 闯关实训（第 32-37 条） ----------

def _stage_states(user):
    stages = Stage.query.order_by(Stage.order).all()
    passed_ids = set()
    if user:
        passed_ids = {r.course_id for r in CourseProgress.query.filter_by(
            user_id=user.id, status='passed').all()}
    data = []
    for idx, s in enumerate(stages):
        courses = Course.query.filter_by(stage_id=s.id).order_by(
            Course.order).all()
        cids = [c.id for c in courses]
        passed_n = len([c for c in cids if c in passed_ids])
        unlocked = idx == 0
        if idx > 0:
            unlocked = data[idx - 1]['state'] == 'done'
        if passed_n == len(cids) and cids:
            state = 'done'
        elif unlocked:
            state = 'now'
        else:
            state = 'lock'
        data.append({'stage': s.to_dict(), 'course_total': len(cids),
                     'passed': passed_n, 'state': state,
                     'progress': int(passed_n / len(cids) * 100) if cids else 0})
    return data


def _progress_dict(p):
    return {'score': p.score, 'dims': p.dims, 'weak': p.weak,
            'status': p.status, 'attempts': p.attempts}


@edu_bp.get('/api/stages')
def stages():
    return ok(_stage_states(current_user()))


@edu_bp.get('/api/stages/<int:sid>/courses')
def stage_courses(sid):
    user = current_user()
    stage = db.get_or_404(Stage, sid)
    courses = Course.query.filter_by(stage_id=sid).order_by(
        Course.order).all()
    progress = {}
    if user:
        for p in CourseProgress.query.filter_by(user_id=user.id).all():
            progress[p.course_id] = p
    states = _stage_states(user)
    st = next((x for x in states if x['stage']['id'] == sid), None)
    if st and st['state'] == 'lock':
        return err(403, '先完成上一阶段并通关，才能解锁 %s' % stage.name)
    return ok({'stage': stage.to_dict(),
               'state': st['state'] if st else 'now',
               'courses': [{'course': c.to_dict(),
                            'progress': (_progress_dict(progress[c.id])
                                         if c.id in progress else None)}
                           for c in courses]})


@edu_bp.post('/api/courses/<int:cid>/submit')
@login_required
def submit_course(user, cid):
    course = db.get_or_404(Course, cid)
    data = request.get_json(force=True)
    title = (data.get('title') or '').strip()
    if not title:
        return err(400, '请填写作品标题')
    art = Artwork(user_id=user.id, title=title, source='course',
                  style_tag=data.get('style_tag') or course.name,
                  cover=data.get('cover') or 'grad:linear-gradient(135deg,#7B75C9,#EAF7ED)',
                  note=data.get('note'))
    db.session.add(art)
    db.session.flush()
    res = score_artwork(title, data.get('note') or '')   # AI 初评
    p = CourseProgress.query.filter_by(user_id=user.id,
                                       course_id=cid).first()
    if p is None:
        p = CourseProgress(user_id=user.id, course_id=cid)
        db.session.add(p)
    p.score = res['total']
    p.dims = res['dims']
    p.weak = res['weak']
    p.status = 'passed' if res['pass'] else 'retry'
    p.attempts = (p.attempts or 0) + 1
    p.artwork_id = art.id
    if res['pass']:
        # 教学评价记录（第 37 条）
        db.session.add(TeachingEval(
            user_id=user.id, kind='course', title=course.name,
            detail='通关分 %.1f' % res['total']))
        cur = Stage.query.get(course.stage_id)
        if cur:
            cids = [c.id for c in Course.query.filter_by(stage_id=cur.id).all()]
            rows = CourseProgress.query.filter(
                CourseProgress.user_id == user.id,
                CourseProgress.course_id.in_(cids),
                CourseProgress.status == 'passed').all()
            if len(rows) == len(cids):
                db.session.add(TeachingEval(
                    user_id=user.id, kind='stage',
                    title='阶段通关：%s %s' % (cur.code, cur.name),
                    detail='全部 %d 关通过' % len(cids)))
    # 评审通知写入消息盒子（新需求文档：作业评审通知）
    db.session.add(Message(user_id=user.id, kind='review',
                           title='作业评审：%s' % course.name,
                           content=('通关分 %.1f，%s' % (
                               res['total'],
                               '已解锁下一关。' if res['pass']
                               else '未达 80 分，可调整后重试。'))[:400],
                           link='/edu/course'))
    db.session.commit()
    res['attempts'] = p.attempts
    return ok({'result': res, 'artwork': art.to_dict()},
              '通关成功' if res['pass'] else '未达标，已推送薄弱维度补学内容')


@edu_bp.get('/api/growth-map')
@login_required
def growth_map(user):
    progress = CourseProgress.query.filter_by(user_id=user.id).all()
    dims_sum = {}
    dims_n = 0
    for p in progress:
        if p.dims:
            dims_n += 1
            for k, v in p.dims.items():
                dims_sum[k] = dims_sum.get(k, 0) + v
    radar = {k: round(dims_sum.get(k, 0) / dims_n, 1) if dims_n else 0
             for k in WEIGHTS}
    passed = len([p for p in progress if p.status == 'passed'])
    return ok({'stages': _stage_states(user), 'radar': radar,
               'passed': passed, 'attempts': len(progress),
               'records': [{'course_id': p.course_id, 'score': p.score,
                            'weak': p.weak, 'status': p.status}
                           for p in progress]})


@edu_bp.get('/api/teach-evals')
@login_required
def teach_evals(user):
    rows = TeachingEval.query.filter_by(user_id=user.id).order_by(
        TeachingEval.id.desc()).limit(20).all()
    return ok([r.to_dict() for r in rows])


# ---------- 教学端详情页（新设计稿：视频 + 关卡分配 + 画板 + 笔记） ----------

@edu_bp.get('/api/courses/<int:cid>')
def course_detail(cid):
    """课程详情 + 同阶段关卡分配表。"""
    user = current_user()
    course = db.get_or_404(Course, cid)
    stage = Stage.query.get(course.stage_id)
    siblings = Course.query.filter_by(stage_id=course.stage_id).order_by(
        Course.order).all()
    progress = {}
    if user:
        for p in CourseProgress.query.filter_by(user_id=user.id).all():
            progress[p.course_id] = p
    states = _stage_states(user)
    st = next((x for x in states if x['stage']['id'] == course.stage_id),
              None)
    locked = st and st['state'] == 'lock'
    return ok({
        'course': course.to_dict(),
        'stage': stage.to_dict() if stage else None,
        'locked': bool(locked),
        # 关卡分配：编号 ①②③…
        'allocation': [
            {'no': i + 1, 'id': c.id, 'name': c.name,
             'current': c.id == cid,
             'status': ('passed' if progress.get(c.id)
                        and progress[c.id].status == 'passed'
                        else 'todo'),
             'score': progress[c.id].score if progress.get(c.id) else None}
            for i, c in enumerate(siblings)],
        'progress': _progress_dict(progress[cid])
            if cid in progress else None,
    })


@edu_bp.get('/api/courses/<int:cid>/note')
@login_required
def get_note(user, cid):
    n = CourseNote.query.filter_by(user_id=user.id, course_id=cid).first()
    return ok({'content': n.content if n else '', 'updated_at':
               n.updated_at.strftime('%Y-%m-%d %H:%M') if n else None})


@edu_bp.post('/api/courses/<int:cid>/note')
@login_required
def save_note(user, cid):
    from datetime import datetime
    data = request.get_json(force=True)
    n = CourseNote.query.filter_by(user_id=user.id, course_id=cid).first()
    if n is None:
        n = CourseNote(user_id=user.id, course_id=cid)
        db.session.add(n)
    n.content = (data.get('content') or '')[:4000]
    n.updated_at = datetime.utcnow()
    db.session.commit()
    return ok(None, '笔记已保存')


# ---------- 教育合作（新设计稿：院校 / 机构 / 大厂青苗） ----------

@edu_bp.get('/api/partners')
def partners():
    kw = (request.args.get('kw') or '').strip()
    q = Partner.query
    if kw:
        q = q.filter(db.or_(Partner.name.contains(kw),
                            Partner.desc.contains(kw)))
    rows = q.order_by(Partner.id).all()
    grouped = {}
    for p in rows:
        grouped.setdefault(p.kind, []).append(p.to_dict())
    return ok(grouped)


@edu_bp.post('/api/partners/apply')
@login_required
def partner_apply(user):
    """合作报名（新需求文档：表单汇总至后台管理端）。"""
    data = request.get_json(force=True)
    p = db.get_or_404(Partner, int(data.get('partner_id') or 0))
    if PartnerApply.query.filter_by(user_id=user.id,
                                    partner_id=p.id).first():
        return err(400, '你已报名过该合作项目，请耐心等待对接')
    db.session.add(PartnerApply(
        user_id=user.id, partner_id=p.id,
        name=(data.get('name') or user.name or '')[:60],
        contact=(data.get('contact') or user.email or '')[:80],
        note=(data.get('note') or '')[:300]))
    db.session.commit()
    return ok(None, '报名成功，%s 的对接老师会尽快联系你' % p.name)


# ---------- 课程树与渠道（新需求文档：闯关课堂章节树 + 课程资源） ----------

@edu_bp.get('/api/course-tree')
def course_tree():
    """章节树：阶段 → 关卡节点（已完成/当前/锁定三种状态标识）。"""
    user = current_user()
    states = _stage_states(user)
    passed_ids = set()
    if user:
        passed_ids = {r.course_id for r in CourseProgress.query.filter_by(
            user_id=user.id, status='passed').all()}
    tree = []
    for st in states:
        courses = Course.query.filter_by(
            stage_id=st['stage']['id']).order_by(Course.order).all()
        nodes = []
        for c in courses:
            nodes.append({'id': c.id, 'name': c.name,
                          'channel': c.channel,
                          'status': ('passed' if c.id in passed_ids
                                     else 'todo'),
                          'stage_state': st['state']})
        tree.append({'stage': st['stage'], 'state': st['state'],
                     'passed': st['passed'], 'course_total': st['course_total'],
                     'nodes': nodes})
    return ok(tree)


@edu_bp.get('/api/channel-courses')
def channel_courses():
    """按来源渠道浏览课程资源（B站/小红书/MOOC教材/商业拆分/平台上传）。"""
    channel = (request.args.get('channel') or '').strip()
    user = current_user()
    q = Course.query
    if channel and channel != '全部':
        q = q.filter_by(channel=channel)
    rows = q.order_by(Course.id).all()
    stage_map = {s.id: s for s in Stage.query.all()}
    progress = {}
    if user:
        for p in CourseProgress.query.filter_by(user_id=user.id).all():
            progress[p.course_id] = p
    return ok([{'id': c.id, 'name': c.name, 'brief': c.brief,
                'channel': c.channel,
                'stage': stage_map[c.stage_id].code if c.stage_id in stage_map else '',
                'passed': progress.get(c.id) and progress[c.id].status == 'passed'}
               for c in rows])
