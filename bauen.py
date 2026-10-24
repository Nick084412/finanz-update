#!/usr/bin/env python3
"""Baut die Briefing-Webseite aus einer Daten-Datei und lädt sie auf GitHub Pages hoch.

Aufruf:  python3 bauen.py daten/2026-10-21.json   (Tagesbriefing, "typ": "tag")
         python3 bauen.py daten/2026-KW43.json    (Wochenüberblick, "typ": "woche")
         python3 bauen.py --nur-bauen ...         (ohne Hochladen)

Ergebnis im Ordner docs/ (GitHub Pages):
  index.html          neuestes Tagesbriefing
  woche.html          neuester Wochenüberblick
  archiv/<name>.html  jede Ausgabe einzeln
  archiv/index.html   Übersicht aller Ausgaben
Ist der Ordner ein Git-Repository mit Remote, werden daten/ und docs/ committet und gepusht.
"""
import datetime as dt
import html
import re
import json
import subprocess
import sys
from pathlib import Path

BASIS = Path(__file__).resolve().parent
SITE = BASIS / "docs"
DATEN = BASIS / "daten"
CSS = (BASIS / "style.css").read_text(encoding="utf-8")
MARKE = "Finanz-Update"
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400'
         '&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&display=swap">')
# Interaktion: Theme, Rubrik-Reiter, Aufklappen, Gelesen, Merkliste, Kopieren, Einblenden
SKRIPT = """<script>
(function () {
  var r = document.documentElement, body = document.body;
  r.classList.add('js');
  function lesen(k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function schreiben(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  function alle(sel, ctx) { return [].slice.call((ctx || document).querySelectorAll(sel)); }
  var ruhig = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Hell / Dunkel */
  var t = lesen('fu-thema-v3', null); if (t === 'light') r.dataset.theme = t;
  alle('.thema-wechsel').forEach(function (tb) {
    tb.addEventListener('click', function () {
      if (r.dataset.theme === 'light') delete r.dataset.theme; else r.dataset.theme = 'light';
      schreiben('fu-thema-v3', r.dataset.theme || null);
    });
  });

  /* Kopfbereich: Auftakt, Scroll-Animation, Mini-Kopf, leichte Mausbewegung */
  var kopfEl = document.querySelector('.kopf-voll'), mini = document.querySelector('.kopf-mini');
  if (kopfEl) {
    var losgehen = function () { kopfEl.classList.add('bereit'); };
    requestAnimationFrame(losgehen); setTimeout(losgehen, 120);
    var tick = false, mx = 0, my = 0;
    function zeichnen() {
      tick = false;
      var h = kopfEl.offsetHeight || 1, p = Math.max(0, Math.min(1, scrollY / h));
      kopfEl.style.setProperty('--p', p.toFixed(4));
      kopfEl.style.setProperty('--mx', mx.toFixed(3)); kopfEl.style.setProperty('--my', my.toFixed(3));
      var zeigen = scrollY > h - 70;
      if (mini) {
        mini.classList.toggle('sichtbar', zeigen); mini.setAttribute('aria-hidden', zeigen ? 'false' : 'true');
        alle('a, button', mini).forEach(function (x) { x.tabIndex = zeigen ? 0 : -1; });
      }
    }
    function anfordern() { if (!tick) { tick = true; requestAnimationFrame(zeichnen); } }
    addEventListener('scroll', anfordern, { passive: true }); addEventListener('resize', anfordern);
    if (!ruhig) kopfEl.addEventListener('pointermove', function (ev) {
      var b = kopfEl.getBoundingClientRect();
      mx = (ev.clientX - b.left) / b.width - .5; my = (ev.clientY - b.top) / b.height - .5; anfordern();
    });
    /* Beweglicher Hintergrund: drei Ebenen Kerzen-Charts ziehen langsam vorbei (Tiefenwirkung) */
    var kerzen = kopfEl.querySelector('.kerzen');
    if (kerzen && kerzen.getContext) {
      var ctx = kerzen.getContext('2d'), W = 0, H = 0, dpr = Math.min(2, devicePixelRatio || 1), laeuft = false, letzte = 0;
      var ebenen = [
        { tempo: 7, breite: 4, abstand: 11, alpha: .2, mitte: .24, hub: .16, tiefe: .35 },
        { tempo: 12, breite: 7, abstand: 18, alpha: .3, mitte: .52, hub: .2, tiefe: .65 },
        { tempo: 19, breite: 11, abstand: 28, alpha: .42, mitte: .78, hub: .15, tiefe: 1 }
      ];
      var neueKerze = function (e) {
        var o = e.wert, c = o + (Math.random() - .47) * .3;
        c += (0 - c) * .03;
        var k = { o: o, c: c, h: Math.max(o, c) + Math.random() * .12, l: Math.min(o, c) - Math.random() * .12 };
        e.wert = c; return k;
      };
      var aufbauen = function () {
        W = kopfEl.clientWidth; H = kopfEl.clientHeight;
        kerzen.width = W * dpr; kerzen.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        var klein = W < 600 ? .7 : 1;
        ebenen.forEach(function (e) {
          e.b = e.breite * klein; e.a = e.abstand * klein; e.wert = 0; e.versatz = 0; e.liste = [];
          for (var i = 0, n = Math.ceil(W / e.a) + 3; i < n; i++) e.liste.push(neueKerze(e));
        });
      };
      var malen = function () {
        ctx.clearRect(0, 0, W, H);
        var cx = W / 2, cy = H * .45;
        ebenen.forEach(function (e) {
          var dx = mx * 30 * e.tiefe, dy = my * 36 * e.tiefe;
          var Y = function (v) { return H * e.mitte - v * H * e.hub + dy; };
          e.liste.forEach(function (k, i) {
            var x = Math.round(i * e.a - e.versatz + dx);
            if (x < -e.a || x > W + e.a) return;
            var ex = (x - cx) / (W * .36), ey = (Y(k.c) - cy) / (H * .3), d = Math.min(1, ex * ex + ey * ey);
            var auf = k.c >= k.o, y1 = Y(Math.max(k.o, k.c)), y2 = Y(Math.min(k.o, k.c));
            ctx.globalAlpha = e.alpha * (.2 + .8 * d);
            ctx.strokeStyle = ctx.fillStyle = auf ? '#d4ad5a' : '#8193b3'; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(x + .5, Y(k.h)); ctx.lineTo(x + .5, y1); ctx.moveTo(x + .5, y2); ctx.lineTo(x + .5, Y(k.l)); ctx.stroke();
            if (auf) ctx.fillRect(x - Math.floor(e.b / 2), y1, e.b, Math.max(1, y2 - y1));
            else ctx.strokeRect(x - Math.floor(e.b / 2) + .5, y1 + .5, e.b - 1, Math.max(1, y2 - y1 - 1));
          });
        });
        ctx.globalAlpha = 1;
      };
      var schritt = function (t) {
        if (!letzte) letzte = t;
        var dt = Math.min(.05, (t - letzte) / 1000); letzte = t;
        ebenen.forEach(function (e) {
          e.versatz += e.tempo * dt;
          while (e.versatz >= e.a) { e.versatz -= e.a; e.liste.shift(); e.liste.push(neueKerze(e)); }
        });
        malen();
        var p = parseFloat(kopfEl.style.getPropertyValue('--p')) || 0;
        if (p < 1 && !document.hidden) requestAnimationFrame(schritt); else { laeuft = false; letzte = 0; }
      };
      var starten = function () { if (!laeuft && !ruhig && !document.hidden) { laeuft = true; requestAnimationFrame(schritt); } };
      aufbauen(); malen(); starten();
      addEventListener('resize', function () { aufbauen(); malen(); });
      addEventListener('scroll', starten, { passive: true });
      document.addEventListener('visibilitychange', starten);
    }
    setTimeout(function () { kopfEl.classList.add('geladen'); }, 2800);
    zeichnen();
    var weiter = kopfEl.querySelector('.weiter');
    if (weiter) weiter.addEventListener('click', function (ev) {
      ev.preventDefault(); scrollTo({ top: kopfEl.offsetHeight - 56, behavior: ruhig ? 'auto' : 'smooth' });
    });
    if (mini) mini.querySelector('.mini-marke').addEventListener('click', function (ev) { ev.preventDefault(); scrollTo({ top: 0, behavior: ruhig ? 'auto' : 'smooth' }); });
  } else if (mini) { mini.classList.add('sichtbar', 'immer'); mini.setAttribute('aria-hidden', 'false'); alle('a, button', mini).forEach(function (x) { x.tabIndex = 0; }); }

  /* Lesefortschritt oben */
  var f = document.querySelector('.fortschritt');
  if (f) addEventListener('scroll', function () {
    var h = document.body.scrollHeight - innerHeight;
    f.style.width = (h > 0 ? Math.min(100, scrollY / h * 100) : 0) + '%';
  }, { passive: true });

  /* Hinweis unten */
  var toast = document.querySelector('.toast'), toastZeit;
  function melden(text) {
    if (!toast) return;
    toast.textContent = text; toast.classList.add('zeigen');
    clearTimeout(toastZeit); toastZeit = setTimeout(function () { toast.classList.remove('zeigen'); }, 2200);
  }

  var basis = body.dataset.basis || '';
  var gelesen = lesen('fu-gelesen', {}), merk = lesen('fu-merkliste', {});
  var steuerungen = [];
  function alleAktualisieren(verzoegert) {
    steuerungen.forEach(function (s) { s.aktualisieren(verzoegert); });
    var mz = Object.keys(merk).length;
    alle('.merk-zahl').forEach(function (z) { z.textContent = mz; z.hidden = !mz; });
  }

  /* Je Bereich (Tag, Woche): Aufklappen, Gelesen, Merken, Rubrik-Reiter */
  function bereichStarten(root) {
    var ausgabe = root.dataset.ausgabe || '', datum = root.dataset.datum || '';
    var meldungen = alle('.meldung', root);
    function key(m) { return ausgabe + '/' + m.id; }
    function setOffen(m, offen) {
      m.classList.toggle('offen', offen);
      m.querySelector('.m-auf').setAttribute('aria-expanded', offen ? 'true' : 'false');
    }
    meldungen.forEach(function (m) {
      setOffen(m, false);
      m.querySelector('.m-auf').addEventListener('click', function () { setOffen(m, !m.classList.contains('offen')); knopfAlleAuf(); });
      m.querySelector('.m-gelesen').addEventListener('click', function () {
        var k = key(m);
        if (gelesen[k]) delete gelesen[k]; else { gelesen[k] = 1; setOffen(m, false); }
        schreiben('fu-gelesen', gelesen); alleAktualisieren(true);
      });
      m.querySelector('.m-merken').addEventListener('click', function () {
        var k = key(m);
        if (merk[k]) { delete merk[k]; melden('Von der Merkliste entfernt'); }
        else {
          merk[k] = {
            titel: m.querySelector('.m-titel').textContent,
            rubrik: m.querySelector('.m-rubrik').textContent,
            datum: datum,
            href: 'archiv/' + ausgabe + '.html#' + m.id,
            text: alle('.m-innen > p:not(.quelle)', m).map(function (p) { return p.textContent; }),
            beratung: (m.querySelector('.tipp p') || {}).textContent || '',
            quellen: alle('.quelle a', m).map(function (a) { return { name: a.textContent, url: a.href }; }),
            zeit: Date.now()
          };
          melden('Auf die Merkliste gesetzt');
        }
        schreiben('fu-merkliste', merk); alleAktualisieren(); merklisteZeichnen();
      });
    });

    var filter = 'alle', nurUngelesen = root.querySelector('.nur-ungelesen'), leiste = root.querySelector('.leiste');
    var reiter = alle('.reiter [role="tab"]', root);
    function filtern() {
      var sichtbar = 0;
      meldungen.forEach(function (m) {
        var an = (filter === 'alle' || m.dataset.rubrik === filter) && !(nurUngelesen && nurUngelesen.checked && gelesen[key(m)]);
        m.hidden = !an; if (an) sichtbar++;
      });
      alle('.block[data-rubrik]', root).forEach(function (s) {
        s.hidden = !alle('.meldung', s).some(function (m) { return !m.hidden; });
      });
      var leer = root.querySelector('.leer'); if (leer) leer.hidden = sichtbar > 0;
    }
    function waehlen(btn, fokus) {
      reiter.forEach(function (b) { var an = b === btn; b.setAttribute('aria-selected', an); b.tabIndex = an ? 0 : -1; });
      filter = btn.dataset.filter; filtern();
      if (fokus) btn.focus();
    }
    reiter.forEach(function (b, i) {
      b.tabIndex = i ? -1 : 0;
      b.addEventListener('click', function () {
        waehlen(b);
        if (leiste && leiste.getBoundingClientRect().top < 0) leiste.scrollIntoView({ behavior: ruhig ? 'auto' : 'smooth' });
      });
      b.addEventListener('keydown', function (ev) {
        var n = { ArrowRight: 1, ArrowLeft: -1 }[ev.key]; if (!n) return;
        ev.preventDefault(); waehlen(reiter[(i + n + reiter.length) % reiter.length], true);
      });
    });
    if (nurUngelesen) nurUngelesen.addEventListener('change', filtern);

    var alleAuf = root.querySelector('.alle-auf');
    function knopfAlleAuf() {
      if (!alleAuf) return;
      var offen = meldungen.filter(function (m) { return !m.hidden; }).every(function (m) { return m.classList.contains('offen'); });
      alleAuf.textContent = offen ? 'Alle zuklappen' : 'Alle aufklappen';
    }
    if (alleAuf) alleAuf.addEventListener('click', function () {
      var zu = alleAuf.textContent.indexOf('zu') > -1;
      meldungen.forEach(function (m) { if (!m.hidden) setOffen(m, !zu); }); knopfAlleAuf();
    });
    var alleGel = root.querySelector('.alle-gelesen');
    if (alleGel) alleGel.addEventListener('click', function () {
      meldungen.forEach(function (m) { if (!m.hidden) gelesen[key(m)] = 1; });
      schreiben('fu-gelesen', gelesen); alleAktualisieren(true); melden('Alles als gelesen markiert');
    });

    var ring = root.querySelector('.fortschritt-lesen .ring'), zahl = root.querySelector('.gelesen-zahl');
    function aktualisieren(verzoegert) {
      var n = 0;
      meldungen.forEach(function (m) {
        var g = !!gelesen[key(m)], s = !!merk[key(m)]; if (g) n++;
        m.classList.toggle('ist-gelesen', g); m.classList.toggle('ist-gemerkt', s);
        m.querySelector('.m-gelesen').setAttribute('aria-pressed', g);
        m.querySelector('.m-gelesen').title = g ? 'Als ungelesen markieren' : 'Als gelesen markieren';
        m.querySelector('.m-merken').setAttribute('aria-pressed', s);
        m.querySelector('.m-merken').title = s ? 'Von der Merkliste nehmen' : 'Für Kundentermin merken';
      });
      if (zahl) zahl.textContent = n;
      if (ring) ring.style.strokeDashoffset = 94.25 * (1 - (meldungen.length ? n / meldungen.length : 0));
      if (verzoegert && nurUngelesen && nurUngelesen.checked) setTimeout(filtern, 450); else filtern();
      knopfAlleAuf();
    }
    function oeffne(m, sanft) {
      if (reiter[0]) waehlen(reiter[0]);
      if (nurUngelesen) { nurUngelesen.checked = false; filtern(); }
      setOffen(m, true); knopfAlleAuf();
      m.scrollIntoView({ behavior: sanft && !ruhig ? 'smooth' : 'auto', block: 'start' });
      m.classList.add('blitz'); setTimeout(function () { m.classList.remove('blitz'); }, 1600);
    }
    alle('.kurz a[href^="#"]:not([data-ziel])', root).forEach(function (a) {
      a.addEventListener('click', function (ev) {
        var m = document.getElementById(a.getAttribute('href').slice(1));
        if (m && root.contains(m)) { ev.preventDefault(); oeffne(m, true); }
      });
    });
    return { root: root, aktualisieren: aktualisieren, oeffne: oeffne };
  }
  alle('.ansicht').forEach(function (r) { steuerungen.push(bereichStarten(r)); });

  /* Bereiche wechseln ohne Neuladen (Tagesbriefing, Wochenüberblick, Archiv) */
  var bereiche = alle('.ansicht'), zielLinks = alle('[data-ziel]'), wechselZeit;
  function strichSetzen(nav) {
    var s = nav.querySelector('.nav-strich'), a = nav.querySelector('[aria-current="page"]');
    if (!s || !a || !a.offsetWidth) return;
    s.style.width = a.offsetWidth + 'px'; s.style.transform = 'translateX(' + a.offsetLeft + 'px)'; s.classList.add('da');
  }
  function alleStriche() { alle('.kopf-nav').forEach(strichSetzen); }
  function bereichZeigen(name, animiert) {
    var neu = bereiche.filter(function (b) { return b.dataset.ansicht === name; })[0];
    if (!neu) return;
    var alt = bereiche.filter(function (b) { return b.classList.contains('aktiv'); })[0];
    zielLinks.forEach(function (a) { if (a.closest('.kopf-nav')) { if (a.dataset.ziel === name) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); } });
    alleStriche();
    try { history.replaceState(null, '', name === 'tag' ? location.pathname : '#' + name); } catch (e) {}
    var miniZeile = document.querySelector('.mini-datum'), kopfZ = neu.querySelector('.ansicht-titel');
    if (miniZeile && kopfZ) miniZeile.textContent = kopfZ.textContent + ' · ' + (neu.querySelector('.ansicht-zeile') || {}).textContent;
    if (alt === neu) return;
    clearTimeout(wechselZeit);
    var start = kopfEl ? kopfEl.offsetHeight - 56 : 0;
    var tauschen = function () {
      bereiche.forEach(function (b) { if (b !== neu) { b.hidden = true; b.classList.remove('aktiv', 'raus', 'rein'); } });
      neu.hidden = false; neu.classList.add('aktiv');
      if (animiert && !ruhig) { neu.classList.remove('rein'); void neu.offsetWidth; neu.classList.add('rein'); }
      alle('.einblenden', neu).forEach(function (x) { x.classList.add('da'); });
      if (animiert && scrollY > start + 4) scrollTo({ top: start, behavior: 'auto' });
    };
    if (animiert && !ruhig && alt) {
      alt.classList.add('raus');
      if (scrollY < start - 4) scrollTo({ top: start, behavior: 'smooth' });
      wechselZeit = setTimeout(tauschen, 260);
    } else tauschen();
  }
  zielLinks.forEach(function (a) {
    a.addEventListener('click', function (ev) {
      if (!bereiche.length) return;
      ev.preventDefault(); bereichZeigen(a.dataset.ziel, true);
    });
  });
  addEventListener('resize', alleStriche);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(alleStriche);
  setTimeout(alleStriche, 400);

  function ankerOeffnen(id, sanft) {
    if (!id) return;
    if (/^(tag|woche|archiv)$/.test(id)) { bereichZeigen(id, false); return; }
    var m = document.getElementById(id); if (!m || !m.classList.contains('meldung')) return;
    var b = m.closest('.ansicht'); if (b) bereichZeigen(b.dataset.ansicht, false);
    steuerungen.forEach(function (s) { if (s.root.contains(m)) s.oeffne(m, sanft); });
  }

  /* Gesprächsaufhänger kopieren */
  alle('.kopieren').forEach(function (b) {
    b.addEventListener('click', function () {
      var text = b.parentNode.querySelector('blockquote').textContent;
      function ok() { b.textContent = 'Kopiert'; b.classList.add('ok'); setTimeout(function () { b.textContent = 'Text kopieren'; b.classList.remove('ok'); }, 1800); }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(ok, function () { melden('Kopieren nicht möglich'); });
      else { var ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); ok(); } catch (e) {} ta.remove(); }
    });
  });

  /* Merkliste */
  var panel = document.getElementById('merkliste'), schleier = document.querySelector('.merk-schleier'), zuletzt;
  function el(tag, cls, text) { var x = document.createElement(tag); if (cls) x.className = cls; if (text) x.textContent = text; return x; }
  function datumKurz(iso) { var p = (iso || '').split('-'); return p.length === 3 ? p[2] + '.' + p[1] + '.' + p[0] : ''; }
  function eintraege() { return Object.keys(merk).map(function (k) { return [k, merk[k]]; }).sort(function (a, b) { return (b[1].zeit || 0) - (a[1].zeit || 0); }); }
  function merklisteZeichnen() {
    if (!panel) return;
    var liste = panel.querySelector('.merk-liste'); liste.textContent = '';
    var es = eintraege();
    panel.querySelector('.merk-leer').hidden = es.length > 0;
    panel.querySelector('.merk-fuss').hidden = !es.length;
    es.forEach(function (pair) {
      var k = pair[0], d = pair[1], li = el('li', 'merk-eintrag');
      li.appendChild(el('p', 'merk-meta', d.rubrik + ' · ' + datumKurz(d.datum)));
      var a = el('a', 'merk-titel', d.titel); a.href = basis + d.href; li.appendChild(a);
      if (d.beratung) li.appendChild(el('p', 'merk-tipp', d.beratung));
      var x = el('button', 'merk-weg', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Entfernen: ' + d.titel);
      x.addEventListener('click', function () { delete merk[k]; schreiben('fu-merkliste', merk); alleAktualisieren(); merklisteZeichnen(); });
      li.appendChild(x); liste.appendChild(li);
    });
  }
  function merkAuf() {
    zuletzt = document.activeElement; merklisteZeichnen();
    panel.classList.add('offen'); schleier.classList.add('offen'); panel.removeAttribute('inert'); panel.setAttribute('aria-hidden', 'false');
    body.classList.add('gesperrt'); setTimeout(function () { panel.querySelector('.merk-zu').focus(); }, 50);
  }
  function merkZu() {
    panel.classList.remove('offen'); schleier.classList.remove('offen'); panel.setAttribute('inert', ''); panel.setAttribute('aria-hidden', 'true');
    body.classList.remove('gesperrt'); if (zuletzt) zuletzt.focus();
  }
  if (panel) {
    panel.setAttribute('inert', '');
    alle('.merk-oeffnen').forEach(function (b) { b.addEventListener('click', merkAuf); });
    panel.querySelector('.merk-zu').addEventListener('click', merkZu);
    schleier.addEventListener('click', merkZu);
    addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && panel.classList.contains('offen')) merkZu(); });
    document.getElementById('merk-leeren').addEventListener('click', function () {
      if (!confirm('Merkliste wirklich leeren?')) return;
      merk = {}; schreiben('fu-merkliste', merk); alleAktualisieren(); merklisteZeichnen();
    });
    document.getElementById('merk-drucken').addEventListener('click', function () {
      var ziel = document.getElementById('druck-bereich'); ziel.textContent = '';
      ziel.appendChild(el('h1', '', 'Merkliste für Kundentermine'));
      ziel.appendChild(el('p', 'druck-datum', 'Stand ' + new Date().toLocaleDateString('de-DE')));
      eintraege().forEach(function (pair) {
        var d = pair[1], a = el('article');
        a.appendChild(el('p', 'kicker', d.rubrik + ' · ' + datumKurz(d.datum)));
        a.appendChild(el('h2', '', d.titel));
        (d.text || []).forEach(function (p) { a.appendChild(el('p', '', p)); });
        if (d.beratung) a.appendChild(el('p', 'druck-tipp', 'Für die Beratung: ' + d.beratung));
        if (d.quellen && d.quellen.length) a.appendChild(el('p', 'quelle', 'Quelle: ' + d.quellen.map(function (q) { return q.name + ' (' + q.url + ')'; }).join(' · ')));
        ziel.appendChild(a);
      });
      body.classList.add('druck-merkliste'); window.print();
    });
    addEventListener('afterprint', function () { body.classList.remove('druck-merkliste'); });
  }

  /* Sanftes Einblenden beim Scrollen */
  if (!ruhig && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('da'); io.unobserve(en.target); } });
    }, { rootMargin: '0px 0px -8% 0px' });
    alle('.kurz, .kz, .block, .aufhaenger').forEach(function (x, i) { x.classList.add('einblenden'); x.style.transitionDelay = (x.classList.contains('kz') ? (i % 6) * 60 : 0) + 'ms'; io.observe(x); });
  }

  alleAktualisieren();
  ankerOeffnen(location.hash.slice(1), false);
  addEventListener('hashchange', function () { ankerOeffnen(location.hash.slice(1), true); });
  alleStriche();
})();
</script>"""

