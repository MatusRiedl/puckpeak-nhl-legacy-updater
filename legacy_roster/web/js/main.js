// The window: the arena, the header, eleven tabs in one row (Setup, Game patch, Update | Roster, Lines, Strategy,
// Jerseys & ice, Calendar, Front office, Draft & Pro | MULTIPLAYER, gold), the Help bar. The team tabs share the team list on the left
// (rail.js; Draft & Pro has its classes there, prospects.js) and, all but the Calendar, the Save bar under them. A tab is
// drawn on its first visit, then kept.
import { html, cls, useState, useEffect, useRef } from './lib.js';
import { connect, call, params } from './bridge.js';
import { useSlice, useMeta, on } from './store.js';
import { Backdrop, Header, TabBar, HelpBar, Details, Question } from './shell.js';
import { Button } from './ui.js';
import { Rail } from './rail.js';
import { SetupTab, UpdateTab, PatchTab } from './update.js';
import { RosterTab, LinesTab, StrategyTab, JerseysTab, SaveBar, EditorModals, saveRoster } from './editor.js';
import { CalendarTab } from './calendar.js';
import { OfficeTab, ContractWindow } from './office.js';
import { ProspectsTab, ClassRail } from './prospects.js';
import { OnlineTab } from './online.js';

const TABS = [
  { id: 'setup', label: 'Setup' }, { id: 'patch', label: 'Game patch' }, { id: 'update', label: 'Update' },
  { id: 'roster', label: 'Roster' }, { id: 'lines', label: 'Lines' }, { id: 'strategy', label: 'Strategy' },
  { id: 'jerseys', label: 'Jerseys & ice' }, { id: 'calendar', label: 'Calendar' }, { id: 'office', label: 'Front office' },
  { id: 'prospects', label: 'Draft & Pro' }, { id: 'online', label: 'MULTIPLAYER', gold: true },
];
const TEAM_TABS = ['roster', 'lines', 'strategy', 'jerseys', 'calendar', 'office', 'prospects'];
const OLD_NAMES = { editor: 'roster', uniforms: 'jerseys', strategies: 'strategy' };
const TIPS = {
  roster: 'Pick a team on the left, then a player.   Alt+Up / Alt+Down: the team before or after.   Ctrl+S saves.',
  lines: 'Click a place, then the player who plays there.   Alt+Up / Alt+Down: the team before or after.',
  strategy: 'Change a strategy, then Apply.   Alt+Up / Alt+Down: the team before or after.',
  jerseys: 'Pick how each jersey is made, then Apply.   Alt+Up / Alt+Down: the team before or after.',
  calendar: 'Click a day to see its games.   Alt+Up / Alt+Down: the team before or after.',
  office: 'Click a player to change his contract.   Alt+Up / Alt+Down: the team before or after.',
  prospects: 'Pick a draft, then a player, or add one.   Alt+Up / Alt+Down: the draft before or after.   Ctrl+S saves.',
};
const CAREER_TIP = 'Pick a career, change your pro, then Save this career (RPCS3 closed).   Alt+Up: the drafts.';
const SHORT = 720;          // window heights below this fold the big logo (768-line laptops)

const tabOf = (id) => {
  const t = OLD_NAMES[id] || id;
  return TABS.some((x) => x.id === t) ? t : null;
};

