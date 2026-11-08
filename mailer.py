"""邮件发送与账号校验工具（逻辑对齐 flaskproject.utils 邮件段）。

只使用阿里云邮件推送（smtpdm.aliyun.com:465 SSL），密钥走环境变量：
  ALIYUN_SMTP_USER      发件邮箱地址（SMTP 用户名）
  ALIYUN_SMTP_PASSWORD  SMTP 密码（阿里云控制台设置，非 AccessKey）
  MAIL_DOMAIN           发件域名，默认 ryanswb.cn
未配置密码时 send_email 打印告警并返回 False（与 flaskproject 行为一致）。
"""
import os
import random
import re
import smtplib
import ssl
import string
import traceback
import uuid
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate

# ---------- 阿里云邮件推送配置 ----------
ALIYUN_EMAIL_SERVER = 'smtpdm.aliyun.com'
ALIYUN_EMAIL_PORT = 465  # SSL 端口
ALIYUN_SMTP_USER = os.getenv('ALIYUN_SMTP_USER', '')
ALIYUN_SMTP_PASSWORD = os.getenv('ALIYUN_SMTP_PASSWORD', '')
MAIL_DOMAIN = os.getenv('MAIL_DOMAIN', 'ryanswb.cn')

SMTP_SERVER = ALIYUN_EMAIL_SERVER
SMTP_PORT = ALIYUN_EMAIL_PORT
SMTP_USER = ALIYUN_SMTP_USER or f'noreply@{MAIL_DOMAIN}'
SMTP_PASSWORD = ALIYUN_SMTP_PASSWORD
SMTP_SENDER_NAME = '帧集 FrameLab'
SMTP_FROM_EMAIL = SMTP_USER

EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'


def is_valid_email(email):
    return bool(email) and bool(re.match(EMAIL_REGEX, email))


def generate_verification_code():
    """生成 6 位随机数字验证码。"""
    return ''.join(random.choices(string.digits, k=6))


def check_password_strength(password):
    """密码强度校验，返回 (bool, msg)。"""
    if not password or len(password) < 6:
        return False, '密码长度至少 6 位'
    if not re.match(r'^[a-zA-Z0-9\x21-\x7e]+$', password):
        return False, '密码仅限英文字母、数字和符号'
    if not (re.search(r'[a-zA-Z]', password) and re.search(r'[0-9]', password)):
        return False, '密码至少同时包含数字和字母'
    return True, '密码强度符合要求'


