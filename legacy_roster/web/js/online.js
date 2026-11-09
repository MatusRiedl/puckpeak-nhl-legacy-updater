// The Play online tab, laid out as NHL 19's Multiplayer tab (owner, 2026-11-09: both games follow the same logic online).
// Three columns: 1 you and the pre-flight checks; 2 the lobby (host / join tiles and the public list, then the two players,
// Ready, chat and the game's steps); 3 your rating and the history. Python (app/online.py) holds everything; this page shows
// the `online` slice and calls online_*. Plan: docs/plans/multiplayer-three-columns.md.
import { html, cls, useState } from './lib.js';
import { call } from './bridge.js';
import { Button, Card, Modal, Segmented, Tag, TextField, Toggle } from './ui.js';

function signed(n) { return n == null ? '' : (n > 0 ? '+' : '') + n; }

function copy(text) {
  try {
    if (navigator.clipboard) return navigator.clipboard.writeText(text);
  } catch (err) { /* the next lines try again */ }
  const area = document.createElement('textarea');
  area.value = text;
  document.body.appendChild(area);
  area.select();
  try { document.execCommand('copy'); } catch (err) { /* nothing more to try */ }
  area.remove();
  return null;
}

function Chevron() {
  return html`<svg class="mp-chev" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
    <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>`;
}

function Mark({ tone }) {
  return html`<span class=${cls('mp-chk', tone)} aria-hidden="true">${tone === 'good'
    ? html`<svg width="12" height="12" viewBox="0 0 12 12"><path d="M2 6.4l2.6 2.6L10 3.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>`
    : tone === 'bad'
      ? html`<svg width="12" height="12" viewBox="0 0 12 12"><path d="M3 3l6 6M9 3l-6 6" fill="none" stroke="currentColor" stroke-width="2"/></svg>`
      : tone === 'caution' ? '!' : '·'}</span>`;
}

function Option({ on, title, sub, disabled, onChange }) {
  return html`<div class="mp-opt">
    <${Toggle} on=${on} label=${title} disabled=${disabled} onChange=${onChange}/>
    <div class="mp-opt-text"><div class="mp-opt-t">${title}</div>${sub && html`<div class="mp-opt-d">${sub}</div>`}</div>
  </div>`;
}

// --- 1 You and pre-flight ------------------------------------------------------------------------------------------------
function NameField({ s }) {
  const [text, setText] = useState(s.account || '');
  const save = () => call('online_name', text);
  return html`<div class="mp-row"><${TextField} className="mp-grow" value=${text} placeholder="Your online name" delay=${0}
    disabled=${!!s.lobby} onChange=${setText} onEnter=${save}/>
    <${Button} small disabled=${!!s.lobby || !text.trim() || text === s.account} onClick=${save}>Save name<//></div>`;
}

function Identity({ s }) {
  const name = s.account || '';
  const sub = name ? (s.native ? 'Your online name' : 'RPCN name from RPCS3') : s.no_account;
  return html`<div class="mp-id">
    <div class="mp-id-head">
      <span class=${cls('mp-avatar', !name && 'off')}>${(name || '?').charAt(0).toUpperCase()}</span>
      <div class="mp-id-main">
        <div class="mp-id-name" title=${name}>${name || 'Player'}</div>
        <div class=${cls('mp-id-sub', !name && 'warn')}>${sub}</div>
      </div>
      <${Button} small disabled=${!!s.busy} onClick=${() => call('online_check')}>Check again<//>
    </div>
    ${s.native && html`<${NameField} s=${s}/>`}
  </div>`;
}

// the checks a lobby needs, one row each with what fixes it (NHL 19's pre-flight rows)
function checkRows(s) {
  const m = s.marks;
  const rows = [];
  const rosterBad = s.guest_problem || (!s.lobby && s.bring_why);
  rows.push({ key: 'roster', label: 'Roster', tone: rosterBad ? 'bad' : 'good',
    text: rosterBad || (s.lobby ? (s.roster || s.brought || 'The lobby\'s roster') : (s.bring || 'Picked in Setup')),
    go: rosterBad ? (s.guest_problem ? ['patch', 'Game patch'] : ['setup', 'Setup']) : null });
  const open = m.game === 'open';
  rows.push({ key: 'patch', label: s.native ? 'Game patch' : 'Game patch and online entry', tone: m.ready ? 'good' : 'bad',
    text: m.ready ? 'Ready for online play' : !m.patched ? 'Not patched' : 'Online entry off',
    setup: !m.ready, note: !m.ready && open ? (s.native ? 'Close the game first.' : 'Close RPCS3 first.') : null });
  rows.push({ key: 'server', label: 'Puck Peak server', tone: s.server === false ? 'bad' : s.server ? 'good' : 'idle',
    text: s.server === false ? 'Not reachable' : s.server ? 'Reachable' : 'Checking...' });
  if (!s.native) {
    rows.push({ key: 'build', label: 'RPCS3 version', tone: s.build_old ? 'bad' : s.build == null ? 'caution' : 'good',
      text: s.build_old || (s.build == null ? 'Not seen yet: it shows after RPCS3 has run once' : 'Build ' + s.build) });
  }
  return rows;
}

