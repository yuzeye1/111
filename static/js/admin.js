/* 管理后台单页逻辑：tab 切换 + 各面板加载与操作 */
(() => {
  const esc = API.esc.bind(API);
  const ROLE_NAMES = { student: '学生', client: '甲方', teacher: '讲师' };
  const ORDER_STATUS = {
    pending: '待接单', accepted: '进行中', delivered: '已交付',
    reviewed: '已验收', settled: '已结算', disputed: '仲裁中',
    cancelled: '已取消',
  };
  const VIS_NAMES = { 0: '私有/已下架', 1: '仅甲方', 2: '公开' };

  // ---------- tab 切换 ----------
  const loaders = {
    overview: loadOverview, users: loadUsers, artworks: loadArtworks,
    materials: loadMaterials, orders: loadOrders, feedback: loadFeedback,
    announce: loadAnnouncements, email: () => {},
  };
  document.querySelectorAll('.adm-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.adm-tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.adm-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      document.getElementById('panel-' + tab).classList.add('active');
      (loaders[tab] || (() => {}))();
    });
  });

  async function api(url, body) {
    const res = body === undefined ? await API.get(url) : await API.post(url, body);
    if (res.code === 401 || res.code === 403) {
      API.toast(res.msg || '无权限', false);
      setTimeout(() => { location.href = '/admin/login'; }, 900);
      return null;
    }
    return res;
  }

  // ---------- 概览 ----------
  async function loadOverview() {
    const res = await api('/api/admin/overview');
    if (!res || res.code !== 0) return;
    const d = res.data;
    const cards = [
      ['用户总数', d.users], ['管理员', d.admins], ['学生', d.students],
      ['甲方', d.clients], ['作品', d.artworks], ['素材', d.materials],
      ['订单总数', d.orders], ['进行中订单', d.orders_open],
      ['待处理报名', d.applications], ['反馈总数', d.feedbacks],
      ['未奖励反馈', d.feedback_unrewarded], ['公告', d.announcements],
      ['评论', d.comments], ['关注关系', d.follows], ['站内消息', d.messages],
    ];
    document.getElementById('ov-cards').innerHTML = cards.map(([k, v]) =>
      `<div class="adm-card glass"><div class="adm-card-num">${v}</div>
       <div class="adm-card-key">${k}</div></div>`).join('');
  }

  // ---------- 用户 ----------
  async function loadUsers() {
    const kw = document.getElementById('u-kw').value.trim();
    const res = await api('/api/admin/users' + (kw ? '?kw=' + encodeURIComponent(kw) : ''));
    if (!res || res.code !== 0) return;
    document.getElementById('u-body').innerHTML = res.data.map((u) => {
      const ops = [];
      ops.push(u.banned
        ? `<button class="btn btn-sm" onclick="ADM.unban(${u.id})">解封</button>`
        : `<button class="btn btn-sm" onclick="ADM.ban(${u.id})">封禁</button>`);
      ops.push(u.is_admin
        ? `<button class="btn btn-sm" onclick="ADM.unsetAdmin(${u.id})">撤管理员</button>`
        : `<button class="btn btn-sm" onclick="ADM.setAdmin(${u.id})">设管理员</button>`);
      ops.push(`<button class="btn btn-sm" onclick="ADM.resetPwd(${u.id})">重置密码</button>`);
      return `<tr><td>${u.id}</td><td>${esc(u.email)}</td><td>${esc(u.name || '')}</td>
        <td>${ROLE_NAMES[u.role] || u.role}</td><td>${u.is_admin ? '✔' : ''}</td>
        <td>${u.credit_score}</td><td>${u.tokens}</td>
        <td>${u.banned ? `<span class="adm-bad">已封禁至 ${u.frozen_until}</span>` : '正常'}</td>
        <td class="adm-ops">${ops.join(' ')}</td></tr>`;
    }).join('') || '<tr><td colspan="9">没有匹配的用户</td></tr>';
  }
  document.getElementById('u-search').addEventListener('click', loadUsers);
  document.getElementById('u-kw').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') loadUsers();
  });

  // ---------- 作品 ----------
  async function loadArtworks() {
    const res = await api('/api/admin/artworks');
    if (!res || res.code !== 0) return;
    document.getElementById('a-body').innerHTML = res.data.map((a) => {
      const btn = (a.visibility || 0) === 0
        ? `<button class="btn btn-sm" onclick="ADM.moderateArtwork(${a.id},'restore')">恢复公开</button>`
        : `<button class="btn btn-sm" onclick="ADM.moderateArtwork(${a.id},'hide')">下架</button>`;
      return `<tr><td>${a.id}</td><td>${esc(a.title || '')}</td>
        <td>${esc(a.user_name || '')}</td><td>${esc(a.source || '')}</td>
        <td>${VIS_NAMES[a.visibility] || a.visibility}</td>
        <td>${a.created_at}</td><td class="adm-ops">${btn}</td></tr>`;
    }).join('') || '<tr><td colspan="7">暂无作品</td></tr>';
  }

  // ---------- 素材 ----------
  async function loadMaterials() {
    const res = await api('/api/admin/materials');
    if (!res || res.code !== 0) return;
    document.getElementById('m-body').innerHTML = res.data.map((m) => {
      const btn = m.hidden
        ? `<button class="btn btn-sm" onclick="ADM.moderateMaterial(${m.id},'restore')">恢复</button>`
        : `<button class="btn btn-sm" onclick="ADM.moderateMaterial(${m.id},'hide')">下架</button>`;
      return `<tr><td>${m.id}</td><td>${esc(m.cat || '')}</td>
        <td>${esc(m.title || '')}</td><td>${esc(m.artist || '')}</td>
        <td>${m.hidden ? '<span class="adm-bad">已下架</span>' : '展示中'}</td>
        <td class="adm-ops">${btn}</td></tr>`;
    }).join('') || '<tr><td colspan="6">暂无素材</td></tr>';
  }

  // ---------- 订单 ----------
  async function loadOrders() {
    const st = document.getElementById('o-status').value;
    const res = await api('/api/admin/orders' + (st ? '?status=' + st : ''));
    if (!res || res.code !== 0) return;
    document.getElementById('o-body').innerHTML = res.data.map((o) => {
      const btn = o.status === 'disputed' ? ''
        : `<button class="btn btn-sm" onclick="ADM.arbitrate(${o.id})">介入仲裁</button>`;
      return `<tr><td>${o.id}</td><td>${esc(o.title || '')}</td>
        <td>${esc(o.client_name || '')}</td><td>${esc(o.taker_name || '—')}</td>
        <td>${o.budget ?? ''}</td><td>${o.applications}</td>
        <td>${ORDER_STATUS[o.status] || o.status}</td>
        <td class="adm-ops">${btn}</td></tr>`;
    }).join('') || '<tr><td colspan="8">暂无订单</td></tr>';
  }
  document.getElementById('o-filter').addEventListener('click', loadOrders);

  // ---------- 反馈 ----------
  async function loadFeedback() {
    const res = await api('/api/admin/feedback');
    if (!res || res.code !== 0) return;
    document.getElementById('f-body').innerHTML = res.data.map((f) =>
      `<tr><td>${f.id}</td><td>${esc(f.user_name || '')}</td>
       <td class="adm-content">${esc(f.content || '')}</td>
       <td>${f.tokens_awarded || 0}</td><td>${f.created_at}</td>
       <td class="adm-ops"><button class="btn btn-sm"
         onclick="ADM.replyFeedback(${f.id})">回复</button></td></tr>`).join('')
      || '<tr><td colspan="6">暂无反馈</td></tr>';
  }

  // ---------- 公告 ----------
  async function loadAnnouncements() {
    const res = await api('/api/admin/announcements');
    if (!res || res.code !== 0) return;
    document.getElementById('an-body').innerHTML = res.data.map((a) =>
      `<tr><td>${a.id}</td><td>${esc(a.title)}</td>
       <td class="adm-content">${esc(a.content)}</td>
       <td>${a.created_at}</td></tr>`).join('')
      || '<tr><td colspan="4">暂无公告</td></tr>';
  }
  document.getElementById('an-send').addEventListener('click', async () => {
    const target = document.querySelector('input[name="an-target"]:checked').value;
    const res = await api('/api/admin/announce', {
      title: document.getElementById('an-title').value,
      content: document.getElementById('an-content').value,
      target,
      user_id: target === 'user' ? document.getElementById('an-uid').value : null,
    });
    if (!res) return;
    API.toast(res.msg, res.code === 0);
    if (res.code === 0) {
      document.getElementById('an-title').value = '';
      document.getElementById('an-content').value = '';
      loadAnnouncements();
    }
  });

  // ---------- 邮件 ----------
  document.getElementById('em-send').addEventListener('click', async () => {
    const target = document.querySelector('input[name="em-target"]:checked').value;
    if (!confirm('确认发送邮件？')) return;
    const res = await api('/api/admin/email/send', {
      subject: document.getElementById('em-subject').value,
      body: document.getElementById('em-body').value,
      user_id: target === 'user' ? document.getElementById('em-uid').value : null,
    });
    if (res) API.toast(res.msg, res.code === 0);
  });

  // ---------- 全局操作 ----------
  window.ADM = {
    async ban(id) {
      const days = prompt('封禁天数（限制接单）', '30');
      if (!days) return;
      const res = await api(`/api/admin/users/${id}/ban`, { days: parseInt(days, 10) || 30 });
      if (res) { API.toast(res.msg, res.code === 0); loadUsers(); }
    },
    async unban(id) {
      const res = await api(`/api/admin/users/${id}/unban`, {});
      if (res) { API.toast(res.msg, res.code === 0); loadUsers(); }
    },
    async setAdmin(id) {
      if (!confirm('确认将该用户设为管理员？')) return;
      const res = await api(`/api/admin/users/${id}/set-admin`, {});
      if (res) { API.toast(res.msg, res.code === 0); loadUsers(); }
    },
    async unsetAdmin(id) {
      if (!confirm('确认撤销该用户的管理员权限？')) return;
      const res = await api(`/api/admin/users/${id}/unset-admin`, {});
      if (res) { API.toast(res.msg, res.code === 0); loadUsers(); }
    },
    async resetPwd(id) {
      const pwd = prompt('输入新密码（至少6位，含字母和数字）');
      if (!pwd) return;
      const res = await api(`/api/admin/users/${id}/reset-password`, { password: pwd });
      if (res) API.toast(res.msg, res.code === 0);
    },
    async moderateArtwork(id, action) {
      const res = await api(`/api/admin/artworks/${id}/moderate`, { action });
      if (res) { API.toast(res.msg, res.code === 0); loadArtworks(); }
    },
    async moderateMaterial(id, action) {
      const res = await api(`/api/admin/materials/${id}/moderate`, { action });
      if (res) { API.toast(res.msg, res.code === 0); loadMaterials(); }
    },
    async arbitrate(id) {
      const note = prompt('仲裁说明（将通知甲方与接单者）');
      if (!note) return;
      const res = await api(`/api/admin/orders/${id}/arbitrate`, { note });
      if (res) { API.toast(res.msg, res.code === 0); loadOrders(); }
    },
    async replyFeedback(id) {
      const reply = prompt('回复内容（首次回复将奖励 5 Token）');
      if (!reply) return;
      const res = await api(`/api/admin/feedback/${id}/reply`, { reply });
      if (res) { API.toast(res.msg, res.code === 0); loadFeedback(); }
    },
  };

  loadOverview();
})();
