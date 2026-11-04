// Interactive web film (WP-30): the film drawn live by the player, with a panel built from the film's own data
// (window.INTERACTIVE, written by export.interactive): chapters (one per shot), the transcript synced word by word
// (tap a line to hear it), a pause after each question so the viewer can think before the answer, and the source
// of every line that states a fact; branches: at a branch the viewer chooses, the page jumps to that choice's shots
// and on to where the branches meet (the film holds every branch in order). window.IFILM = {t, seek, play, pause,
// choose, state} for scripts and tests.
(function () {
  const ft = window.FILMTIME, aud = document.getElementById('aud'), D = window.INTERACTIVE;
  const css = `body{margin:0;background:#15120f;color:#f2ebe2;font:15px/1.45 system-ui,sans-serif}
#wrap{display:flex;gap:16px;justify-content:center;align-items:flex-start;padding:12px}
#stage{width:min(56vh,92vw)!important;height:auto!important;display:block;border-radius:10px}
#side{width:min(420px,92vw);max-height:calc(100vh - 24px);overflow:auto}
#side h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:#a8998a;margin:14px 0 6px}
button{font:inherit;color:inherit;background:#2a241f;border:1px solid #3a342e;border-radius:8px;padding:6px 10px;cursor:pointer}
button:focus-visible{outline:2px solid #e8743a}
#bar{display:flex;gap:8px;align-items:center}#sc{flex:1}
.ch{display:block;width:100%;text-align:left;margin:3px 0}.ch.on{border-color:#e8743a}
.ln{display:block;width:100%;text-align:left;margin:4px 0;background:none;border:1px solid transparent}.ln.on{background:#2a241f;border-color:#3a342e}
.who{color:#a8998a;font-size:12px;display:block}.w.on{color:#ffb37a}
.src{font-size:12px;color:#e8a46a}
#ask{position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,.55)}
#ask div{background:#2a241f;border-radius:14px;padding:22px;max-width:340px;text-align:center}
@media (max-width:760px){#wrap{flex-direction:column;align-items:center}#side{max-height:none}}`;
  document.head.insertAdjacentHTML('beforeend', `<style>${css}</style>`);
  const stage = document.getElementById('stage'), wrap = document.createElement('div'); wrap.id = 'wrap';
  stage.parentNode.insertBefore(wrap, stage); wrap.appendChild(stage);
  const side = document.createElement('div'); side.id = 'side'; wrap.appendChild(side);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  side.innerHTML = `<h1 style="font-size:20px;margin:4px 0 8px">${esc(D.title)}</h1>
<div id="bar"><button id="pp" aria-label="Play">▶</button><input id="sc" type="range" min="0" max="1000" value="0" aria-label="Position"><span id="tm">0.0 s</span></div>
<h2>Chapters</h2><div id="chs">${D.chapters.map((c, i) => `<button class="ch" data-t="${c.start}">${i + 1}. ${esc(c.title)}</button>`).join('')}</div>
<h2>What they say</h2><div id="lns">${D.lines.map(l => `<button class="ln" data-t="${l.start}" data-id="${esc(l.id)}"><span class="who">${esc(l.name)}</span>${l.words.map((w, k) => `<span class="w" data-k="${k}">${esc(w.text)}</span>`).join(' ')}${l.source ? `<span class="src"><br>Source: <a href="${esc(l.source.url)}" target="_blank" rel="noopener" style="color:inherit">${esc(l.source.title || l.source.url)}</a></span>` : ''}</button>`).join('')}</div>
<h2>Sources</h2><ul id="srcs">${D.sources.map(s => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener" style="color:#e8a46a">${esc(s.title || s.url)}</a></li>`).join('') || '<li>none</li>'}</ul>`;
  const ask = document.createElement('div'); ask.id = 'ask'; ask.setAttribute('role', 'dialog');
  ask.innerHTML = '<div><p id="askq" style="font-size:18px;margin:0 0 6px"></p><p style="color:#a8998a;margin:0 0 14px">What do you think? Have a guess, then hear the answer.</p><button id="go">Hear the answer</button></div>';
  document.body.appendChild(ask);
  const chooseEl = document.createElement('div'); chooseEl.id = 'ask'; chooseEl.setAttribute('role', 'dialog'); chooseEl.style.cssText = 'display:none';
  chooseEl.innerHTML = '<div><p id="chq" style="font-size:18px;margin:0 0 12px"></p><div id="cho" style="display:flex;flex-direction:column;gap:8px"></div></div>';
  document.body.appendChild(chooseEl);
  const BR = D.branches || [];
  let open = null, active = null, path = [], decided = new Set();   // open: the branch asking; active: the chosen choice playing
  const $ = id => document.getElementById(id), sc = $('sc'), tm = $('tm'), pp = $('pp');
  let t = ft.start, playing = false, last = 0, asked = new Set();
  const setPlay = on => { playing = on; pp.textContent = on ? '⏸' : '▶'; pp.setAttribute('aria-label', on ? 'Pause' : 'Play');
    if (aud && aud.src) { if (on) { aud.currentTime = t; aud.play().catch(() => {}); } else aud.pause(); } };
  const mark = () => {
    for (const b of document.querySelectorAll('.ch')) b.classList.toggle('on', +b.dataset.t <= t + 1e-6 && t < (D.chapters.find(c => c.start === +b.dataset.t) || {}).end);
    for (const b of document.querySelectorAll('.ln')) { const l = D.lines.find(x => x.id === b.dataset.id), on = l.start <= t && t < l.end + 0.15; b.classList.toggle('on', on);
      if (on) b.querySelectorAll('.w').forEach(w => w.classList.toggle('on', l.words[+w.dataset.k].start <= t)); else b.querySelectorAll('.w.on').forEach(w => w.classList.remove('on')); } };
  const show = () => { window.frameAtTime(t); sc.value = Math.round((t - ft.start) / (ft.end - ft.start) * 1000); tm.textContent = t.toFixed(1) + ' s'; mark(); };
  const seek = v => { t = Math.max(ft.start, Math.min(ft.end, v)); asked = new Set([...asked].filter(p => p < t)); decided = new Set([...decided].filter(a => a < t)); if (active && (t < active.start || t >= active.end)) active = null; if (aud && aud.src) aud.currentTime = t; show(); };
  const loop = ms => {
    if (playing) { const t2 = Math.min(ft.end, t + Math.min(0.1, (ms - last) / 1000));
      const p = D.pauses.find(p => p.t > t && p.t <= t2 && !asked.has(p.t));
      const br = BR.find(b => b.at > t - 1e-6 && b.at <= t2 && !decided.has(b.at));
      if (active && t2 >= active.end) { const to = active.then; active = null; seek(to); }   // the chosen branch is over: on to where they meet
      else if (br) { t = br.at; open = br; setPlay(false); $('chq').textContent = br.prompt;
        $('cho').innerHTML = br.choices.map((c, i) => `<button data-i="${i}">${esc(c.label)}</button>`).join('');
        for (const btn of $('cho').querySelectorAll('button')) btn.onclick = () => choose(+btn.dataset.i);
        chooseEl.style.display = 'flex'; $('cho').querySelector('button').focus(); }
      else if (p) { t = p.t; asked.add(p.t); setPlay(false); $('askq').textContent = p.question; ask.style.display = 'flex'; $('go').focus(); }
      else { t = t2; if (t >= ft.end) setPlay(false); }
      show(); }
    last = ms; requestAnimationFrame(loop); };
  function choose(i) {
    if (!open) return; const c = open.choices[i]; decided.add(open.at); path.push({ at: open.at, choice: c.label });
    const then = open.then; open = null; chooseEl.style.display = 'none'; seek(c.start); active = { start: c.start, end: c.end, then }; setPlay(true); }
  pp.onclick = () => setPlay(!playing);
  $('go').onclick = () => { ask.style.display = 'none'; setPlay(true); };
  sc.oninput = () => seek(ft.start + (sc.value / 1000) * (ft.end - ft.start));
  for (const b of document.querySelectorAll('.ch, .ln')) b.onclick = e => { if (e.target.closest('a')) return; seek(+b.dataset.t); setPlay(true); };
  document.addEventListener('keydown', e => { if (e.key === ' ' && e.target === document.body) { e.preventDefault(); setPlay(!playing); } });
  window.IFILM = { get t() { return t; }, seek, choose, play: () => setPlay(true), pause: () => setPlay(false),
    state: () => ({ t, playing, asking: ask.style.display === 'flex', asked: [...asked], choosing: chooseEl.style.display === 'flex', path: path.slice(), active }) };
  const wait = () => (window.ready ? (show(), requestAnimationFrame(loop)) : setTimeout(wait, 50)); wait();
})();