function Check({ c, s }) {
  const m = s.marks;
  const action = c.setup
    ? html`<${Button} small kind="primary" disabled=${!!s.busy || !s.account || m.game === 'open'}
        onClick=${() => call('online_setup')}>Set up online<//>`
    : c.go ? html`<${Button} small kind="primary" onClick=${() => call('tab', c.go[0])}>${c.go[1]}<//>`
      : c.tone === 'good' ? html`<${Tag} tone="good">${c.key === 'server' ? 'reachable' : 'ok'}<//>`
        : c.tone === 'caution' ? html`<${Tag} tone="caution">check<//>` : null;
  return html`<div class=${cls('mp-check', c.tone)}>
    <${Mark} tone=${c.tone}/>
    <div class="mp-check-main"><div class="mp-check-label">${c.label}</div><div class="mp-check-value">${c.text}</div>
      ${c.note && html`<div class="mp-note warn">${c.note}</div>`}</div>
    ${action}
  </div>`;
}

const HELP = (s) => [
  s.native ? 'Type the name other players will see at the top of this column.'
    : 'Make your online account once in RPCS3 (Configuration > RPCN). This tab reads only its name.',
  'Set up online puts in the game patch (after asking) and its online entry.',
  'Pick the roster you want to play with in Setup. The one who makes the lobby brings it; the other gets a copy.',
  'One of you makes a lobby (private: send the code; public: it shows in the list), the other joins, both press Ready.',
  'The game starts by itself on both PCs. If it stops on a menu, the Game card says what to press.',
];

function Advanced({ s }) {
  const [open, setOpen] = useState(false);
  const m = s.marks;
  return html`<div class=${cls('mp-adv', open && 'open')}>
    <button type="button" class="mp-adv-head" aria-expanded=${open} onClick=${() => setOpen(!open)}>
      <span class="mp-adv-main"><span class="mp-lbl">Advanced</span><span class="mp-adv-d">Set up again, how online play works</span></span>
      <${Chevron}/>
    </button>
    ${open && html`<div class="mp-adv-body">
      ${m.ready && html`<div class="mp-row"><${Button} small disabled=${!!s.busy || !s.account || m.game === 'open'}
          onClick=${() => call('online_setup')}>Set up again<//><span class="mp-note">Puts the online entry and the settings back.</span></div>`}
      <ul class="mp-help">${HELP(s).map((t, k) => html`<li key=${k}>${t}</li>`)}</ul>
    </div>`}
  </div>`;
}

function You({ s }) {
  if (s.state === 'no-rpcs3') {
    return html`<${Card} n=${1} title="You and pre-flight" className="mp-card-fill">
      <div class="mp-body mp-fill"><div class="mp-empty">${s.no_rpcs3}</div></div><//>`;
  }
  const rows = checkRows(s);
  const fix = rows.filter((c) => c.tone === 'bad').length;
  return html`<${Card} n=${1} title="You and pre-flight" className="mp-card-fill">
    <div class="mp-body mp-fill">
      <${Identity} s=${s}/>
      ${fix > 0 && html`<div class="mp-notice bad"><b>${fix} ${fix === 1 ? 'thing' : 'things'} to fix</b>
        <span>before a lobby can start the game.</span></div>`}
      <div class="mp-checks">${rows.map((c) => html`<${Check} key=${c.key} c=${c} s=${s}/>`)}</div>
      ${s.note && html`<div class=${cls('mp-note', s.note.tone === 'bad' ? 'bad' : s.note.tone === 'good' ? 'good' : 'warn')}
        role=${s.note.tone === 'bad' ? 'alert' : null}>${s.note.text}</div>`}
      ${s.busy && html`<div class="mp-note">${s.busy}</div>`}
      <div class="mp-hl"></div>
      <div class="mp-lbl">When the game starts</div>
      <${Option} on=${!!(s.overlay && s.overlay.on)} disabled=${!(s.overlay && s.overlay.can)} title="Chat and results in game"
        sub=${s.overlay && s.overlay.can ? 'Your friend\'s chat and the result card over the game. Ctrl+Shift+F1 to F6 send the six phrases.'
          : 'Windows only.'}
        onChange=${(on) => call('online_overlay', on)}/>
      <div class="mp-spacer"></div>
      <${Advanced} s=${s}/>
    </div>
  <//>`;
}

