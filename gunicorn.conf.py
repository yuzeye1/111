# gunicorn 生产配置（对应部署方案：127.0.0.1:8010，nginx 反代 beta.ryanswb.cn）
bind = "127.0.0.1:8010"
workers = 2
timeout = 120
accesslog = "logs/access.log"
errorlog = "logs/error.log"
