"""数据库初始化与全部表模型（参考 flaskproject.databaseinit）。

一张表一个类，全部集中在此文件，由 app.py 调用 init_db() 完成建库建表。
"""
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def mask_email(email):
    """公开场景邮箱掩码：ab***@x.com。"""
    if not email or '@' not in email:
        return email or ''
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        head = local[0] + '***'
    else:
        head = local[:2] + '***'
    return head + '@' + domain

# 五维解析字段
ANALYSIS_KEYS = ['构图亮点', '色彩逻辑', '视觉层级', '美学韵律', '可借鉴点']

ORDER_FLOW = ['pending', 'accepted', 'delivered', 'reviewed', 'settled']

# 订阅档位：商业定价模型（Free 免费获客 / Pro 盈利 / Team 拉客单）
TIER_CONFIG = {
    0: {'name': 'Free', 'price': 0, 'storage_gb': 1, 'inspire_daily': 5,
        'free_quota': 30, 'seats': 1},
    1: {'name': 'Pro', 'price': 49, 'storage_gb': 3, 'inspire_daily': 15,
        'seats': 1},
    2: {'name': 'Team', 'price': 199, 'storage_gb': 10, 'inspire_daily': 30,
        'seats': 5},
}

# 人民币定价：Pro 支持月付/年付，Team 仅月付（含 5 席）
TIER_RMB_PRICE = {1: {'month': 49, 'year': 399}, 2: {'month': 199}}

# 充值套餐（新设计稿：金币 Token）
RECHARGE_PACKAGES = [
    {'id': 'r6',  'tokens': 60,   'price': 6},
    {'id': 'r30', 'tokens': 300,  'price': 30, 'bonus': 30},
    {'id': 'r98', 'tokens': 980,  'price': 98, 'bonus': 180},
]

# 订阅月费（Token 计价）
TIER_TOKEN_PRICE = {1: 120, 2: 300}

FEEDBACK_TOKEN_AWARD = 2

# AI 生成（作品创建页）：单次消耗与可选模型（新需求文档）
GEN_TOKEN_COST = 3
GEN_MODELS = [
    {'id': 'nano', 'name': 'nano banana', 'desc': '快出图，适合灵感草稿'},
    {'id': 'libai', 'name': 'lib AI', 'desc': '风格化强，适合国潮与插画'},
    {'id': 'jimeng', 'name': '即梦', 'desc': '细节丰富，适合写实与包装'},
]

# 课程资源渠道（教育端主页：课程选择区域）
COURSE_CHANNELS = ['B站', '小红书', 'MOOC教材', '商业拆分', '平台上传']


def init_db(app):
    """建表 + 按环境初始化数据。

    - 任何环境都 create_all() 建表；
    - production：只建表，绝不灌演示数据；若用户表为空且 env 提供
      ADMIN_EMAIL/ADMIN_PASSWORD，创建一个管理员账号便于运维；
    - development：建表后若关键表为空且 AUTOSEED 开启，自动灌本地演示数据。
    """
    import os

    db.init_app(app)
    with app.app_context():
        db.create_all()
        env = (app.config.get('ENV') or os.getenv('FLASK_CONFIG')
               or 'development').lower()
        if env.startswith('prod'):
            _ensure_admin(app)
        else:
            autoseed = str(app.config.get('AUTOSEED',
                                          os.getenv('AUTOSEED', 'true'))
                           ).lower() not in ('0', 'false', 'no')
            if autoseed and Material.query.first() is None:
                from seed import run_seed
                run_seed()


def _ensure_admin(app):
    """生产首次部署：无该账号时按 env 创建管理员（可选，多 worker 并发安全）。"""
    import os

    email = (os.getenv('ADMIN_EMAIL') or '').strip()
    password = os.getenv('ADMIN_PASSWORD') or ''
    if not email or not password:
        return
    if User.query.filter_by(email=email).first() is not None:
        return
    admin = User(email=email, name='管理员', role='teacher',
                 verified=True, email_verified=True, is_admin=True)
    admin.set_password(password)
    db.session.add(admin)
    try:
        db.session.commit()
    except Exception:
        # 多 worker 并发首启：另一进程已抢先创建同名管理员，放弃即可
        db.session.rollback()


