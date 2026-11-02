// The Setup, Update and Game patch tabs: where RPCS3 is, which roster (Setup); what to update and how to save (Update);
// the RPCS3 game patch (Game patch). All three show the Update controller's state (app/update.py).
import { html, cls, useEffect, useRef, useState } from './lib.js';
import { Button, Toggle, Checkbox, Segmented, Card, PathText, RegionTag, Flag, TextField, Info } from './ui.js';
import { call } from './bridge.js';
import { DiscordButton, KofiButton } from './shell.js';

const goTo = (tab) => window.dispatchEvent(new CustomEvent('lr-tab', { detail: tab }));

// --- Setup ------------------------------------------------------------------------------------------------
function RpcsCard({ r, exp, busy }) {
  const note = r.note;
  return html`<${Card} n="1" title="Where is your game?" aside=${r.kind || ''} style=${{ '--i': 0 }}>
    <div class="card-body">
      <div class="row">
        <${PathText} path=${r.path} unset="Not set yet"/>
        <${Button} kind=${r.path ? 'ghost' : 'primary'} disabled=${!r.enabled} onClick=${() => call('pick_rpcs3')}>
          ${r.path ? 'Change' : r.find_label}</${Button}>
      </div>
      ${r.other && html`<div class="row" style=${{ marginTop: '8px' }}>
        <${Button} small disabled=${!r.enabled} onClick=${() => call('switch_host')}>Switch to ${r.other}</${Button}>
      </div>`}
      ${note && html`<div class=${cls('note', note.tone)}>${note.text}</div>`}
      ${r.native && html`<div class="note info">${r.native}</div>`}
      ${r.warnings.map((w) => html`<div key=${w} class="note amber">${w}</div>`)}
      ${r.needs_game && html`<div class="row" style=${{ marginTop: '10px' }}>
        <${Button} kind="primary" disabled=${busy} onClick=${() => call('pick_game', false)}>Pick the game (.iso)...</${Button}>
        <${Button} disabled=${busy} onClick=${() => call('pick_game', true)}>or its folder...</${Button}>
      </div>`}
      ${exp.on && exp.game && html`<div class="note muted">${exp.game}</div>`}
      <${Checkbox} on=${exp.on} disabled=${busy} onChange=${(v) => call('set_export_only', v)}>Export files to a folder</${Checkbox}>
      ${exp.on && html`<div class="small-note">The files are made into a new folder and nothing in RPCS3 is changed.
        A short text in the folder says where each part goes.</div>`}
    </div>
  </${Card}>`;
}

function DownloadsCard({ items }) {
  return html`<${Card} title="Downloads" aside="kept on this PC" style=${{ '--i': 1 }}>
    <div class="card-body"><div class="list">
      ${items.map((d) => html`<div key=${d.title} class="step dl"><div class="main">
        <div class="title">${d.title}</div>
        <div class=${cls('sub', d.tone === 'good' && 'goodtext', d.tone === 'amber' && 'ambertext')}>${d.text}</div>
        ${d.bar != null && html`<div class="bar"><span style=${{ width: `${Math.round(d.bar * 100)}%` }}></span></div>`}
      </div></div>`)}
    </div></div>
  </${Card}>`;
}

function ProgramCard({ s, version }) {
  return html`<${Card} title="This program" aside=${version ? `version ${version}` : ''} style=${{ '--i': 2 }}>
    <div class="card-body">
      <div class="row wrap">
        <${Checkbox} on=${s.check_updates} onChange=${(v) => call('set_check_updates', v)}>Look for a newer version when this program starts</${Checkbox}>
        <${Button} small disabled=${s.busy} onClick=${() => call('check_updates_now')}>Check for updates now</${Button}>
      </div>
    </div>
  </${Card}>`;
}

function RosterRow({ r, isNew }) {
  const usable = r.usable;
  return html`<div class=${cls('roster', r.selected && 'sel', !usable && 'off', isNew && 'appear')}
      role="radio" aria-checked=${r.selected} tabindex=${usable ? 0 : -1}
      onClick=${() => usable && call('select_roster', r.folder)}
      onKeyDown=${(e) => { if (usable && (e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); e.stopPropagation(); call('select_roster', r.folder); } }}>
    <span class="dot"></span>
    <div class="main">
      <div class="name"><span class="n">${r.name}</span>${r.tag && html`<span class="chip patch">${r.tag}</span>`}${r.chip && html`<span class=${cls('chip', r.chip.kind)}>${r.chip.text}</span>`}</div>
      <div class="meta"><${RegionTag} region=${r.region}/><span class="t">${r.meta}</span></div>
      ${r.problem && html`<div class="problem">${r.problem}</div>`}
      ${r.misfit && html`<div class="problem">${r.misfit}</div>`}
    </div>
    ${r.actions && html`<div class="acts" onClick=${(e) => e.stopPropagation()}>
      <${Button} small onClick=${() => call('open_roster_folder', r.folder)}>Open folder</${Button}>
      <${Button} small kind="danger" disabled=${!r.delete_enabled} onClick=${() => call('ask_delete', r.folder)}>Delete</${Button}>
    </div>`}
  </div>`;
}

