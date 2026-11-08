# 帧集 FrameLab

面向设计学习者与创作者的全链路设计成长平台：**学（教育端）→ 练（创作端）→ 接单变现（主站）** 三个平台共用一套账号与数据库，以扁平结构单 Flask 应用交付。

## 三个平台

| 平台 | 页面路径 | 内容 |
|---|---|---|
| 主站（客户端） | `/index` | 作品广场、派单大厅（报名制）、甲方中心、实习通道、兴趣社区 |
| 教育端 | `/edu/index` | 美学赏析素材库、L1-L4 闯关实训、六维美学评分、成长雷达 |
| 创作端 | `/create/index` | 灵感 AI 六维方案、作品上传、云端作品集、工作流沉淀 |

三端数据互通：教育端通关等级决定主站接单门槛，创作端作品出现在主站广场。

## 功能亮点

- **邮箱验证码注册 + JWT 登录**（三平台共用），未配置 SMTP 时验证码本地回显便于联调
- **六维美学评分引擎**（构图/色彩/层级/留白/风格/创意）与**五维风格匹配**（通关/美学/风格/评价/稳定）
- **派单报名制交易闭环**：设计师提交方案 → 甲方选定 → 冻结保证金 → 交付/验收/仲裁
- **Token 经济**：注册奖励、接单结算、仲裁退款、反馈赠送
- **管理后台** `/admin/`：用户管理、作品/素材下架、订单仲裁、公告、邮件通知
- 消息盒子与社交互动（点赞/评论/关注）贯穿全站
- 暗色设计系统（CSS 变量 tokens + 极光动画 + 玻璃拟态），无前端框架、原生 JS

## 技术栈

Python 3.8 · Flask 2.3 · SQLAlchemy（SQLite 开发 / 可切 MySQL）· Flask-JWT-Extended · Jinja2 · 原生 HTML/CSS/JS · Gunicorn（生产）

## 本地运行

```bash
# 1) 创建虚拟环境并安装依赖
python -m venv .venv
.venv/Scripts/pip.exe install -r requirements.txt

# 2) 准备环境变量（模板已给出，密钥均留空）
cp .env.example .env

# 3) 启动
.venv/Scripts/python.exe app.py        # Windows
# 或 flask run（.flaskenv 已配置）
```

浏览器打开 `http://127.0.0.1:5001`。开发模式空库会自动灌入演示数据（`AUTOSEED=true`）。

### 演示账号（密码均 `frame123`）

| 角色 | 邮箱 |
|---|---|
| 学生 / 设计师 | `student@demo.framelab` |
| 甲方 | `client@demo.framelab` |
| 管理员 | `admin@demo.framelab` |

### 常用命令

```bash
.venv/Scripts/python.exe -X utf8 seed.py        # 重灌演示数据（清库重建）
.venv/Scripts/python.exe -X utf8 user_set.py user list   # 用户运维 CLI（admin/user 子命令）
```

## 目录结构

```
frameLab/
├── app.py               # 唯一入口：装配 5 个蓝图（main/edu/create/auth/admin）
├── config.py            # 开发配置（config_production.py 生产配置，密钥由 .env 提供）
├── databaseinit.py      # db + 全部表模型
├── marketplace.py       # 主站蓝图 / + /api/market、/api/social
├── education.py         # 教育端蓝图 /edu
├── creation.py          # 创作端蓝图 /create
├── userHandle.py        # 账号蓝图 /api/auth（JWT）
├── admin.py             # 管理后台蓝图 /admin
├── aesthetics.py        # 六维美学评分
├── matching.py          # 五维风格匹配
├── inspire_engine.py    # 灵感六维方案生成器
├── seed.py              # 演示数据脚本
├── user_set.py          # 用户运维 CLI
├── templates/           # Jinja2 页面（按平台分目录）
├── static/              # CSS / JS / uploads
└── markdown/            # 项目文档（PRD / 功能清单 / 结构说明）
```

分层约定：蓝图只做校验编排（薄）；算法文件是纯函数；模型只管表和 `to_dict()`。

## 更多文档

- [产品设计方案 PRD](markdown/帧集FrameLab产品设计方案PRD.md)
- [开发功能清单](markdown/开发功能清单.md)
- [项目结构与本地运行说明](markdown/项目结构与本地运行说明.md)
