// The Play online tab: your online account, the one-press setup, a lobby of two by code, and what to press in the game.
// Python (app/online.py) holds everything; this page shows the `online` slice and calls online_*.
import { html, cls, useState } from './lib.js';
import { call } from './bridge.js';
import { Button, Card, Modal, Segmented, TextField, Toggle } from './ui.js';

function Check({ ok, label, note, tab, fix }) {
  return html`<div class=${cls('om', ok ? 'ok' : 'no')}><span class="dot">${ok ? '✓' : '•'}</span>
    <span class="lab">${label}</span>${note && html`<span class="small-note">${note}</span>`}
    ${!ok && tab && html`<${Button} small onClick=${() => call('tab', tab)}>${fix}<//>`}</div>`;
}

function rankText(card) {
  if (!card) return 'No rated match yet';
  if (card.placing > 0) return `Placing: ${card.placing} more match${card.placing === 1 ? '' : 'es'} · rating ${card.rating}`;
  return `${card.tier} · rating ${card.rating}${card.rank ? ` · #${card.rank} of ${card.of}` : ''}`;
}

function NameField({ s }) {
  const [text, setText] = useState(s.account || '');
  const save = () => call('online_name', text);
  return html`<div class="row"><${TextField} className="on-say" value=${text} placeholder="Your online name" delay=${0}
    disabled=${!!s.lobby} onChange=${setText} onEnter=${save}/>
    <${Button} small disabled=${!!s.lobby || !text.trim() || text === s.account} onClick=${save}>Save name<//></div>`;
}

function YouCard({ s }) {
  const m = s.marks, r = s.ranks;
  const rosterBad = s.guest_problem || (!s.lobby && s.bring_why);
  return html`<${Card} title="You" style=${{ '--i': 0 }}>
    <div class="card-body">
      ${s.account
        ? html`<div class="row on-account"><span class="who">${s.account}</span>
            <span class="small-note">${r ? rankText(r.card) : s.native ? 'Your online name' : 'RPCN name from RPCS3'}</span></div>`
        : html`<div class="small-note">${s.no_account}</div>`}
      ${s.native && html`<${NameField} s=${s}/>`}
      <${Check} ok=${!rosterBad} label="Roster" note=${rosterBad ? null : (s.roster || s.bring || null)}
        tab=${s.guest_problem ? 'patch' : 'setup'} fix=${s.guest_problem ? 'Game patch' : 'Setup'}/>
      <${Check} ok=${m.patched && m.online} label=${s.native ? 'Game patch' : 'Game patch and online entry'} tab="patch" fix="Game patch"/>
      <${Check} ok=${s.server !== false} label="Puck Peak server" note=${s.server === false ? 'not reachable' : null}/>
      ${!s.native && html`<${Check} ok=${s.build != null && !s.build_old} label="RPCS3 version" note=${s.build != null ? 'build ' + s.build : 'not seen yet'}/>`}
      <div class="row on-actions">
        <${Button} kind="primary" disabled=${!!s.busy || !s.account || m.game === 'open'}
          onClick=${() => call('online_setup')}>${m.ready ? 'Set up again' : 'Set up online'}<//>
        <${Button} small disabled=${!!s.busy} onClick=${() => call('online_check')}>Check again<//>
        ${m.game === 'open' && html`<span class="small-note">${s.native ? 'Close the game first.' : 'Close RPCS3 first.'}</span>`}
      </div>
      ${r && html`<div class="row on-actions"><${Toggle} on=${!r.hidden} label="Show me on the leaderboard"
        onChange=${(on) => call('online_hide', !on)}/><span class="lab">Show me on the leaderboard</span>
        <span class="small-note">${r.hidden ? 'Others see you as "Hidden player".' : 'Your RPCN name, rank and matches are public.'}</span></div>`}
      ${s.overlay && s.overlay.can && html`<div class="row on-actions"><${Toggle} on=${s.overlay.on}
        label="Show chat and results over the game" onChange=${(on) => call('online_overlay', on)}/>
        <span class="lab">Show chat and results over the game</span>
        <span class="small-note">${s.overlay.on ? 'In the game, Ctrl+Shift+F1 to F6 send the six phrases.' : 'Off: chat and results only show here.'}</span></div>`}
    </div>
  <//>`;
}