// --- 2 Lobby, none open yet: a host tile, a join tile, the public list, how a match comes about -------------------------
const HOWTO = [
  ['Create or join', 'One lobby, two players.'],
  ['Both press Ready', 'The host brings the roster; the other gets a copy.'],
  ['The app starts the game', 'On both PCs, by itself.'],
];

function HowTo() {
  return html`<div class="mp-howto">${HOWTO.map(([t, d], i) => html`<div class="mp-howto-step" key=${i}>
    <span class="mp-ftag">${i + 1}</span><div><b>${t}</b><div class="mp-howto-d">${d}</div></div></div>`)}</div>`;
}

function age(seconds) {
  if (seconds < 60) return 'just now';
  const m = Math.round(seconds / 60);
  return m < 60 ? m + ' min' : Math.round(m / 60) + ' h';
}

function OpenRow({ r, ok, busy }) {
  return html`<div class=${cls('mp-lobby-row', !r.joinable && 'no')}>
    <div class="mp-lobby-main">
      <span class="who" title=${r.host}>${r.host}</span>
      <span class="ros" title=${r.roster_name}>${r.roster_name || 'roster'}</span>
    </div>
    <span class="age">${age(r.age_seconds)}</span>
    <${Button} small kind=${r.joinable ? 'primary' : 'ghost'} disabled=${!ok || busy || !r.joinable}
      onClick=${() => call('online_join', r.code)}>Join<//>
    ${r.why && html`<span class="why">${r.why}</span>`}
    ${r.warn && html`<span class="why">${r.warn}</span>`}
  </div>`;
}

