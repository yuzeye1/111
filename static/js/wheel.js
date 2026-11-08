/* 游戏化抽奖转盘：深色渐变 6 扇形 + 金边刻度 + 毛玻璃「立即抽取」。
 * 4.2 秒缓动旋转，停稳后回调 onResult(prize, index)。
 * 用法：const w = FrameWheel.mount(el, prizes, onResult); w.spin();
 */
(function () {
  const SIZE = 340, C = SIZE / 2, R = 146;
  const SPIN_MS = 4200;
  /* 每扇形一段深色渐变（黑紫 / 深蓝交替，科技暗色风） */
  const GRADS = [
    ['#3b2a6d', '#150e2b'],
    ['#1f3a6e', '#0b1230'],
    ['#4a2a7a', '#190d33'],
    ['#1e4a6e', '#0a1a2e'],
    ['#552a86', '#1d0d3a'],
    ['#2a2a5e', '#0f0f28'],
  ];

  function polar(r, deg) {
    const a = (deg - 90) * Math.PI / 180;
    return [C + r * Math.cos(a), C + r * Math.sin(a)];
  }

  function mount(el, prizes, onResult) {
    const n = prizes.length;
    const step = 360 / n;

    /* ---- 扇形 + 渐变 + 标签 ---- */
    let defs = '', sectors = '', labels = '', seps = '';
    for (let i = 0; i < n; i++) {
      const g = GRADS[i % GRADS.length];
      defs += '<linearGradient id="wg' + i + '" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0" stop-color="' + g[0] + '"/>' +
        '<stop offset="1" stop-color="' + g[1] + '"/></linearGradient>';
      const a0 = i * step, a1 = (i + 1) * step;
      const p0 = polar(R, a0), p1 = polar(R, a1);
      sectors += '<path d="M ' + C + ' ' + C +
        ' L ' + p0[0].toFixed(2) + ' ' + p0[1].toFixed(2) +
        ' A ' + R + ' ' + R + ' 0 0 1 ' + p1[0].toFixed(2) + ' ' + p1[1].toFixed(2) +
        ' Z" fill="url(#wg' + i + ')" stroke="rgba(255,215,130,.28)" stroke-width="1"/>';
      const mid = i * step + step / 2;
      labels += '<g transform="rotate(' + mid + ' ' + C + ' ' + C + ')">' +
        '<text x="' + C + '" y="' + (C - R + 40) + '" text-anchor="middle" ' +
        'fill="#efe8ff" font-size="13" font-weight="700" letter-spacing="1">' +
        prizes[i].label + '</text></g>';
      const s0 = polar(R, a0), s1 = polar(28, a0);
      seps += '<line x1="' + s1[0].toFixed(2) + '" y1="' + s1[1].toFixed(2) +
        '" x2="' + s0[0].toFixed(2) + '" y2="' + s0[1].toFixed(2) +
        '" stroke="rgba(255,215,130,.4)" stroke-width="1.2"/>';
    }

    /* ---- 金边刻度：48 格，扇形边界处加粗 ---- */
    let ticks = '';
    for (let k = 0; k < 48; k++) {
      const major = k % (48 / n) === 0;
      const q0 = polar(major ? 152 : 155, k * 7.5), q1 = polar(161, k * 7.5);
      ticks += '<line x1="' + q0[0].toFixed(2) + '" y1="' + q0[1].toFixed(2) +
        '" x2="' + q1[0].toFixed(2) + '" y2="' + q1[1].toFixed(2) +
        '" stroke="url(#wgold)" stroke-width="' + (major ? 3 : 1.2) +
        '" opacity="' + (major ? 1 : .62) + '"/>';
    }

    el.innerHTML =
      '<div class="wheel-wrap">' +
      '<svg viewBox="0 0 ' + SIZE + ' ' + SIZE + '" aria-label="抽奖转盘">' +
      '<defs>' + defs +
      '<linearGradient id="wgold" x1="0" y1="0" x2="1" y2="1">' +
      '<stop offset="0" stop-color="#ffe9b0"/><stop offset=".5" stop-color="#d9a441"/>' +
      '<stop offset="1" stop-color="#ffdf9e"/></linearGradient>' +
      '</defs>' +
      '<circle cx="' + C + '" cy="' + C + '" r="164" fill="rgba(10,6,24,.6)"/>' +
      '<circle cx="' + C + '" cy="' + C + '" r="150" fill="none" stroke="url(#wgold)" stroke-width="2.5"/>' +
      ticks +
      '<g class="wheel-rotor">' + sectors + seps + labels + '</g>' +
      '<polygon points="' + (C - 11) + ',4 ' + (C + 11) + ',4 ' + C + ',30" fill="url(#wgold)"/>' +
      '</svg>' +
      '<button class="wheel-hub" type="button">立即抽取</button>' +
      '</div>';

    const rotor = el.querySelector('.wheel-rotor');
    const hub = el.querySelector('.wheel-hub');
    rotor.style.transformBox = 'view-box';
    rotor.style.transformOrigin = 'center';

    const w = { rot: 0, spinning: false };

    w.spin = function () {
      if (w.spinning) return false;
      w.spinning = true;
      hub.disabled = true;
      const idx = Math.floor(Math.random() * n);
      const mid = idx * step + step / 2;
      /* 目标：让 idx 扇形中线停在顶部指针处，另加 4 圈 + ±18° 抖动 */
      const need = ((-mid - w.rot) % 360 + 360) % 360;
      const jitter = Math.round(Math.random() * 36 - 18);
      w.rot += 4 * 360 + need + jitter;
      rotor.style.transition = 'transform ' + SPIN_MS + 'ms cubic-bezier(.12,.82,.08,1)';
      rotor.style.transform = 'rotate(' + w.rot + 'deg)';
      setTimeout(function () {
        w.spinning = false;
        hub.disabled = false;
        if (onResult) onResult(prizes[idx], idx);
      }, SPIN_MS + 80);
      return true;
    };

    hub.addEventListener('click', w.spin);
    w.hub = hub;
    return w;
  }

  window.FrameWheel = { mount: mount, SPIN_MS: SPIN_MS };
})();
