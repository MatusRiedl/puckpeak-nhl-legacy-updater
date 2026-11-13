// The team tabs of the Roster editor: Roster (players | the player's card), Lines, Strategy and Jerseys & ice beside the
// team list, the Save bar under them, and the windows that stay windows (Team, My edits, Face of a player, Equipment).
// Python holds the roster (app/editor.py and the tabs' controllers); what is typed on the card stays here until Apply,
// Save or a pick of another player sends it along.
import { html, cls, useState, useEffect, useRef, useMemo, Fragment } from './lib.js';
import { call } from './bridge.js';
import { useSlice } from './store.js';
import { Button, Segmented, Card, TextField, Modal } from './ui.js';
import { Code } from './rail.js';

const COLUMNS = [
  { key: 'pos', title: 'Pos', w: '44px' }, { key: 'num', title: '#', w: '38px' }, { key: 'name', title: 'Name', w: 'minmax(120px, 1.4fr)' },
  { key: 'age', title: 'Age', w: '44px' }, { key: 'nat', title: 'Nat', w: '48px' }, { key: 'ovr', title: 'OVR', w: '48px' },
  { key: 'note', title: 'Change', w: 'minmax(90px, 1fr)' },
];
const GRID = COLUMNS.map((c) => c.w).join(' ');
const FIELDS = [
  ['first', 'First name'], ['last', 'Last name'], ['num', 'Number'], ['pos', 'Position'], ['style', 'Type'],
  ['shoots', 'Shoots'], ['birth', 'Born (YYYY-MM-DD)'], ['country', 'Country'], ['height', 'Height (cm)'],
  ['weight', 'Weight (kg)'], ['team', 'Team'], ['ovr', 'Overall'],
];
const kindOf = (pos) => (pos === 'G' ? 'G' : pos === 'D' ? 'D' : 'F');     // whose player types (ratings.STYLE_CHOICES)
const SAVE_MODES = [{ value: 'update', label: 'Update this roster' }, { value: 'new', label: 'Save as a new roster' }];

// what is typed on the player's card while it differs from Python's (null: nothing): Save and Ctrl+S send it along
export const cardDraft = { current: null };
export const saveRoster = () => call('editor_save', cardDraft.current);

// Python has one card; the Roster tab and the Draft & Pro tab both show it, so what is typed is kept here, for both
const typed = { key: undefined, form: {}, dirty: false, pickSeq: null, subs: new Set() };
function setTyped(next) {
  Object.assign(typed, next);
  cardDraft.current = typed.dirty && typed.key != null ? typed.form : null;
  typed.subs.forEach((f) => f());
}

export function useCardForm(s) {
  const [, tick] = useState(0);
  useEffect(() => {
    const f = () => tick((n) => n + 1);
    typed.subs.add(f);
    return () => { typed.subs.delete(f); };
  }, []);
  const card = s && s.card;
  const cardKey = card ? card.key : null;
  useEffect(() => {                   // a card filled again by Python: what was typed is taken or dropped there
    if (typed.key === cardKey) return;
    setTyped({ key: cardKey, form: card ? { ...card.values, ratings: { ...card.values.ratings } } : {}, dirty: false });
  }, [cardKey]);
  const pickSeq = card && card.face_pick ? card.face_pick.seq : null;
  useEffect(() => {                   // a face picked in the Face of a player window goes onto the card (no created look)
    if (pickSeq == null || typed.pickSeq === pickSeq) return;
    const { head, skin, eyes } = card.face_pick;
    setTyped({ pickSeq, dirty: true,
      form: { ...typed.form, head, ...(skin != null ? { skin } : {}), ...(eyes != null ? { eyes } : {}), look: null } });
  }, [pickSeq]);
  const lookSeq = card && card.look_pick ? card.look_pick.seq : null;
  useEffect(() => {                   // a look made in the Look window goes onto the card
    if (lookSeq == null || typed.pickSeq === lookSeq) return;
    setTyped({ pickSeq: lookSeq, dirty: true, form: { ...typed.form, look: card.look_pick.look } });
  }, [lookSeq]);
  const set = (k, v) => {
    const next = { ...typed.form, [k]: v };
    if (k === 'pos' && kindOf(v) !== kindOf(typed.form.pos)) next.style = '';   // forward <-> defence: his new position's usual type
    setTyped({ form: next, dirty: true });
  };
  const setRating = (a, v) => setTyped({ form: { ...typed.form, ratings: { ...(typed.form.ratings || {}), [a]: v } }, dirty: true });
  return { form: typed.form, dirty: typed.dirty, set, setRating };
}

function sortValue(row, key) {
  const v = row[key];
  const n = typeof v === 'number' ? v : parseFloat(v);
  return Number.isFinite(n) && String(v).trim() !== '' ? [0, n] : [1, String(v).toLowerCase()];
}

function sorted(rows, sort) {
  if (!sort) return rows;
  const out = rows.slice();
  out.sort((a, b) => {
    const x = sortValue(a, sort.key), y = sortValue(b, sort.key);
    const c = x[0] - y[0] || (x[1] < y[1] ? -1 : x[1] > y[1] ? 1 : 0);
    return sort.desc ? -c : c;
  });
  return out;
}

// a team tab with nothing to show for the team picked (free agents, no roster yet, a team without jerseys of its own)
function Why({ s, loading }) {
  return html`<div class="why card">${s.view && html`<${Code} team=${s.view}/>`}
    <p>${s.why || (loading ? 'Reading the jerseys...' : '')}</p>${loading && html`<div class="spinner small"></div>`}</div>`;
}

// the head of a team tab: the team's code, the title, a Not applied mark
function TabHead({ view, title, dirty, children }) {
  return html`<header class="card-head">
    ${view && html`<${Code} team=${view}/>`}<span class="title">${title}</span>${children}
    ${dirty && html`<span class="aside"><span class="pill">not applied</span></span>`}
  </header>`;
}

