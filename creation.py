"""创作端平台：灵感 AI + 创作工具 + 云端作品集。

独立平台，挂在 /create/ 命名空间下（页面 /create/index，接口 /create/api/*）。
新需求文档：创作端向下延伸美学鉴赏 / 作品创建 / 作品集书架 / 作品详情。
"""
import base64
import hashlib
import random
import re
import uuid
from datetime import datetime

from flask import Blueprint, current_app, render_template, request

from databaseinit import (Artwork, GEN_MODELS, GEN_TOKEN_COST, GenLog,
                          InspireCall, Material, RechargeLog, SkillTag,
                          TIER_CONFIG, User, WorkflowCase, WorkflowTemplate,
                          db)
from inspire_engine import build_plan, build_plan_ai
import ai_provider
from utils import current_user, err, login_required, ok

create_bp = Blueprint('create', __name__, url_prefix='/create')

ALLOWED_EXT = {'jpg', 'jpeg', 'png', 'webp', 'psd', 'ai', 'pdf'}

EXTERNAL_TOOLS = [
    {'name': '悟空图像', 'url': 'https://www.photosir.com/',
     'desc': '亦心科技官方图像软件 · 官网下载安装，海报与文创 AI 闪绘'},
    {'name': '即梦', 'url': 'https://jimeng.jianying.com/',
     'desc': '多风格出图，适合新媒体视觉'},
    {'name': 'LibLib', 'url': 'https://www.liblib.art/',
     'desc': '模型社区，适合三维写实与产品渲染'},
]


# ---------- 平台页面 ----------

@create_bp.get('/')
@create_bp.get('/index')
def index():
    return render_template('create/index.html')


@create_bp.get('/preview')
def preview():
    """作品预览工作台（新设计稿：新建 / 万向画布 / AI 唤醒）。"""
    return render_template('create/preview.html')


@create_bp.get('/gallery')
def gallery():
    """美学鉴赏素材库（新需求文档：瀑布流 + 筛选 + 大图预览弹窗）。"""
    return render_template('create/gallery.html')


@create_bp.get('/studio')
def studio():
    """作品创建画布（新需求文档：AI 生成 + Token 扣减）。"""
    return render_template('create/studio.html', models=GEN_MODELS)


@create_bp.get('/shelf')
def shelf():
    """作品集书架（新需求文档：排序 / 一键作品集 / 导出简历）。"""
    return render_template('create/shelf.html')


@create_bp.get('/artwork/<int:aid>')
def artwork_page(aid):
    """作品详情（新需求文档：权限 / 分享 / 编辑入口）。"""
    return render_template('create/artwork.html', aid=aid)


# ---------- 灵感 AI（第 12-16 条） ----------

@create_bp.get('/api/tools')
def tools():
    """外部专业工具跳转清单（第 17 条）。"""
    return ok(EXTERNAL_TOOLS)


@create_bp.post('/api/inspire')
@login_required
def inspire(user):
    data = request.get_json(force=True)
    theme = (data.get('theme') or '').strip()
    style = data.get('style') or '扁平商业'
    pain = data.get('pain') or '风格同质化严重'
    if not theme:
        return err(400, '请填写创作主题')

    # 每日免费次数按订阅档位提升（新设计稿：Token 升级系统）
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
    used = InspireCall.query.filter(
        InspireCall.user_id == user.id,
        InspireCall.created_at >= today_start).count()
    free_limit = TIER_CONFIG[user.tier or 0]['inspire_daily']
    if used >= free_limit:
        if user.points < 1:
            return err(402, '今日免费次数已用完且积分不足，明天再来、完成任务赚积分，或升级订阅')
        user.points -= 1

    result = build_plan_ai(theme, style, pain)
    db.session.add(InspireCall(user_id=user.id, theme=theme, style=style,
                               pain=pain, result=result))
    db.session.commit()
    result['remain_free'] = max(free_limit - used - 1, 0)
    return ok(result)


