/* 全站动效增强（黑紫科技风，渐进增强：JS 失效不影响内容显示）。
 *  1) 全局星点闪烁层
 *  2) 滚动揭示（组内错峰）
 *  3) 鼠标追光 spotlight
 *  4) 3D 倾斜（[data-tilt]）
 *  5) 数字滚动（[data-count]）
 * 可重入：MutationObserver 监听异步注入的 DOM（innerHTML 渲染的卡片等），
 * 用 dataset 标记去重，保证动态节点同样获得动效。
 */
(function () {
  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  const RV_SEL = '.card, .portal, .plan-card, .tool-card, .res-group, .pack, ' +
    '.rail-card, .section-title, .dark-diffuse, .ref-card, .wheel-row, ' +
    '.cert-card, .stat-row, .feat-row, .wave-band';
  const SPOT_SEL = '.card, .portal, .plan-card, .tool-card, .res-group, .ref-card, .push-card';
  const TILT_SEL = '[data-tilt]';
  const COUNT_SEL = '[data-count]';

  let io = null, io2 = null;

  function pick(root, sel) {
    const out = [];
    if (!root || !root.querySelectorAll) return out;
    if (root.nodeType === 1 && root.matches && root.matches(sel)) out.push(root);
    const list = root.querySelectorAll(sel);
    for (let i = 0; i < list.length; i++) out.push(list[i]);
    return out;
  }

  function finish(el) {
    /* 揭示完成后交还原生 transition / hover 形变 */
    setTimeout(function () {
      el.classList.remove('rv', 'rv-in');
      el.style.transitionDelay = '';
    }, 1000);
  }

  function reveal(el) {
    if (el.dataset.fxRv) return;
    el.dataset.fxRv = '1';
    const idx = el.parentElement ? Array.prototype.indexOf.call(el.parentElement.children, el) : 0;
    el.style.transitionDelay = (Math.min(Math.max(idx, 0), 5) * 70) + 'ms';
    el.classList.add('rv');
    if (io) io.observe(el);
    else { el.classList.add('rv-in'); finish(el); }
  }

  function spot(el) {
    if (el.dataset.fxSpot) return;
    el.dataset.fxSpot = '1';
    el.classList.add('spot');
    el.addEventListener('mousemove', function (ev) {
      const r = el.getBoundingClientRect();
      el.style.setProperty('--mx', (ev.clientX - r.left).toFixed(0) + 'px');
      el.style.setProperty('--my', (ev.clientY - r.top).toFixed(0) + 'px');
    });
  }

  function tilt(el) {
    if (el.dataset.fxTilt) return;
    el.dataset.fxTilt = '1';
    el.addEventListener('mousemove', function (ev) {
      const r = el.getBoundingClientRect();
      const px = (ev.clientX - r.left) / r.width - .5;
      const py = (ev.clientY - r.top) / r.height - .5;
      el.style.setProperty('--ry', (px * 8).toFixed(2) + 'deg');
      el.style.setProperty('--rx', (-py * 8).toFixed(2) + 'deg');
    });
    el.addEventListener('mouseleave', function () {
      el.style.setProperty('--rx', '0deg');
      el.style.setProperty('--ry', '0deg');
    });
  }

  function runCount(el) {
    const target = +el.dataset.count || 0;
    const t0 = performance.now();
    (function tick(t) {
      const p = Math.min((t - t0) / 1200, 1);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(tick);
    })(t0);
  }

  function count(el) {
    if (el.dataset.fxCount) return;
    el.dataset.fxCount = '1';
    if (io2) io2.observe(el);
    else runCount(el);
  }

  function enhance(root) {
    pick(root, RV_SEL).forEach(reveal);
    pick(root, SPOT_SEL).forEach(spot);
    pick(root, TILT_SEL).forEach(tilt);
    pick(root, COUNT_SEL).forEach(count);
  }

  ready(function () {
    /* ---- 1) 星点 ---- */
    if (!document.querySelector('.fx-stars')) {
      const box = document.createElement('div');
      box.className = 'fx-stars';
      let html = '';
      for (let i = 0; i < 42; i++) {
        html += '<i style="left:' + (Math.random() * 100).toFixed(1) +
          '%;top:' + (Math.random() * 100).toFixed(1) +
          '%;animation-delay:' + (Math.random() * 4).toFixed(1) +
          's;animation-duration:' + (3 + Math.random() * 3).toFixed(1) + 's"></i>';
      }
      box.innerHTML = html;
      document.body.appendChild(box);
    }

    /* ---- 观察器 ---- */
    if ('IntersectionObserver' in window) {
      io = new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (e.isIntersecting) { e.target.classList.add('rv-in'); finish(e.target); io.unobserve(e.target); }
        });
      }, { threshold: .12, rootMargin: '0px 0px -6% 0px' });
      io2 = new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (e.isIntersecting) { runCount(e.target); io2.unobserve(e.target); }
        });
      }, { threshold: .4 });
    }

    enhance(document);

    /* 异步注入的 DOM（innerHTML 渲染的卡片）补挂动效 */
    if ('MutationObserver' in window) {
      let pending = [];
      let timer = null;
      const mo = new MutationObserver(function (muts) {
        muts.forEach(function (m) {
          for (let i = 0; i < m.addedNodes.length; i++) {
            const n = m.addedNodes[i];
            if (n.nodeType === 1) pending.push(n);
          }
        });
        if (!pending.length) return;
        if (timer) clearTimeout(timer);
        timer = setTimeout(function () {
          const list = pending; pending = []; timer = null;
          list.forEach(enhance);
        }, 60);
      });
      mo.observe(document.body, { childList: true, subtree: true });
    }
  });
})();

/* 自定义光标（森林极光原型同款）：白点即时跟随 + 描边圆环阻尼跟随 */
(function () {
  if (!window.matchMedia || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
  var dot = document.querySelector('.cursor-dot');
  var ring = document.querySelector('.cursor-ring');
  if (!dot || !ring) return;
  var x = window.innerWidth / 2, y = window.innerHeight / 2, rx = x, ry = y;
  document.addEventListener('mousemove', function (e) {
    x = e.clientX; y = e.clientY;
    dot.style.left = x + 'px'; dot.style.top = y + 'px';
  });
  (function loop() {
    rx += (x - rx) * 0.18; ry += (y - ry) * 0.18;
    ring.style.left = rx + 'px'; ring.style.top = ry + 'px';
    requestAnimationFrame(loop);
  })();
  document.addEventListener('mouseover', function (e) {
    var interactive = e.target.closest && e.target.closest('a,button,input,select,textarea,[role="button"]');
    ring.classList.toggle('is-hover', !!interactive);
  });
})();
