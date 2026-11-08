import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    ENV = 'development'
    # 开发环境空库时自动灌本地演示数据（生产配置强制关闭）
    AUTOSEED = os.getenv('AUTOSEED', 'true')
    SECRET_KEY = os.getenv('SECRET_KEY', 'framelab-dev-key')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY') or SECRET_KEY
    # flask-jwt-extended 默认 15 分钟，演示站会频繁掉线，放宽到 7 天
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 默认 SQLite；生产用环境变量 DATABASE_URL 覆盖（如 MySQL）
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or (
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'framelab.db'))
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 单文件 25MB（功能清单第 7 条）
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    FREE_STORAGE_BYTES = 1024 ** 3        # 免费空间 1GB（第 8 条）
    EXPOSURE_UNLOCK = 500                 # 工作流转教学权限（第 5 条）
    INSPIRE_FREE_DAILY = 5                # 灵感每天免费次数（第 14 条）
    JSON_AS_ASCII = False
    PORT = 5001
