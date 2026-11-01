// Interactive web export controls: play/pause, scrub, step, with the soundtrack synced to the scrubber.
(function () {
  const ft = window.FILMTIME, aud = document.getElementById('aud');
  document.body.style.background = '#111';
  const stage = document.getElementById('stage');
  stage.style.width = 'min(100vw, calc((100vh - 70px) * 9 / 16))'; stage.style.height = 'auto'; stage.style.display = 'block'; stage.style.margin = '0 auto';
  const bar = document.createElement('div');
  bar.style.cssText = 'position:fixed;left:0;right:0;bottom:0;display:flex;gap:10px;align-items:center;padding:10px 14px;background:#1b1b1b;color:#eee;font:14px system-ui';
  bar.innerHTML = '<button id="pp">▶</button><button id="st">⏭ frame</button><input id="sc" type="range" min="0" max="1000" value="0" style="flex:1"><span id="tm">0.0 s</span>';
  document.body.appendChild(bar);
  const sc = document.getElementById('sc'), tm = document.getElementById('tm'), pp = document.getElementById('pp');
  let t = ft.start, playing = false, last = 0;
  const show = () => { window.frameAtTime(t); sc.value = Math.round((t - ft.start) / (ft.end - ft.start) * 1000); tm.textContent = t.toFixed(1) + ' s'; };
  const loop = ms => { if (playing) { t += (ms - last) / 1000; if (t >= ft.end) { t = ft.end; playing = false; pp.textContent = '▶'; } show(); } last = ms; requestAnimationFrame(loop); };
  pp.onclick = () => { playing = !playing; pp.textContent = playing ? '⏸' : '▶'; if (aud && aud.src) { aud.currentTime = t; playing ? aud.play().catch(() => {}) : aud.pause(); } };
  document.getElementById('st').onclick = () => { playing = false; pp.textContent = '▶'; t = Math.min(ft.end, t + 1 / ft.fps); show(); };
  sc.oninput = () => { t = ft.start + (sc.value / 1000) * (ft.end - ft.start); if (aud && aud.src) aud.currentTime = t; show(); };
  const wait = () => (window.ready ? (show(), requestAnimationFrame(loop)) : setTimeout(wait, 50)); wait();
})();
