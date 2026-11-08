"""DashScope（阿里云百炼）AI 接入层（纯标准库 urllib，无第三方依赖）。

统一封装两类能力，供创作端「灵感方案」与「AI 生成图片」调用：
  1) 文本对话  chat()             —— qwen-plus，OpenAI 兼容端点
  2) 文生图    text_to_image()    —— wanx2.1-t2i-turbo，原生异步任务 + 轮询

设计原则：
  * 仅用标准库 urllib.request，避免运行环境（venv）缺 requests 导致启动失败。
  * 未配置 DASHSCOPE_API_KEY 或调用失败/超时/限流时，返回 None，
    由调用方回退到本地规则引擎 / SVG 合成，保证功能永不中断。
  * 生成的图片会下载到本地 uploads（DashScope 返回的是带签名、会过期的 OSS 链接）。
"""
import json
import os
import time
import urllib.error
import urllib.request
import uuid

# 端点常量
CHAT_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
T2I_SUBMIT_URL = ('https://dashscope.aliyuncs.com/api/v1/services/'
                  'aigc/text2image/image-synthesis')
TASK_URL = 'https://dashscope.aliyuncs.com/api/v1/tasks/'

CHAT_MODEL = os.getenv('DASHSCOPE_CHAT_MODEL', 'qwen-plus')
IMAGE_MODEL = os.getenv('DASHSCOPE_IMAGE_MODEL', 'wanx2.1-t2i-turbo')


def _api_key():
    return (os.getenv('DASHSCOPE_API_KEY')
            or os.getenv('IMAGE_API_KEY')
            or os.getenv('LLM_API_KEY') or '').strip()


def is_enabled():
    return bool(_api_key())


def _headers(async_task=False):
    h = {'Authorization': 'Bearer ' + _api_key(),
         'Content-Type': 'application/json'}
    if async_task:
        h['X-DashScope-Async'] = 'enable'
    return h


def _http(url, payload=None, headers=None, timeout=45):
    """极简 HTTP：返回 (status, body_bytes)；网络/HTTP 错误返回 (None, b'')."""
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers=headers or {},
        method='POST' if data is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:  # 非 2xx
        try:
            return e.code, e.read()
        except Exception:  # noqa: BLE001
            return e.code, b''
    except Exception as e:  # noqa: BLE001  网络/超时/DNS 等
        print('[ai] http error: %s' % e)
        return None, b''


def _json_of(body):
    try:
        return json.loads(body.decode('utf-8'))
    except Exception:  # noqa: BLE001
        return None


# ---------- 文本对话 ----------

def chat(prompt, system=None, model=None, temperature=0.8, max_tokens=1500,
         timeout=45):
    """单轮/多轮对话，返回助手文本；任何异常返回 None。"""
    if not is_enabled():
        return None
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    if isinstance(prompt, list):
        messages.extend(prompt)
    else:
        messages.append({'role': 'user', 'content': prompt})
    status, body = _http(CHAT_URL,
                         {'model': model or CHAT_MODEL,
                          'messages': messages,
                          'temperature': temperature,
                          'max_tokens': max_tokens},
                         headers=_headers(), timeout=timeout)
    if status != 200:
        print('[ai] chat http %s: %s' % (status, body[:200]))
        return None
    data = _json_of(body) or {}
    return (data.get('choices') or [{}])[0].get(
        'message', {}).get('content') or None


def chat_json(prompt, system=None, model=None, temperature=0.7,
              max_tokens=1500, timeout=45):
    """对话并要求返回 JSON，解析失败返回 None。"""
    text = chat(prompt, system=system, model=model, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout)
    if not text:
        return None
    return _extract_json(text)


def _extract_json(text):
    """从模型输出中稳健提取 JSON 对象（容忍 ```json 包裹与前后废话）。"""
    s = text.strip()
    if s.startswith('```'):
        s = s.strip('`')
        if s.lower().startswith('json'):
            s = s[4:]
    start, end = s.find('{'), s.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(s[start:end + 1])
    except Exception:  # noqa: BLE001
        return None


# ---------- 文生图 ----------

def text_to_image(prompt, upload_dir, size='1024*1024', negative_prompt=None,
                  model=None, n=1, poll_timeout=90, poll_interval=3):
    """异步提交文生图任务并轮询，成功后下载图片到 upload_dir。

    返回本地相对路径（如 '/static/uploads/xxx.png'）；失败返回 None。
    """
    if not is_enabled() or not prompt:
        return None
    payload = {'model': model or IMAGE_MODEL,
               'input': {'prompt': prompt[:800]},
               'parameters': {'size': size, 'n': n}}
    if negative_prompt:
        payload['input']['negative_prompt'] = negative_prompt[:400]
    status, body = _http(T2I_SUBMIT_URL, payload,
                         headers=_headers(async_task=True), timeout=45)
    if status != 200:
        print('[ai] t2i submit http %s: %s' % (status, body[:200]))
        return None
    task_id = ((_json_of(body) or {}).get('output') or {}).get('task_id')
    if not task_id:
        return None

    deadline = time.time() + poll_timeout
    img_url = None
    while time.time() < deadline:
        time.sleep(poll_interval)
        st, tb = _http(TASK_URL + task_id, headers=_headers(), timeout=30)
        if st != 200:
            continue
        out = ((_json_of(tb) or {}).get('output') or {})
        status_ = out.get('task_status')
        if status_ == 'SUCCEEDED':
            results = out.get('results') or []
            if results:
                img_url = results[0].get('url')
            break
        if status_ in ('FAILED', 'CANCELED', 'UNKNOWN'):
            print('[ai] t2i task %s: %s' % (status_, out.get('message', '')))
            return None
    if not img_url:
        return None
    return _download(img_url, upload_dir)


def _download(url, upload_dir):
    """下载远程图片到本地 uploads，返回相对 URL。"""
    status, content = _http(url, timeout=60)
    if status != 200 or not content:
        return None
    ext = 'png'
    # 依据魔数判断常见格式（OSS 链接不一定带可靠 Content-Type）
    if content[:3] == b'\xff\xd8\xff':
        ext = 'jpg'
    elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        ext = 'webp'
    name = '%s.%s' % (uuid.uuid4().hex, ext)
    os.makedirs(upload_dir, exist_ok=True)
    with open(os.path.join(upload_dir, name), 'wb') as f:
        f.write(content)
    return '/static/uploads/' + name