function signed(n) { return n == null ? '' : (n > 0 ? '+' : '') + n; }

const STATUS = { waiting: 'waiting', disputed: 'reports differ', voided: 'no result', forfeit: 'left early' };

function MatchRow({ m }) {
  return html`<div class="om-match pick" title="Box score" onClick=${() => call('online_box', m.id)}>
    <span class=${cls('res', m.result === 'W' ? 'w' : m.result === 'L' ? 'l' : '')}>${m.result || '-'}</span>
    <span class="who" title=${m.opponent}>${m.opponent}</span>
    <span class="score">${m.team} ${m.for == null ? '-' : m.for}-${m.against == null ? '-' : m.against} ${m.opp_team}</span>
    <span class=${cls('delta', m.delta > 0 ? 'up' : m.delta < 0 ? 'down' : '')}>${STATUS[m.status] || signed(m.delta)}</span>
  </div>`;
}

function BoardRow({ p, me, placement }) {
  return html`<div class=${cls('om-board', me && 'me')}>
    <span class="rank">${p.rank || '-'}</span><span class="who" title=${p.name}>${p.name}</span>
    <span class="tier">${p.rank ? p.tier : `Placing ${placement - p.placing}/${placement}`}</span>
    <span class="rating">${p.rating}</span><span class="wl">${p.w}-${p.l}</span>
  </div>`;
}

// The rating over the last matches: one line, the newest value labelled; each point's value on hover.
function Sparkline({ values }) {
  if (values.length < 2) return null;
  const W = 300, H = 56, P = 6;
  const lo = Math.min(...values), hi = Math.max(...values), span = Math.max(hi - lo, 1);
  const pts = values.map((v, k) => [P + (k * (W - 2 * P)) / (values.length - 1), P + ((hi - v) * (H - 2 * P)) / span]);
  const last = pts[pts.length - 1];
  return html`<div class="om-spark"><div class="lab">Rating, last ${values.length} rated matches</div>
    <svg viewBox=${`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label=${`Rating from ${values[0]} to ${values[values.length - 1]}`}>
      <polyline points=${pts.map((p) => p.join(',')).join(' ')} fill="none" vector-effect="non-scaling-stroke"/>
      ${pts.map((p, k) => html`<circle key=${k} cx=${p[0]} cy=${p[1]} r="7" class="hit"><title>${values[k]}</title></circle>`)}
      <path d=${`M${last[0]} ${last[1]}h0`} class="dot" vector-effect="non-scaling-stroke"/>
    </svg>
    <div class="ends"><span>${lo === hi ? '' : `low ${lo}`}</span><span>${lo === hi ? values[0] : `high ${hi}`}</span></div></div>`;
}

function Records({ title, rows }) {
  if (!rows.length) return null;
  return html`<div class="om-records"><div class="lab">${title}</div>
    ${rows.map((x) => html`<div class="om-rec" key=${x.name}><span class="who" title=${x.name}>${x.name}</span>
      <span class="wl">${x.w}-${x.l}</span></div>`)}</div>`;
}

function StatsView({ st }) {
  if (st.note) return html`<div class="small-note">${st.note}</div>`;
  return html`<div class="om-tiles">${st.tiles.map((t) => html`<div class="om-tile" key=${t.label}>
      <div class="lab">${t.label}</div><div class="val">${t.value}</div>${t.sub && html`<div class="sub">${t.sub}</div>`}</div>`)}</div>
    ${st.form.length > 0 && html`<div class="om-form"><span class="lab">Form</span>
      ${st.form.map((f, k) => html`<span key=${k} class=${cls('res', f === 'W' ? 'w' : 'l')}>${f}</span>`)}</div>`}
    <${Sparkline} values=${st.curve}/>
    <div class="om-recs"><${Records} title="Against" rows=${st.opponents}/><${Records} title="With" rows=${st.teams}/></div>`;
}

function BoxView({ b }) {
  if (!b.on || !b.id) return html`<div class="small-note">${b.note}</div>`;
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
    ${b.loading && !b.note && html`<div class="small-note">Reading the box score...</div>`}
    ${b.note && html`<div class="small-note">${b.note}</div>`}`;
}

