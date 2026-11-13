// The frame around the tabs: the arena, the header, the tab switch, the Help bar, the details.
import { html, cls, useRef, useLayoutEffect, useState, useEffect } from './lib.js';
import { ProgressBar, Button, Modal } from './ui.js';
import { call } from './bridge.js';
import { useLog } from './store.js';

export function Backdrop() {
  // the glossy white band with its red edges over the top of the game's menus
  return html`<div class="backdrop" aria-hidden="true">
    <div class="lights"></div>
    <svg viewBox="0 0 1000 150" preserveAspectRatio="none">
      <defs>
        <linearGradient id="band" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stop-color="#fff" stop-opacity=".0"/>
          <stop offset=".18" stop-color="#fff" stop-opacity=".55"/>
          <stop offset=".5" stop-color="#fff" stop-opacity=".22"/>
          <stop offset=".82" stop-color="#fff" stop-opacity=".55"/>
          <stop offset="1" stop-color="#fff" stop-opacity=".0"/>
        </linearGradient>
        <linearGradient id="red" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stop-color="#c8102e" stop-opacity="0"/>
          <stop offset=".2" stop-color="#e2233f" stop-opacity=".9"/>
          <stop offset=".8" stop-color="#e2233f" stop-opacity=".9"/>
          <stop offset="1" stop-color="#c8102e" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <path d="M0,30 Q500,-34 1000,30" fill="none" stroke="url(#red)" stroke-width="1.6"/>
      <path d="M0,40 Q500,-22 1000,40 L1000,50 Q500,-8 0,50 Z" fill="url(#band)"/>
      <path d="M0,54 Q500,-2 1000,54" fill="none" stroke="url(#red)" stroke-width="2.2"/>
    </svg>
    <div class="floor"></div>
  </div>`;
}

// Discord's mark (simple-icons, CC0), drawn here: the page loads nothing from the internet
const DISCORD_MARK = 'M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z';

// the Discord button, first in the Setup tab (owner, 0.50.2: more visible there than in the header's corner)
export function DiscordButton() {
  return html`<button type="button" class="discord" title="gg.puckpeak.com" onClick=${() => call('open_discord')}>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d=${DISCORD_MARK}/></svg>
    <span class="t">Join our Discord</span><span class="sub">Updates, patches, help · gg.puckpeak.com</span></button>`;
}

// the Ko-fi button right under it (owner, 0.50.4): tips for the development, the look of the one in Puck Peak's sidebar
export function KofiButton() {
  return html`<button type="button" class="kofi" title="ko-fi.com/iksperial" onClick=${() => call('open_kofi')}>
    <span class="cup" aria-hidden="true">☕</span>
    <span class="txt"><span class="t">Buy me a coffee</span><span class="sub">Support the development</span></span></button>`;
}

export function Header({ meta }) {
  // the BLUELINE wordmark | "brought to you by" Puck Peak, then the game line: the same header as Overtime, the NHL 19 app (owner, 2026-11-13)
  return html`<header class="header">
    <div class="brand">
      <div class="wordmark">${meta.brand}</div>
      <div class="vsep"></div>
      <div class="by" title=${meta.site_label} onClick=${() => call('open_site')}>Brought to you by
        <img class="logo" src="img/logo.png" alt="Puck Peak" draggable="false"/></div>
    </div>
    <div><div class="crumb"><span class="light">${meta.subtitle}</span>
      <span class="sep">|</span><span class="ver">version ${meta.version}</span></div></div>
  </header>`;
}

export function TabBar({ tabs, tab, onTab }) {
  const box = useRef(null);
  const [thumb, setThumb] = useState(null);
  useLayoutEffect(() => {
    const measure = () => {
      const el = box.current && box.current.querySelector('button.on');
      if (el) setThumb({ x: el.offsetLeft - 2, w: el.offsetWidth });
    };
    measure();
    const watch = new ResizeObserver(measure);
    watch.observe(box.current);
    return () => watch.disconnect();
  }, [tab]);
  const index = tabs.findIndex((t) => t.id === tab);
  const onGold = index >= 0 && tabs[index].gold;
  const step = (d) => onTab(tabs[(index + d + tabs.length) % tabs.length].id);
  return html`<nav class="tabs">
    <span class="keycap" title="Ctrl+Page Up" onClick=${() => step(-1)}>L1</span>
    <div class="tabset" ref=${box}>
      ${thumb && html`<span class=${cls('thumb', onGold && 'gold')} style=${{ width: thumb.w + 'px', transform: `translateX(${thumb.x}px)` }}></span>`}
      ${tabs.map((t) => html`<button type="button" key=${t.id} class=${cls(t.id === tab && 'on', t.gold && 'gold')} onClick=${() => onTab(t.id)}>${t.label}</button>`)}
    </div>
    <span class="keycap" title="Ctrl+Page Down" onClick=${() => step(1)}>R1</span>
  </nav>`;
}

