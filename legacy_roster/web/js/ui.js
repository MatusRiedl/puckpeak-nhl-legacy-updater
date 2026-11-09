// The small parts the tabs are built from.
import { html, cls, useRef, useLayoutEffect, useState, useEffect } from './lib.js';

export function Button({ kind = 'ghost', small, big, block, disabled, onClick, title, className, children }) {
  return html`<button type="button" title=${title}
    class=${cls('btn', kind, small && 'small', big && 'big', block && 'block', className)}
    disabled=${disabled} onClick=${onClick}>${children}</button>`;
}

export function Toggle({ on, disabled, onChange, label, gold }) {
  return html`<button type="button" role="switch" aria-checked=${!!on} aria-label=${label}
    class=${cls('toggle', on && 'on', gold && 'gold')} disabled=${disabled} onClick=${() => onChange(!on)}></button>`;
}

// a small chip: tone good | caution | bad | info | gold
export function Tag({ tone = 'info', title, children }) {
  return html`<span class=${cls('tag', tone)} title=${title}>${children}</span>`;
}

export function Checkbox({ on, disabled, onChange, title, children }) {
  return html`<div role="checkbox" aria-checked=${!!on} tabindex="0" title=${title}
    class=${cls('check', on && 'on', disabled && 'disabled')}
    onClick=${() => !disabled && onChange(!on)}
    onKeyDown=${(e) => { if (!disabled && (e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); onChange(!on); } }}>
    <span class="box"><svg viewBox="0 0 12 12"><path d="M2 6.5 5 9.2 10.2 3" fill="none" stroke="#fff" stroke-width="2"/></svg></span>
    ${children}
  </div>`;
}

// a choice of a few, with a thumb that slides to the one picked
export function Segmented({ options, value, disabled, onChange, className }) {
  const box = useRef(null);
  const [thumb, setThumb] = useState(null);
  useLayoutEffect(() => {
    const measure = () => {
      const el = box.current && box.current.querySelector('button.on');
      setThumb(el && el.offsetWidth ? { x: el.offsetLeft - 2, w: el.offsetWidth } : null);
    };
    measure();
    const watch = new ResizeObserver(measure);     // fonts arriving, a tab shown again
    watch.observe(box.current);
    return () => watch.disconnect();
  }, [value, options.map((o) => o.label).join('|')]);
  return html`<div ref=${box} class=${cls('seg', disabled && 'disabled', className)}>
    ${thumb && html`<span class="thumb" style=${{ width: thumb.w + 'px', transform: `translateX(${thumb.x}px)` }}></span>`}
    ${options.map((o) => html`<button type="button" key=${o.value} class=${o.value === value ? 'on' : ''}
        disabled=${disabled} onClick=${() => o.value !== value && onChange(o.value)}>${o.icon}${o.label}</button>`)}
  </div>`;
}

export function Card({ n, title, aside, grow, className, style, children }) {
  return html`<section class=${cls('card', grow && 'grow', className)} style=${style}>
    <header class="card-head">
      ${n != null && html`<span class="num">${n}</span>`}
      <span class="title">${title}</span>
      ${aside && html`<span class="aside">${aside}</span>`}
    </header>
    ${children}
  </section>`;
}

export function Flag({ region }) {
  if (region === 'EU') {
    const stars = [];
    for (let k = 0; k < 12; k++) {
      const a = (Math.PI * 2 * k) / 12;
      stars.push(html`<circle key=${k} cx=${9 + 3.6 * Math.sin(a)} cy=${6 - 3.6 * Math.cos(a)} r="0.65" fill="#ffcc00"/>`);
    }
    return html`<svg class="flag" viewBox="0 0 18 12"><rect width="18" height="12" fill="#003399"/>${stars}</svg>`;
  }
  const stripes = [];
  for (let k = 0; k < 13; k += 2) stripes.push(html`<rect key=${k} y=${(k * 12) / 13} width="18" height=${12 / 13} fill="#b22234"/>`);
  return html`<svg class="flag" viewBox="0 0 18 12"><rect width="18" height="12" fill="#fff"/>${stripes}
    <rect width="7.2" height=${(7 * 12) / 13} fill="#3c3b6e"/></svg>`;
}

export function RegionTag({ region }) {
  return html`<span class="chip region"><${Flag} region=${region}/>${region}</span>`;
}

// a path shortened in the middle by the layout itself: the end (file name) always shows
export function PathText({ path, unset }) {
  if (!path) return html`<div class="field path unset">${unset}</div>`;
  const cut = Math.max(path.lastIndexOf('\\'), path.lastIndexOf('/'));
  const head = cut > 0 ? path.slice(0, cut + 1) : '';
  const tail = cut > 0 ? path.slice(cut + 1) : path;
  return html`<div class="field path" title=${path}><span class="head">${head}</span><span class="tail">${tail}</span></div>`;
}

export function ProgressBar({ value, active, indeterminate }) {
  return html`<div class=${cls('progress', active && 'active', indeterminate && 'indeterminate')}
    role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow=${Math.round((value || 0) * 100)}>
    <div class="fill" style=${{ transform: `scaleX(${Math.max(0, Math.min(1, value || 0))})` }}></div>
    <div class="sweep"></div>
  </div>`;
}

// an input the player types in: Python's value is shown unless the player is typing
export function TextField({ value, disabled, onChange, delay = 250, className, placeholder, onEnter }) {
  const [text, setText] = useState(value || '');
  const typing = useRef(false);
  const timer = useRef(null);
  useEffect(() => { if (!typing.current) setText(value || ''); }, [value]);
  return html`<input class=${cls('field', className)} value=${text} disabled=${disabled} placeholder=${placeholder}
    spellcheck="false"
    onFocus=${() => { typing.current = true; }}
    onBlur=${() => { typing.current = false; clearTimeout(timer.current); if (text !== value) onChange(text); }}
    onKeyDown=${(e) => { if (e.key === 'Enter') { clearTimeout(timer.current); onChange(text); onEnter && onEnter(); } }}
    onInput=${(e) => { const t = e.target.value; setText(t); clearTimeout(timer.current);
      timer.current = setTimeout(() => onChange(t), delay); }}/>`;
}

