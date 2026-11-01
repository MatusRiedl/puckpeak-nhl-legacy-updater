// Talking to Python. In the program it is pywebview's js_api; opened in a normal browser with
// ?demo or ?fixture=<file.json> it is a stand-in (demo.js), for design work and screenshots.
import { receive } from './store.js';

let api = null;
export const params = new URLSearchParams(location.search);
export const offline = params.has('demo') || params.has('fixture') || !!window.__FIXTURE__;

const READY_WAIT = 10000;      // ms the window library has to offer the program's calls

function pywebviewReady() {
  return new Promise((resolve, reject) => {
    const there = () => window.pywebview && window.pywebview.api && window.pywebview.api.ready;
    if (there()) return resolve();
    const timer = setTimeout(() => reject(new Error('The window could not reach the program.')), READY_WAIT);
    window.addEventListener('pywebviewready', () => { clearTimeout(timer); resolve(); }, { once: true });
  });
}

export async function connect() {
  if (window.__FIXTURE__) {           // tools/window_shot.py put the state into the page itself
    api = { ready: () => window.__FIXTURE__ };
  } else if (offline) {
    const demo = await import('./demo.js');
    api = await demo.makeApi(params, receive);
  } else {
    await pywebviewReady();
    api = window.pywebview.api;
  }
  receive(await api.ready());
}

export function call(name, ...args) {
  const fn = api && api[name];
  if (!fn) return Promise.resolve(null);
  return Promise.resolve(fn(...args))
    .then((reply) => {
      if (reply && reply.error) console.error(name, reply.error);
      return reply;
    })
    .catch((err) => { console.error(name, err); return null; });
}