MERKLISTE = """<div class="merk-schleier"></div>
<aside class="merk-panel" id="merkliste" role="dialog" aria-modal="true" aria-labelledby="merk-titel" aria-hidden="true">
  <div class="merk-kopf"><div><p class="kicker">Für Kundentermine</p><h2 id="merk-titel">Merkliste</h2></div><button type="button" class="merk-zu" aria-label="Merkliste schließen">×</button></div>
  <ul class="merk-liste"></ul>
  <div class="merk-leer"><p class="leer-titel">Noch nichts gemerkt.</p><p>Tippe bei einer Meldung auf das Lesezeichen. Sie bleibt hier gespeichert, auch über mehrere Tage, bis du sie entfernst.</p></div>
  <div class="merk-fuss"><button type="button" class="knopf" id="merk-drucken">Drucken</button><button type="button" class="text-knopf" id="merk-leeren">Liste leeren</button></div>
</aside>
<div class="druck-bereich" id="druck-bereich"></div>
<div class="toast" role="status" aria-live="polite"></div>"""



def laufband(daten):
    """Laufband mit den echten Kennzahlen der Ausgabe."""
    teile = []
    for k in daten.get("kennzahlen") or []:
        m = re.search(r"[+−-]\s?\d+(?:,\d+)?\s?%", k.get("stand", ""))
        chg = ""
        if m:
            art = "minus" if m.group(0)[0] in "−-" else "plus"
            chg = f'<span class="lb-chg {art}">{"▼" if art == "minus" else "▲"} {e(m.group(0))}</span>'
        teile.append(f'<span class="lb-eintrag"><span class="lb-name">{e(k["name"])}</span>'
                     f'<span class="lb-wert">{e(k["wert"])}</span>{chg}</span><i class="lb-raute"></i>')
    if not teile:
        return ""
    band = "".join(teile)
    return (f'<div class="laufband" aria-label="Kennzahlen"><div class="lb-band">{band}'
            f'<span aria-hidden="true" class="lb-kopie">{band}</span></div></div>')


