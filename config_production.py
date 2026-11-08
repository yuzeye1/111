import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class ProductionConfig:
    ENV = 'production'
    # 生产首次部署只建表，绝不灌演示数据
    AUTOSEED = 'false'
    # 生产密钥必须由服务器 .env 提供，不给默认值
    SECRET_KEY = os.environ['SECRET_KEY']
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY') or SECRET_KEY
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 生产数据库由环境变量指定，如 mysql+pymysql://user:pwd@localhost:3306/framelab
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    FREE_STORAGE_BYTES = 1024 ** 3
    EXPOSURE_UNLOCK = 500
    INSPIRE_FREE_DAILY = 5
    JSON_AS_ASCII = False
    PORT = 8010