// --- Roster: the players ------------------------------------------------------------------------------------
function Players({ s, onPick }) {
  const [sort, setSort] = useState(null);
  const rows = useMemo(() => sorted(s.rows, sort), [s.rows, sort]);
  const body = useRef(null);
  const pickBy = (step) => {
    if (!rows.length) return;
    const at = rows.findIndex((r) => r.who === s.selected && r.tag !== 'left');
    const next = rows[Math.max(0, Math.min(rows.length - 1, at < 0 ? 0 : at + step))];
    if (next) onPick(next.id);
  };
  useEffect(() => {
    const el = body.current && body.current.querySelector('.prow.sel');
    if (el) el.scrollIntoView({ block: 'nearest' });
  }, [s.selected, rows]);
  const head = (c) => {
    const on = sort && sort.key === c.key;
    return html`<button type="button" key=${c.key} class=${cls('th', on && 'on')}
      onClick=${() => setSort(on ? { key: c.key, desc: !sort.desc } : { key: c.key, desc: c.key === 'ovr' || c.key === 'age' })}>
      ${c.title}${on && html`<span class="arrow">${sort.desc ? '▼' : '▲'}</span>`}</button>`;
  };
  const title = s.searching ? `${s.rows.length} found for “${s.query}”` : s.team_name;
  return html`<${Card} title=${title || 'Players'} aside=${s.rows.length ? `${s.rows.length} players` : ''} className="ed-players">
    <div class="ptable" style=${{ '--grid': GRID }}>
      <div class="phead">${COLUMNS.map(head)}</div>
      <div class="pbody scroll" ref=${body} tabindex="0"
        onKeyDown=${(e) => {
          if (!e.altKey && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) { e.preventDefault(); pickBy(e.key === 'ArrowDown' ? 1 : -1); }
        }}>
        ${rows.length === 0 && html`<div class="empty small">${s.searching ? 'Nobody by that name.' : 'No players.'}</div>`}
        ${rows.map((r) => html`<div key=${r.id} class=${cls('prow', r.tag, r.who === s.selected && r.tag !== 'left' && 'sel')}
            onClick=${() => onPick(r.id)}>
            <span>${r.pos}</span><span class="num">${r.num}</span><span class="name">${r.name}</span>
            <span class="num">${r.age}</span><span>${r.nat}</span><span class="num ovr">${r.ovr}</span>
            <span class="note" title=${r.note}>${r.note}</span></div>`)}
      </div>
    </div>
  <//>`;
}

// --- Roster: the player's card -----------------------------------------------------------------------------------
function Picture() {
  const p = useSlice('picture');
  if (!p || (!p.url && !p.caption)) return html`<div class="portrait none"></div>`;
  return html`<div class=${cls('portrait', p.loading && 'loading')}>
    ${p.url ? html`<img key=${p.url.length + ':' + p.token} src=${p.url} alt=""/>` : html`<div class="silhouette"></div>`}
    <div class="caption">${p.caption}</div>
  </div>`;
}

function Field({ k, form, set, card, choices, disabled }) {
  const v = form[k] == null ? '' : form[k];
  if (k === 'pos') {
    return html`<select class="field select" value=${v} disabled=${disabled} onChange=${(e) => set(k, e.target.value)}>
      ${choices.positions.map((p) => html`<option key=${p} value=${p}>${p}</option>`)}</select>`;
  }
  if (k === 'style') {
    const list = choices.styles[kindOf(form.pos)] || [];
    const known = list.some(([n]) => String(n) === String(v));
    return html`<select class="field select" value=${known ? String(v) : ''} disabled=${disabled}
      title="The game shows it next to his rating (Edit Lines, Team Rosters)"
      onChange=${(e) => set(k, e.target.value)}>
      ${!known && html`<option value="">${card.new ? 'Not chosen' : 'Usual for the position'}</option>`}
      ${list.map(([n, label]) => html`<option key=${n} value=${String(n)}>${label}</option>`)}</select>`;
  }
  if (k === 'skin' || k === 'eyes') {
    const list = k === 'skin' ? choices.skins : choices.eyes;
    return html`<select class="field select" value=${String(v)} disabled=${disabled} onChange=${(e) => set(k, e.target.value)}>
      ${v === '' && html`<option value="">Not chosen</option>`}
      ${list.map((n) => html`<option key=${n} value=${String(n)}>${n}</option>`)}</select>`;
  }
  if (k === 'shoots') {
    return html`<${Segmented} className="tiny" value=${v} disabled=${disabled}
      options=${[{ value: 'L', label: 'L' }, { value: 'R', label: 'R' }]} onChange=${(x) => set(k, x)}/>`;
  }
  if (k === 'country') {
    const list = choices.countries.includes(v) || !v ? choices.countries : [v, ...choices.countries];
    return html`<select class="field select" value=${v} disabled=${disabled} onChange=${(e) => set(k, e.target.value)}>
      ${list.map((c) => html`<option key=${c} value=${c}>${c}</option>`)}</select>`;
  }
  if (k === 'team') {
    return html`<select class="field select" value=${String(v)} disabled=${disabled}
      onChange=${(e) => set(k, e.target.value === 'FA' ? 'FA' : Number(e.target.value))}>
      ${(card.teams || choices.teams).map(([value, label]) => html`<option key=${value} value=${String(value)}>${label}</option>`)}</select>`;
  }
  const off = disabled || (k === 'ovr' && !card.new);
  return html`<input class="field" value=${v} disabled=${off} spellcheck="false"
    inputmode=${['num', 'height', 'weight', 'ovr'].includes(k) ? 'numeric' : undefined}
    placeholder=${k === 'birth' ? '2004-11-16' : ''} onInput=${(e) => set(k, e.target.value)}/>`;
}

