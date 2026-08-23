// CV page: fit the true-A4 sheets to narrow viewports, and the print button.
// Vanilla, no deps.
(function () {
  var stage = document.querySelector('.cv-stage');
  var doc = document.querySelector('.cv-doc');

  // ---- Print / save as PDF ----
  var printBtn = document.querySelector('[data-cv-print]');
  if (printBtn) {
    printBtn.addEventListener('click', function () { window.print(); });
  }

  if (!stage || !doc) return;

  // ---- Fit to width ----
  // The sheets are laid out at true A4 (210mm). On a screen narrower than
  // that, scale the document down so it is readable without a horizontal
  // scroll. `zoom` is used rather than `transform` because it scales layout,
  // so the stage's height follows and nothing needs re-measuring. Where zoom
  // is unsupported the stage simply scrolls — the sheets stay correct.
  if (!(window.CSS && CSS.supports && CSS.supports('zoom', '0.5'))) return;

  // 210mm in CSS px. Measured rather than assumed, so the value comes from
  // the same engine that lays the sheet out.
  var probe = document.createElement('div');
  probe.style.cssText = 'position:absolute;visibility:hidden;width:210mm';
  document.body.appendChild(probe);
  var pageWidth = probe.getBoundingClientRect().width;
  document.body.removeChild(probe);
  if (!pageWidth) return;

  var GUTTER = 32; // breathing room either side of the sheet
  var queued = false;
  var applied = null;

  function fit() {
    queued = false;
    var available = stage.clientWidth - GUTTER;
    var scale = Math.min(1, available / pageWidth);
    if (!(scale > 0)) scale = 1;
    // Zooming changes the stage's own box, which the observer below sees —
    // writing only on a real change keeps that from looping.
    if (applied !== null && Math.abs(scale - applied) < 0.001) return;
    applied = scale;
    doc.style.setProperty('--cv-zoom', String(scale));
  }

  function schedule() {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(fit);
  }

  // Printing is unaffected: the print stylesheet pins `zoom: 1` on the
  // document, which wins over the fitted value.
  fit();
  window.addEventListener('resize', schedule);
  if ('ResizeObserver' in window) new ResizeObserver(schedule).observe(stage);
})();