const VIEWS = [{ value: 'mine', label: 'Matches' }, { value: 'stats', label: 'My stats' }, { value: 'box', label: 'Box score' },
  { value: 'board', label: 'Leaderboard' }];

function RanksCard({ s }) {
  const r = s.ranks;
  if (!r) return null;
  const view = r.tab;
  const aside = html`<${Button} small onClick=${() => call('online_ranks')}>Refresh<//>
    <${Button} small onClick=${() => call('online_board')}>Open in browser<//>`;
  return html`<${Card} title="Ranks" aside=${aside} grow className="om-ranks" style=${{ '--i': 1 }}>
    <div class="card-body fill">
      <div class="row"><${Segmented} options=${VIEWS} value=${view} onChange=${(v) => call('online_ranks_tab', v)}/>
        ${view === 'mine' && r.history.length > 0 && html`<span class="small-note">Press a match for its box score.</span>`}</div>
      <div class="scroll">
        ${view === 'mine'
          ? (r.history.length ? r.history.map((m) => html`<${MatchRow} key=${m.id} m=${m}/>`)
            : html`<div class="small-note">No matches yet. A versus match from a lobby counts when both reports agree.</div>`)
          : view === 'stats' ? html`<${StatsView} st=${r.stats}/>`
          : view === 'box' ? html`<${BoxView} b=${r.box}/>`
          : html`${r.highlights.map((h) => html`<div class="om-hl" key=${h.kind}><b>${h.title}</b> ${h.name} <span>${h.value}</span></div>`)}
              ${r.top.map((p) => html`<${BoardRow} key=${p.name + p.rank} p=${p} me=${p.name === s.account} placement=${r.placement}/>`)}
              ${r.me && html`<${BoardRow} p=${r.me} me=${true} placement=${r.placement}/>`}
              ${!r.top.length && html`<div class="small-note">No rated matches yet.</div>`}`}
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

function Chat({ s }) {
  const [text, setText] = useState('');
  const send = (t) => { if (t.trim()) { call('online_say', t); setText(''); } };
  const lines = s.chat.slice(-8);
  return html`<div class="om-chat">
    <div class="log">${lines.length ? lines.map((c) => html`<div key=${c.seq} class=${cls('c', c.mine && 'mine')}><b>${c.name}</b> ${c.text}</div>`)
      : html`<div class="small-note">Say hello. Lines are not kept after the lobby closes.</div>`}</div>
    <div class="row">${s.phrases.map((p) => html`<${Button} small key=${p} disabled=${s.chat_wait} onClick=${() => send(p)}>${p}<//>`)}</div>
    <div class="row"><${TextField} className="on-say" value=${text} placeholder="Message" delay=${0} onChange=${setText} onEnter=${() => send(text)}/>
      <${Button} small disabled=${s.chat_wait || !text.trim()} onClick=${() => send(text)}>Send<//></div>
  </div>`;
}

function Member({ m, me, progress }) {
  const ok = m.roster_ok && m.patch_ok;
  const flag = !m.roster_ok ? 'needs the roster' : !m.patch_ok ? 'other game patch' : (m.role === 'host' ? 'brings the roster' : 'same roster');
  return html`<div class=${cls('om-member', me && 'me')}>
    <span class="who">${m.name}</span><span class="role">${m.role === 'host' ? 'host' : 'guest'}</span>
    <span class=${cls('om-flag', ok ? 'ok' : 'no')} title=${m.patch ? 'game patch: ' + m.patch : ''}>${flag}</span>
    <span class="prog">${m.ready ? 'Ready · ' : ''}${progress[m.progress] || ''}</span>
  </div>`;
}

function LobbyCard({ s }) {
  const [text, setText] = useState('');
  const lob = s.lobby, ok = s.state !== 'no-rpcs3' && s.state !== 'no-account' && s.state !== 'not-set-up';
  if (!lob) {
    return html`<${Card} title="Play a friend" style=${{ '--i': 2 }}>
      <div class="card-body">
        <div class="small-note">One of you makes a lobby. Public lobbies are in the list below for anybody; a private one is joined with its code. Then both press Ready.</div>
        <div class=${cls('om-bring', s.bring_why && 'no')}>${s.bring_why ? s.bring_why : 'You bring: ' + s.bring + ' (picked in Setup)'}</div>
        <div class="row on-actions">
          <${Segmented} options=${[{ value: 'private', label: 'Private' }, { value: 'public', label: 'Public' }]}
            value=${s.public ? 'public' : 'private'} disabled=${!!s.busy} onChange=${(v) => call('online_public', v === 'public')}/>
          <${Button} kind="primary" disabled=${!ok || !!s.busy || !!s.bring_why || !!s.build_old} onClick=${() => call('online_create')}>Make a lobby<//>
        </div>
        ${s.build_old && html`<div class="om-why">${s.build_old}</div>`}
        <div class="small-note">Joining copies your friend's roster into your Puck Peak Online save (a backup is kept).</div>
        <div class="row on-actions">
          <${TextField} className="on-code" value=${text} placeholder="Lobby code from a friend" onChange=${setText}
            onEnter=${() => call('online_join', text)}/>
          <${Button} disabled=${!ok || !!s.busy || !text.trim()} onClick=${() => call('online_join', text)}>Join<//>
        </div>
      </div>
    <//>`;
  }
  const mine = lob.members.find((m) => m.name === s.account);
  return html`<${Card} title="Your lobby" aside=${lob.state} style=${{ '--i': 2 }}>
    <div class="card-body">
      <div class="row on-codebox"><span class="on-code-big selectable">${s.code}</span>
        <${Button} small onClick=${() => navigator.clipboard && navigator.clipboard.writeText(s.code)}>Copy<//>
        <span class="small-note">${s.public && s.role === 'host' ? 'Listed for everybody. You can also send this code.' : 'Tell your friend this code.'}</span></div>
      <div class="om-members">${lob.members.map((m) => html`<${Member} key=${m.name} m=${m} me=${m.name === s.account} progress=${s.progress}/>`)}</div>
      ${s.brought && html`<div class="small-note">You bring: ${s.brought}</div>`}
      ${lob.members.length < 2 && html`<div class="small-note">Waiting for your friend to join...</div>`}
      <div class="small-note">The match is the game's standard online match: 5 minute periods, NHL rules.</div>
      ${lob.reason && html`<div class="om-why">${lob.reason}</div>`}
      ${s.hint && html`<div class="om-why">${s.hint}${s.guest_problem && html` <${Button} small onClick=${() => call('tab', 'patch')}>Open Game patch<//>`}</div>`}
      ${s.build_note && html`<div class="om-why">${s.build_note.text}</div>`}
      ${s.game_note && html`<div class="om-why">${s.game_note.text}</div>`}
      ${s.ended && html`<div class="small-note">The game has closed. For a rematch, leave and make a new lobby.</div>`}
      ${s.chat && html`<${Chat} s=${s}/>`}
      <div class="row on-actions">
        ${!s.launched && html`<${Button} kind="primary" disabled=${!!s.busy || lob.members.length < 2 || (!!s.guest_problem && !(mine && mine.ready))}
          onClick=${() => call('online_ready', !(mine && mine.ready))}>${mine && mine.ready ? 'Not ready' : 'Ready'}<//>`}
        <${Button} disabled=${!!s.busy} onClick=${() => call('online_leave')}>Leave<//>
      </div>
    </div>
  <//>`;
}