// the player's card; `extra` goes under its title (the Draft & Pro tab's prospect part), `empty` is said without a card
export function PlayerCard({ s, form, set, setRating, dirty, onApply, extra, empty }) {
  const card = s.card;
  if (!card) {
    return html`<${Card} title="Player" className="ed-card">
      <div class="card-body fill"><div class="empty">${s.loaded ? (empty || 'Pick a player, or make a new one.') : ''}</div></div><//>`;
  }
  const labels = card.new && form.pos === 'G' ? card.goalie_labels : card.labels;
  const busy = s.busy;
  const contract = !card.new && card.contract && card.contract.shown;
  return html`<${Card} title=${card.new ? 'New player' : 'Player'} aside=${dirty ? html`<span class="pill">not applied</span>` : ''}
      className="ed-card">
    <div class="card-body scroll" key=${card.key}
      onKeyDown=${(e) => { if (e.key === 'Enter' && e.target.tagName === 'INPUT') { e.preventDefault(); onApply(); } }}>
      <div class="pc-title">${card.title}</div>
      <div class="pc-note">${card.note}</div>
      ${extra}
      <${Picture}/>
      <div class="row pc-buttons">
        ${contract && html`<${Button} small kind="gold" onClick=${() => call('contract_open', card.who)} disabled=${busy}
          title="Cap hit, years, one-way or two-way, an extension">${card.contract.edited ? 'Contract (edited)...' : 'Contract...'}<//>`}
        <${Button} small onClick=${() => call('editor_photo')} disabled=${busy}>Choose picture...<//>
        ${!card.new && card.equipment && html`<${Button} small onClick=${() => call('equipment_open')} disabled=${busy}
          title="Stick, tape, helmet, visor, gloves, skates, the tucks; for a goalie also the mask (with a picture of your own), pads, blocker and trapper">Equipment...<//>`}
      </div>
      <div class="pc-form">
        ${FIELDS.map(([k, label]) => html`<label key=${k} class="pc-row"><span>${label}</span>
          <${Field} k=${k} form=${form} set=${set} card=${card} choices=${s.choices} disabled=${busy}/></label>`)}
      </div>
      <div class="pc-sub">Face</div>
      ${form.look ? html`<${LookPart} card=${card} form=${form} rows=${s.choices.look_rows} busy=${busy}/>` : html`
      <div class="pc-form">
        ${card.created && html`<div class="face-note"><span class="pc-note">${lookLeft(card, form)}</span>
          <${Button} small onClick=${() => call('look_open', null)} disabled=${busy || !lookRoom(card, form)}
            title="Head shape, skin tone, hair, facial hair, eyebrows, eyes, scars: the game's Create Player">Look...<//></div>`}
        <label class="pc-row"><span>Head</span>
          <input class="field" inputmode="numeric" value=${form.head == null ? '' : form.head} disabled=${busy}
            placeholder=${card.new ? 'generic' : ''} onInput=${(e) => set('head', e.target.value.replace(/[^0-9]/g, ''))}/></label>
        <div class="face-note"><span class="pc-note">${faceNote(card, form)}</span>
          <${Button} small onClick=${() => call('face_open')} disabled=${busy}
            title="Take the face of another player, or pick a generic head">Face of a player...<//></div>
        ${[['skin', 'Skin colour'], ['eyes', 'Eye colour']].map(([k, label]) => html`<label key=${k} class="pc-row"><span>${label}</span>
          <${Field} k=${k} form=${form} set=${set} card=${card} choices=${s.choices} disabled=${busy}/></label>`)}
      </div>`}
      <div class="pc-sub">Ratings <span class="faint">(40-99)</span></div>
      <div class="pc-ratings">
        ${labels.map((a) => html`<label key=${a} class="rt"><span title=${a}>${a}</span>
          <input class="field" inputmode="numeric" maxlength="2" value=${(form.ratings || {})[a] || ''} disabled=${busy}
            onInput=${(e) => setRating(a, e.target.value.replace(/[^0-9]/g, ''))}/></label>`)}
      </div>
    </div>
    <div class="card-foot row">
      <${Button} kind="primary" onClick=${onApply} disabled=${busy}>Apply<//>
      <${Button} onClick=${() => call('editor_undo')} disabled=${busy || !card.undo}>Undo my edit<//>
    </div>
  <//>`;
}

// a created look on the card: its words, Look... to change it, Face of a player... for a generic head instead
function LookPart({ card, form, rows, busy }) {
  const pick = card.look_pick;
  const changed = JSON.stringify(form.look) !== JSON.stringify(card.values.look);
  return html`<div class="pc-form">
    <div class="pc-row"><span>Look</span><span class="look-words">${lookWords(form.look, rows)}</span></div>
    <div class="face-note"><span class="pc-note">${changed ? (pick ? pick.note : 'Created look (press Apply)')
        : card.new ? "The game's Create Player look" : 'His created look'}</span>
      <${Button} small kind="gold" onClick=${() => call('look_open', form.look)} disabled=${busy}
        title="Head shape, skin tone, hair, facial hair, eyebrows, eyes, scars: the game's Create Player">Look...<//>
      <${Button} small onClick=${() => call('face_open')} disabled=${busy}
        title="A generic head or another player's face instead of the created look">Face of a player...<//></div>
  </div>`;
}

// 'Head 5, Skin Tone 8, Short Shaggy, brown hair, ...' (faces.look_words)
function lookWords(look, rows) {
  const word = (key) => {
    const row = (rows || []).find((r) => r.key === key);
    const hit = row && row.choices.find(([n]) => n === look[key]);
    return hit ? hit[1] : '';
  };
  const out = [word('shape'), word('tone'), word('hair')];
  if (look.hair !== 0) out.push(word('hair_colour').toLowerCase() + ' hair');
  if (look.facial_hair !== 9) out.push('facial hair ' + word('facial_hair').toLowerCase() + ' (' + word('facial_hair_colour').toLowerCase() + ')');
  out.push(word('eyes').toLowerCase() + ' eyes');
  return out.filter(Boolean).join(', ');
}

// can this card's player get a created look, and how many are left (the game keeps a few for its own Create Player)
const lookKind = (form) => (form.pos === 'G' ? 'G' : 'S');
const lookRoom = (card, form) => card.looks_left && card.looks_left[lookKind(form)] > 0;
function lookLeft(card, form) {
  if (!lookRoom(card, form)) return 'No created look is left for a ' + (lookKind(form) === 'G' ? 'goalie' : 'skater') + ': the game\'s Create Player places are in use.';
  return 'A generic head. A created look is possible (' + card.looks_left[lookKind(form)] + ' left).';
}

// whose head the card's face is: the window's pick, a typed number, or what Python says of his own
function faceNote(card, form) {
  const pick = card.face_pick;
  if (pick && String(form.head) === pick.head) return pick.note;
  if (String(form.head || '') !== String(card.values.head || '')) return form.head ? 'Head ' + form.head + ' (press Apply)' : '';
  return card.face_note;
}

export function RosterTab({ s }) {
  const { form, dirty, set, setRating } = useCardForm(s);
  if (!s || !s.roster) return null;
  return html`<div class=${cls('tt-roster', s.busy && 'busy')}>
    <div class="tt-bar">
      <${TextField} className="search" value=${s.query} placeholder="Find a player" disabled=${!s.loaded}
        onChange=${(t) => call('editor_search', t)} delay=${220}/>
      <${Button} small onClick=${() => call('editor_new_player')} disabled=${!s.loaded}>New player<//>
      <${Button} small onClick=${() => call('team_open')} disabled=${!s.team_tools.team}
        title="The team's name, city, abbreviation and logo">Team...<//>
    </div>
    <div class="tt-two">
      <${Players} s=${s} onPick=${(id) => call('editor_player', id, cardDraft.current)}/>
      <${PlayerCard} s=${s} form=${form} set=${set} setRating=${setRating} dirty=${dirty} onApply=${() => call('editor_apply', form)}/>
    </div>
  </div>`;
}

// --- the windows that stay windows ---------------------------------------------------------------------------------
function FaceWindow({ m }) {
  const pics = useSlice('face_pics') || {};
  return html`<${Modal} full title="Face of a player" onClose=${() => call('modal_close')}
      buttons=${html`<${Button} onClick=${() => call('modal_close')}>Close<//>`}>
    <p class="small-note">Take another player's face: his head (the hair comes with it), skin and eye colour. Or pick one of
      the game's generic heads: the player keeps his skin and eye colour. The card shows the change; press Apply there. The
      game shows the face in a game.</p>
    <div class="face-main">
      <div class="face-side">
        <div class="t">Another player's face</div>
        <${TextField} className="search face-search" value=${m.query} placeholder="Find a player" delay=${220}
          onChange=${(t) => call('face_search', t)}/>
        <div class="list face-list">
          ${m.query && m.found.length === 0 && html`<div class="empty small">Nobody by that name.</div>`}
          ${m.found.map((p) => html`<button type="button" key=${p.who} class="edit-row face-pick"
              onClick=${() => call('face_pick_player', p.who)}>
            <span class="n">${p.name}</span><span class="w">${p.pos} · ${p.team}</span>
            <span class="faint">${p.face} ${p.head}</span></button>`)}
        </div>
      </div>
      <div class="face-side">
        <div class="t">A generic head</div>
        ${m.note && html`<div class="small-note">${m.note}</div>`}
        ${m.pics === 'none'
          ? html`<label class="pc-row face-generic"><span>Generic head</span>
              <select class="field select" value="" onChange=${(e) => { if (e.target.value) call('face_pick_generic', Number(e.target.value)); }}>
                <option value="">Pick a number...</option>
                ${m.generic.map((h) => html`<option key=${h} value=${String(h)}>${h}</option>`)}</select></label>`
          : html`<${FaceHeads} m=${m} pics=${pics}/>`}
      </div>
    </div>
  <//>`;
}

// the generic heads as the game's own pictures (a number alone where the game has none); the card's head in view
function FaceHeads({ m, pics }) {
  const box = useRef(null);
  useEffect(() => {
    const el = box.current && box.current.querySelector('.face-head.on');
    if (el) box.current.scrollTop = Math.max(0, el.offsetTop - 4);
  }, [m.current, m.pics]);
  return html`<div class="face-heads" ref=${box}>${m.generic.map((h) => {
    const url = pics[String(h)];
    return html`<button type="button" key=${h} class=${cls('face-head', h === m.current && 'on')}
        title=${'Generic head ' + h} onClick=${() => call('face_pick_generic', h)}>
      <span class="pic">${url ? html`<img src=${url} alt=""/>` : m.pics === 'ready' ? 'no picture' : ''}</span>
      <span>${h}</span></button>`;
  })}</div>`;
}

function TeamWindow({ m }) {
  const [fields, setFields] = useState(m.fields);
  return html`<${Modal} title=${m.name} onClose=${() => call('modal_close')} buttons=${html`
      <${Button} kind="pick" onClick=${() => call('team_apply', fields)}>Apply<//>
      <${Button} onClick=${() => call('team_undo')} disabled=${!m.mine}>Undo team edit<//>
      <${Button} onClick=${() => call('modal_close')}>Close<//>`}>
    <p class="small-note">The logo goes into the game when you press Save. The game's menus show these names after an update with "Team names" on.</p>
    <div class="tw-form">
      ${[['full', 'Full name'], ['city', 'City'], ['abbr', 'Abbreviation']].map(([k, label]) => html`
        <label key=${k} class="pc-row"><span>${label}</span>
          <input class="field" value=${fields[k] || ''} spellcheck="false"
            onInput=${(e) => setFields({ ...fields, [k]: e.target.value })}/></label>`)}
    </div>
    <div class="tw-logo">
      <div class="logo-box">${m.logo ? html`<img src=${m.logo} alt=""/>` : html`<span class="faint">${m.logo_text || 'the game’s logo'}</span>`}</div>
      <${Button} small onClick=${() => call('team_logo')}>Choose logo...<//>
    </div>
  <//>`;
}

function EditsWindow({ m }) {
  return html`<${Modal} title="My edits" onClose=${() => call('modal_close')}
      buttons=${html`<${Button} kind="pick" onClick=${() => call('modal_close')}>Close<//>`}>
    <p class="small-note">Kept on this PC and applied after every update (the Update tab's My edits switch). Removing one
      stops that; a roster that was saved with it keeps it.</p>
    <div class="list edits-list">
      ${m.items.length === 0 && html`<div class="empty small">No edits yet.</div>`}
      ${m.items.map((it) => html`<div key=${it.kind + it.key} class="edit-row">
          <span class=${cls('chip', it.kind === 'team' ? 'made' : 'muted')}>${it.kind === 'team' ? 'Team' : 'Player'}</span>
          <span class="n">${it.name}</span><span class="w">${it.what}</span>
          <${Button} small kind="danger-quiet" onClick=${() => call('edits_remove', it.kind, it.key)}>Remove<//></div>`)}
    </div>
  <//>`;
}

// the model pictures of one choice: the one in use is brought into view when the window opens
function EqGrid({ r, pics, loaded }) {
  const box = useRef(null);
  useEffect(() => {
    const el = box.current && box.current.querySelector('.eq-opt.on');
    if (el) box.current.scrollTop = Math.max(0, el.offsetTop - 4);
  }, [r.choice, loaded]);
  return html`<div class="eq-grid scroll" ref=${box}>${r.items.map((it) => html`<button type="button" key=${it.value}
      class=${cls('eq-opt', it.value === r.value && 'on')} title=${r.label + ' ' + it.value}
      onClick=${() => call('equipment_pick', r.choice, it.value)}>
      ${(pics[r.choice] || {})[String(it.value)] ? html`<img src=${pics[r.choice][String(it.value)]} alt=""/>` : ''}
      <span>${it.value}</span></button>`)}</div>`;
}

function EquipmentWindow({ q }) {
  const pics = useSlice('equip_pics') || {};
  return html`<${Modal} full title=${q.title} onClose=${() => call('equipment_close')} buttons=${html`
      <${Button} kind="pick" onClick=${() => call('equipment_apply', false)} disabled=${!q.can_player}>Apply to this player<//>
      <${Button} onClick=${() => call('equipment_apply', true)} disabled=${!q.can_team}
        title="Tape, helmet, visor and the tucks, for every skater of the team without a choice of his own">
        Apply to the whole team${q.team ? ' (' + q.team + ')' : ''}<//>
      <${Button} onClick=${() => call('equipment_undo')} disabled=${!q.undo}>Take back my equipment edits<//>
      <${Button} onClick=${() => call('equipment_close')}>Close<//>`}>
    <p class="small-note">Pick what the player uses. The game shows it in a new roster, or after "Save to this roster". The
      pictures are the game's own; a stick or helmet of 2026 is the nearest model the game has. Tape, helmet, visor and the tucks
      can also be set for a whole team: "Apply to the whole team" writes every skater of the team who has no choice of his own.
      Real sock tucks, pants and tape of NHL players, and neck guards of goalies, come from the program's data with every update;
      what you pick here always wins over them.</p>
    ${q.note && html`<div class="note warn">${q.note}</div>`}
    ${q.goalie && html`<div class="eq-row mask-pic">
      <div class="t">Own picture on the mask${q.mask_picture ? html` <span class="pill">changed</span>` : ''}</div>
      <div class="row">
        <${Button} small onClick=${() => call('equipment_mask_picture')}>My picture...<//>
        <${Button} small onClick=${() => call('equipment_mask_template')}>Save the mask layout to paint on<//>
        <${Button} small onClick=${() => call('equipment_mask_clear')} disabled=${!q.mask_picture}>Game's own mask<//>
      </div>
      <p class="small-note">${q.mask_picture ? 'Picture: ' + q.mask_picture : 'No picture of your own: the goalie wears the mask picked below.'}${' '}
        Keep it 512 x 512. The goalie gets a mask number nobody wears, so no other goalie changes. Shown in the game after
        "Photos and logos" is run.</p>
    </div>`}
    <div class="list eq-rows">
      ${q.rows.map((r) => html`<div key=${r.choice} class=${cls('eq-row', r.touched && 'touched')}>
          <div class="t">${r.label}${r.touched ? html` <span class="pill">changed</span>` : ''}</div>
          ${r.kind === 'buttons'
            ? html`<div class="eq-buttons">${r.items.map((it) => html`<button type="button" key=${it.value}
                class=${cls('eq-opt', it.value === r.value && 'on')}
                onClick=${() => call('equipment_pick', r.choice, it.value)}>
                ${r.picture && pics[r.choice] && pics[r.choice][String(it.value)]
                  ? html`<img src=${pics[r.choice][String(it.value)]} alt=""/>` : ''}<span>${it.label}</span></button>`)}</div>`
            : html`<${EqGrid} r=${r} pics=${pics} loaded=${q.loaded}/>`}
        </div>`)}
      ${!q.loaded && html`<div class="empty small">Reading the game's pictures...</div>`}
    </div>
  <//>`;
}

// the game's Create Player look: every part with the game's words, its own pictures from the player's disc
function LookWindow({ m }) {
  const pics = useSlice('look_pics') || {};
  return html`<${Modal} full title="Look" onClose=${() => call('modal_close')} buttons=${html`
      <${Button} kind="pick" onClick=${() => call('look_done')}>Use this look<//>
      <${Button} onClick=${() => call('look_random')}>Random<//>
      <${Button} onClick=${() => call('modal_close')}>Close<//>`}>
    <p class="small-note">The parts of the game's Create Player, with its own words. The card shows the look; press Apply
      there. The game shows the face in a game and on the player's card (Edit Players).</p>
    ${m.note && html`<div class="note">${m.note}</div>`}
    <div class="look-now">${m.words}</div>
    <div class="list eq-rows look-rows">
      ${m.rows.map((r) => {
        const own = r.pictures && m.pics !== 'none' ? pics[r.key] || {} : null;
        return html`<div key=${r.key} class=${cls('eq-row', 'look-' + r.key)}>
          <div class="t">${r.label}</div>
          <div class="eq-buttons">${r.choices.map(([n, word]) => {
            const url = own && own[String(n)];
            return html`<button type="button" key=${n} class=${cls('eq-opt', n === m.look[r.key] && 'on', url && 'pic')}
                title=${word} onClick=${() => call('look_set', r.key, n)}>
              ${url ? html`<img src=${url} alt=""/>` : own && m.pics === 'loading' ? html`<span class="pic-wait"></span>` : ''}
              <span>${r.key === 'shape' ? n : r.key === 'tone' ? n : word}</span></button>`;
          })}</div>
        </div>`;
      })}
    </div>
  <//>`;
}

// the windows, drawn once over every tab
export function EditorModals({ s }) {
  const equipment = useSlice('equipment');
  const m = s && s.modal;
  return html`<${Fragment}>
    ${m && m.kind === 'team' && html`<${TeamWindow} key=${'team' + m.slot} m=${m}/>`}
    ${m && m.kind === 'edits' && html`<${EditsWindow} m=${m}/>`}
    ${m && m.kind === 'face' && html`<${FaceWindow} m=${m}/>`}
    ${m && m.kind === 'look' && html`<${LookWindow} m=${m}/>`}
    ${equipment && html`<${EquipmentWindow} key=${'q' + equipment.who} q=${equipment}/>`}<//>`;
}

// --- Jerseys & ice (app/uniforms.py; a custom team's look: app/teamkit.py) ---------------------------------------------
function Thumb({ url, loading, size = 78 }) {
  return html`<div class=${cls('thumb-box', !url && 'none')} style=${{ width: size + 'px', height: size + 'px' }}>
    ${url ? html`<img src=${url} alt=""/>` : html`<span>${loading ? '' : 'no picture'}</span>`}</div>`;
}

function Colour({ part, label, c }) {
  return html`<label class="pc-row colour"><span>${label}</span>
    <${TextField} value=${c.text} onChange=${(t) => call('uniforms_colour', part, t)}/>
    <span class="swatch" style=${{ background: c.hex }}>
      <input type="color" value=${c.hex} onChange=${(e) => call('uniforms_colour', part, e.target.value)}/></span>
  </label>`;
}

function UniformsBody({ u }) {
  const thumbs = useSlice('thumbs') || {};
  return html`
    <p class="small-note">Pick how each jersey version is made. The game shows the change after an update with "Photos, logos
      and team names" on; the Restore button of that row on the Update tab puts the game's own back. A jersey made from colours uses the
      team's logo as its crest. The two colours and the arena name below are saved into the roster too (Save, or the next update): the
      game's menus, sticks and gear use them. Only a jersey set to "From the colours" follows the colours.</p>
    ${u.note && html`<div class="note warn">${u.note}</div>`}
    ${u.shared && html`<div class="note">${u.shared}</div>`}
    ${u.pack_note && html`<div class="note gold">${u.pack_note}</div>`}
    ${u.colours_used && html`<div class="uw-colours">
      <${Colour} part="primary" label="Main colour" c=${u.colours.primary}/>
      <${Colour} part="secondary" label="Second colour" c=${u.colours.secondary}/>
      <div class="row crest"><span class="small-note">${u.crest}</span>
        <${Button} small onClick=${() => call('uniforms_crest', true)}>Crest picture...<//>
        <${Button} small onClick=${() => call('uniforms_crest', false)} disabled=${!u.crest_mine}>Team logo<//></div>
    </div>`}
    ${!u.loaded && html`<div class="empty small">Reading the game's jerseys...</div>`}
    <div class="list uw-rows">
      ${u.rows.map((r) => html`<div key=${r.variant} class="uw-row">
          <${Thumb} url=${thumbs[String(r.variant)]} loading=${u.pictures}/>
          <div class="main"><div class="t">${r.label}</div>
            <${Segmented} value=${r.mode} options=${r.options.map(([value, label]) => ({ value, label }))}
              onChange=${(x) => call('uniforms_pick', r.variant, x)}/>
            ${r.legs && html`<div class="small-note">${r.legs}</div>`}</div>
          <div class="uw-tpl">
            ${r.templates.includes('pack') && html`<${Button} small onClick=${() => call('uniforms_template', r.variant, 'pack')}
              title="This season's jersey as a picture to paint on">This season's template...<//>`}
            <${Button} small onClick=${() => call('uniforms_template', r.variant, 'game')} disabled=${!u.pictures}
              title="The game's own jersey as a picture to paint on">${r.templates.includes('pack') ? "Game's template..." : 'Save a template...'}<//>
          </div>
        </div>`)}
      ${u.loaded && html`<div class="uw-sub">Centre-ice logo</div>
        <div class="uw-row">
          <${Thumb} url=${thumbs.ice} loading=${u.pictures}/>
          <div class="main">
            <${Segmented} value=${u.ice.mode} options=${u.ice.options.map(([value, label]) => ({ value, label }))}
              onChange=${(x) => call('uniforms_ice', x)}/>
            ${u.ice.locked ? html`<div class="small-note">${u.ice.why}</div>` : u.ice.group ? html`
            <div class="small-note">${u.ice.group}</div>
            <div class="small-note faint">A picture of your own: 1024 x 1024 with a clear background; the strip in the middle,
              where the red line crosses, is made clear by the program.</div>` : html`
            <label class="pc-row arena"><span>Arena name on the ice</span>
              <${TextField} value=${u.ice.arena} onChange=${(t) => call('uniforms_arena', t)} delay=${400}/></label>
            <div class="small-note faint">This is the arena's name in the game's menus and intros; the centre-ice logo shows it
              round the ring when it is made from the logo.</div>
            <div class="small-note faint">A picture of your own: 1024 x 1024 with a clear background; the strip in the middle,
              where the red line crosses, is made clear by the program.</div>`}
          </div>
          <${Button} small onClick=${() => call('uniforms_template', 'ice')} disabled=${!u.pictures}>Save a template...<//>
        </div>`}
    </div>`;
}

function PicGrid({ items, value, pics, kind, onPick, logo }) {
  const box = useRef(null);
  useEffect(() => {
    const el = box.current && box.current.querySelector('.eq-opt.on');
    if (el) box.current.scrollTop = Math.max(0, el.offsetTop - 4);
  }, [value, Object.keys(pics).length > 0]);
  return html`<div class=${cls('eq-grid scroll', logo && 'ct-logos')} ref=${box}>${items.map((n) => {
    const url = pics[kind + ':' + n];
    return html`<button type="button" key=${n} class=${cls('eq-opt', String(n) === String(value) && 'on')}
      title=${(logo ? 'Logo ' : 'Design ') + n} onClick=${() => onPick(n)}>
      ${url ? html`<img src=${url} alt=""/>` : ''}<span>${n}</span></button>`;
  })}</div>`;
}

function CustomKitBody({ u }) {
  const pics = useSlice('thumbs') || {};
  const kit = (action, ...args) => call('uniforms_kit', action, ...args);
  return html`
    <p class="small-note">The game draws this team like a team made in Create a Team: pick its crest, its jerseys and its
      colours. The pictures are the game's own; in the game they are painted in the colours below. The centre ice at its home
      games shows the crest. The game shows the change after an update with My edits on (a crest picture also needs "Photos,
      logos and team names").</p>
    ${u.note && html`<div class="note warn">${u.note}</div>`}
    ${!u.loaded && html`<div class="empty small">Reading the game's Create a Team pictures...</div>`}
    <div class="list eq-rows">
      <div class="eq-row">
        <div class="t">Crest</div>
        <div class="row ct-crest"><span class="small-note">${u.crest.text}</span>
          ${u.crest.own && html`<${Button} small onClick=${() => kit('logo', 'own')}
            disabled=${u.crest.value === 'own'}>The team's own crest<//>`}
          <${Button} small onClick=${() => call('uniforms_kit_picture')}>My picture...<//></div>
        <${PicGrid} items=${u.crest.logos} value=${u.crest.value} pics=${pics} kind="logo" logo
          onPick=${(n) => kit('logo', n)}/>
      </div>
      ${u.designs.map((d) => html`<div key=${d.part} class="eq-row">
        <div class="t">${d.label}</div>
        <${PicGrid} items=${d.items} value=${d.value} pics=${pics} kind=${d.kind}
          onPick=${(n) => kit('design', d.part, n)}/>
      </div>`)}
      <div class="eq-row">
        <div class="t">Team colours</div>
        <div class="uw-colours ct-team">
          ${u.team.map((c) => html`<label key=${c.i} class="pc-row colour"><span>${c.label}</span>
            <${TextField} value=${c.text} onChange=${(t) => kit('colour', c.i, t)}/>
            <span class="swatch" style=${{ background: c.hex }}>
              <input type="color" value=${c.hex} onChange=${(e) => kit('colour', c.i, e.target.value)}/></span>
          </label>`)}
        </div>
        <div class="row"><${Button} small kind="pick" onClick=${() => kit('paint')}>Paint everything with these colours<//>
          <span class="small-note faint">Home in the main colour, away on white. The pieces set one by one below start again.
            A typed colour leaves Coachella Valley's and Henderson's hand-made jerseys alone; this button paints them too.</span></div>
      </div>
      <div class="eq-row">
        <div class="t">Arena</div>
        <label class="pc-row arena"><span>Arena name on the ice</span>
          <${TextField} value=${u.arena} onChange=${(t) => call('uniforms_arena', t)} delay=${400}/></label>
        <div class="small-note faint">The arena's name in the game's menus and intros. A team that shares its arena with another
          team renames it for both. The centre ice at home games shows the crest.</div>
      </div>
      <div class="eq-row">
        <div class="t">Colours in detail</div>
        <${Segmented} value=${u.side} options=${[{ value: 1, label: 'Home' }, { value: 2, label: 'Away' }]}
          onChange=${(x) => kit('side', x)}/>
        <div class="ct-pieces">
          ${u.pieces.map((p) => html`<div key=${p.piece} class=${cls('ct-piece', p.touched && 'touched')}>
            <div class="ct-name">${p.label}${p.touched ? html` <span class="pill">changed</span>` : ''}</div>
            <div class="ct-zones">${p.zones.map((z) => html`<label key=${z.zone} class="ct-zone" title=${z.label}>
              <span class=${cls('swatch', p.locked && 'locked')} style=${{ background: z.hex }}>
                ${!p.locked && html`<input type="color" value=${z.hex}
                  onChange=${(e) => kit('zone', p.piece, z.zone, e.target.value)}/>`}</span>
              <span class="zl">${z.label}</span></label>`)}</div>
            ${p.locked ? html`<span class="small-note faint">From the crest picture</span>`
              : p.touched && html`<${Button} small onClick=${() => kit('reset', p.piece)}>Back<//>`}
          </div>`)}
        </div>
      </div>
    </div>`;
}

export function JerseysTab({ u }) {
  if (!u) return null;
  if (u.slot == null) return html`<${Why} s=${u} loading=${u.loading}/>`;
  const custom = u.kind === 'custom';
  return html`<section class=${cls('card grow tt-tab', custom ? 'kit-tab' : 'jerseys-tab')}>
    <${TabHead} view=${u.view} title=${u.title} dirty=${u.dirty}/>
    <div class="card-body tt-body scroll">${custom ? html`<${CustomKitBody} key=${'k' + u.slot} u=${u}/>`
      : html`<${UniformsBody} key=${'u' + u.slot} u=${u}/>`}</div>
    <div class="card-foot tt-foot">
      <${Button} kind="primary" onClick=${() => call('uniforms_apply')} disabled=${!u.dirty}>Apply<//>
      <${Button} onClick=${() => call('uniforms_undo')}
        title="This team's jerseys and ice as the update makes them">Undo all for this team<//>
      <span class="small-note faint">Kept in My edits. The pictures go into the game with the next update (RPCS3 closed).</span>
    </div>
  </section>`;
}

// --- Lines: click a place, then a player (app/lines.py) ----------------------------------------------------
function LnPlayer({ p }) {
  return p ? html`<span class="ln-who"><b>${p.name}</b><span class="faint">${p.pos} · ${p.ovr ?? '-'}${p.pos !== 'G' && p.shoots ? ' · shoots ' + p.shoots : ''}</span></span>`
    : html`<span class="faint">empty</span>`;
}

export function LinesTab({ n }) {
  if (!n) return null;
  if (!n.units) return html`<${Why} s=${n}/>`;
  const letters = n.tab === 'letters';
  return html`<section class="card grow tt-tab lines-tab">
    <${TabHead} view=${n.view} title=${n.title} dirty=${n.touched}>
      <${Segmented} options=${n.tabs.map((t) => ({ value: t.id, label: t.label }))} value=${n.tab}
        onChange=${(v) => call('lines_tab', v)}/>
    <//>
    <div class="card-body fill tt-body">
      <p class="small-note">${letters ? n.letters_rule : n.note}</p>
      <div class="ln-main">
        ${letters
          ? html`<div class="list ln-letters scroll">${n.players.filter((p) => p.pos !== 'G').map((p) => html`
              <div key=${p.who} class=${cls('ln-row', !p.dressed && 'scratch')}>
                <${LnPlayer} p=${p}/><span class="faint">${p.dressed ? '' : 'scratched'}</span>
                <${Segmented} options=${[{ value: 'C', label: 'C' }, { value: 'A', label: 'A' }, { value: '', label: 'none' }]}
                  value=${p.letter || ''} onChange=${(v) => call('lines_letter', p.who, v || null)}/>
              </div>`)}</div>`
          : html`<div class="ln-units scroll">${n.units.map((u) => html`<div key=${u.title} class="ln-unit">
                <div class="t">${u.title}</div>
                <div class="ln-slots">${u.slots.map((sl) => html`<button type="button" key=${sl.slot} title=${sl.full}
                    class=${cls('ln-slot', sl.picked && 'on')} onClick=${() => call('lines_slot', sl.slot)}>
                    <span class="k">${sl.label}</span><${LnPlayer} p=${sl.player}/></button>`)}</div>
              </div>`)}</div>
            <div class="ln-side">
              <div class="t">${n.picked_label ? 'Who plays ' + n.picked_label + '?' : 'Players (click a place first)'}</div>
              <div class="list scroll">${n.players.map((p) => html`<button type="button" key=${p.who}
                  class=${cls('ln-row', !p.dressed && 'scratch', !p.fits && 'off')} disabled=${!n.picked || !p.fits}
                  onClick=${() => call('lines_place', p.who)}>
                  <${LnPlayer} p=${p}/>${p.letter ? html`<span class="ln-letter">${p.letter}</span>` : ''}
                  <span class="faint w">${p.where || (p.dressed ? '' : 'scratched')}</span></button>`)}</div>
            </div>`}
      </div>
      ${n.carry && html`<div class="note ln-carry"><${Button} onClick=${() => call('lines_carry')}>${n.carry}<//></div>`}
      ${n.problems.length > 0 && html`<div class="note warn ln-problems">${n.problems.slice(0, 4).map((t) => html`<div key=${t}>${t}</div>`)}
        ${n.problems.length > 4 ? html`<div>... and ${n.problems.length - 4} more</div>` : ''}</div>`}
    </div>
    <div class="card-foot tt-foot">
      <${Button} kind="primary" onClick=${() => call('lines_apply')} disabled=${!n.can_apply}>Apply<//>
      <${Button} onClick=${() => call('lines_undo')} disabled=${!n.mine && !n.touched}
        title="The next update gives the team its lines again">Take back my lines<//>
      ${n.mine && html`<span class="small-note faint">This team plays your lines.</span>`}
    </div>
  </section>`;
}

// --- Strategy (app/strategy.py) ----------------------------------------------------------------------------
export function StrategyTab({ g }) {
  if (!g) return null;
  if (!g.sections) return html`<${Why} s=${g}/>`;
  return html`<section class="card grow tt-tab strategy-tab">
    <${TabHead} view=${g.view} title=${g.title} dirty=${g.can_apply}/>
    <div class="card-body tt-body scroll">
      <p class="small-note">${g.note}</p>
      <div class="st-grid">${g.sections.map((sec) => html`<div key=${sec.title} class="st-sec">
          <div class="uw-sub">${sec.title}</div>
          ${sec.rows.map((r) => html`<div key=${r.field} class=${cls('st-row', r.changed && 'touched', r.hidden && 'hidden')}>
              <div class="t">${r.label}${r.hidden ? html` <span class="faint">(not in the game's menu)</span>` : ''}${r.changed ? html` <span class="pill">changed</span>` : ''}</div>
              ${r.kind === 'choice'
                ? html`<div class="eq-buttons">${r.options.map((o) => html`<button type="button" key=${o.value}
                    class=${cls('eq-opt', o.value === r.value && 'on')} onClick=${() => call('strategy_set', r.field, o.value)}>
                    <span>${o.label}</span></button>`)}</div>`
                : html`<div class="st-slider"><span class="l">${r.left}</span>
                    <input type="range" min="0" max=${r.top} step="1" value=${r.value}
                      onInput=${(e) => call('strategy_set', r.field, Number(e.target.value))}/>
                    <span class="r">${r.right}</span><b class="v">${r.value}</b></div>`}
            </div>`)}
        </div>`)}</div>
    </div>
    <div class="card-foot tt-foot">
      <${Button} kind="primary" onClick=${() => call('strategy_apply')} disabled=${!g.can_apply}>Apply<//>
      <${Button} onClick=${() => call('strategy_reset')} disabled=${!g.can_apply}>Back to the roster's<//>
      <${Button} onClick=${() => call('strategy_undo')} disabled=${!g.mine}>Take back my strategies<//>
    </div>
  </section>`;
}

// --- the Save bar under the team tabs (not the Calendar) -------------------------------------------------------------
export function SaveBar({ s }) {
  if (!s || !s.roster) return null;
  if (s.save.file) return html`<div class="savebar card">
    <${Button} kind=${s.edits_count ? 'gold-line' : 'ghost'} onClick=${() => call('edits_open')}>My edits (${s.edits_count})<//>
    <span class="sb-roster ambertext" style=${{ whiteSpace: 'normal' }} title=${s.roster.folder}>${s.save.file}</span>
  </div>`;
  return html`<div class="savebar card">
    <${Button} kind=${s.edits_count ? 'gold-line' : 'ghost'} onClick=${() => call('edits_open')}>My edits (${s.edits_count})<//>
    <span class=${cls('sb-roster', s.unsaved ? 'ambertext' : 'faint')} title=${s.roster.name}>
      ${s.unsaved ? `${s.unsaved} not saved yet` : 'Everything saved'} · ${s.roster.name}</span>
    <span class="sp"></span>
    <${Segmented} options=${SAVE_MODES} value=${s.save.mode} disabled=${!s.save.mode_enabled}
      onChange=${(v) => call('editor_save_mode', v)}/>
    <${TextField} className="name" value=${s.save.name} disabled=${s.busy} onChange=${(t) => call('editor_name', t)}/>
    <${Button} kind="primary" className="go" disabled=${!s.save.button.enabled} onClick=${saveRoster}
      title="Ctrl+S">${s.save.button.text}<//>
    <span class="keycap" title="Ctrl+S saves">Ctrl+S</span>
  </div>`;
}