def ausgabe_nr(daten):
    """Laufende Nummer der Ausgabe (je Typ), gezählt aus den Daten-Dateien."""
    nr = 0
    for p in DATEN.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if d.get("typ") == daten.get("typ") and d.get("datum", "") <= daten.get("datum", ""):
            nr += 1
    return max(nr, 1)


def kopf(titel, zeile, archiv_link, aktiv, daten=None, kombi=False):
    def link(key, text, kurz):
        cur = ' aria-current="page"' if key == aktiv else ""
        beschriftung = f'<span class="l-lang">{text}</span><span class="l-kurz">{kurz}</span>'
        if kombi:
            return f'<a href="#{key}" data-ziel="{key}"{cur}>{beschriftung}</a>'
        return f'<a href="{archiv_link}index.html#{key}"{cur}>{beschriftung}</a>'
    nav = (f'{link("tag", "Tagesbriefing", "Heute")}{link("woche", "Wochenüberblick", "Woche")}{link("archiv", "Archiv", "Archiv")}'
           '<span class="nav-strich" aria-hidden="true"></span>')
    knoepfe = ('<button class="thema merk-oeffnen" type="button">Merkliste <span class="merk-zahl" hidden>0</span></button>'
               '<button class="thema thema-wechsel" type="button">Hell / Dunkel</button>')
    voll = daten is not None
    woche = bool(daten and daten.get("typ") == "woche")
    weiter_text = "Zum Überblick" if woche else "Zum Briefing"
    if voll and daten.get("rubriken"):
        rubriken = [r for r in daten.get("rubriken", []) if r.get("meldungen")]
        anzahl = sum(len(r["meldungen"]) for r in rubriken)
        worte = sum(len(" ".join((m.get("text") if isinstance(m.get("text"), list) else [m.get("text", "")]) + [m.get("beratung", "")]).split())
                    for r in rubriken for m in r["meldungen"])
        jahr = daten["datum"][:4]
        oben = f'Ausgabe Nr. {ausgabe_nr(daten)} · Jahrgang {jahr}'
        eckdaten = (f'<ul class="eckdaten"><li><b>{anzahl}</b> Meldungen</li><li><b>{len(rubriken)}</b> Rubriken</li>'
                    f'<li><b>{max(1, round(worte / 200))}</b> Min. Lesezeit</li></ul>')
        weiter = f'<a class="weiter" href="#inhalt-start"><span>{weiter_text}</span><i aria-hidden="true"></i></a>'
        finanz = '<canvas class="kerzen" aria-hidden="true"></canvas>' + laufband(daten)
    elif voll:
        oben = "Erscheint jeden Sonntag"
        eckdaten = ('<ul class="eckdaten"><li><b>5</b> Punkte der Woche</li><li><b>6</b> Kennzahlen im Vergleich</li>'
                    '<li><b>3</b> Gesprächsaufhänger</li></ul>')
        weiter = '<a class="weiter" href="#inhalt-start"><span>Zur Vorschau</span><i aria-hidden="true"></i></a>'
        finanz = '<canvas class="kerzen" aria-hidden="true"></canvas>' + laufband(daten)
    else:
        oben, eckdaten, weiter, finanz = "Für die Beratung", "", "", ""
    mini = f"""<div class="kopf-mini" aria-hidden="true">
  <div class="mini-innen">
    <a class="mini-marke" href="#top" tabindex="-1">{MARKE}<i></i></a>
    <span class="mini-datum">{titel} · {zeile}</span>
    <nav class="kopf-nav mini-nav" aria-label="Bereiche">{nav.replace('<a ', '<a tabindex="-1" ')}</nav>
    <span class="kopf-knoepfe">{knoepfe.replace('type="button"', 'type="button" tabindex="-1"')}</span>
  </div>
</div>""" if voll else ""
    return f"""<div class="fortschritt" aria-hidden="true"></div>
{mini}<header class="kopf{' kopf-voll' if voll else ''}" id="top">
  {finanz}
  <div class="kopf-meta spalte-breit"><span><b>Für die Beratung</b></span><span class="kopf-knoepfe">{knoepfe}</span></div>
  <div class="kopf-inhalt">
    <p class="kopf-oben">{oben}</p>
    <h1><span>{MARKE}</span></h1>
    <div class="ornament" aria-hidden="true"><i></i></div>
    <p class="ausgabe">{titel} · {zeile}</p>
    {eckdaten}
    <nav class="kopf-nav haupt-nav" aria-label="Bereiche">{nav}</nav>
  </div>
  {weiter}
</header>
<span id="inhalt-start"></span>"""


