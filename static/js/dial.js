/* 帧集全局转盘组件（新需求文档：启动首页与个人中心复用同一封装组件）
   用法：const dial = new FrameDial(el, {
            sectors: [{label, icon, action}],
            center: {label: 'start', action: fn},
            onSector: fn,          // 点击分区回调
            autoSpin: true,        // 空闲时缓慢自转
        });
   交互：拖拽旋转带阻尼缓动；分区为环上胶囊标签（反向旋转保持水平），点击触发 onSector。 */
class FrameDial {
  constructor(el, opts) {
    this.el = el;
    this.opts = Object.assign({ autoSpin: true }, opts || {});
    this.angle = 0;
    this.vel = 0;
    this.dragging = false;
    this.render();
    requestAnimationFrame(t => this.tick(t));
  }

  sectorCount() { return (this.opts.sectors || []).length; }

  /* 玻璃盘分区着色：conic-gradient 硬停止 + 1px 分隔线 */
  diskGradient() {
    const n = Math.max(this.sectorCount(), 1);
    const step = 360 / n;
    const tints = ['rgba(91,140,255,.20)', 'rgba(167,139,250,.20)',
                   'rgba(79,214,180,.18)', 'rgba(86,211,216,.18)',
                   'rgba(242,201,76,.14)', 'rgba(255,107,139,.14)'];
    const stops = [];
    for (let i = 0; i < n; i++) {
      const from = (i * step).toFixed(2);
      const to = ((i + 1) * step).toFixed(2);
      stops.push(tints[i % tints.length] + ' ' + from + 'deg ' + to + 'deg');
      stops.push('rgba(255,255,255,.14) ' + to + 'deg calc(' + to + 'deg + 1px)');
    }
    return 'conic-gradient(from 0deg, ' + stops.join(', ') + ')';
  }

  render() {
    const o = this.opts;
    const sectors = o.sectors || [];
    const n = Math.max(sectors.length, 1);
    const step = 360 / n;
    // 分区胶囊沿环分布（百分比定位，随转子公转，标签反向自转保持水平）
    const sectorHtml = sectors.map((s, i) => {
      const mid = (i * step + step / 2 - 90) * Math.PI / 180;
      const x = (50 + 45 * Math.cos(mid)).toFixed(2);
      const y = (50 + 45 * Math.sin(mid)).toFixed(2);
      return `<button class="fd-sector" data-sector="${i}" style="--x:${x}%;--y:${y}%">
                <span class="fd-pill"><i>${s.icon || ''}</i>${s.label || ''}</span>
              </button>`;
    }).join('');

    this.el.classList.add('frame-dial');
    this.el.innerHTML = `
      <div class="fd-ripple r1"></div><div class="fd-ripple r2"></div>
      <div class="fd-ripple r3"></div><div class="fd-ripple r4"></div>
      <div class="fd-rotor">
        <div class="fd-disk" style="background:${this.diskGradient()}"></div>
        ${sectorHtml}
      </div>
      ${o.center ? `<button class="fd-center" data-center="1">${o.center.label || 'start'}</button>` : ''}`;
    this.bindDrag();
    this.el.querySelectorAll('[data-center]').forEach(c =>
      c.addEventListener('click', e => {
        e.stopPropagation();
        if (o.center && o.center.action) o.center.action();
      }));
    this.el.querySelectorAll('[data-sector]').forEach(s =>
      s.addEventListener('click', () => {
        if (this.movedFar) return;   // 拖拽后不触发误点
        const sec = o.sectors[+s.dataset.sector];
        if (o.onSector) o.onSector(sec, +s.dataset.sector);
        else if (sec && typeof sec.action === 'function') sec.action();
      }));
  }

  bindDrag() {
    let last = 0, startTime = 0;
    const angleOf = e => {
      const r = this.el.getBoundingClientRect();
      return Math.atan2(e.clientY - (r.top + r.height / 2),
                        e.clientX - (r.left + r.width / 2)) * 180 / Math.PI;
    };
    this.el.addEventListener('mousedown', e => {
      this.dragging = true;
      this.movedFar = false;
      last = angleOf(e); startTime = Date.now();
    });
    window.addEventListener('mousemove', e => {
      if (!this.dragging) return;
      const a = angleOf(e);
      let d = a - last;
      if (d > 180) d -= 360;
      if (d < -180) d += 360;
      this.angle += d;
      this.vel = d;
      if (Math.abs(this.angle) > 6) this.movedFar = true;
      last = a;
    });
    window.addEventListener('mouseup', () => { this.dragging = false; });
    // 触屏
    this.el.addEventListener('touchstart', e => {
      this.dragging = true; this.movedFar = false;
      last = angleOf(e.touches[0]); startTime = Date.now();
    }, { passive: true });
    this.el.addEventListener('touchmove', e => {
      if (!this.dragging) return;
      const a = angleOf(e.touches[0]);
      let d = a - last;
      if (d > 180) d -= 360;
      if (d < -180) d += 360;
      this.angle += d; this.vel = d;
      if (Math.abs(this.angle) > 6) this.movedFar = true;
      last = a;
    }, { passive: true });
    this.el.addEventListener('touchend', () => { this.dragging = false; });
  }

  tick() {
    if (!this.dragging) {
      // 阻尼缓动：速度衰减 + 空闲慢速自转
      this.vel *= 0.94;
      this.angle += this.vel + (this.opts.autoSpin ? 0.06 : 0);
    }
    this.el.style.setProperty('--fd-angle', this.angle + 'deg');
    requestAnimationFrame(() => this.tick());
  }
}
