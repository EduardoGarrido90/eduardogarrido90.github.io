/* Conmutador de idioma español / inglés para las páginas de docencia.
   Se carga de forma bloqueante en <head> para fijar el idioma antes del primer
   pintado y evitar el parpadeo. El contenido vive duplicado en el HTML dentro
   de <span class="es"> y <span class="en">; la hoja de estilo oculta el que no
   toca según el atributo data-lang del elemento <html>. */
(function () {
  var STORE = 'docencia-lang';
  var doc = document.documentElement;

  function normalize(lang) {
    return lang === 'en' ? 'en' : 'es';
  }

  function detect() {
    var lang = null;
    try {
      var q = window.location.search.match(/[?&]lang=(es|en)\b/i);
      if (q) { return normalize(q[1].toLowerCase()); }
    } catch (e) {}
    try { lang = window.localStorage.getItem(STORE); } catch (e) {}
    return normalize(lang);
  }

  function setLang(lang) {
    lang = normalize(lang);
    doc.setAttribute('data-lang', lang);
    doc.setAttribute('lang', lang);
    var title = doc.getAttribute('data-title-' + lang);
    if (title) { document.title = title; }
    var buttons = document.querySelectorAll('[data-set-lang]');
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute('aria-pressed',
        buttons[i].getAttribute('data-set-lang') === lang ? 'true' : 'false');
    }
    try { window.localStorage.setItem(STORE, lang); } catch (e) {}
    return lang;
  }

  /* Antes del primer pintado: sólo los atributos, el DOM aún no existe. */
  var initial = detect();
  doc.setAttribute('data-lang', initial);
  doc.setAttribute('lang', initial);

  function wire() {
    var buttons = document.querySelectorAll('[data-set-lang]');
    for (var i = 0; i < buttons.length; i++) {
      (function (btn) {
        btn.addEventListener('click', function () {
          setLang(btn.getAttribute('data-set-lang'));
        });
      })(buttons[i]);
    }
    setLang(doc.getAttribute('data-lang'));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }
})();
