// What Python pushes: the slices of state (one per tab), the details log, and one-off events.
import { useSyncExternalStore } from './lib.js';

const slices = {};
let meta = {};
let log = { lines: [], version: 0 };
const subscribers = new Set();
const handlers = {};
const MAX_LINES = 5000;

function notify() {
  for (const fn of subscribers) fn();
}

function subscribe(fn) {
  subscribers.add(fn);
  return () => subscribers.delete(fn);
}

export function receive(message) {
  if (!message) return;
  if (message.error) {            // Python could not build the first page (it is in the error log): say so, with the way out
    if (window.__lrFail) window.__lrFail(message.error);
    return;
  }
  if (message.meta) {
    meta = message.meta;
    if (window.__lrOk) window.__lrOk();
  }
  if (message.slices) {
    for (const [name, value] of Object.entries(message.slices)) slices[name] = value;
  }
  if (message.log) {
    let lines = message.log.clear ? [] : log.lines;
    if (message.log.lines && message.log.lines.length) {
      lines = lines.concat(message.log.lines);
      if (lines.length > MAX_LINES) lines = lines.slice(lines.length - MAX_LINES);
    }
    log = { lines, version: log.version + 1 };
  }
  notify();
  for (const [name, payload] of message.events || []) {
    for (const fn of handlers[name] || []) fn(payload);
  }
}

export function on(event, fn) {
  (handlers[event] = handlers[event] || []).push(fn);
  return () => { handlers[event] = handlers[event].filter((f) => f !== fn); };
}

export function useSlice(name) {
  return useSyncExternalStore(subscribe, () => slices[name]);
}

export function useMeta() {
  return useSyncExternalStore(subscribe, () => meta);
}

export function useLog() {
  return useSyncExternalStore(subscribe, () => log);
}

window.LR = { receive };