@create_bp.get('/api/inspire/records')
@login_required
def inspire_records(user):
    rows = InspireCall.query.filter_by(user_id=user.id).order_by(
        InspireCall.id.desc()).limit(10).all()
    return ok([{'theme': r.theme, 'style': r.style, 'pain': r.pain,
                'result': r.result,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')}
               for r in rows])


@create_bp.post('/api/workflows')
@login_required
def save_workflow(user):
    """六维方案存为专属工作流模板（第 15 条）。"""
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()
    prompt = (data.get('prompt') or '').strip()
    if not name or not prompt:
        return err(400, '请填写模板名称与提示词')
    w = WorkflowTemplate(user_id=user.id, name=name, prompt=prompt)
    db.session.add(w)
    db.session.commit()
    return ok(w.id, '工作流模板已保存')


@create_bp.get('/api/workflows')
@login_required
def my_workflows(user):
    rows = WorkflowTemplate.query.filter_by(user_id=user.id).all()
    return ok([{'id': r.id, 'name': r.name, 'prompt': r.prompt,
                'shared': r.shared} for r in rows])


# ---------- 作品上传与作品集（第 18-20、24-25 条） ----------

def _store_upload(user, file_storage):
    ext = file_storage.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        return None, None, '不支持的格式，仅限 jpg/png/webp/psd/ai/pdf'
    size = file_storage.content_length or 0
    if size > current_app.config['MAX_CONTENT_LENGTH']:
        return None, None, '单文件不能超过 25MB'
    blob = file_storage.read()
    if len(blob) > current_app.config['MAX_CONTENT_LENGTH']:
        return None, None, '单文件不能超过 25MB'
    size = len(blob)
    free = TIER_CONFIG[user.tier or 0]['storage_gb'] * 1024 ** 3
    if user.storage_used + size > free:
        return None, None, ('空间不足：已用 %.2fGB / %s 空间 %dGB。可清理旧作品、'
                            '升级订阅扩容，或将作品转移到主站公开展示区'
                            % (user.storage_used / 1024 ** 3,
                               TIER_CONFIG[user.tier or 0]['name'],
                               TIER_CONFIG[user.tier or 0]['storage_gb']))
    name = '%s.%s' % (uuid.uuid4().hex, ext)
    path = current_app.config['UPLOAD_FOLDER'] + '/' + name
    with open(path, 'wb') as f:
        f.write(blob)
    user.storage_used += size
    return size, name, None


@create_bp.post('/api/artworks')
@login_required
def upload_artwork(user):
    data = request.form if request.files else request.get_json(force=True)
    title = (data.get('title') or '').strip()
    if not title:
        return err(400, '请填写作品标题')
    size = 0
    saved_name = None
    if request.files and request.files.get('file'):
        size, saved_name, msg = _store_upload(user, request.files['file'])
        if msg:
            db.session.rollback()
            return err(400, msg)
    if not saved_name and data.get('cover_data'):
        # 画板 / 万向画布导出的 dataURL（新设计稿）
        m = re.match(r'data:image/(png|jpeg|webp);base64,(.+)',
                     data.get('cover_data'))
        if not m:
            return err(400, '画板数据格式不正确')
        blob = base64.b64decode(m.group(2))
        if len(blob) > current_app.config['MAX_CONTENT_LENGTH']:
            return err(400, '画板作品不能超过 25MB')
        free = TIER_CONFIG[user.tier or 0]['storage_gb'] * 1024 ** 3
        if user.storage_used + len(blob) > free:
            return err(402, '空间不足，去个人中心升级订阅扩容')
        name = '%s.%s' % (uuid.uuid4().hex, m.group(1))
        with open(current_app.config['UPLOAD_FOLDER'] + '/' + name,
                  'wb') as f:
            f.write(blob)
        user.storage_used += len(blob)
        size = len(blob)
        saved_name = name
    art = Artwork(
        user_id=user.id, title=title,
        source=data.get('source') or 'external',
        style_tag=data.get('style_tag') or '未分类',
        prompt=data.get('prompt'), note=data.get('note'),
        model=data.get('model'),
        tokens_spent=int(data.get('tokens_spent') or 0),
        visibility=int(data.get('visibility') or 2),
        storage_bytes=size)
    if saved_name:
        art.cover = '/static/uploads/' + saved_name
    else:
        art.cover = data.get('cover') or 'grad:linear-gradient(135deg,#6A4DD4,#E2ECF5)'
    SkillTag.ensure(user.id, art.style_tag)
    db.session.add(art)
    db.session.commit()
    return ok(art.to_dict(), '作品已存入云端作品集，上传时间已记录为原创时间戳')


@create_bp.get('/api/artworks')
@login_required
def my_artworks(user):
    source = request.args.get('source')
    uid = request.args.get('user_id', type=int)
    if uid and uid != user.id:
        q = Artwork.query.filter_by(user_id=uid)
    else:
        q = Artwork.query.filter_by(user_id=user.id)
        if source:
            q = q.filter_by(source=source)
    rows = q.order_by(Artwork.id.desc()).all()
    return ok({'items': [a.to_dict() for a in rows],
               'target_user_id': uid or user.id})


@create_bp.get('/api/portfolio/<int:uid>')
def portfolio(uid):
    """作品集实时风格分析 + 自动排版（第 20 条）。"""
    rows = Artwork.query.filter_by(user_id=uid).order_by(
        Artwork.id.desc()).all()
    groups = {}
    for a in rows:
        groups.setdefault(a.style_tag or '未分类', []).append(a.to_dict())
    layout = [{'style': k, 'count': len(v), 'items': v}
              for k, v in sorted(groups.items(),
                                 key=lambda x: -len(x[1]))]
    return ok({'user_id': uid, 'styles': len(groups),
               'total': len(rows), 'layout': layout})


# ---------- 工作流提取与曝光（第 23-24 条 + 第 5 条） ----------

@create_bp.post('/api/workflow-cases')
@login_required
def extract_workflow(user):
    data = request.get_json(force=True)
    if user.exposure < current_app.config['EXPOSURE_UNLOCK']:
        return err(403, ('曝光度不足：当前 %d / %d。作品被浏览、收藏、邀约、'
                         '成交都可积累曝光度'
                         % (user.exposure,
                            current_app.config['EXPOSURE_UNLOCK'])))
    case = WorkflowCase(
        user_id=user.id,
        title=(data.get('title') or '我的工作流案例').strip(),
        steps=data.get('steps') or [
            {'step': '灵感方案', 'content': data.get('theme', '')},
            {'step': '提示词', 'content': data.get('prompt', '')},
            {'step': '成稿说明', 'content': data.get('note', '')}])
    db.session.add(case)
    user.points += 10   # 曝光奖励积分
    db.session.commit()
    return ok(case.to_dict(), '工作流案例已发布，获得 10 积分')


@create_bp.get('/api/workflow-cases')
def workflow_cases():
    rows = WorkflowCase.query.order_by(WorkflowCase.id.desc()).limit(20).all()
    return ok([r.to_dict() for r in rows])


# ---------- 美学鉴赏（新需求文档：创作端分支） ----------

@create_bp.get('/api/materials')
def gallery_materials():
    """瀑布流素材：风格/流派/色彩/媒介/时代筛选 + 关键词。"""
    cat = (request.args.get('cat') or '').strip()
    kw = (request.args.get('kw') or '').strip()
    q = Material.query
    if cat and cat != '全部':
        q = q.filter(db.or_(Material.cat == cat, Material.style == cat))
    if kw:
        q = q.filter(Material.title.contains(kw))
    rows = q.order_by(Material.id.desc()).all()
    return ok([r.to_dict(with_analysis=True) for r in rows])


# ---------- 作品创建：AI 生成（新需求文档） ----------

def _synth_svg(prompt, palette):
    """按提示词种子合成一张抽象流体 SVG（无外部生图服务时的演示生成图）。"""
    seed = int(hashlib.md5((prompt or 'frame').encode('utf-8')).hexdigest(), 16)
    rng = random.Random(seed)
    colors = palette or ['#6A4DD4', '#A4A7E3', '#75CBD1']
    c0, c1 = colors[0], colors[min(1, len(colors) - 1)]
    c2 = colors[min(2, len(colors) - 1)]
    shapes = []
    for _ in range(9):
        cx, cy = rng.randint(60, 964), rng.randint(60, 964)
        r = rng.randint(60, 300)
        o = rng.randint(10, 45)
        col = rng.choice(colors)
        shapes.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{col}" '
                      f'opacity="0.{o}"/>')
    for _ in range(5):
        x, y = rng.randint(0, 800), rng.randint(100, 900)
        w = rng.randint(160, 420)
        shapes.append(f'<path d="M{x} {y} q {w // 2} {rng.randint(-120, 120)} '
                      f'{w} 0" stroke="{rng.choice(colors)}" fill="none" '
                      f'stroke-width="{rng.randint(6, 26)}" opacity="0.5"/>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c0}"/>'
        f'<stop offset="0.55" stop-color="{c1}"/>'
        f'<stop offset="1" stop-color="{c2}"/></linearGradient></defs>'
        '<rect width="1024" height="1024" fill="url(#g)"/>'
        + ''.join(shapes) + '</svg>')
    name = '%s.svg' % uuid.uuid4().hex
    with open(current_app.config['UPLOAD_FOLDER'] + '/' + name, 'w',
              encoding='utf-8') as f:
        f.write(svg)
    return '/static/uploads/' + name