function RosterCard({ s }) {
  const seen = useRef(null);
  const list = useRef(null);
  const folders = s.rosters.map((r) => r.folder);
  // rows that are new since the last look slide in; the first fill does not animate row by row
  const fresh = seen.current ? new Set(folders.filter((f) => !seen.current.has(f))) : new Set();
  useEffect(() => { seen.current = new Set(folders); });
  useEffect(() => {
    const el = list.current && list.current.querySelector('.roster.sel');
    if (el) el.scrollIntoView({ block: 'nearest' });
  }, [s.selected, folders.join('|')]);
  const exp = s.export;
  return html`<${Card} n="2" title="Which roster do you work on?" grow className="rosters" style=${{ '--i': 3 }}>
    <div class="card-body fill">
      ${exp.on && html`<div class="export-src">
          <div class=${cls('note', exp.tone)} style=${{ marginTop: 0, marginBottom: '8px' }}>${exp.text}</div>
          <${Button} small kind=${exp.from_file ? 'primary' : 'ghost'} disabled=${s.busy} onClick=${() => call('pick_export_file')}>Or pick a roster file (SYS-DATA)...</${Button}>
        </div>`}
      ${html`
        <div class="small-note roster-use">${exp.on ? 'The export starts from the roster you pick here, or from the roster file.'
          : 'The Update tab, the team tabs and their Save all use this roster.'}</div>
        ${s.room && html`<div class=${cls('room', s.room.tone)}>
          ${s.room.counts.map((c) => html`<span key=${c.region} class=${cls('count', c.tone)}
              title=${s.room.tip}><${Flag} region=${c.region}/>${c.text}</span>`)}
          ${s.room.text && html`<span class="text">${s.room.text}</span>`}</div>`}
        ${s.fresh.length > 0 && html`<div class="fresh">Start fresh:
          ${s.fresh.map((f) => html`<${Button} small key=${f.folder} disabled=${s.busy}
              onClick=${() => call('select_roster', f.folder)}><${Flag} region=${f.region}/>${f.label}</${Button}>`)}</div>`}
        ${s.rosters.length ? html`<div class="scroll" ref=${list}><div class="list" role="radiogroup">
            ${s.rosters.map((r) => html`<${RosterRow} key=${r.folder} r=${r} isNew=${fresh.has(r.folder)}/>`)}
          </div></div>` : html`<div class="empty">${s.empty}</div>`}`}
    </div>
  </${Card}>`;
}

export function SetupTab({ s, version }) {
  if (!s) return null;
  return html`<div class="columns">
    <div class="col">
      <div class="linkrow"><${DiscordButton}/><${KofiButton}/></div>
      <${RpcsCard} r=${s.rpcs3} exp=${s.export} busy=${s.busy}/>
      ${s.downloads && html`<${DownloadsCard} items=${s.downloads}/>`}
      <${ProgramCard} s=${s} version=${version}/>
    </div>
    <div class="col">
      <${RosterCard} s=${s}/>
    </div>
  </div>`;
}

// --- Update -------------------------------------------------------------------------------------------------
function FromBar({ s }) {
  const r = s.rosters.find((x) => x.selected);
  const exp = s.export;
  return html`<div class="upd-from card">
    ${exp.on ? html`<span class="faint">Exporting files from</span><span class=${cls('t', exp.tone)}>${exp.text}</span>`
      : r ? html`<span class="faint">Updating</span><b class="n">${r.name}</b><${RegionTag} region=${r.region}/>
          ${r.tag && html`<span class="chip patch">${r.tag}</span>`}
          ${r.misfit && html`<span class="chip hidden" title=${r.misfit}>Not loadable now: update it</span>`}
          <span class="faint t">${r.meta}</span>`
        : html`<span class="faint">No roster picked yet.</span>`}
    <span class="sp"></span>
    <a onClick=${() => goTo('setup')}>${r || exp.on ? 'Change it in Setup' : 'Pick one in Setup'}</a>
  </div>`;
}