export function HelpBar({ status, progress, detailsOpen, onDetails, hint }) {
  const value = progress ? progress.value : 0;
  const shown = progress && (progress.active || value > 0);
  return html`<footer class="helpbar">
    <${ProgressBar} value=${value} active=${progress && progress.active} indeterminate=${progress && progress.indeterminate}/>
    <span class="pct">${shown ? Math.round(value * 100) + '%' : ''}</span>
    <span class=${cls('status', status && status.tone)} title=${status && status.text}>${status ? status.text : ''}</span>
    <span class="keys">
      ${hint && html`<span class="key"><span class="keycap">Enter</span>${hint}</span>`}
      <span class="key" onClick=${onDetails}><span class="keycap">D</span>${detailsOpen ? 'Hide details' : 'Details'}</span>
    </span>
  </footer>`;
}

export function Details({ open, onClose }) {
  const log = useLog();
  const box = useRef(null);
  const follow = useRef(true);
  useEffect(() => {
    const el = box.current;
    if (el && open && follow.current) el.scrollTop = el.scrollHeight;
  }, [log.version, open]);
  return html`<div class=${cls('details', open && 'open')} aria-hidden=${!open}>
    <div class="d-head">DETAILS<span class="sp"></span>
      <${Button} small onClick=${() => call('open_error_log')}>Error log</${Button}>
      <${Button} small onClick=${onClose}>Close</${Button}></div>
    <pre ref=${box} onScroll=${(e) => { const el = e.target; follow.current = el.scrollTop + el.clientHeight >= el.scrollHeight - 8; }}
      >${log.lines.join('\n')}</pre>
  </div>`;
}

// a question from Python (Delete, Restore default...), in the look of the game's Help box
// Put text on the clipboard: the page's own way first, a hidden text box as the fallback (a plain page may refuse the first).
function copyText(text) {
  const fallback = () => {
    const box = document.createElement('textarea');
    box.value = text;
    box.style.position = 'fixed';
    box.style.opacity = '0';
    document.body.appendChild(box);
    box.select();
    try { document.execCommand('copy'); } catch (e) { /* nothing more to try */ }
    document.body.removeChild(box);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).catch(fallback);
  else fallback();
}

export function Question({ dialog, onAnswer }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => { setCopied(false); }, [dialog && dialog.id]);
  if (!dialog) return null;
  const cancel = dialog.buttons.find((b) => b.style === 'plain' && !b.keep) || (dialog.buttons.length === 1 ? dialog.buttons[0] : null);
  const kinds = { primary: 'pick', danger: 'danger', plain: 'ghost' };
  const press = (b) => {
    if (b.copy) { copyText(dialog.copy); setCopied(true); return; }       // the window stays open
    onAnswer(dialog.id, b.answer);
  };
  return html`<${Modal} title=${dialog.title} wide=${dialog.wide} onClose=${cancel ? () => onAnswer(dialog.id, cancel.answer) : null}
    buttons=${dialog.buttons.map((b, k) => html`<${Button} key=${k} kind=${kinds[b.style] || 'ghost'} big
      onClick=${() => press(b)}>${b.copy && copied ? 'Copied' : b.label}</${Button}>`)}>
    ${dialog.lines.map((line, k) => html`<p key=${k}>${line}</p>`)}
    ${(dialog.rows || []).map((row) => html`<div key=${row.head} class="q-row">
      <div class="q-head">${row.head}</div>
      <div class="q-text selectable">${row.text}</div></div>`)}
    ${(dialog.notes || []).map((line, k) => html`<p key=${'n' + k} class="q-note">${line}</p>`)}
  </${Modal}>`;
}