def format_email_content(content_type, data=None):
    """格式化邮件内容，返回 (text_content, html_content)。

    content_type: verification 验证码 / password_reset 密码重置
    """
    data = data or {}
    text_content = '=' * 60 + '\n【系统邮件，请勿回复】\n' + '=' * 60 + '\n\n'

    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>帧集 FrameLab</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
                background: linear-gradient(135deg, #0f1120 0%, #1a1d33 100%);
                margin: 0; padding: 20px; line-height: 1.6;
            }
            .container { max-width: 600px; margin: 0 auto; background: #ffffff;
                border-radius: 16px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.35); }
            .header { background: linear-gradient(135deg, #6A4DD4 0%, #3E5BA3 55%, #75CBD1 100%);
                color: #fff; padding: 40px 30px; text-align: center; }
            .header h1 { margin: 0; font-size: 26px; font-weight: 700; letter-spacing: 1px; }
            .header p { margin-top: 10px; font-size: 14px; opacity: 0.9; }
            .icon-wrapper { width: 76px; height: 76px; margin: 0 auto 18px;
                background: rgba(255,255,255,0.18); border-radius: 50%;
                display: flex; align-items: center; justify-content: center; }
            .icon { font-size: 38px; }
            .content { padding: 40px 35px; color: #333; }
            .greeting { font-size: 20px; font-weight: 600; color: #2c3e50; margin-bottom: 18px; }
            .info-text { font-size: 16px; color: #555; margin-bottom: 22px; line-height: 1.8; }
            .code-box { background: linear-gradient(135deg, #6A4DD415 0%, #75CBD115 100%);
                border: 2px solid #6A4DD4; border-radius: 12px; padding: 28px 20px;
                text-align: center; margin: 24px 0; }
            .code-label { font-size: 13px; color: #6A4DD4; margin-bottom: 14px; font-weight: 600;
                text-transform: uppercase; letter-spacing: 2px; }
            .code { font-size: 30px; font-weight: 700; color: #6A4DD4; letter-spacing: 6px;
                font-family: 'Courier New', monospace; background: #fff; display: inline-block;
                padding: 14px 22px; border-radius: 8px; box-shadow: 0 4px 15px rgba(106,77,212,0.2); }
            .expire-note { background: #fff3cd; border-left: 4px solid #ffc107; padding: 14px 18px;
                margin: 18px 0; border-radius: 4px; font-size: 14px; color: #856404; }
            .warning { background: #f8d7da; border-left: 4px solid #dc3545; padding: 14px 18px;
                margin: 18px 0; border-radius: 4px; font-size: 14px; color: #721c24; }
            .divider { height: 1px; background: linear-gradient(90deg, transparent, #e9ecef, transparent); margin: 28px 0; }
            .footer { background: #f8f9fa; padding: 28px; text-align: center; border-top: 1px solid #e9ecef; }
            .footer p { margin: 5px 0; font-size: 13px; color: #6c757d; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
    """

    if content_type == 'password_reset':
        code = data.get('code', '')
        expire_minutes = data.get('expire_minutes', 10)
        text_content += '尊敬的用户：\n\n您正在重置帧集 FrameLab 账号密码。\n\n'
        text_content += f'验证码：【{code}】\n\n'
        text_content += f'此验证码在 {expire_minutes} 分钟内有效。\n'
        text_content += '如果这不是您本人的操作，请忽略此邮件。\n\n'
        html_content += f"""
                    <div class="icon-wrapper"><div class="icon">🔑</div></div>
                    <h1>重置密码</h1>
                    <p>您正在找回帧集账号</p>
                </div>
            </div>
            <div class="content">
                <div class="greeting">尊敬的用户：</div>
                <div class="info-text">您正在重置密码，请使用以下验证码完成操作。</div>
                <div class="code-box">
                    <div class="code-label">验证码</div>
                    <div class="code">{code}</div>
                </div>
                <div class="expire-note">⏰ <strong>有效期：</strong>此验证码将在 <strong>{expire_minutes} 分钟</strong>后失效，请尽快使用。</div>
                <div class="warning">⚠️ <strong>安全提醒：</strong>如果这不是您本人的操作，请忽略此邮件，切勿将验证码透露给他人。</div>
        """
    else:
        # verification：注册 / 绑定 / 通用验证码
        code = data.get('code', '')
        expire_minutes = data.get('expire_minutes', 10)
        text_content += '尊敬的用户：\n\n您的验证码是：\n\n'
        text_content += f'    【{code}】\n\n'
        text_content += f'此验证码在 {expire_minutes} 分钟内有效，请尽快使用。\n'
        text_content += '如果这不是您本人的操作，请忽略此邮件。\n\n'
        html_content += f"""
                    <div class="icon-wrapper"><div class="icon">🔐</div></div>
                    <h1>邮箱验证</h1>
                    <p>欢迎加入帧集 FrameLab</p>
                </div>
            </div>
            <div class="content">
                <div class="greeting">尊敬的用户：</div>
                <div class="info-text">感谢您使用帧集 FrameLab！您的验证码如下，请在有效期内完成验证。</div>
                <div class="code-box">
                    <div class="code-label">验证码</div>
                    <div class="code">{code}</div>
                </div>
                <div class="expire-note">⏰ <strong>有效期：</strong>此验证码将在 <strong>{expire_minutes} 分钟</strong>后失效，请尽快使用。</div>
                <div class="warning">⚠️ <strong>安全提醒：</strong>如果这不是您本人的操作，请忽略此邮件，切勿将验证码透露给他人。</div>
        """

    text_content += '=' * 60 + '\n此邮件由系统自动发送，请勿直接回复。\n' + '=' * 60 + '\n'
    html_content += """
                <div class="divider"></div>
                <div class="info-text" style="font-size: 14px; color: #888;">如有任何问题，请联系平台客服获取帮助。</div>
            </div>
            <div class="footer">
                <p>此邮件由系统自动发送，请勿直接回复</p>
                <p>帧集 FrameLab · 全链路设计成长平台</p>
            </div>
        </div>
    </body>
    </html>
    """
    return text_content, html_content


def send_email(to_email, subject, content='', content_type='general', data=None):
    """发送邮件，返回是否成功（bool）。"""
    try:
        if not SMTP_PASSWORD:
            print(f'[邮件发送] ⚠️ 未配置 ALIYUN_SMTP_PASSWORD，跳过发送到 {to_email}')
            print(f'[邮件发送] 验证码/内容：{data or content}')
            return False

        print(f'[邮件发送] 准备发送邮件到: {to_email}, 主题: {subject}')
        if content_type != 'general' and data:
            text_content, html_content = format_email_content(content_type, data)
        else:
            text_content = content
            html_content = (
                '<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
                f'<body style="font-family:\'Microsoft YaHei\',Arial,sans-serif;">'
                f'<p>{content}</p></body></html>'
            )

        msg = MIMEMultipart('alternative')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = f'<{uuid.uuid4().hex}@{MAIL_DOMAIN}>'
        msg['X-Mailer'] = 'Python/SMTP'
        msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        from_email = SMTP_FROM_EMAIL
        msg['From'] = formataddr((str(Header(SMTP_SENDER_NAME, 'utf-8')), from_email))
        msg['To'] = formataddr((str(Header('用户', 'utf-8')), to_email))

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context)
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        print(f'[邮件发送] 邮件发送成功到: {to_email}')
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f'[邮件发送] SMTP 认证错误: {str(e)}')
        traceback.print_exc()
        return False
    except smtplib.SMTPException as e:
        print(f'[邮件发送] SMTP 错误: {str(e)}')
        traceback.print_exc()
        return False
    except Exception as e:
        print(f'[邮件发送] 其他错误: {str(e)}')
        traceback.print_exc()
        return False


def send_admin_notice(to_email, subject, body):
    """管理员后台发送的系统通知邮件（复用 SMTP 通道）。"""
    return send_email(to_email, subject, content=body, content_type='general')