function StepRow({ row }) {
  // a group row (Photos and logos) has an arrow that opens its parts; its switch turns them all on or off
  const [open, setOpen] = useState(false);
  const kids = row.children;
  const head = html`<div class=${cls('step', row.on && 'on', row.restoring && 'restoring', row.featured && 'featured', row.child && 'child')}>
    <div class="main">
      <div class="title">
        ${kids && html`<button class=${cls('arrow', open && 'open')} aria-expanded=${open} title=${open ? 'Hide the parts' : 'Choose the parts'}
            onClick=${() => setOpen(!open)}>▸</button>`}${row.title}</div>
      <div class="sub">${row.sub}</div>
      ${row.bar != null && html`<div class="bar"><span style=${{ width: `${Math.round(row.bar * 100)}%` }}></span></div>`}
      ${row.warn && html`<div class="warn">${row.warn}</div>`}
      ${row.hint && html`<div class="hint">${row.hint}</div>`}
    </div>
    ${row.action && html`<${Button} small disabled=${!row.action.enabled} title=${row.action.tip}
        onClick=${() => call(row.action.call)}>${row.action.label}</${Button}>`}
    ${row.restore && html`<${Button} small kind=${row.restoring ? 'amber' : 'ghost'} disabled=${!row.restore_enabled}
        title=${row.restoring ? 'Press again to keep it as it is' : 'Put this part back as the game had it, in the next save'}
        onClick=${() => call('toggle_restore', row.key)}>${row.restoring ? 'Restoring' : 'Restore'}</${Button}>`}
    <${Toggle} on=${row.on} gold=${row.featured} disabled=${!row.enabled} label=${row.title}
        onChange=${(v) => call('set_step', row.key, v)}/>
  </div>`;
  if (!kids) return head;
  return html`<div class="stepgroup">${head}
    ${open && html`<div class="kids">${kids.map((k) => html`<${StepRow} key=${k.key} row=${k}/>`)}</div>`}</div>`;
}

function StepsCard({ s }) {
  // two columns where there is room; the Photos row (first, gold) stays at the top of the first
  const half = Math.ceil(s.steps.length / 2);
  return html`<${Card} n="1" title="What should be updated?" grow className="steps" style=${{ '--i': 1 }}>
    <div class="card-body fill">
      <div class="scroll"><div class="upd-steps">
        <div class="list">${s.steps.slice(0, half).map((row) => html`<${StepRow} key=${row.key} row=${row}/>`)}</div>
        <div class="list">${s.steps.slice(half).map((row) => html`<${StepRow} key=${row.key} row=${row}/>`)}</div>
      </div></div>
    </div>
    <div class="card-foot">
      ${s.later && html`<div class="later">${s.later}</div>`}
      ${s.restore_all.shown && html`<div><${Button} small kind="danger" className="glow" disabled=${!s.restore_all.enabled}
          onClick=${() => call('restore_default')}>Restore default: rosters, calendar and pictures</${Button}></div>`}
      ${s.export.on && html`<div class="later">${s.export.why}</div>`}
    </div>
  </${Card}>`;
}

function Result({ result }) {
  // the box keeps showing the last result while it closes
  const [shown, setShown] = useState(result);
  useEffect(() => { if (result) setShown(result); }, [result]);
  const r = result || shown;
  return html`<div class=${cls('result-wrap', result && 'open')} style=${{ '--i': 2 }}
      onTransitionEnd=${(e) => { if (e.target === e.currentTarget && !result) setShown(null); }}>
    <div class="inner">${r && html`<div class=${cls('result', r.good ? 'good' : 'bad')}>
      <div class="r-head"><div class="r-title">${r.title}</div>
        <button class="x" title="Close" onClick=${() => call('result_action', 'close')}>✕</button></div>
      <div class="r-body selectable">
        ${(r.bad || []).map((line, k) => html`<p class="bad" key=${'b' + k}>${line}</p>`)}
        ${r.lines.map((line, k) => html`<p key=${k}>${line}</p>`)}
        ${r.items.length > 0 && html`<dl class="items">${r.items.map(([t, text], k) => html`
          <dt key=${'t' + k}>${t}</dt><dd key=${'d' + k}>${text}</dd>`)}</dl>`}
      </div>
      ${r.buttons.length > 0 && html`<div class="r-buttons">${r.buttons.map((b) => html`
        <${Button} small key=${b.action} kind=${b.action === 'start_rpcs3' ? 'primary' : 'ghost'}
          onClick=${() => call('result_action', b.action)}>${b.label}</${Button}>`)}</div>`}
      ${r.dim && html`<div class="dim">${r.dim}</div>`}
    </div>`}</div>
  </div>`;
}

