#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""帧集 FrameLab 用户运维脚本（邮箱版，参考 flaskproject.user_set）。

以邮箱为用户主键标识，提供管理员权限与用户账号的命令行运维能力。
输出统一使用 [INFO]/[OK]/[ERROR] 前缀，列表按 ID 升序。

用法：
    # 管理员权限
    python user_set.py admin add <email>       # 将邮箱账号设为管理员
    python user_set.py admin remove <email>    # 撤销管理员权限
    python user_set.py admin list              # 列出全部管理员（按 ID 排序）

    # 用户管理
    python user_set.py user create --email <邮箱> --password <密码> [--name <昵称>] [--role student|client|teacher]
    python user_set.py user remove --id <ID>
    python user_set.py user remove --email <邮箱>

    # 查询
    python user_set.py user info <搜索词>       # 同时匹配 ID / 邮箱 / 昵称
    python user_set.py user info --id <ID>
    python user_set.py user info --email <邮箱>
    python user_set.py user info --name <昵称>
    python user_set.py user list               # 列出全部用户（按 ID 排序）

    # 重置密码
    python user_set.py user reset --email <邮箱> --password <新密码>
    python user_set.py user reset --id <ID> --password <新密码>
"""
import argparse
import os
import re
import sys

from dotenv import load_dotenv

# 必须先于其他模块导入，保证 .env 生效
load_dotenv()

from flask import Flask

from config import Config
from databaseinit import User, db

VALID_ROLES = ('student', 'client', 'teacher')


def _info(msg):
    print('[INFO] %s' % msg)


def _ok(msg):
    print('[OK] %s' % msg)


def _error(msg):
    print('[ERROR] %s' % msg)


# ---------- 应用与数据库 ----------

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)

with app.app_context():
    db.create_all()


# ---------- 校验 ----------

def is_valid_email(email):
    return bool(email) and bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))


def validate_password(password):
    if not password:
        return False, '密码不能为空'
    if len(password) < 6:
        return False, '密码长度至少 6 位'
    if not re.match(r'^[a-zA-Z0-9\x21-\x7e]+$', password):
        return False, '密码仅限英文字母、数字和符号'
    if not (re.search(r'[a-zA-Z]', password) and re.search(r'[0-9]', password)):
        return False, '密码至少同时包含数字和字母'
    return True, ''


def validate_id(user_id):
    if not user_id or not str(user_id).isdigit():
        return False, 'ID 必须是数字'
    if int(user_id) <= 0:
        return False, 'ID 必须大于 0'
    return True, ''


def find_user(user_id=None, email=None):
    if user_id:
        return db.session.get(User, int(user_id))
    if email:
        return User.query.filter_by(email=email.strip().lower()).first()
    return None


# ---------- 展示 ----------

ROLE_NAMES = {'student': '学生', 'client': '甲方', 'teacher': '讲师'}


def _fmt_created(u):
    return u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else '—'


def _print_table(users):
    print('{:<5} {:<32} {:<12} {:<8} {:<7} {:<9} {:<16}'.format(
        'ID', '邮箱', '昵称', '身份', '管理员', '信用', '注册时间'))
    print('-' * 96)
    for u in users:
        print('{:<5} {:<32} {:<12} {:<8} {:<7} {:<9} {:<16}'.format(
            u.id, u.email or '—', (u.name or '—')[:12],
            ROLE_NAMES.get(u.role, u.role or '—'),
            '是' if u.is_admin else '否',
            u.credit_score, _fmt_created(u)))


# ---------- 管理员 ----------

def admin_list():
    admins = User.query.filter_by(is_admin=True).order_by(User.id.asc()).all()
    if not admins:
        _info('当前没有管理员')
        return True
    _ok('管理员列表（共 %d 位）：' % len(admins))
    _print_table(admins)
    return True


def admin_set(email, action):
    email = (email or '').strip().lower()
    if not is_valid_email(email):
        _error('邮箱格式不正确：%s' % email)
        return False
    user = User.query.filter_by(email=email).first()
    if not user:
        _error('邮箱 %s 对应的用户不存在' % email)
        return False
    if action == 'add':
        if user.is_admin:
            _info('用户 %s 已是管理员，无需重复设置' % email)
            return True
        user.is_admin = True
        db.session.commit()
        _ok('已将 %s（ID %d）设为管理员' % (email, user.id))
    elif action == 'remove':
        if not user.is_admin:
            _info('用户 %s 本就不是管理员' % email)
            return True
        user.is_admin = False
        db.session.commit()
        _ok('已撤销 %s（ID %d）的管理员权限' % (email, user.id))
    else:
        _error('无效动作 %s，请使用 add 或 remove' % action)
        return False
    return True


# ---------- 用户增删查改 ----------

def user_create(email, password, name=None, role='student'):
    email = (email or '').strip().lower()
    if not is_valid_email(email):
        _error('邮箱格式不正确：%s' % email)
        return False
    valid, msg = validate_password(password)
    if not valid:
        _error(msg)
        return False
    if role not in VALID_ROLES:
        _error('身份 role 仅支持 %s' % '/'.join(VALID_ROLES))
        return False
    if User.query.filter_by(email=email).first():
        _error('邮箱 %s 已存在' % email)
        return False
    user = User(email=email, name=name or email.split('@')[0], role=role,
                email_verified=True, verified=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    _ok('用户创建成功：ID %d | 邮箱 %s | 身份 %s'
        % (user.id, user.email, ROLE_NAMES.get(role, role)))
    return True


def _related_user_models():
    """收集所有含 user_id 列的模型（用于级联清理）。"""
    models = []
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        if cls is User or not hasattr(cls, '__table__'):
            continue
        if 'user_id' in {c.key for c in cls.__table__.columns}:
            models.append(cls)
    return models


def user_remove(user_id=None, email=None):
    user = find_user(user_id=user_id, email=email)
    if not user:
        _error('用户不存在（id=%s email=%s）' % (user_id, email))
        return False
    if user.is_admin:
        _error('不能删除管理员账号，请先撤销管理员权限')
        return False
    uid = user.id
    label = '%s（ID %d）' % (user.email, uid)
    try:
        from databaseinit import (Announcement, Follow, Order, OrderApplication,
                                  OrderRecord)
        # 1) 通用：删除所有 user_id 归属的行
        for cls in _related_user_models():
            try:
                db.session.query(cls).filter_by(user_id=uid).delete(
                    synchronize_session=False)
            except Exception:
                pass
        # 2) 关注关系（follower/following 双向）
        Follow.query.filter(db.or_(Follow.follower_id == uid,
                                   Follow.following_id == uid)).delete(
            synchronize_session=False)
        # 3) 报名记录
        OrderApplication.query.filter_by(user_id=uid).delete(
            synchronize_session=False)
        # 4) 管理员发布的公告
        Announcement.query.filter_by(admin_id=uid).delete(
            synchronize_session=False)
        # 5) 订单流水（操作人）与接单者引用
        OrderRecord.query.filter_by(actor_id=uid).delete(
            synchronize_session=False)
        for o in Order.query.filter_by(taker_id=uid).all():
            o.taker_id = None
        db.session.delete(user)
        db.session.commit()
        _ok('用户已删除：%s' % label)
        return True
    except Exception as exc:
        db.session.rollback()
        _error('删除用户失败：%s' % exc)
        return False


def user_info(user_id=None, email=None, name=None, term=None):
    users = []
    if term:
        if str(term).isdigit():
            u = db.session.get(User, int(term))
            if u:
                users.append(u)
        like = '%%%s%%' % term
        users.extend(User.query.filter(db.or_(
            User.email.like(like), User.name.like(like))).all())
        users = list({u.id: u for u in users}.values())
    elif user_id:
        u = db.session.get(User, int(user_id))
        if u:
            users.append(u)
    elif email:
        u = User.query.filter_by(email=email.strip().lower()).first()
        if u:
            users.append(u)
    elif name:
        users = User.query.filter_by(name=name).all()

    if not users:
        _error('未找到匹配的用户')
        return False
    users.sort(key=lambda x: x.id)
    _ok('查询到 %d 位用户：' % len(users))
    for u in users:
        print('-' * 60)
        print('ID       : %d' % u.id)
        print('邮箱     : %s' % (u.email or '—'))
        print('昵称     : %s' % (u.name or '—'))
        print('身份     : %s' % ROLE_NAMES.get(u.role, u.role or '—'))
        print('管理员   : %s' % ('是' if u.is_admin else '否'))
        print('邮箱验证 : %s' % ('已验证' if u.email_verified else '未验证'))
        print('资格认证 : %s' % ('已认证' if u.verified else '未认证'))
        print('信用分   : %s' % u.credit_score)
        print('Token    : %s' % u.tokens)
        print('注册时间 : %s' % _fmt_created(u))
    print('-' * 60)
    return True


def user_list():
    users = User.query.order_by(User.id.asc()).all()
    if not users:
        _info('当前没有用户')
        return True
    _ok('用户列表（共 %d 位）：' % len(users))
    _print_table(users)
    return True


def user_reset(user_id=None, email=None, password=None):
    valid, msg = validate_password(password)
    if not valid:
        _error(msg)
        return False
    user = find_user(user_id=user_id, email=email)
    if not user:
        _error('用户不存在（id=%s email=%s）' % (user_id, email))
        return False
    user.set_password(password)
    db.session.commit()
    _ok('密码已重置：%s（ID %d）' % (user.email, user.id))
    return True


# ---------- CLI ----------

def build_parser():
    parser = argparse.ArgumentParser(
        description='帧集 FrameLab 用户运维脚本（邮箱版）')
    sub = parser.add_subparsers(dest='command')

    admin_p = sub.add_parser('admin', help='管理员权限')
    admin_p.add_argument('args', nargs='*', help='add/remove <email> 或 list')

    user_p = sub.add_parser('user', help='用户管理')
    usub = user_p.add_subparsers(dest='action')

    c = usub.add_parser('create', help='创建用户')
    c.add_argument('--email', required=True)
    c.add_argument('--password', required=True)
    c.add_argument('--name')
    c.add_argument('--role', default='student')

    r = usub.add_parser('remove', help='删除用户')
    rg = r.add_mutually_exclusive_group(required=True)
    rg.add_argument('--id')
    rg.add_argument('--email')

    i = usub.add_parser('info', help='查询用户')
    i.add_argument('--id')
    i.add_argument('--email')
    i.add_argument('--name')
    i.add_argument('term', nargs='?', help='同时匹配 ID/邮箱/昵称')

    usub.add_parser('list', help='列出全部用户')

    rp = usub.add_parser('reset', help='重置密码')
    rpg = rp.add_mutually_exclusive_group(required=True)
    rpg.add_argument('--id')
    rpg.add_argument('--email')
    rp.add_argument('--password', required=True)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        _error('请提供命令')
        print(__doc__)
        sys.exit(1)

    with app.app_context():
        if args.command == 'admin':
            a = args.args or []
            if a and a[0] == 'list':
                sys.exit(0 if admin_list() else 1)
            if len(a) >= 2 and a[0] in ('add', 'remove'):
                sys.exit(0 if admin_set(a[1], a[0]) else 1)
            _error('用法：admin add/remove <email> 或 admin list')
            sys.exit(1)

        if args.command == 'user':
            act = args.action
            if act == 'create':
                ok_ = user_create(args.email, args.password,
                                  args.name, args.role)
            elif act == 'remove':
                ok_ = user_remove(user_id=args.id, email=args.email)
            elif act == 'info':
                if not (args.term or args.id or args.email or args.name):
                    _error('请提供 <搜索词> 或 --id/--email/--name')
                    sys.exit(1)
                if args.id:
                    valid, msg = validate_id(args.id)
                    if not valid:
                        _error(msg)
                        sys.exit(1)
                ok_ = user_info(user_id=args.id, email=args.email,
                                name=args.name, term=args.term)
            elif act == 'list':
                ok_ = user_list()
            elif act == 'reset':
                if args.id:
                    valid, msg = validate_id(args.id)
                    if not valid:
                        _error(msg)
                        sys.exit(1)
                ok_ = user_reset(user_id=args.id, email=args.email,
                                 password=args.password)
            else:
                _error('请提供有效的 user 子命令')
                print(__doc__)
                sys.exit(1)
            sys.exit(0 if ok_ else 1)


if __name__ == '__main__':
    main()