@create_bp.post('/api/generate')
@login_required
def generate(user):
    """AI 生成：扣 Token → 灵感引擎出方案 → 合成 SVG 图 → 记历史。"""
    data = request.get_json(force=True)
    prompt = (data.get('prompt') or '').strip()
    style = data.get('style') or '扁平商业'
    model = data.get('model') or 'nano'
    if not prompt:
        return err(400, '请先填写提示词')
    if model not in {m['id'] for m in GEN_MODELS}:
        return err(400, '模型不存在')
    if user.tokens < GEN_TOKEN_COST:
        return err(402, 'Token 不足：生成一次需 %d，当前 %d。去充值或做任务赚 Token'
                    % (GEN_TOKEN_COST, user.tokens))
    user.tokens -= GEN_TOKEN_COST
    plan = build_plan_ai(prompt, style, '创意概念平淡')
    # 优先用 DashScope 文生图（以方案的提示词为基底，叠加风格）；
    # 不可用/失败时回退到本地 SVG 合成，保证生成永不中断。
    img_prompt = '%s，%s风格，暗色黑紫艺术氛围，高质感' % (
        plan.get('prompt') or prompt, style)
    cover = ai_provider.text_to_image(
        img_prompt, current_app.config['UPLOAD_FOLDER'],
        size='1024*1024')
    source = 'ai'
    if not cover:
        cover = _synth_svg(prompt, plan.get('palette', {}).get('swatches'))
        source = 'synth'
    gen = GenLog(user_id=user.id, prompt=prompt[:500], style=style,
                 model=model, cover=cover, tokens=GEN_TOKEN_COST)
    db.session.add(gen)
    db.session.add(RechargeLog(user_id=user.id, kind='generate',
                               tokens=-GEN_TOKEN_COST, amount=0,
                               note='AI 生成《%s…》(%s)' % (prompt[:8], style)))
    db.session.commit()
    return ok({'gen': gen.to_dict(), 'plan': plan,
               'tokens': user.tokens, 'source': source},
              '生成完成，消耗 %d Token' % GEN_TOKEN_COST)