function useShort() {
  const [short, setShort] = useState(window.innerHeight < SHORT);
  useEffect(() => {
    const fit = () => setShort(window.innerHeight < SHORT);
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
  return short;
}

function typingIn(target) {
  return target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable);
}

// the first tab is always Setup, the start of the right order: Setup, Game patch, Update
function startTab(update) {
  return update ? 'setup' : null;
}

function NoRoster({ editor, onSetup }) {
  return html`<div class="empty ed-none"><div>
    <div class="big">${(editor && editor.status.text) || 'Pick RPCS3 and a roster in Setup first.'}</div>
    <${Button} kind="primary" onClick=${onSetup}>Go to Setup<//></div></div>`;
}

function App() {
  const meta = useMeta();
  const update = useSlice('update');
  const editor = useSlice('editor');
  const rail = useSlice('rail');
  const lines = useSlice('lines');
  const strategy = useSlice('strategy');
  const uniforms = useSlice('uniforms');
  const calendar = useSlice('calendar');
  const office = useSlice('office');
  const contract = useSlice('contract');
  const prospects = useSlice('prospects');
  const career = useSlice('career');
  const online = useSlice('online');
  const [tab, setTab] = useState(() => tabOf(params.get('tab')));
  const [seen, setSeen] = useState(() => new Set(tab ? [tab] : []));
  const [from, setFrom] = useState(null);         // {dir: 'from-left' | 'from-right', team: the tab left was a team tab}
  const careers = tab === 'prospects' && !!prospects && prospects.view === 'careers';     // Draft & Pro's Be a Pro careers
  const [details, setDetails] = useState(params.has('details'));
  const told = useRef(false);
  const short = useShort();
  const [enter, setEnter] = useState(true);       // the cards rise in once, when the window opens
  useEffect(() => {
    if (!meta.version) return undefined;
    const t = setTimeout(() => setEnter(false), 1400);
    return () => clearTimeout(t);
  }, [meta.version]);

  useEffect(() => {                               // the first tab, once Python has said where RPCS3 and the roster are
    if (tab) return undefined;
    const first = startTab(update);
    if (first) {
      setTab(first);
      setSeen(new Set([first]));
      return undefined;
    }
    return undefined;
  }, [tab, update]);
  useEffect(() => {                               // the first tab has drawn: the window works ("Starting..." goes)
    if (meta.version && tab && window.__lrOk) window.__lrOk();
  }, [meta.version, tab]);
  useEffect(() => {                               // Python learns the tab in view (a team tab reads the roster then)
    if (meta.version && tab && !told.current) {
      told.current = true;
      call('tab', tab);
    }
  }, [meta.version, tab]);

  const pickTab = (want) => {
    const id = tabOf(want);
    if (!id || id === tab) return;
    const i = TABS.findIndex((t) => t.id === id), j = TABS.findIndex((t) => t.id === tab);
    setFrom({ dir: i > j ? 'from-right' : 'from-left', team: TEAM_TABS.includes(tab) });
    setTab(id);
    setSeen((s) => (s.has(id) ? s : new Set(s).add(id)));
    told.current = true;
    call('tab', id);
  };

  useEffect(() => on('details', (p) => setDetails(p && p.open !== undefined ? p.open : true)), []);
  useEffect(() => on('focus_tab', (p) => pickTab(p.tab)), [tab]);
  useEffect(() => {
    const go = (e) => pickTab(e.detail);
    window.addEventListener('lr-tab', go);
    return () => window.removeEventListener('lr-tab', go);
  }, [tab]);

  const teamTab = TEAM_TABS.includes(tab);
  useEffect(() => {
    const key = (e) => {
      const modal = document.querySelector('.modal-back');
      if (e.ctrlKey && (e.key === 'PageUp' || e.key === 'PageDown')) {
        e.preventDefault();
        if (modal || !tab) return;
        const i = TABS.findIndex((t) => t.id === tab);
        pickTab(TABS[(i + (e.key === 'PageDown' ? 1 : TABS.length - 1)) % TABS.length].id);
        return;
      }
      if (e.ctrlKey && !e.altKey && !e.shiftKey && e.key >= '0' && e.key <= '9') {     // Ctrl+0: the tenth
        e.preventDefault();
        if (!modal) pickTab(TABS[(Number(e.key) + 9) % 10].id);
        return;
      }
      if (e.key === 'F5' || (e.ctrlKey && (e.key === 'r' || e.key === 'R'))) { e.preventDefault(); return; }
      if (e.ctrlKey && (e.key === 's' || e.key === 'S')) {
        e.preventDefault();
        if (careers) { if (!modal && career && career.dirty && !career.busy) call('career_save'); }
        else if (teamTab && tab !== 'calendar' && !modal && editor && editor.save.button.enabled) saveRoster();
        return;
      }
      if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
        if (teamTab && !modal) {
          e.preventDefault();
          call(tab === 'prospects' ? 'prospects_step' : 'rail_step', e.key === 'ArrowDown' ? 1 : -1);
        }
        return;
      }
      if (typingIn(e.target) || modal) return;
      if ((e.key === 'd' || e.key === 'D') && !e.ctrlKey && !e.altKey) setDetails((d) => !d);
      else if (e.key === 'Escape' && details) setDetails(false);
      else if (e.key === 'Enter' && tab === 'update' && update && update.save.button.enabled
               && !(e.target && e.target.closest && e.target.closest('button, a, [role=radio], [role=checkbox], [role=button]'))) call('start');
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [tab, details, update, editor, careers, career]);

  if (!meta.version || !tab) return html`<div class="app"><${Backdrop}/></div>`;
  // on the team tabs the Help bar says what the editor says (or how the tab works), unless an update runs
  const status = teamTab && editor && !(update && update.busy)
    ? (editor.status.text && (editor.busy || editor.status.tone !== 'info' || !editor.loaded) ? editor.status
      : { text: careers ? CAREER_TIP : TIPS[tab], tone: 'info' })
    : update && update.status;
  const progress = update && (update.busy || !(editor && editor.busy)) ? update.progress
    : { value: 0, active: false, indeterminate: true };
  const hint = tab === 'update' && update && update.save.button.enabled ? update.save.button.text : null;
  const anim = (id, inner) => tab === id && from && (inner ? from.team : !from.team || !TEAM_TABS.includes(id)) && from.dir;
  const pane = (id, body) => (seen.has(id) || tab === id) && html`<section key=${id} class=${cls('pane', anim(id))}
    hidden=${tab !== id}>${body}</section>`;
  const tpane = (id, body) => (seen.has(id) || tab === id) && html`<section key=${id} class=${cls('tpane', `tp-${id}`, anim(id, true))}
    hidden=${tab !== id}>${body}</section>`;
  const roster = editor && editor.roster;
  const noSave = tab === 'calendar' || careers;     // the Calendar changes nothing; a Be a Pro career has its own Save
  return html`<div class=${cls('app', enter && 'enter', short && 'compact')}>
    <${Backdrop}/>
    <${Header} meta=${meta} play=${update && update.play}/>
    <${TabBar} tabs=${TABS} tab=${tab} onTab=${pickTab}/>
    <main class="stage">
      ${pane('setup', html`<${SetupTab} s=${update} version=${meta.version}/>`)}
      ${pane('update', html`<${UpdateTab} s=${update}/>`)}
      ${pane('patch', html`<${PatchTab} s=${update}/>`)}
      ${pane('online', update && update.export && update.export.on
        ? html`<div class="export-off"><div class="note muted">${update.export.why}</div>
            <${Button} onClick=${() => call('set_export_only', false)}>Switch off "Export files to a folder"</${Button}></div>`
        : html`<${OnlineTab} s=${online}/>`)}
      <section class=${cls('pane', 'teamstage', noSave && 'nosave', teamTab && from && !from.team && from.dir)}
          hidden=${!teamTab}>
        ${tab === 'prospects' ? html`<${ClassRail} p=${prospects}/>` : html`<${Rail} s=${rail}/>`}
        <div class=${cls('tpanes', editor && editor.busy && 'busy')}>
          ${roster ? html`
            ${tpane('roster', html`<${RosterTab} s=${editor}/>`)}
            ${tpane('lines', html`<${LinesTab} n=${lines}/>`)}
            ${tpane('strategy', html`<${StrategyTab} g=${strategy}/>`)}
            ${tpane('jerseys', html`<${JerseysTab} u=${uniforms}/>`)}
            ${tpane('calendar', html`<${CalendarTab} s=${calendar}/>`)}
            ${tpane('office', html`<${OfficeTab} s=${office}/>`)}
            ${tpane('prospects', html`<${ProspectsTab} s=${editor} p=${prospects} c=${career}/>`)}`
          : html`<${NoRoster} editor=${editor} onSetup=${() => pickTab('setup')}/>`}
          ${roster && !editor.loaded && html`<div class="ed-loading"><div class="spinner"></div><div>${editor.status.text}</div></div>`}
        </div>
        ${!noSave && html`<${SaveBar} s=${editor}/>`}
      </section>
    </main>
    <${Details} open=${details} onClose=${() => setDetails(false)}/>
    <${HelpBar} status=${status} progress=${progress} detailsOpen=${details} onDetails=${() => setDetails(!details)} hint=${hint}/>
    <${EditorModals} s=${editor}/>
    <${ContractWindow} c=${contract}/>
    <${Question} dialog=${update && update.dialog} onAnswer=${(id, a) => call('answer', id, a)}/>
  </div>`;
}

// After an error while drawing, React takes everything off the screen: the window would stay plain blue with no word
// of it anywhere. This says what happened (boot.js) and leaves the way out on screen.
class Guard extends window.React.Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    if (window.__lrFail) {
      window.__lrFail(`Error in the page: ${error && error.message || error}`, true, info && info.componentStack);
    }
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

// the window never navigates away: links open in the player's browser (through Python)
document.addEventListener('dragover', (e) => e.preventDefault());
document.addEventListener('drop', (e) => e.preventDefault());
document.addEventListener('contextmenu', (e) => { if (!typingIn(e.target) && !e.target.closest('.selectable, pre')) e.preventDefault(); });
if (params.has('still')) document.documentElement.classList.add('still');

window.ReactDOM.createRoot(document.getElementById('root')).render(html`<${Guard}><${App}/></${Guard}>`);
connect().catch((err) => {
  if (window.__lrFail) window.__lrFail(String(err && err.message || err));
  else document.getElementById('root').textContent = 'The window could not start: ' + err;
});