def fuss_html(text):
    zeile = f"<p>{text}</p>" if text else ""
    return f"""<footer class="spalte fuss">
  {zeile}
  <p class="hinweis"><span>Automatisch zusammengestellt aus öffentlichen Quellen. Keine Anlage- oder Rechtsberatung; Kurse und Zinsen vor Kundengesprächen kurz prüfen.</span></p>
  <p class="marke-fuss">{MARKE}</p>
</footer>"""


def veraenderung(text):
    """Hebt Veränderungen wie '−0,06 %' oder '+1,2 %' farbig mit Pfeil hervor."""
    def ersetzen(m):
        wert = m.group(0)
        art = "minus" if wert[0] in "−-" else "plus"
        return f'<span class="chg {art}">{wert}</span>'
    return re.sub(r"[+−-]\s?\d+(?:,\d+)?\s?%", ersetzen, text)

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
          "September", "Oktober", "November", "Dezember"]


def e(text):
    return html.escape(str(text or ""), quote=True)


def datum_lang(iso):
    d = dt.date.fromisoformat(iso)
    return f"{WOCHENTAGE[d.weekday()]}, {d.day}. {MONATE[d.month - 1]} {d.year}"


def quellen_html(quellen):
    teile = []
    for q in quellen or []:
        name = e(q.get("name"))
        datum = f", {e(q['datum'])}" if q.get("datum") else ""
        if q.get("url"):
            teile.append(f'<a href="{e(q["url"])}" target="_blank" rel="noopener">{name}</a>{datum}')
        else:
            teile.append(f"{name}{datum}")
    if not teile:
        return ""
    wort = "Quelle" if len(teile) == 1 else "Quellen"
    return f'<p class="quelle">{wort}: {" · ".join(teile)}</p>'


