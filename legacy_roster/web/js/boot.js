// The page's first words and its safety net. A plain script (not a module), so it runs even when a module or a style
// file is missing: before this the window could stay solid blue or black with nothing to read.
//   - "Starting..." shows until the program's first data arrives (store.js calls __lrOk).
//   - Any error of the page, a file that does not load, or no data after 25 s: the reason on screen, with "Try again",
//     "Open the simple window" and "Open the start log", and the line goes to Python's start log (api.log_js).
(function () {
  var boot = document.getElementById('boot');
  if (!boot) return;
  var done = false, failed = false;

  function api(name, arg) {
    try {
      var a = window.pywebview && window.pywebview.api;
      if (a && a[name]) return a[name](arg);
    } catch (e) { /* the program is not there */ }
  }

  function tell(text) { api('log_js', String(text).slice(0, 600)); }

  function button(label, click) {
    var b = document.createElement('button');
    b.textContent = label;
    b.style.cssText = 'margin:6px;padding:8px 16px;font:600 14px sans-serif;color:#fff;background:#1b5fa8;border:1px solid #5aa0e8;border-radius:4px;cursor:pointer';
    b.onclick = click;
    return b;
  }

  window.__lrFail = function (message) {
    if (done) return;
    tell('FAIL ' + message);
    if (failed) return;
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
  };

  window.__lrOk = function () {
    done = true;
    clearTimeout(timer);
    if (boot.parentNode) boot.parentNode.removeChild(boot);
  };

  window.addEventListener('error', function (e) {
    if (e.target && e.target !== window && (e.target.src || e.target.href)) {
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