const INFO_EDGE = 12;

// where the "?"'s text goes: under the "?" when it fits there, else over it, else beside it (when two columns fit),
// else over the "?" as near it as the window lets it be
function infoSpot(dot, pop) {
  const r = dot.getBoundingClientRect();
  const vw = window.innerWidth, vh = window.innerHeight, edge = INFO_EDGE;
  const h = pop ? pop.offsetHeight : 0;
  const full = Math.min(1000, vw - 2 * edge);
  const near = Math.max(edge, Math.min(vh - edge - h, r.top + r.height / 2 - h / 2));
  const right = vw - r.right - 10 - edge, left = r.left - 10 - edge;
  let spot;
  if (r.bottom + 8 + h <= vh - edge) spot = { top: r.bottom + 8 };
  else if (r.top - 8 - h >= edge) spot = { top: r.top - 8 - h };
  else if (Math.max(right, left) >= 820) {
    const width = Math.min(1000, Math.max(right, left));
    spot = { left: right >= left ? r.right + 10 : r.left - 10 - width, top: near, width };
  } else spot = { top: near };
  const place = { left: Math.max(edge, Math.min(r.left - 16, vw - full - edge)), width: full, ...spot,
                  maxHeight: vh - 2 * edge };
  for (const k of ['left', 'top', 'width']) place[k] = Math.round(place[k]);
  return place;
}

// a "?" that explains more while the pointer is on it (or the keyboard is); a click keeps it open, Escape or a click
// elsewhere closes it. The text goes into <body> at a fixed place, so no card cuts it off.
export function Info({ title, sections, label = 'More about this' }) {
  const dot = useRef(null);
  const pop = useRef(null);
  const timer = useRef(null);
  const [hover, setHover] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [place, setPlace] = useState(null);
  const [, setSize] = useState(0);
  const open = hover || pinned;
  const show = () => { clearTimeout(timer.current); setHover(true); };
  const hide = () => { clearTimeout(timer.current); timer.current = setTimeout(() => setHover(false), 180); };
  const close = () => { clearTimeout(timer.current); setHover(false); setPinned(false); };
  // drawn hidden first, then placed by its real height; placed again whenever that or the window changes
  useLayoutEffect(() => {
    if (!open) { if (place) setPlace(null); return; }
    const next = infoSpot(dot.current, pop.current);
    if (!place || Object.keys(next).some((k) => next[k] !== place[k])) setPlace(next);
  });
  useEffect(() => {
    if (!open) return undefined;
    const again = () => setSize((n) => n + 1);
    window.addEventListener('resize', again);
    return () => window.removeEventListener('resize', again);
  }, [open]);
  useEffect(() => {
    if (!open) return undefined;
    const key = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    const away = (e) => { if (!dot.current.contains(e.target) && !(pop.current && pop.current.contains(e.target))) close(); };
    window.addEventListener('keydown', key, true);
    window.addEventListener('mousedown', away, true);
    return () => { window.removeEventListener('keydown', key, true); window.removeEventListener('mousedown', away, true); };
  }, [open]);
  useEffect(() => () => clearTimeout(timer.current), []);
  const width = place ? place.width : Math.min(1000, window.innerWidth - 2 * INFO_EDGE);
  const text = open && html`<div ref=${pop} role="tooltip"
      class=${cls('info-pop', width >= 900 ? 'three' : width >= 600 && 'two')}
      style=${place || { width, left: 0, top: 0, visibility: 'hidden' }}
      onMouseEnter=${show} onMouseLeave=${hide}>
    <div class="i-title">${title}</div>
    <div class="i-parts">${sections.map((s) => html`<div key=${s.head} class="i-part">
      <div class="i-head">${s.head}</div>
      <ul>${s.items.map((t, k) => html`<li key=${k}>${t}</li>`)}</ul>
    </div>`)}</div>
  </div>`;
  return html`<button type="button" ref=${dot} class=${cls('info-dot', open && 'open')} aria-label=${label}
      aria-expanded=${open} onMouseEnter=${show} onMouseLeave=${hide} onFocus=${show} onBlur=${hide}
      onClick=${() => (pinned ? close() : setPinned(true))}>?</button>
    ${text && window.ReactDOM ? window.ReactDOM.createPortal(text, document.body) : text}`;
}

export function Modal({ title, wide, full, onClose, buttons, children }) {
  useEffect(() => {
    const key = (e) => { if (e.key === 'Escape' && onClose) { e.stopPropagation(); onClose(); } };
    window.addEventListener('keydown', key, true);
    return () => window.removeEventListener('keydown', key, true);
  }, [onClose]);
  const page = html`<div class=${cls('modal-back', full && 'full')} onMouseDown=${(e) => { if (e.target === e.currentTarget && onClose) onClose(); }}>
    <div class=${cls('modal', wide && 'wide', full && 'full')} role="dialog" aria-modal="true">
      <div class="m-head">${title}</div>
      <div class="m-body">${children}</div>
      ${buttons && html`<div class="m-buttons">${buttons}</div>`}
    </div>
  </div>`;
  // the big windows go straight into <body>: a parent that moves (the tab's slide-in) would keep them under the logo
  return full && window.ReactDOM ? window.ReactDOM.createPortal(page, document.body) : page;
}