ICON_MERKEN = ('<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5h8v11l-4-2.8-4 2.8z"/></svg>')
ICON_GELESEN = ('<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.25"/><path d="M5.2 8.2l1.9 1.9 3.7-3.9"/></svg>')
ICON_PFEIL = ('<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4"/></svg>')


def anriss(absaetze, laenge=150):
    """Erster Satz der Meldung als Vorschau im zugeklappten Zustand."""
    text = " ".join(a for a in absaetze if a)
    satz = text
    for m in re.finditer(r"(\S+)[.!?]\s+(?=[A-ZÄÖÜ„])", text):
        wort = m.group(1)
        if wort.isdigit() or (len(wort) <= 2 and wort not in ("%", "€")):  # „16. Oktober“, „z. B.“ sind kein Satzende
            continue
        satz = text[:m.end()].strip()
        break
    return satz if len(satz) <= laenge else satz[:laenge].rsplit(" ", 1)[0] + " …"


def meldung_html(m, rubrik, ri, mi, px=""):
    mid = px + (m.get("id") or f"m{ri}-{mi}")
    absaetze = m["text"] if isinstance(m.get("text"), list) else [m.get("text", "")]
    text = "".join(f"<p>{e(a)}</p>" for a in absaetze if a)
    tipp = (f'<div class="tipp"><span class="tipp-label">Für die Beratung</span>'
            f'<p>{e(m["beratung"])}</p></div>') if m.get("beratung") else ""
    worte = len(" ".join(absaetze + [m.get("beratung", "")]).split())
    q = (m.get("quellen") or [{}])[0]
    meta = " · ".join(x for x in [e(q.get("name")), e(q.get("datum")), f"{max(1, round(worte / 200))} Min."] if x)
    return f"""<article class="meldung" id="{e(mid)}" data-rubrik="r{ri}">
  <div class="m-kopf">
    <h3><button class="m-auf" type="button" aria-expanded="true" aria-controls="{e(mid)}-text">
      <span class="m-rubrik">{e(rubrik)}</span>
      <span class="m-titel">{e(m["titel"])}</span>
      <span class="m-anriss">{e(anriss(absaetze))}</span>
      <span class="m-meta">{meta}<span class="m-pfeil">{ICON_PFEIL}</span></span>
    </button></h3>
    <div class="m-aktionen">
      <button class="m-merken" type="button" aria-pressed="false" title="Für Kundentermin merken">{ICON_MERKEN}<span class="sr">Merken</span></button>
      <button class="m-gelesen" type="button" aria-pressed="false" title="Als gelesen markieren">{ICON_GELESEN}<span class="sr">Gelesen</span></button>
    </div>
  </div>
  <div class="m-text" id="{e(mid)}-text"><div class="m-innen">{text}{tipp}{quellen_html(m.get("quellen"))}</div></div>
</article>"""


