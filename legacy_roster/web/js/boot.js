// The page's first words and its safety net. A plain script (not a module), so it runs even when a module or a style
// file is missing: before this the window could stay solid blue or black with nothing to read.
//   - "Starting..." shows until the page has drawn the program's first data (main.js calls __lrOk, Python then knows
//     the window works: api.page_up).
//   - A file that does not load: the page loads itself again, up to RETRIES times.
//   - Any error of the page, a file that still does not load, or nothing after 25 s: the reason on screen, with "Try
//     again", "Open the simple window" and "Open the start log", and the line goes to Python's start log (api.log_js).
//   - Once the page is up an error is only written down, unless it took the page away (fatal: main.js's Guard).
(function () {
  var boot = document.getElementById('boot');
  if (!boot) return;
  var done = false, failed = false;
  var waiting = [];               // lines for Python: its calls only exist once the page has loaded
  var RETRIES = 5;
  var LIBRARY_WAIT = 10000;       // ms, as bridge.js

  function api(name, arg) {
    try {
      var a = window.pywebview && window.pywebview.api;
      if (a && a[name]) return arg === undefined ? a[name]() : a[name](arg);    // Python counts an empty argument too
    } catch (e) { /* the program is not there */ }
  }

  function flush() {
    var a = window.pywebview && window.pywebview.api;
    while (a && a.log_js && waiting.length) api('log_js', waiting.shift());
  }

  function tell(text) {
    if (waiting.length < 30) waiting.push(String(text).slice(0, 1500));
    flush();
  }
  window.addEventListener('pywebviewready', flush);

  function button(label, click) {
    var b = document.createElement('button');
    b.textContent = label;
    b.style.cssText = 'margin:6px;padding:8px 16px;font:600 14px sans-serif;color:#fff;background:#1b5fa8;border:1px solid #5aa0e8;border-radius:4px;cursor:pointer';
    b.onclick = click;
    return b;
  }

  window.__lrFail = function (message, fatal, more) {
    tell('FAIL ' + message + (more ? ' ' + more : ''));
    if (failed || (done && !fatal)) return;
    failed = true;
    boot.textContent = '';
    boot.style.cssText = 'position:fixed;left:0;top:0;right:0;bottom:0;z-index:99999;display:flex;flex-direction:column;'
      + 'align-items:center;justify-content:center;text-align:center;padding:24px;background:#07111f;color:#dfe9f5;font:16px sans-serif';
    var title = document.createElement('div');
    title.textContent = 'The window did not start properly';
    title.style.cssText = 'font:700 22px sans-serif;margin-bottom:12px';
    var why = document.createElement('div');
    why.textContent = message;
    why.style.cssText = 'max-width:640px;margin-bottom:8px;color:#9fb6d0';
    var help = document.createElement('div');
    help.textContent = 'Try again. If it keeps happening, open the simple window, and send us the start log.';
    help.style.cssText = 'max-width:640px;margin-bottom:16px';
    var row = document.createElement('div');
    row.appendChild(button('Try again', function () { location.reload(); }));
    row.appendChild(button('Open the simple window', function () { api('classic'); }));
    row.appendChild(button('Open the start log', function () { api('open_start_log'); }));
    [title, why, help, row].forEach(function (n) { boot.appendChild(n); });
    if (!boot.parentNode) document.body.appendChild(boot);
  };

  window.__lrOk = function () {
    if (done) return;
    done = true;
    failed = false;
    clearTimeout(timer);
    if (boot.parentNode) boot.parentNode.removeChild(boot);
    api('page_up');
  };

  // One file the browser could not get takes the whole page with it (a module's imports fail together). Loading the
  // page again gets it: this happens now and then, also on a healthy PC, and the player need not see it.
  var tries = Number((/[?&]again=(\d+)/.exec(location.search) || [])[1] || 0);
  if (tries) tell('loaded again, try ' + tries);

  // Not before the window library has set itself up on this page: it does that once per load, and on the next page it
  // would forget the page's first question, so the page would wait for its data for ever.
  function loadAgain() {
    if (done || tries >= RETRIES) return false;
    function go() { location.replace(location.pathname + '?again=' + (tries + 1)); }
    var a = window.pywebview && window.pywebview.api;
    if (a && a.ready) {
      go();
    } else {
      window.addEventListener('pywebviewready', go, { once: true });
      setTimeout(go, LIBRARY_WAIT);
    }
    return true;
  }

  window.addEventListener('error', function (e) {
    if (e.target && e.target !== window && (e.target.src || e.target.href)) {
      if (/^(SCRIPT|LINK)$/.test(e.target.tagName) && loadAgain()) return;
      window.__lrFail('A file of the program could not be loaded: ' + (e.target.src || e.target.href));
    } else if (!/ResizeObserver/.test(e.message || '')) {      // the browser's harmless "loop" notice
      window.__lrFail('Error in the page: ' + e.message + (e.filename ? ' (' + e.filename + ':' + e.lineno + ')' : ''));
    }
  }, true);
  window.addEventListener('unhandledrejection', function (e) {
    window.__lrFail('Error in the page: ' + (e.reason && e.reason.message || e.reason));
  });

  var timer = setTimeout(function () {
    window.__lrFail('The program did not send its data in time.');
  }, 25000);
})();