function SaveCard({ s }) {
  const v = s.save;
  return html`<${Card} n="2" title="Save" className="upd-savecard" style=${{ '--i': 3 }}>
    <div class="card-body upd-save">
      ${v.mode_shown && html`<${Segmented} value=${v.mode} disabled=${!v.mode_enabled}
          options=${[{ value: 'update', label: 'Update this roster' }, { value: 'new', label: 'Save as a new roster' }]}
          onChange=${(m) => call('set_save_mode', m)}/>`}
      <${TextField} value=${v.name} disabled=${!v.name_enabled} onChange=${(t) => call('set_name', t)}/>
      ${v.save_for && html`<span class="savefor-wrap"><span class="savefor">Save for</span>
        <${Segmented} value=${v.save_for.value} disabled=${!v.save_for.enabled}
          options=${v.save_for.options.map((o) => ({ value: o, label: o,
            icon: o === 'EU + NA' ? html`<${Flag} region="EU"/><${Flag} region="NA"/>` : html`<${Flag} region=${o}/>` }))}
          onChange=${(x) => call('set_save_for', x)}/></span>`}
      <${Button} kind="primary" big className=${cls('go', s.busy && 'working')} disabled=${!v.button.enabled}
        onClick=${() => call('start')}>${v.button.text}</${Button}>
    </div>
    <div class="small-note upd-note">${v.note}</div>
  </${Card}>`;
}

export function UpdateTab({ s }) {
  if (!s) return null;
  return html`<div class="upd">
    <${FromBar} s=${s}/>
    <${StepsCard} s=${s}/>
    <${Result} result=${s.result}/>
    <${SaveCard} s=${s}/>
  </div>`;
}

// --- Game patch ---------------------------------------------------------------------------------------------
export function PatchTab({ s }) {
  if (!s) return null;
  const p = s.patch;
  return html`<div class="columns">
    <div class="col">
      <${Card} title=${p.title} className="patch" style=${{ '--i': 0 }}>
        <div class="card-body">
          <div class="sub">${p.sub}</div>
          <div class="row patch-state">
            <div class=${cls('state', p.state.tone)}>${p.state.text}</div>
            ${p.buttons.map((b) => html`<${Button} small key=${b.call} kind=${b.kind} disabled=${!b.enabled}
                onClick=${() => call(b.call)}>${b.label}</${Button}>`)}
          </div>
          <div class="checks">${p.checks.map((c) => html`<div key=${c.key} class="sw">
            <${Checkbox} on=${c.on} title=${c.tip} disabled=${!c.enabled || s.busy}
              onChange=${(v) => call('set_patch_switch', c.key, v)}>${c.label}</${Checkbox}>
            ${c.tip && html`<div class="small-note sw-tip">${c.tip}</div>`}</div>`)}</div>
          ${p.note && html`<div class="hint">${p.note}</div>`}
        </div>
      </${Card}>
      ${(p.regions || []).map((r, k) => html`<${Card} key=${r.title} title=${`${r.region} version`} aside=${r.title}
          className="patch region" style=${{ '--i': k + 1 }}>
        <div class="card-body">
          <div class="row patch-state"><${Flag} region=${r.region}/><div class=${cls('state', r.tone)}>${r.state}</div></div>
          <div class="small-note region-rosters">Rosters: ${r.rosters.map((x) => x.name + (x.tag ? ` (${x.tag})` : '')
            + (x.misfit ? ' (not loadable now: update it)' : '')).join(' · ') || 'none yet'}</div>
        </div>
      </${Card}>`)}
    </div>
    <div class="col">
      <${Card} title=${p.info ? p.info.title : 'What the game patch does'} grow style=${{ '--i': 3 }}>
        <div class="card-body fill"><div class="scroll patch-info">
          ${(p.info ? p.info.sections : []).map((sec) => html`<div key=${sec.head} class="pi-part"><div class="pi-head">${sec.head}</div>
            <ul>${sec.items.map((it, k) => html`<li key=${k}>${it}</li>`)}</ul></div>`)}
        </div></div>
      </${Card}>
    </div>
  </div>`;
}

// kept for the classic look of the patch row elsewhere (the "?" next to Patch)
export { Info };
