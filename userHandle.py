"""账号系统（全平台共用）：邮箱注册 / 登录 / 验证码 / 找回密码 / 当前用户。

鉴权沿用 JWT（前端 localStorage 存 token），身份标识由手机号改为邮箱。
邮件与校验逻辑对齐 flaskproject：阿里云 SMTP + EmailVerificationCode + 密码强度。
"""
from datetime import datetime, timedelta

from flask import Blueprint, request
from flask_jwt_extended import create_access_token

from databaseinit import EmailVerificationCode, User, db
from mailer import (check_password_strength, generate_verification_code,
                    is_valid_email, send_email)
from matching import aesthetic_avg, user_level
from utils import current_user, err, login_required, ok

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

CODE_EXPIRE_MINUTES = 10
CODE_RESEND_SECONDS = 60


def _verify_code(email, code, type_):
    """校验验证码，成功返回 (record, None)，失败返回 (None, 错误响应)。"""
    record = (EmailVerificationCode.query
              .filter_by(email=email, code=code, type=type_, is_used=False)
              .order_by(EmailVerificationCode.created_at.desc()).first())
    if not record:
        return None, err(400, '验证码错误')
    if datetime.utcnow() > record.expires_at:
        return None, err(400, '验证码已过期，请重新获取')
    return record, None


def _issue_code(email, type_, user_id=None):
    """生成并发送验证码，含 60 秒限频。返回响应。"""
    last = (EmailVerificationCode.query
            .filter_by(email=email, type=type_, is_used=False)
            .order_by(EmailVerificationCode.created_at.desc()).first())
    if last:
        delta = (datetime.utcnow() - last.created_at).total_seconds()
        if delta < CODE_RESEND_SECONDS:
            return err(400, '请 %d 秒后再试' % (CODE_RESEND_SECONDS - int(delta)))

    code = generate_verification_code()
    db.session.add(EmailVerificationCode(
        user_id=user_id, email=email, code=code, type=type_, is_used=False,
        expires_at=datetime.utcnow() + timedelta(minutes=CODE_EXPIRE_MINUTES)))
    db.session.commit()

    subject = ('重置密码验证码' if type_ == 'reset'
               else '注册验证码' if type_ == 'register' else '邮箱验证码')
    ctype = 'password_reset' if type_ == 'reset' else 'verification'
    sent = send_email(email, subject, '', ctype,
                      {'code': code, 'expire_minutes': CODE_EXPIRE_MINUTES})
    if sent:
        return ok(None, '验证码已发送到你的邮箱')
    # 真实邮件发送失败：标记该验证码作废，提示用户重试，不再回显验证码
    last_code = (EmailVerificationCode.query
                 .filter_by(email=email, type=type_, is_used=False)
                 .order_by(EmailVerificationCode.created_at.desc()).first())
    if last_code:
        last_code.is_used = True
        db.session.commit()
    return err(500, '验证码发送失败，请稍后重试或联系客服')


@auth_bp.post('/send-code')
def send_code():
    data = request.get_json(force=True)
    email = (data.get('email') or '').strip().lower()
    type_ = data.get('type') or 'register'
    if not is_valid_email(email):
        return err(400, '邮箱格式不正确')
    if type_ not in ('register', 'reset', 'bind', 'login'):
        return err(400, '验证码类型不合法')

    exists = User.query.filter_by(email=email).first()
    if type_ == 'register' and exists:
        return err(400, '该邮箱已注册')
    if type_ in ('reset', 'bind', 'login') and not exists:
        return err(400, '该邮箱未注册')
    return _issue_code(email, type_, user_id=exists.id if exists else None)


@auth_bp.post('/register')
def register():
    data = request.get_json(force=True)
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    code = (data.get('code') or '').strip()

    if not is_valid_email(email):
        return err(400, '邮箱格式不正确')
    if User.query.filter_by(email=email).first():
        return err(400, '该邮箱已注册')
    if not code:
        return err(400, '请输入邮箱验证码')

    record, error = _verify_code(email, code, 'register')
    if error:
        return error

    valid, msg = check_password_strength(password)
    if not valid:
        return err(400, msg)

    record.is_used = True
    user = User(
        email=email,
        email_verified=True,
        name=(data.get('name') or '').strip() or ('同学' + email.split('@')[0][:6]),
        school=data.get('school'),
        major=data.get('major'),
        grade=data.get('grade'),
        role=data.get('role') if data.get('role') in ('student', 'client')
        else 'student',
        # 注册福利：1GB 空间 + 30 积分；信用分初始 90
        points=30,
        credit_score=90,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return ok({'token': create_access_token(identity=str(user.id)),
              'user': user.to_dict()}, '注册成功')


@auth_bp.post('/login')
def login():
    data = request.get_json(force=True)
    email = (data.get('email') or '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(data.get('password') or ''):
        return err(401, '邮箱或密码错误')
    return ok({'token': create_access_token(identity=str(user.id)),
              'user': user.to_dict()}, '登录成功')


@auth_bp.post('/reset-password')
def reset_password():
    data = request.get_json(force=True)
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()
    new_password = data.get('new_password') or data.get('password') or ''

    user = User.query.filter_by(email=email).first()
    if not user:
        return err(400, '该邮箱未注册')
    record, error = _verify_code(email, code, 'reset')
    if error:
        return error
    valid, msg = check_password_strength(new_password)
    if not valid:
        return err(400, msg)

    record.is_used = True
    user.set_password(new_password)
    user.email_verified = True
    db.session.commit()
    return ok(None, '密码已重置，请用新密码登录')


@auth_bp.get('/me')
def me():
    user = current_user()
    if not user:
        return ok(None)
    return ok({'user': user.to_dict(),
               'level': user_level(user),
               'aesthetic_avg': aesthetic_avg(user)})