def kennzahlen_html(daten, px=""):
    kz = daten.get("kennzahlen") or []
    if not kz:
        return ""
    zeilen = []
    for k in kz:
        quelle = (f' · <a href="{e(k["quelle_url"])}" target="_blank" rel="noopener">{e(k.get("quelle_name", "Quelle"))}</a>'
                  if k.get("quelle_url") else (f" · {e(k['quelle_name'])}" if k.get("quelle_name") else ""))
        vorher = f'<span class="kz-vorher">Vorwoche {e(k["vorher"])}</span>' if k.get("vorher") else ""
        zeilen.append(
            f'<div class="kz"><span class="kz-name">{e(k["name"])}</span>'
            f'<span class="kz-wert">{e(k["wert"])}</span>{vorher}'
            f'<span class="kz-stand">{veraenderung(e(k.get("stand")))}{quelle}</span></div>')
    hinweis = f'<p class="kz-hinweis">{e(daten["kennzahlen_hinweis"])}</p>' if daten.get("kennzahlen_hinweis") else ""
    return (f'<section class="block" aria-labelledby="{px}h-kz"><p class="kicker">Märkte &amp; Zinsen</p><h2 id="{px}h-kz">Zahlen auf einen Blick</h2>'
            f'<div class="kz-liste">{"".join(zeilen)}</div>{hinweis}</section>')