function age(seconds) {
  if (seconds < 60) return 'just now';
  const m = Math.round(seconds / 60);
  return m < 60 ? m + ' min' : Math.round(m / 60) + ' h';
}

function OpenRow({ r, ok, busy }) {
  return html`<div class=${cls('om-open', !r.joinable && 'no')}>
    <span class="who" title=${r.host}>${r.host}</span>
    <span class="ros" title=${r.roster_name}>${r.roster_name || 'roster'}</span>
    <span class="meta">${age(r.age_seconds)} · ${r.members} of ${r.max}</span>
    <${Button} small kind=${r.joinable ? 'primary' : 'ghost'} disabled=${!ok || busy || !r.joinable}
      onClick=${() => call('online_join', r.code)}>Join<//>
    ${r.why && html`<span class="why">${r.why}</span>`}
    ${r.warn && html`<span class="why">${r.warn}</span>`}
  </div>`;
}

function OpenCard({ s }) {
  const ok = s.state === 'ready';
  return html`<${Card} title="Open lobbies" aside=${s.open.length ? String(s.open.length) : null} grow style=${{ '--i': 3 }}>
    <div class="card-body fill"><div class="scroll">
      ${s.open_error && html`<div class="om-why">${s.open_error}</div>`}
      ${!s.open_error && !s.open.length && html`<div class="small-note">${ok
        ? 'Nobody is waiting right now. Make a public lobby and your friends will see it here.'
        : 'Set up online first to see the lobbies.'}</div>`}
      ${s.open.map((r) => html`<${OpenRow} key=${r.code} r=${r} ok=${ok} busy=${!!s.busy}/>`)}
      <div class="row on-actions"><${Button} small disabled=${!ok} onClick=${() => call('online_list')}>Refresh<//>
        <span class="small-note">The list refreshes by itself.</span></div>
    </div></div>
  <//>`;
}

