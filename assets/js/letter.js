// Printable letter pages: print button + WebKit print-margin fix. Vanilla, no deps.
(function () {
  // ---- Print button ----
  var btn = document.querySelector('.toolbar__btn');
  if (btn) {
    btn.addEventListener('click', function () { window.print(); });
  }

  // ---- WebKit vertical print margins ----
  // Safari and every iOS browser shell never repeat a table's thead/tfoot
  // on printed pages (WebKit bug 17205), so the spacers that carry the
  // top/bottom page margin reach only the first sheet there. Move those
  // margins onto @page instead, and drop the spacers so page one is not
  // inset twice. Engine check, not browser check: navigator.vendor is
  // 'Apple Computer, Inc.' exactly for WebKit.
  if (/apple/i.test(navigator.vendor || '')) {
    // Read the inset from the stylesheet rather than repeating it here —
    // letter pages set their own --ltr-margin to fit their text on a page.
    var inset =
      getComputedStyle(document.documentElement)
        .getPropertyValue('--ltr-margin').trim() || '0.5in';
    var style = document.createElement('style');
    style.textContent =
      '@media print{@page{size:A4;margin:' + inset + ' 0}' +
      '.sheet__vspace{height:0}}';
    document.head.appendChild(style);
  }
})();
