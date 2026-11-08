/* FrameLab 前端 API 封装：JWT 自动携带 + 统一 {code,msg,data} 处理 */

const API = {
  tokenKey: 'framelab_jwt',

  getToken() {
    return localStorage.getItem(this.tokenKey);
  },

  setToken(t) {
    localStorage.setItem(this.tokenKey, t);
  },

  logout() {
    localStorage.removeItem(this.tokenKey);
    location.href = '/login';
  },

  async request(method, url, body) {
    const headers = {};
    const t = this.getToken();
    if (t) headers['Authorization'] = 'Bearer ' + t;
    let payload = null;
    if (body instanceof FormData) {
      payload = body;
    } else if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      payload = JSON.stringify(body);
    }
    const res = await fetch(url, {
      method, headers, body: payload, credentials: 'same-origin',
    });
    const data = await res.json().catch(() => ({ code: -1, msg: '网络错误' }));
    if (res.status === 401) {
      localStorage.removeItem(this.tokenKey);
      return { code: 401, msg: '请先登录', data: null };
    }
    return data;
  },

  get(url)        { return this.request('GET', url); },
  post(url, body) { return this.request('POST', url, body); },
  delete(url)     { return this.request('DELETE', url); },
  upload(url, fd) { return this.request('POST', url, fd); },

  toast(msg, ok = true) {
    const el = document.createElement('div');
    el.className = 'toast ' + (ok ? 'toast-ok' : 'toast-err');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.classList.add('show'), 10);
    setTimeout(() => el.remove(), 3200);
  },

  esc(s) {
    return String(s ?? '').replace(/[&<>"']/g,
      c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  },

  coverCss(cover) {
    if (!cover) return 'linear-gradient(135deg,#A4A7E3,#6A4DD4)';
    if (cover.startsWith('grad:')) return cover.slice(5);
    return `url('${this.esc(cover)}') center/cover`;
  },

  async ensureLogin() {
    const me = await this.get('/api/auth/me');
    if (me.code !== 0 || !me.data) return null;
    return me.data.user || me.data;
  },
};

function fmtDate(s) { return s || ''; }

function levelBadge(lv) {
  const names = { 0: 'L0 新手', 1: 'L1', 2: 'L2', 3: 'L3', 4: 'L4+' };
  return names[Math.min(lv, 4)] || 'L' + lv;
}