# ---------- 用户与技能标签 ----------

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    email_verified = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(256))
    name = db.Column(db.String(50))
    school = db.Column(db.String(100))
    major = db.Column(db.String(100))
    grade = db.Column(db.String(20))
    # student 学生 / client 甲方 / teacher 认证讲师
    role = db.Column(db.String(20), default='student')
    is_admin = db.Column(db.Boolean, default=False)   # 管理员标识（后台权限）
    verified = db.Column(db.Boolean, default=False)
    credit_score = db.Column(db.Integer, default=90)    # 信用分（第 41 条）
    exposure = db.Column(db.Integer, default=0)         # 曝光度（第 5 条）
    points = db.Column(db.Integer, default=30)          # 积分
    tokens = db.Column(db.Integer, default=0)           # 金币 Token（新设计稿）
    tier = db.Column(db.Integer, default=0)              # 订阅档 0/1/2
    resume = db.Column(db.JSON)                          # 工作简历 {bio,skills,experience}
    storage_used = db.Column(db.BigInteger, default=0)  # 已用空间（字节）
    frozen_until = db.Column(db.DateTime)               # 接单冻结期
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash or '', raw)

    def to_dict(self, brief=False):
        d = {
            'id': self.id, 'name': self.name,
            'email': mask_email(self.email) if brief else self.email,
            'school': self.school, 'major': self.major, 'grade': self.grade,
            'role': self.role, 'is_admin': bool(self.is_admin),
            'verified': self.verified,
            'credit_score': self.credit_score, 'exposure': self.exposure,
            'points': self.points, 'tokens': self.tokens, 'tier': self.tier,
        }
        if not brief:
            d['storage_used'] = self.storage_used
            d['storage_free'] = TIER_CONFIG[self.tier or 0]['storage_gb'] * 1024 ** 3
            d['tier_name'] = TIER_CONFIG[self.tier or 0]['name']
            d['frozen_until'] = (self.frozen_until.isoformat()
                                 if self.frozen_until else None)
        return d


class SkillTag(db.Model):
    __tablename__ = 'skill_tags'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    tag = db.Column(db.String(50))

    @staticmethod
    def ensure(user_id, tag):
        if not tag:
            return
        if not SkillTag.query.filter_by(user_id=user_id, tag=tag).first():
            db.session.add(SkillTag(user_id=user_id, tag=tag))


# ---------- 邮箱验证码（注册 / 重置 / 绑定 / 登录） ----------

class EmailVerificationCode(db.Model):
    __tablename__ = 'email_verification_codes'

    id = db.Column(db.Integer, primary_key=True)
    # 注册时尚无用户，user_id 可为空
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)
    # register 注册 / reset 重置密码 / bind 绑定邮箱 / login 登录
    type = db.Column(db.String(20), nullable=False, index=True)
    is_used = db.Column(db.Boolean, default=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- 教育端：素材库 ----------

class Material(db.Model):
    __tablename__ = 'materials'

    id = db.Column(db.Integer, primary_key=True)
    cat = db.Column(db.String(20), index=True)      # 经典艺术/现代商业/小众创意/美学理论
    style = db.Column(db.String(30), index=True)
    title = db.Column(db.String(120))
    artist = db.Column(db.String(60))
    year = db.Column(db.String(20))
    scene = db.Column(db.String(60))                # 适用场景
    cover = db.Column(db.String(500))               # grad:linear-gradient(...) 或 /static/uploads/..
    analysis = db.Column(db.JSON)                   # 五维解析
    hidden = db.Column(db.Boolean, default=False)   # 管理员下架
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, with_analysis=False):
        d = {
            'id': self.id, 'cat': self.cat, 'style': self.style,
            'title': self.title, 'artist': self.artist, 'year': self.year,
            'scene': self.scene, 'cover': self.cover,
            'hidden': bool(self.hidden),
        }
        if with_analysis:
            d['analysis'] = self.analysis
        return d


class Favorite(db.Model):
    __tablename__ = 'favorites'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    material_id = db.Column(db.Integer, db.ForeignKey('materials.id'))
    folder = db.Column(db.String(30), default='默认收藏夹')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- 教育端：闯关实训 ----------

class Stage(db.Model):
    __tablename__ = 'stages'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(4))          # L1 - L4
    name = db.Column(db.String(40))
    desc = db.Column(db.String(200))
    order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {'id': self.id, 'code': self.code, 'name': self.name,
                'desc': self.desc}


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey('stages.id'), index=True)
    name = db.Column(db.String(80))
    brief = db.Column(db.String(300))       # 命题/知识点说明
    channel = db.Column(db.String(20))      # 课程来源渠道（B站/小红书/MOOC教材/商业拆分/平台上传）
    order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {'id': self.id, 'stage_id': self.stage_id,
                'name': self.name, 'brief': self.brief,
                'channel': self.channel}