function Pick({ s }) {
  const [code, setCode] = useState('');
  const m = s.marks, idle = !s.busy, ok = m.ready;
  const join = () => { if (code.trim() && ok && idle) call('online_join', code); };
  return html`<div class="mp-body mp-fill mp-pick">
    ${!ok && html`<div class="mp-notice caution">
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" class="mp-warn"><path d="M10 2l9 16H1z" fill="none" stroke="currentColor" stroke-width="2"/>
        <path d="M10 8v5M10 15v1" stroke="currentColor" stroke-width="2"/></svg>
      <span class="sp"><b>Set up online first.</b> Online play needs the game patch and its online entry, so a lobby cannot start the game yet.</span>
      <${Button} small kind="amber" disabled=${!idle || !s.account || m.game === 'open'} onClick=${() => call('online_setup')}>Set up online<//>
    </div>`}
    <div class="mp-tiles">
      <div class="mp-tile host">
        <div class="mp-tile-t">Host a lobby</div>
        <div class="mp-tile-d">You get a short code to send to a friend, or your lobby shows in the public list.</div>
        <div class="mp-tile-opt"><${Toggle} on=${s.public} label="Show it in the public list" disabled=${!idle}
          onChange=${(on) => call('online_public', on)}/><span>Show it in the public list</span></div>
        <div class=${cls('mp-bring', s.bring_why && 'no')}>${s.bring_why ? s.bring_why : html`You bring: <b>${s.bring}</b> (picked in Setup)`}</div>
        ${s.build_old && html`<div class="mp-note bad">${s.build_old}</div>`}
        <${Button} kind="gold" big block disabled=${!ok || !idle || !!s.bring_why || !!s.build_old}
          onClick=${() => call('online_create')}>Create lobby<//>
      </div>
      <div class="mp-tile join">
        <div class="mp-tile-t">Join a friend</div>
        <div class="mp-tile-d">Type the code your friend sent you. Their roster is copied into your Puck Peak Online save (a backup is kept).</div>
        <input class="field mp-code-in" placeholder="CODE" value=${code} maxlength="8" spellcheck="false" aria-label="Lobby code"
          onInput=${(e) => setCode(e.target.value.toUpperCase())} onKeyDown=${(e) => { if (e.key === 'Enter') join(); }}/>
        <${Button} big block kind=${code ? 'primary' : 'ghost'} disabled=${!ok || !idle || !code.trim()} onClick=${join}>Join with a code<//>
      </div>
    </div>
    <div class="mp-public">
      <div class="mp-row"><span class="mp-lbl">Public lobbies</span>${s.open.length > 0 && html`<${Tag}>${s.open.length}<//>`}
        <span class="sp"></span><${Button} small disabled=${!ok} onClick=${() => call('online_list')}>Refresh<//></div>
      ${s.open_error && html`<div class="mp-note warn">${s.open_error}</div>`}
      ${s.open.length
        ? html`<div class="mp-list">${s.open.map((r) => html`<${OpenRow} key=${r.code} r=${r} ok=${ok} busy=${!idle}/>`)}</div>`
        : !s.open_error && html`<div class="mp-public-empty"><div><div class="mp-public-t">${ok ? 'No public lobbies right now' : 'Set up online first to see the lobbies'}</div>
            <div class="mp-public-d">${ok ? 'Make one, or ask a friend for a code. The list refreshes by itself.' : 'Then the open lobbies show here.'}</div></div></div>`}
    </div>
    <${HowTo}/>
  </div>`;
}

// --- 2 Lobby, open: the code, the two players, Ready, chat ---------------------------------------------------------------
function chip(s) {
  const lob = s.lobby;
  if (s.ended) return { tone: 'info', text: 'game closed' };
  if (s.launched || lob.state === 'playing') return { tone: 'good', text: 'in the game' };
  if (lob.state === 'starting') return { tone: 'good', text: 'both ready' };
  if (lob.state === 'expired') return { tone: 'bad', text: 'closed' };
  return lob.members.length < 2 ? { tone: 'info', text: 'waiting for a friend' } : { tone: 'info', text: 'full: press Ready' };
}

function Player({ m, me, progress, launched }) {
  const roster = !m.roster_ok ? html`<${Tag} tone="bad">needs the roster<//>`
    : html`<${Tag} tone="good">${m.role === 'host' ? 'brings the roster' : 'roster ok'}<//>`;
  return html`<div class=${cls('mp-player', m.ready && 'ready', me && 'me')}>
    <span class="mp-player-name" title=${m.name}>${m.name}${me && html`<span class="you">you</span>`}</span>
    <span class="mp-player-role">${m.role === 'host' ? 'host' : 'guest'}</span>
    <div class="mp-marks">
      ${launched
        ? html`<${Tag} tone="info">${progress[m.progress] || 'starting'}<//>`
        : html`<${Tag} tone=${m.ready ? 'good' : 'caution'}>${m.ready ? 'ready' : 'not ready'}<//>`}
      ${roster}
      ${!m.patch_ok && html`<${Tag} tone="caution" title=${m.patch ? 'game patch: ' + m.patch : ''}>other game patch<//>`}
    </div>
  </div>`;
}

function Chat({ s }) {
  const [text, setText] = useState('');
  const send = (t) => { if (t.trim()) { call('online_say', t); setText(''); } };
  const lines = s.chat.slice(-8);
  return html`<div class="mp-chat">
    <div class="mp-lbl">Chat</div>
    <div class="mp-chat-log" role="log" aria-live="polite">${lines.length
      ? lines.map((c) => html`<div key=${c.seq} class=${cls('mp-chat-line', c.mine && 'mine')}><b>${c.mine ? 'You' : c.name}</b><span>${c.text}</span></div>`)
      : html`<div class="mp-chat-empty">Say hi. Lines are not kept after the lobby closes.</div>`}</div>
    <div class="mp-chat-in"><input class="field" placeholder="Message" maxlength="140" value=${text} spellcheck="false"
        onInput=${(e) => setText(e.target.value)} onKeyDown=${(e) => { if (e.key === 'Enter') send(text); }}/>
      <${Button} small disabled=${s.chat_wait || !text.trim()} onClick=${() => send(text)}>Send<//></div>
    <div class="mp-chat-quick">${s.phrases.map((p, i) => html`<button key=${p} type="button" class="mp-chat-chip"
        disabled=${s.chat_wait} title=${s.overlay && s.overlay.on ? `Ctrl+Shift+F${i + 1} in the game` : null} onClick=${() => send(p)}>${p}</button>`)}</div>
  </div>`;
}

function Lobby({ s }) {
  const lob = s.lobby;
  const c = chip(s);
  const mine = lob.members.find((m) => m.name === s.account);
  const partner = lob.members.find((m) => m.name !== s.account);
  const two = lob.members.length >= 2;
  return html`<${Card} n=${2} title=${s.launched ? `Lobby ${s.code}` : 'Lobby'} className="mp-stage"
      aside=${html`<${Tag} tone=${c.tone}>${c.text}<//>`}>
    <div class="mp-body">
      ${!s.launched && html`<div class="mp-code"><span class="mp-code-big selectable">${s.code}</span>
        <${Button} small onClick=${() => copy(s.code)}>Copy<//>
        <span class="mp-note">${s.public && s.role === 'host' ? 'Listed for everybody. You can also send this code.' : 'Tell your friend this code.'}</span></div>`}
      <div class="mp-players">
        ${lob.members.map((m) => html`<${Player} key=${m.name} m=${m} me=${m.name === s.account} progress=${s.progress} launched=${s.launched}/>`)}
        ${!two && html`<div class="mp-player empty">Waiting for a friend</div>`}
      </div>
      ${s.brought && html`<div class="mp-note">You bring: <b>${s.brought}</b></div>`}
      ${lob.reason && html`<div class="mp-note warn">${lob.reason}</div>`}
      ${s.hint && html`<div class="mp-notice caution"><span class="sp">${s.hint}</span>
        ${s.guest_problem && html`<${Button} small kind="amber" onClick=${() => call('tab', 'patch')}>Open Game patch<//>`}</div>`}
      ${s.build_note && html`<div class="mp-note warn">${s.build_note.text}</div>`}
      ${s.game_note && html`<div class="mp-note warn">${s.game_note.text}</div>`}
      ${!s.launched && html`<div class="mp-row">
        ${!two && html`<${Button} kind="gold" big disabled>Waiting for a friend<//>`}
        ${two && !(mine && mine.ready) && html`<${Button} kind="gold" big disabled=${!!s.busy || !!s.guest_problem}
          onClick=${() => call('online_ready', true)}>Ready<//>`}
        ${two && mine && mine.ready && html`<${Button} kind="gold" big disabled>Waiting for ${partner ? partner.name : 'your friend'}<//>
          <${Button} small disabled=${!!s.busy} onClick=${() => call('online_ready', false)}>Not ready<//>`}
        <span class="sp"></span>
        <${Button} small disabled=${!!s.busy} onClick=${() => call('online_leave')}>Leave<//>
      </div>`}
      ${s.launched && html`<div class="mp-row"><span class="sp"></span><${Button} small disabled=${!!s.busy} onClick=${() => call('online_leave')}>Leave<//></div>`}
      ${!s.launched && html`<div class="mp-note">${two ? 'Both press Ready, then the game starts by itself.' : 'Give your friend the code. Both press Ready, then the game starts by itself.'}
        ${' '}The match is the game's standard online match: 5 minute periods, NHL rules.</div>`}
      ${s.ended && html`<div class="mp-note">The game has closed. For a rematch, leave and make a new lobby.</div>`}
      ${two && s.chat && html`<${Chat} s=${s}/>`}
    </div>
  <//>`;
}

function Game({ s }) {
  return html`<${Card} title="Game" aside=${s.launched ? 'now, in the game' : 'when the game starts'}>
    <div class="mp-body">
      <div class="mp-steps">
        ${s.why && html`<div class="mp-step fail"><span class="n">!</span><span>${s.why}</span></div>`}
        ${s.steps.map((t, k) => html`<div key=${k} class=${cls('mp-step', s.launched && 'live')}><span class="n">${k + 1}</span><span>${t}</span></div>`)}
      </div>
      <div class="mp-note">The game does the rest once both of you are in the session.</div>
    </div>
  <//>`;
}

// --- 3 Your rating and the history ---------------------------------------------------------------------------------------
function RatingCard({ s }) {
  const r = s.ranks, c = r.card;
  const aside = html`<span class="mp-aside-opt"><${Toggle} on=${!r.hidden} label="Show me on the leaderboard"
    onChange=${(on) => call('online_hide', !on)}/><span>Show me on the leaderboard</span></span>`;
  if (!c) {
    return html`<${Card} n=${3} title="Your rating" aside=${aside}>
      <div class="mp-body"><div class="mp-empty">No rated match yet. A versus match from a lobby counts once both reports agree.</div>
        ${r.hidden && html`<div class="mp-note">Others see you as "Hidden player".</div>`}</div><//>`;
  }
  const placement = r.placement || 5;
  const placed = placement - (c.placing || 0);
  const last = (r.history || []).find((m) => m.delta != null);
  const low = (r.tiers || []).find((t) => t.name === c.tier);
  let bar = 1;
  if (c.placing > 0) bar = placed / placement;
  else if (c.next_at && low && c.next_at > low.min) bar = (c.rating - low.min) / (c.next_at - low.min);
  const streak = Math.abs(c.streak || 0) >= 2 ? `${Math.abs(c.streak)} ${c.streak > 0 ? 'wins' : 'losses'} in a row` : '';
  return html`<${Card} n=${3} title="Your rating" aside=${aside}>
    <div class="mp-body mp-rating">
      <div class="mp-rating-n">${c.rating}</div>
      <div class="mp-rating-side">
        <div class="mp-rating-top">
          <${Tag} tone=${c.placing > 0 ? 'info' : 'good'}>${c.placing > 0 ? `Placing ${placed}/${placement}` : c.tier}<//>
          ${last && html`<span class=${cls('mp-delta', last.delta > 0 && 'plus', last.delta < 0 && 'minus')}>${signed(last.delta)} last game</span>`}
          <span class="mp-rating-rec">Record ${c.w || 0}-${c.l || 0}</span>
        </div>
        <div class="mp-progress" title=${c.next_tier && c.next_at ? `${c.next_at - c.rating} to ${c.next_tier}` : null}>
          <span style=${{ width: `${Math.round(Math.min(1, Math.max(0, bar)) * 100)}%` }}></span></div>
        <div class="mp-rating-note">${c.placing > 0
          ? `${c.placing} more rated ${c.placing === 1 ? 'match' : 'matches'} to get your rank`
          : `${c.rank ? `#${c.rank} of ${c.of}` : 'Ranked'}${c.next_tier && c.next_at ? ` · ${c.next_at - c.rating} to ${c.next_tier} (${c.next_at})` : ''}`}</div>
        ${streak && html`<div class="mp-rating-note">${streak}</div>`}
        ${r.hidden && html`<div class="mp-rating-note">Others see you as "Hidden player".</div>`}
      </div>
    </div>
  <//>`;
}

const STATUS = {
  confirmed: ['good', 'confirmed'], waiting: ['caution', 'waiting for the other report'], disputed: ['bad', 'reports differ'],
  voided: ['info', 'no result'], forfeit: ['caution', 'left early'],
};

function MatchRow({ m, me }) {
  const [tone, text] = STATUS[m.status] || ['info', m.status || 'match'];
  const score = m.for == null ? '–' : `${m.for}–${m.against == null ? '?' : m.against}`;
  return html`<div class=${cls('mp-match', m.status)} title="Box score" onClick=${() => call('online_box', m.id)}>
    <div class="mp-match-a">
      <span class=${cls('mp-side', m.result === 'W' && 'won')}><span class="mp-side-name">${me || 'You'}</span>
        ${m.team && html`<span class="mp-team">${m.team}</span>`}</span>
      <div class="mp-match-sub"><${Tag} tone=${tone}>${text}<//>
        ${m.delta != null && html`<span class=${cls('mp-delta', m.delta > 0 && 'plus', m.delta < 0 && 'minus')}>${signed(m.delta)}</span>`}</div>
    </div>
    <span class=${cls('mp-score', m.status !== 'confirmed' && 'tentative')}>${score}</span>
    <div class="mp-match-b">
      <span class=${cls('mp-side', m.result === 'L' && 'won')}>${m.opp_team && html`<span class="mp-team">${m.opp_team}</span>`}
        <span class="mp-side-name" title=${m.opponent}>${m.opponent}</span></span>
    </div>
  </div>`;
}

function BoardRow({ p, me, placement }) {
  return html`<div class=${cls('mp-prow', me && 'you')}>
    <span class="mp-prow-n mp-rk">${p.rank ? '#' + p.rank : '…'}</span>
    <span class="mp-prow-name" title=${p.name}>${p.name}${me && html`<span class="you">you</span>`}</span>
    <span class="mp-prow-tier">${p.rank ? p.tier : `Placing ${placement - p.placing}/${placement}`}</span>
    <span class="mp-prow-n mp-rt">${p.rating}</span><span class="mp-prow-n">${p.w}-${p.l}</span>
  </div>`;
}

// The rating over the last matches: one line, the newest value labelled; each point's value on hover.
function Sparkline({ values }) {
  if (values.length < 2) return null;
  const W = 300, H = 56, P = 6;
  const lo = Math.min(...values), hi = Math.max(...values), span = Math.max(hi - lo, 1);
  const pts = values.map((v, k) => [P + (k * (W - 2 * P)) / (values.length - 1), P + ((hi - v) * (H - 2 * P)) / span]);
  const last = pts[pts.length - 1];
  return html`<div class="om-spark"><div class="mp-lbl">Rating, last ${values.length} rated matches</div>
    <svg viewBox=${`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label=${`Rating from ${values[0]} to ${values[values.length - 1]}`}>
      <polyline points=${pts.map((p) => p.join(',')).join(' ')} fill="none" vector-effect="non-scaling-stroke"/>
      ${pts.map((p, k) => html`<circle key=${k} cx=${p[0]} cy=${p[1]} r="7" class="hit"><title>${values[k]}</title></circle>`)}
      <path d=${`M${last[0]} ${last[1]}h0`} class="dot" vector-effect="non-scaling-stroke"/>
    </svg>
    <div class="ends"><span>${lo === hi ? '' : `low ${lo}`}</span><span>${lo === hi ? values[0] : `high ${hi}`}</span></div></div>`;
}

function Records({ title, rows }) {
  if (!rows.length) return null;
  return html`<div class="om-records"><div class="mp-lbl">${title}</div>
    ${rows.map((x) => html`<div class="om-rec" key=${x.name}><span class="who" title=${x.name}>${x.name}</span>
      <span class="wl">${x.w}-${x.l}</span></div>`)}</div>`;
}

function StatsView({ st }) {
  if (st.note) return html`<div class="mp-empty">${st.note}</div>`;
  return html`<div class="om-tiles">${st.tiles.map((t) => html`<div class="om-tile" key=${t.label}>
      <div class="mp-lbl">${t.label}</div><div class="val">${t.value}</div>${t.sub && html`<div class="sub">${t.sub}</div>`}</div>`)}</div>
    ${st.form.length > 0 && html`<div class="om-form"><span class="mp-lbl">Form</span>
      ${st.form.map((f, k) => html`<span key=${k} class=${cls('res', f === 'W' ? 'w' : 'l')}>${f}</span>`)}</div>`}
    <${Sparkline} values=${st.curve}/>
    <div class="om-recs"><${Records} title="Against" rows=${st.opponents}/><${Records} title="With" rows=${st.teams}/></div>`;
}

function BoxView({ b }) {
  if (!b.on || !b.id) return html`<div class="mp-empty">${b.note}</div>`;
  return html`<div class="om-box-pick">
      <${Button} small disabled=${!b.older} onClick=${() => call('online_box', b.older)}>‹ Older<//>
      <span class="title" title=${b.title}>${b.title}</span>
      <${Button} small disabled=${!b.newer} onClick=${() => call('online_box', b.newer)}>Newer ›<//></div>
    ${b.sides && html`<div class="om-box">
      <div class="head"><span></span>${b.sides.map((x, k) => html`<span key=${k} class=${cls('side', k === 0 && 'me')}>
        <b title=${x.team}>${x.team || '-'}</b><small title=${x.name}>${x.name}</small></span>`)}</div>
      <div class="line goals"><span>Goals</span>${b.sides.map((x, k) => html`<span key=${k}>${x.score == null ? '-' : x.score}</span>`)}</div>
      ${b.rows.map((x) => html`<div class="line" key=${x.label}><span>${x.label}</span><span>${x.me}</span><span>${x.them}</span></div>`)}
    </div>`}
    ${b.loading && !b.note && html`<div class="mp-note">Reading the box score...</div>`}
    ${b.note && html`<div class="mp-note">${b.note}</div>`}`;
}

const VIEWS = [{ value: 'mine', label: 'Recent matches' }, { value: 'stats', label: 'My stats' }, { value: 'box', label: 'Box score' },
  { value: 'board', label: 'Leaderboard' }];

function History({ s }) {
  const r = s.ranks, view = r.tab;
  const aside = html`<${Button} small onClick=${() => call('online_ranks')}>Refresh<//>
    <${Button} small onClick=${() => call('online_board')}>Open in browser<//>`;
  return html`<${Card} title="History" aside=${aside} className="mp-card-fill mp-hist-card">
    <div class="mp-body mp-fill mp-hist">
      <${Segmented} options=${VIEWS} value=${view} onChange=${(v) => call('online_ranks_tab', v)}/>
      <div class="mp-hist-scroll">
        ${view === 'mine' && (r.history.length
          ? html`<div class="mp-matches">${r.history.map((m) => html`<${MatchRow} key=${m.id} m=${m} me=${s.account}/>`)}</div>
              <div class="mp-note">A result counts once both reports agree. Press a match for its box score.</div>`
          : html`<div class="mp-empty">No matches yet. Every match two players start from a lobby shows up here; it counts when both reports agree.</div>`)}
        ${view === 'stats' && html`<${StatsView} st=${r.stats}/>`}
        ${view === 'box' && html`<${BoxView} b=${r.box}/>`}
        ${view === 'board' && html`
          ${r.highlights.map((h) => html`<div class="om-hl" key=${h.kind}><b>${h.title}</b> ${h.name} <span>${h.value}</span></div>`)}
          ${r.top.length > 0 && html`<div class="mp-players-table">
            <div class="mp-prow head"><span class="mp-prow-n mp-rk">Rank</span><span class="mp-prow-name">Player</span>
              <span class="mp-prow-tier">Tier</span><span class="mp-prow-n mp-rt">Rating</span><span class="mp-prow-n">W-L</span></div>
            ${r.top.map((p) => html`<${BoardRow} key=${p.name + p.rank} p=${p} me=${p.name === s.account} placement=${r.placement}/>`)}
            ${r.me && html`<${BoardRow} p=${r.me} me=${true} placement=${r.placement}/>`}
          </div>`}
          ${!r.top.length && html`<div class="mp-empty">No rated matches yet.</div>`}`}
      </div>
    </div>
  <//>`;
}

function ResultWindow({ r }) {
  const close = () => call('online_result_seen');
  const score = r.for == null ? '' : `${r.team} ${r.for} - ${r.against} ${r.opp_team}`;
  return html`<${Modal} title=${'Match against ' + r.opponent} onClose=${close}
    buttons=${html`<${Button} kind="primary" onClick=${close}>OK<//>`}>
    <div class="om-result">
      ${score && html`<div class="score">${score}</div>`}
      <div class="line">${r.line}</div>
      ${r.rating != null && html`<div class="rating">Rating ${r.before} → <b>${r.rating}</b>
        <span class=${r.delta > 0 ? 'up' : 'down'}> (${signed(r.delta)})</span></div>`}
      ${r.tier && html`<div class="small-note">${r.placing > 0 ? `Placing: ${r.placing} more match${r.placing === 1 ? '' : 'es'} before your rank shows.`
        : r.tier + (r.next_tier ? ` · ${r.next_tier} at ${r.next_at}` : '')}</div>`}
    </div>
  <//>`;
}

export function OnlineTab({ s }) {
  if (!s) return null;
  const side = !!s.ranks;
  return html`<div class=${cls('online mp', !side && 'no-side')}>
    <div class="mp-col mp-col-you"><${You} s=${s}/></div>
    <div class="mp-col mp-col-lobby">
      ${s.lobby
        ? html`<${Lobby} s=${s}/>`
        : html`<${Card} n=${2} title="Lobby" aside="Play one friend at a time" className="mp-card-fill mp-stage">
            ${s.state === 'no-rpcs3' || !s.account
              ? html`<div class="mp-body mp-fill"><div class="mp-empty">${s.state === 'no-rpcs3' ? s.no_rpcs3
                  : s.native ? 'Type your online name first (left): a lobby is tied to it.'
                    : 'Make your online account in RPCS3 first (left): a lobby is tied to its name.'}</div>
                  <div class="mp-spacer"></div><${HowTo}/></div>`
              : html`<${Pick} s=${s}/>`}
          <//>`}
      ${s.lobby && s.steps.length > 0 && !s.ended && html`<${Game} s=${s}/>`}
    </div>
    ${side && html`<div class="mp-col mp-col-side"><${RatingCard} s=${s}/><${History} s=${s}/></div>`}
    ${s.result && html`<${ResultWindow} r=${s.result}/>`}
  </div>`;
}