function StepsCard({ s }) {
  return html`<${Card} title=${s.launched ? 'Now, in the game' : 'Then, in the game'} grow style=${{ '--i': 3 }}>
    <div class="card-body fill"><div class="scroll">
      ${s.why && html`<div class="om-why">${s.why}</div>`}
      <ol class="om-steps">${s.steps.map((t, k) => html`<li key=${k}>${t}</li>`)}</ol>
      <div class="small-note">The game does the rest once both of you are in the session.</div>
    </div></div>
  <//>`;
}

function HelpCard({ s }) {
  return html`<${Card} title="How it works" grow style=${{ '--i': 3 }}>
    <div class="card-body fill"><div class="scroll patch-info">
      <ul>
        <li>${s.native ? 'Type the name other players will see under You.' : 'Make your online account once in RPCS3. This tab reads only its name.'}</li>
        <li>Press Set up online. It adds the online part of the game patch.</li>
        <li>Pick the roster you want to play with in Setup. The one who makes the lobby brings it; the other gets a copy.</li>
        <li>Online play needs the game patch. Set up puts it in for you, after asking.</li>
        <li>One of you makes a lobby (private: send the code; public: it shows in the list), the other joins, both press Ready.</li>
        <li>The game starts by itself on both PCs. Follow the short list of buttons to press in the game.</li>
      </ul>
    </div></div>
  <//>`;
}

export function OnlineTab({ s }) {
  if (!s) return null;
  return html`<div class="columns online">
    <div class="col">
      ${s.state === 'no-rpcs3'
        ? html`<${Card} title="You" style=${{ '--i': 0 }}><div class="card-body"><div class="small-note">${s.no_rpcs3}</div></div><//>`
        : html`<${YouCard} s=${s}/>`}
      ${s.note && html`<div class=${cls('om-note', s.note.tone)}>${s.note.text}</div>`}
      ${s.busy && html`<div class="small-note">${s.busy}</div>`}
      <${RanksCard} s=${s}/>
    </div>
    <div class="col">
      <${LobbyCard} s=${s}/>
      ${s.lobby ? (s.steps.length && !s.ended ? html`<${StepsCard} s=${s}/>` : html`<${HelpCard} s=${s}/>`) : html`<${OpenCard} s=${s}/>`}
    </div>
    ${s.result && html`<${ResultWindow} r=${s.result}/>`}
  </div>`;
}
