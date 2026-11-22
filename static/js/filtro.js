/* Filtro per titolo e per argomento nelle pagine delle sezioni. */
(function () {
  var box = document.getElementById('cerca');
  if (!box) return;
  var cards = [].slice.call(document.querySelectorAll('[data-video]'));
  var chips = [].slice.call(document.querySelectorAll('[data-tag-filter]'));
  var none = document.getElementById('nessuno');
  var tag = '';

  function apply() {
    var q = box.value.trim().toLowerCase();
    var shown = 0;
    cards.forEach(function (c) {
      var tags = (c.getAttribute('data-tags') || '').split(',');
      var ok = (!tag || tags.indexOf(tag) > -1) &&
               (!q || (c.getAttribute('data-title') || '').indexOf(q) > -1);
      c.hidden = !ok;
      if (ok) shown++;
    });
    if (none) none.hidden = shown > 0;
  }

  box.addEventListener('input', apply);
  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      var t = chip.getAttribute('data-tag-filter');
      tag = (tag === t) ? '' : t;
      chips.forEach(function (c) {
        c.setAttribute('aria-pressed', String(c.getAttribute('data-tag-filter') === tag));
      });
      apply();
    });
  });
})();