class CourseProgress(db.Model):
    __tablename__ = 'course_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), index=True)
    score = db.Column(db.Float)             # 通关分（第 34 条）
    dims = db.Column(db.JSON)               # 六维得分
    weak = db.Column(db.JSON)               # 薄弱维度
    status = db.Column(db.String(20), default='available')  # passed / retry
    attempts = db.Column(db.Integer, default=0)
    artwork_id = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class TeachingEval(db.Model):
    __tablename__ = 'teaching_evals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    kind = db.Column(db.String(20))    # course 课程完成 / stage 阶段通关 / workflow 教学内容采纳
    title = db.Column(db.String(120))
    detail = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'kind': self.kind, 'title': self.title,
                'detail': self.detail,
                'created_at': self.created_at.strftime('%Y-%m-%d')}


# ---------- 创作端：作品与灵感 ----------

class Artwork(db.Model):
    __tablename__ = 'artworks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    title = db.Column(db.String(120))
    # external 外部工具 / studio 站内 / course 闯关作业 / order 接单交付 / workflow 工作流
    source = db.Column(db.String(20), default='external')
    style_tag = db.Column(db.String(30))
    cover = db.Column(db.String(500))
    prompt = db.Column(db.Text)
    note = db.Column(db.String(500))
    visibility = db.Column(db.Integer, default=2)   # 0 私有 / 1 仅甲方可见 / 2 完全公开
    model = db.Column(db.String(40))               # 生成所用 AI 模型（作品创建页）
    tokens_spent = db.Column(db.Integer, default=0)  # 生成消耗 Token
    storage_bytes = db.Column(db.BigInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, brief=False):
        d = {
            'id': self.id, 'user_id': self.user_id, 'title': self.title,
            'source': self.source, 'style_tag': self.style_tag,
            'cover': self.cover, 'prompt': self.prompt, 'note': self.note,
            'visibility': self.visibility or 0, 'model': self.model,
            'tokens_spent': self.tokens_spent or 0,
            'created_at': self.created_at.strftime('%Y-%m-%d'),
        }
        if not brief:
            d['storage_bytes'] = self.storage_bytes
        return d


class InspireCall(db.Model):
    __tablename__ = 'inspire_calls'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    theme = db.Column(db.String(120))
    style = db.Column(db.String(30))
    pain = db.Column(db.String(60))
    result = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WorkflowTemplate(db.Model):
    __tablename__ = 'workflow_templates'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    name = db.Column(db.String(80))
    prompt = db.Column(db.Text)
    shared = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WorkflowCase(db.Model):
    __tablename__ = 'workflow_cases'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    title = db.Column(db.String(120))
    steps = db.Column(db.JSON)             # 灵感→提示词→草图→成稿 链路
    status = db.Column(db.String(20), default='published')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'title': self.title, 'steps': self.steps,
                'status': self.status,
                'created_at': self.created_at.strftime('%Y-%m-%d')}


# ---------- 主站：派单与实习 ----------

class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    company = db.Column(db.String(100))
    kind = db.Column(db.String(20), default='company')   # company / club
    verified = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {'id': self.id, 'company': self.company, 'kind': self.kind,
                'verified': self.verified}


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    title = db.Column(db.String(120))
    type = db.Column(db.String(30))          # 海报/文创/IP/包装/新媒体
    budget = db.Column(db.Float)
    days = db.Column(db.Integer)
    tags = db.Column(db.JSON)
    requirement = db.Column(db.String(500))
    deposit = db.Column(db.Float)            # 保证金（第 38 条）
    # pending→accepted→delivered→reviewed→settled / disputed
    status = db.Column(db.String(20), default='pending', index=True)
    taker_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'title': self.title, 'type': self.type,
            'budget': self.budget, 'days': self.days, 'tags': self.tags or [],
            'requirement': self.requirement, 'deposit': self.deposit,
            'status': self.status, 'taker_id': self.taker_id,
            'created_at': self.created_at.strftime('%Y-%m-%d'),
        }


class OrderRecord(db.Model):
    __tablename__ = 'order_records'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), index=True)
    action = db.Column(db.String(20))        # grab/deliver/review/settle/dispute
    actor_id = db.Column(db.Integer)
    note = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), index=True)
    rating = db.Column(db.Integer)           # 1-5
    comment = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CreditLog(db.Model):
    __tablename__ = 'credit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    delta = db.Column(db.Integer)
    reason = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Internship(db.Model):
    __tablename__ = 'internships'

    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(100))
    title = db.Column(db.String(80))
    pay = db.Column(db.String(60))
    need_level = db.Column(db.Integer, default=2)
    tags = db.Column(db.JSON)
    remote = db.Column(db.Boolean, default=False)
    verified = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'company': self.company, 'title': self.title,
                'pay': self.pay, 'need_level': self.need_level,
                'tags': self.tags or [], 'remote': self.remote,
                'verified': self.verified}


