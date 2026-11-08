"""帧集 FrameLab 唯一入口（参考 flaskproject.app）。

三个平台共享这一个应用与数据库：
  主站（客户端）  /  /index  /login  /register  /profile/<id>  接口 /api/market/*
  教育端         /edu/index                                接口 /edu/api/*
  创作端         /create/index                              接口 /create/api/*
  账号系统（共用）/api/auth/*

开发运行：python app.py（端口 5001）
生产运行：gunicorn -c gunicorn.conf.py app:app
"""
import os

from dotenv import load_dotenv

# 必须先于其他模块导入，保证 .env 生效
load_dotenv()

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config import Config
from databaseinit import init_db
from userHandle import auth_bp
from education import edu_bp
from creation import create_bp
from marketplace import main_bp
from admin import admin_bp
from utils import current_user, err

config_name = os.getenv('FLASK_CONFIG', 'development')
if config_name == 'production':
    from config_production import ProductionConfig
    app_config = ProductionConfig
else:
    app_config = Config

app = Flask(__name__)
app.config.from_object(app_config)

print(f"[APP] FrameLab 启动 | 配置: {config_name} | 端口: {app.config['PORT']}")
print(f"[APP] 数据库: {app.config['SQLALCHEMY_DATABASE_URI']}")

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.instance_path, exist_ok=True)

CORS(app)
JWTManager(app)
init_db(app)

app.register_blueprint(main_bp)
app.register_blueprint(edu_bp)
app.register_blueprint(create_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)


# 静态资源版本号：CSS/JS 有更新时改这里，模板引用会带 ?v= 强制浏览器重新下载
STATIC_VER = '20261108'


@app.context_processor
def _inject_static_ver():
    return {'static_v': STATIC_VER}


@app.errorhandler(404)
def not_found(_):
    return err(404, '接口不存在')


@app.errorhandler(500)
def server_error(_):
    return err(500, '服务器内部错误')


@app.get('/api/health')
def health():
    u = current_user()
    return jsonify({'code': 0, 'msg': 'FrameLab running',
                    'data': {'user': u.name if u else None}})


if __name__ == '__main__':
    # 开发端口固定 5001，避开 flaskproject 的 5000
    port = app.config['PORT']
    # 启动后自动开浏览器：只在主进程开一次（debug 重载子进程 WERKZEUG_RUN_MAIN=true 不重复开），
    # 这样 run.cmd 只需一个窗口且完整显示服务日志，无需额外 cmd 技巧。
    if os.getenv('OPEN_BROWSER', '1') == '1' and \
            os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        import threading
        import webbrowser
        threading.Timer(2.0, lambda: webbrowser.open(
            'http://127.0.0.1:%d' % port)).start()
    app.run(host='0.0.0.0', port=port, debug=True)
