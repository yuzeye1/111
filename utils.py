"""通用工具：统一响应格式 + 登录态装饰器。"""
from functools import wraps

from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from databaseinit import User


def ok(data=None, msg='ok'):
    return jsonify({'code': 0, 'msg': msg, 'data': data})


def err(code, msg):
    return jsonify({'code': code, 'msg': msg, 'data': None}), code


def current_user():
    """可选登录：带有效 JWT 返回 User，否则 None。"""
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    uid = get_jwt_identity()
    if not uid:
        return None
    return User.query.get(int(uid))


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return err(401, '请先登录')
        return fn(user, *args, **kwargs)
    return wrapper