def ausgabe_titel(daten):
    woche = daten.get("typ") == "woche"
    titel = "Finanz-Wochenüberblick" if woche else "Finanz-Morgenbriefing"
    zeile = daten.get("unterzeile") or (
        f"{daten.get('kw', '')} · {datum_lang(daten['datum'])}" if woche else datum_lang(daten["datum"]))
    return titel, zeile


def ansicht_kopf(kicker, titel, zeile):
    return (f'<header class="ansicht-kopf"><p class="kicker">{e(kicker)}</p><h2 class="ansicht-titel">{e(titel)}</h2>'
            f'<p class="ansicht-zeile">{e(zeile)}</p></header>')


def ansicht_inhalt(daten, archiv_link):
    """Inhalt einer Ausgabe (Tag oder Woche) ohne Seitenrahmen. Wochen-IDs bekommen das Präfix „w-“."""
    woche = daten.get("typ") == "woche"
    px = "w-" if woche else ""
    titel, zeile = ausgabe_titel(daten)
    kopf_html = ansicht_kopf("Wochenüberblick" if woche else "Tagesbriefing", titel, zeile)

    top_titel = "Die Woche in 5 Punkten" if woche else "In einer Minute"
    top = "".join(
        f'<li><a href="#{px}{e(t["anker"])}">{e(t["titel"])}</a><span>{e(t.get("kurz"))}</span></li>'
        if t.get("anker") else f'<li><strong>{e(t["titel"])}</strong><span>{e(t.get("kurz"))}</span></li>'
        for t in daten.get("top", []))
    top_html = f'<section class="kurz" aria-labelledby="{px}h-kurz"><p class="kicker">Überblick</p><h2 id="{px}h-kurz">{top_titel}</h2><ol>{top}</ol></section>' if top else ""

    rubriken = [r for r in daten.get("rubriken", []) if r.get("meldungen")]
    anzahl = sum(len(r["meldungen"]) for r in rubriken)
    reiter = f'<button type="button" role="tab" aria-selected="true" data-filter="alle">Alle <span class="zahl">{anzahl}</span></button>' + "".join(
        f'<button type="button" role="tab" aria-selected="false" data-filter="r{i}">{e(r["titel"])} <span class="zahl">{len(r["meldungen"])}</span></button>'
        for i, r in enumerate(rubriken))
    leiste_html = f"""<div class="leiste">
  <div class="reiter" role="tablist" aria-label="Rubriken">{reiter}</div>
  <div class="werkzeuge">
    <div class="fortschritt-lesen" aria-live="polite"><svg viewBox="0 0 36 36" aria-hidden="true"><circle class="ring-grund" cx="18" cy="18" r="15"/><circle class="ring" cx="18" cy="18" r="15"/></svg><span><b class="gelesen-zahl">0</b> von {anzahl} gelesen</span></div>
    <div class="werkzeug-knoepfe">
      <label class="schalter"><input type="checkbox" class="nur-ungelesen"><span class="schalter-bahn" aria-hidden="true"></span>Nur ungelesene</label>
      <button type="button" class="text-knopf alle-auf">Alle aufklappen</button>
      <button type="button" class="text-knopf alle-gelesen">Alle gelesen</button>
    </div>
  </div>
</div>""" if rubriken else ""

    abschnitte = "".join(
        f'<section class="block" data-rubrik="r{i}" aria-labelledby="{px}r{i}"><p class="kicker">Rubrik {i + 1:02d}</p><h2 id="{px}r{i}">{e(r["titel"])}</h2>'
        f'{"".join(meldung_html(m, r["titel"], i, j, px) for j, m in enumerate(r["meldungen"]))}</section>'
        for i, r in enumerate(rubriken))
    leer_html = ('<div class="leer" hidden><p class="leer-titel">Alles gelesen.</p>'
                 '<p>In dieser Ansicht gibt es keine ungelesenen Meldungen mehr.</p></div>') if rubriken else ""

    auf = daten.get("aufhaenger") or []
    auf_titel = "Für deine Kundentermine diese Woche" if woche else "Gesprächsaufhänger"
    auf_html = (f'<section class="aufhaenger" aria-labelledby="{px}h-auf"><p class="kicker">Für das Gespräch</p><h2 id="{px}h-auf">{auf_titel}</h2>'
                + "".join(f'<figure class="zitat"><blockquote>{e(a)}</blockquote>'
                          f'<button type="button" class="kopieren">Text kopieren</button></figure>' for a in auf)
                + "</section>") if auf else ""

    vorschau_html = ""
    if woche and not rubriken:
        teile = [("Die Woche in 5 Punkten", "Die fünf wichtigsten Fakten der Woche, in je ein, zwei Sätzen."),
                 ("Zahlen im Wochenvergleich", "DAX, MSCI World, EZB-Zins, Bauzins, Inflation und Bundesanleihe – Stand Freitag gegen Vorwoche."),
                 ("Rückblick nach Themen", "Altersvorsorge, Versicherungen, Geldanlage, Baufinanzierung, Regulierung und was Kunden lesen."),
                 ("Ausblick auf die neue Woche", "Termine und Entscheidungen, die für deine Beratung zählen."),
                 ("Für deine Kundentermine", "Drei Gesprächsaufhänger zum Kopieren.")]
        liste = "".join(f"<li><strong>{e(t)}</strong><span>{e(b)}</span></li>" for t, b in teile)
        vorschau_html = (f'<section class="kurz" aria-labelledby="w-h-vorschau"><p class="kicker">Vorschau</p>'
                         f'<h2 id="w-h-vorschau">{e(daten.get("vorschau_titel"))}</h2><ol>{liste}</ol>'
                         f'<p class="vorschau-link"><a href="#tag" data-ziel="tag">Zum heutigen Tagesbriefing →</a></p></section>')

    fuss = f'<p class="ansicht-fuss">{e(daten.get("fusszeile"))}</p>' if daten.get("fusszeile") else ""
    kz = "" if (woche and not rubriken) else kennzahlen_html(daten, px)
    return f"""{kopf_html}
{vorschau_html}
{top_html}
{kz}
{leiste_html}
<div class="meldungen">
{abschnitte}
{leer_html}
</div>
{auf_html}
{fuss}"""