class Application(db.Model):
    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id'))
    status = db.Column(db.String(20), default='applied')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- 金币 Token：充值 / 升级 / 反馈 ----------

class RechargeLog(db.Model):
    __tablename__ = 'recharge_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    kind = db.Column(db.String(20))    # recharge 充值 / upgrade 订阅 / feedback 反馈奖励
    tokens = db.Column(db.Integer)    # 变动数量（升级为负数）
    amount = db.Column(db.Float)      # 支付金额（演示支付）
    note = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'kind': self.kind, 'tokens': self.tokens,
                'amount': self.amount, 'note': self.note,
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')}


class Feedback(db.Model):
    __tablename__ = 'feedbacks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    content = db.Column(db.String(500))
    tokens_awarded = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'content': self.content,
                'tokens_awarded': self.tokens_awarded,
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')}


# ---------- 课程笔记（教学端详情页） ----------

class CourseNote(db.Model):
    __tablename__ = 'course_notes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), index=True)
    content = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- 作品点赞 ----------

class Like(db.Model):
    __tablename__ = 'likes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    artwork_id = db.Column(db.Integer, db.ForeignKey('artworks.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- 教育合作（院校 / 机构 / 大厂青苗） ----------

class Partner(db.Model):
    __tablename__ = 'partners'

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), index=True)   # 院校 / 机构 / 大厂青苗
    name = db.Column(db.String(100))
    desc = db.Column(db.String(300))
    cover = db.Column(db.String(500))             # grad:... 渐变标识
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'kind': self.kind, 'name': self.name,
                'desc': self.desc, 'cover': self.cover}


# ---------- AI 生成记录（作品创建页） ----------

class GenLog(db.Model):
    __tablename__ = 'gen_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    prompt = db.Column(db.Text)
    style = db.Column(db.String(30))
    model = db.Column(db.String(40))
    cover = db.Column(db.String(500))        # 合成图（SVG）路径或渐变
    tokens = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'prompt': self.prompt, 'style': self.style,
                'model': self.model, 'cover': self.cover, 'tokens': self.tokens,
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')}


# ---------- 消息盒子（邀约 / 评审 / 需求通知） ----------

class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    kind = db.Column(db.String(20))          # invite 邀约 / review 评审 / order 需求 / coop 合作
    title = db.Column(db.String(120))
    content = db.Column(db.String(500))
    link = db.Column(db.String(200))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'kind': self.kind, 'title': self.title,
                'content': self.content, 'link': self.link,
                'is_read': self.is_read,
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')}


# ---------- 教育合作报名 ----------

class PartnerApply(db.Model):
    __tablename__ = 'partner_applies'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('partners.id'))
    name = db.Column(db.String(60))
    contact = db.Column(db.String(80))
    note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- 用户互动：评论 / 关注 ----------

class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    artwork_id = db.Column(db.Integer, db.ForeignKey('artworks.id'), index=True)
    content = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        u = User.query.get(self.user_id) if self.user_id else None
        return {'id': self.id, 'user_id': self.user_id,
                'user_name': (u.name if u else '匿名'),
                'artwork_id': self.artwork_id, 'content': self.content,
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')}


class Follow(db.Model):
    __tablename__ = 'follows'
    __table_args__ = (db.UniqueConstraint('follower_id', 'following_id',
                                          name='uq_follow_pair'),)

    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    following_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- 管理员公告 ----------

class Announcement(db.Model):
    __tablename__ = 'announcements'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120))
    content = db.Column(db.String(500))
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'title': self.title, 'content': self.content,
                'admin_id': self.admin_id,
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')}


# ---------- 派单报名（报名制：设计师提交方案，甲方选定） ----------

class OrderApplication(db.Model):
    __tablename__ = 'order_applications'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    note = db.Column(db.String(400))            # 报名方案说明
    status = db.Column(db.String(16), default='pending')  # pending/accepted/rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        u = User.query.get(self.user_id) if self.user_id else None
        return {'id': self.id, 'order_id': self.order_id,
                'user_id': self.user_id,
                'user_name': (u.name if u else '匿名'),
                'note': self.note, 'status': self.status,
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')}