@create_bp.get('/api/gen-history')
@login_required
def gen_history(user):
    rows = GenLog.query.filter_by(user_id=user.id).order_by(
        GenLog.id.desc()).limit(30).all()
    return ok([r.to_dict() for r in rows])


# ---------- 作品详情与权限（新需求文档） ----------

def _load_visible_artwork(user, aid):
    a = Artwork.query.get(aid)
    if not a:
        return None, err(404, '作品不存在')
    if a.user_id != (user.id if user else -1):
        vis = a.visibility or 0
        if vis == 0:
            return None, err(403, '该作品为私有，仅作者可见')
        if vis == 1 and (not user or user.role != 'client'):
            return None, err(403, '该作品仅对认证甲方可见')
    return a, None


@create_bp.get('/api/artworks/<int:aid>')
def artwork_detail(aid):
    user = current_user()
    a, e = _load_visible_artwork(user, aid)
    if e:
        return e
    author = User.query.get(a.user_id)
    return ok({'artwork': a.to_dict(),
               'owner': a.user_id == (user.id if user else -1),
               'author_name': author.name if author else ''})


@create_bp.post('/api/artworks/<int:aid>/visibility')
@login_required
def set_visibility(user, aid):
    a = Artwork.query.get(aid)
    if not a or a.user_id != user.id:
        return err(403, '只能修改自己的作品')
    vis = int((request.get_json(force=True).get('visibility') or 0))
    if vis not in (0, 1, 2):
        return err(400, '权限档位不合法')
    a.visibility = vis
    db.session.commit()
    return ok({'visibility': vis},
              '已设为%s' % {0: '私有', 1: '仅甲方可见', 2: '完全公开'}[vis])