def archiv_inhalt(link_praefix):
    eintraege = []
    ausgaben = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in DATEN.glob("*.json")]
    for p, d in sorted(ausgaben, key=lambda x: (x[1]["datum"], x[0].stem), reverse=True):
        art = "Wochenüberblick " + d.get("kw", "") if d.get("typ") == "woche" else "Morgenbriefing"
        eintraege.append(f'<li><a href="{link_praefix}{p.stem}.html">{e(datum_lang(d["datum"]))}</a> <span>{e(art)}</span></li>')
    return (ansicht_kopf("Alle Ausgaben", "Archiv", f"{len(eintraege)} Ausgaben, die neueste zuerst")
            + f'<ul class="archiv">{"".join(eintraege)}</ul>')


def seite_rahmen(hero_daten, titel, zeile, archiv_link, ansichten, aktiv, kombi):
    """ansichten: Liste (name, html, ausgabe, datum)."""
    views = "".join(
        f'<section class="ansicht{" aktiv" if name == aktiv else ""}" data-ansicht="{name}" data-ausgabe="{e(ausgabe)}" '
        f'data-datum="{e(datum)}"{"" if name == aktiv else " hidden"} aria-label="{e(name)}">{inhalt}</section>'
        for name, inhalt, ausgabe, datum in ansichten)
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{MARKE} · {titel} · {e(datum_lang(hero_daten['datum']))}</title>
<meta name="description" content="{titel} für die Finanzberatung">
{FONTS}
<style>{CSS}</style>
</head>
<body data-basis="{archiv_link}">
{kopf(titel, zeile, archiv_link, aktiv, hero_daten, kombi)}
<main class="spalte" id="inhalt">
{views}
</main>
{fuss_html("")}
{MERKLISTE}
{SKRIPT}
</body>
</html>
"""


def seite(daten, archiv_link, stem=""):
    """Einzelne Ausgabe (Archivseite) im vollen Design."""
    titel, zeile = ausgabe_titel(daten)
    name = "woche" if daten.get("typ") == "woche" else "tag"
    return seite_rahmen(daten, titel, zeile, archiv_link, [(name, ansicht_inhalt(daten, archiv_link), stem, daten["datum"])], name, False)


def neueste(typ):
    beste = None
    for p in DATEN.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("typ") == typ and (beste is None or (d["datum"], p.stem) > (beste[1]["datum"], beste[0].stem)):
            beste = (p, d)
    return beste


def gesamt_bauen():
    """Startseite mit allen drei Bereichen; Wechsel ohne Neuladen."""
    tag = neueste("tag")
    woche = neueste("woche")
    if not tag:
        return
    tp, td = tag
    if woche:
        wp, wd = woche
        w_stem = wp.stem
    else:
        d = dt.date.fromisoformat(td["datum"])
        sonntag = d + dt.timedelta(days=(6 - d.weekday()) or 7)
        wd = {"typ": "woche", "datum": td["datum"], "unterzeile": f"ab {datum_lang(sonntag.isoformat())}",
              "vorschau_titel": f"Der erste Wochenüberblick erscheint am {datum_lang(sonntag.isoformat())}."}
        w_stem = ""
    titel, zeile = ausgabe_titel(td)
    ansichten = [("tag", ansicht_inhalt(td, ""), tp.stem, td["datum"]),
                 ("woche", ansicht_inhalt(wd, ""), w_stem, wd["datum"]),
                 ("archiv", archiv_inhalt("archiv/"), "", "")]
    (SITE / "index.html").write_text(seite_rahmen(td, titel, zeile, "", ansichten, "tag", True), encoding="utf-8")
    weiterleitung = ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={ziel}">'
                     '<title>Finanz-Update</title><a href="{ziel}">Weiter</a>')
    (SITE / "woche.html").write_text(weiterleitung.format(ziel="index.html#woche"), encoding="utf-8")
    (SITE / "archiv" / "index.html").write_text(weiterleitung.format(ziel="../index.html#archiv"), encoding="utf-8")


def hochladen(beschreibung):
    """Committet Daten und Webseite und lädt sie zu GitHub hoch (GitHub Pages zeigt docs/)."""
    git = ["git", "-C", str(BASIS)]
    if not (BASIS / ".git").exists() or not subprocess.run(git + ["remote"], capture_output=True, text=True).stdout.strip():
        print(f"Noch nicht online – nur lokal gebaut: {(SITE / 'index.html').as_uri()}")
        return
    subprocess.run(git + ["add", "-A", "daten", "docs"], check=True)
    if subprocess.run(git + ["diff", "--cached", "--quiet"]).returncode == 0:
        print("Keine Änderungen zum Hochladen.")
        return
    subprocess.run(git + ["commit", "-q", "-m", beschreibung], check=True)
    if subprocess.run(git + ["push", "-q", "origin", "HEAD:main"]).returncode != 0:
        subprocess.run(git + ["pull", "-q", "--rebase", "origin", "main"], check=True)
        subprocess.run(git + ["push", "-q", "origin", "HEAD:main"], check=True)
    print("Hochgeladen.")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nur_bauen = "--nur-bauen" in sys.argv
    if len(args) != 1:
        sys.exit(__doc__)
    quelle = Path(args[0]).resolve()
    daten = json.loads(quelle.read_text(encoding="utf-8"))
    (SITE / "archiv").mkdir(parents=True, exist_ok=True)
    (SITE / ".nojekyll").touch()

    (SITE / "archiv" / f"{quelle.stem}.html").write_text(seite(daten, "../", quelle.stem), encoding="utf-8")
    gesamt_bauen()
    print(f"Gebaut: docs/index.html (Tag, Woche, Archiv), docs/archiv/{quelle.stem}.html")
    if not nur_bauen:
        hochladen(f"{'Wochenüberblick' if daten.get('typ') == 'woche' else 'Briefing'} {quelle.stem}")


if __name__ == "__main__":
    main()
