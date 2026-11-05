/* Pokémon-Kartenpreise – Suche, Preisvergleich, Verlauf und Ausblick */
"use strict";

const API = "https://api.tcgdex.net/v2";
const EBAY_KAT = "183454";
const TAG = 86400000;
let daten = { karten: [] };

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const eur = (x, ziffern) => (x == null || isNaN(x) ? "–" : x.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: ziffern ?? (x < 100 ? 2 : 0) }));
const usd = (x) => (x == null ? "–" : x.toLocaleString("de-DE", { style: "currency", currency: "USD" }));
const datum = (d) => new Date(d).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
const prozent = (x) => (x > 0 ? "+" : "") + x.toLocaleString("de-DE", { maximumFractionDigits: 1 }) + " %";
const tageAlt = (d) => Math.round((Date.now() - new Date(d)) / TAG);

async function holeJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

/* ------------------------------------------------------------------ Thema */
$("#thema").addEventListener("click", () => {
  const html = document.documentElement;
  const neu = html.dataset.theme === "light" ? "dark" : "light";
  html.dataset.theme = neu;
  try { localStorage.setItem("pk-thema", neu); } catch (e) {}
});

/* ------------------------------------------------------------------ Beobachtete Karten */
async function ladeListe() {
  try {
    daten = await holeJson("daten.json?" + Date.now());
  } catch (e) {
    $("#liste").innerHTML = '<p class="hinweis">Noch keine Daten – der Abruf läuft zum ersten Mal.</p>';
    return;
  }
  $("#rabatt").textContent = daten.rabatt_prozent ?? 20;
  $("#stand").textContent = `Stand ${new Date(daten.stand).toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" })} · eBay ${daten.ebay_aktiv ? "aktiv" : "noch nicht eingerichtet"}`;
  $("#liste").innerHTML = daten.karten.map(kachelBeobachtet).join("") || '<p class="hinweis">Noch keine Karten in der Beobachtungsliste.</p>';
  const deals = daten.karten.flatMap((k) => (k.deals || []).map((d) => ({ k, d })));
  $("#deals").innerHTML = deals.slice(0, 8).map(({ k, d }) => `
    <a class="deal" href="${esc(d.url)}" target="_blank" rel="noopener">
      ${k.bild ? `<img src="${esc(k.bild.replace("high.webp", "low.webp"))}" alt="">` : ""}
      <div><b>${esc(k.name)}</b> · ${esc(k.set)}<br><span class="klein">${esc(d.grund)}${d.warnung ? ' · <span class="marke warn">Fake/Betrug prüfen</span>' : ""}<br>${esc(d.titel)}</span></div>
      <span class="preis num">${eur(d.gesamt)}</span>
    </a>`).join("");
  document.querySelectorAll("#liste .karte").forEach((b) => b.addEventListener("click", () => oeffne(b.dataset.id)));
}

function kachelBeobachtet(k) {
  const cm = k.cardmarket || {};
  const sofort = (k.ebay?.angebote || []).filter((a) => a.art === "Sofort-Kaufen");
  const ebayMin = sofort[0]?.gesamt;
  const veraenderung = cm.avg30 && cm.trend ? ((cm.trend / cm.avg30 - 1) * 100) : null;
  return `<button class="karte" type="button" data-id="${esc(k.id)}">
    <img src="${esc(k.bild || "")}" alt="${esc(k.name)}" loading="lazy">
    <span class="titel">${esc(k.name)}</span>
    <span class="unter">${esc(k.set)} · ${esc(k.nummer)}${k.nummerOffiziell ? "/" + k.nummerOffiziell : ""}</span>
    <span class="preiszeile"><span>Cardmarket</span><b>${eur(cm.trend)}</b></span>
    <span class="preiszeile"><span>eBay ab</span><b>${ebayMin ? eur(ebayMin) : "–"}</b></span>
    <span class="preiszeile"><span>30 Tage</span><b class="${veraenderung >= 0 ? "plus" : "minus"}">${veraenderung == null ? "–" : prozent(veraenderung)}</b></span>
    ${k.deals?.length ? `<span class="marke">${k.deals.length} günstige${k.deals.length === 1 ? "s Angebot" : " Angebote"}</span>` : ""}
  </button>`;
}

/* ------------------------------------------------------------------ Suche */
$("#suche").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = $("#eingabe").value.trim();
  if (q.length < 2) return;
  $("#bereich-suche").hidden = false;
  $("#treffer").innerHTML = "";
  $("#suche-status").textContent = "Suche …";
  try {
    let treffer = await holeJson(`${API}/de/cards?name=${encodeURIComponent(q)}&pagination:itemsPerPage=60`);
    if (!treffer.length) treffer = await holeJson(`${API}/en/cards?name=${encodeURIComponent(q)}&pagination:itemsPerPage=60`);
    treffer = treffer.filter((t) => t.image).reverse(); // neuere Sets zuerst
    $("#suche-status").textContent = treffer.length ? `${treffer.length} Karten gefunden – für Preise antippen.` : "Keine Karte gefunden. Tipp: deutscher oder englischer Name, ohne Zusatz wie „ex“.";
    $("#treffer").innerHTML = treffer.map((t) => `<button class="karte" type="button" data-id="${esc(t.id)}">
      <img src="${esc(t.image)}/low.webp" alt="${esc(t.name)}" loading="lazy">
      <span class="titel">${esc(t.name)}</span><span class="unter">${esc(t.id)}</span></button>`).join("");
    document.querySelectorAll("#treffer .karte").forEach((b) => b.addEventListener("click", () => oeffne(b.dataset.id)));
  } catch (e) {
    $("#suche-status").textContent = "Die Suche ist gerade nicht erreichbar. Bitte gleich noch einmal versuchen.";
  }
});
$("#suche-zu").addEventListener("click", () => { $("#bereich-suche").hidden = true; });

/* ------------------------------------------------------------------ Detail */
const dialog = $("#detail");
$("#detail-zu").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });

async function holeKarteLive(id) {
  const k = await holeJson(`${API}/de/cards/${encodeURIComponent(id)}`);
  let set = {};
  try { set = await holeJson(`${API}/de/sets/${encodeURIComponent(k.set.id)}`); } catch (e) {}
  const cm = k.pricing?.cardmarket || {};
  const tp = k.pricing?.tcgplayer || {};
  const tpv = Object.values(tp).find((v) => v && typeof v === "object" && v.marketPrice) || {};
  const pos = (x) => (typeof x === "number" && x > 0 ? x : null);
  return {
    id: k.id, name: k.name, set: k.set.name, setId: k.set.id, nummer: k.localId,
    nummerOffiziell: k.set.cardCount?.official, seltenheit: k.rarity || "",
    bild: k.image ? k.image + "/high.webp" : null, release: set.releaseDate || null,
    cardmarket: { trend: pos(cm.trend), ab: pos(cm.low), durchschnitt: pos(cm.avg), avg1: pos(cm.avg1), avg7: pos(cm.avg7), avg30: pos(cm.avg30), stand: cm.updated },
    tcgplayer_usd: pos(tpv.marketPrice),
  };
}

async function oeffne(id) {
  $("#detail-inhalt").innerHTML = '<p class="hinweis">Lade Live-Preise …</p>';
  if (!dialog.open) dialog.showModal();
  const beobachtet = daten.karten.find((k) => k.id === id);
  let k;
  try {
    k = await holeKarteLive(id);
  } catch (e) {
    if (!beobachtet) { $("#detail-inhalt").innerHTML = '<p class="hinweis">Preise konnten nicht geladen werden.</p>'; return; }
    k = { ...beobachtet };
  }
  if (beobachtet) Object.assign(k, { ebay: beobachtet.ebay, deals: beobachtet.deals, wunschpreis: beobachtet.wunschpreis });
  let verlauf = null;
  try { verlauf = await holeJson(`verlauf/${encodeURIComponent(id)}.json?${Date.now()}`); } catch (e) {}
  zeigeDetail(k, verlauf, !!beobachtet);
}

function suchbegriff(k) {
  return `${k.name} ${k.nummer}${k.nummerOffiziell ? "/" + k.nummerOffiziell : ""}`;
}

function zeigeDetail(k, verlauf, beobachtet) {
  const cm = k.cardmarket || {};
  const angebote = k.ebay?.angebote || [];
  const sofort = angebote.filter((a) => a.art === "Sofort-Kaufen");
  const ebayMin = sofort[0];
  const q = encodeURIComponent(suchbegriff(k));
  const ebaySuche = `https://www.ebay.de/sch/i.html?_nkw=${q}&_sacat=${EBAY_KAT}&_sop=15&LH_BIN=1`;
  const ebayVerkauft = `https://www.ebay.de/sch/i.html?_nkw=${q}&_sacat=${EBAY_KAT}&LH_Sold=1&LH_Complete=1&_sop=13`;
  const cmLink = `https://www.cardmarket.com/de/Pokemon/Products/Search?searchString=${encodeURIComponent(k.name)}`;

  const preise = [["Cardmarket", cm.trend], ["eBay", ebayMin?.gesamt]].filter((p) => p[1]);
  const bester = preise.length === 2 ? (preise[0][1] <= preise[1][1] ? "Cardmarket" : "eBay") : null;

  const punkte = punkteAus(verlauf, cm);
  const prog = prognose(punkte);
  const eintrag = JSON.stringify({ id: k.id, suche: suchbegriff(k), wunschpreis: cm.trend ? Math.round(cm.trend * 0.85) : null });

  $("#detail-inhalt").innerHTML = `
    <div class="d-oben">
      <div>${k.bild ? `<img src="${esc(k.bild)}" alt="${esc(k.name)}">` : ""}</div>
      <div>
        <h2 id="d-name">${esc(k.name)}</h2>
        <p class="d-meta">${esc(k.set)} · Nr. ${esc(k.nummer)}${k.nummerOffiziell ? "/" + k.nummerOffiziell : ""} · ${esc(k.seltenheit)}${k.release ? ` · Release ${datum(k.release)}` : ""}<br><span class="klein">ID ${esc(k.id)}${cm.stand ? ` · Cardmarket-Stand ${new Date(cm.stand).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" })}` : ""}</span></p>
        <div class="vergleich">
          <div class="kachel ${bester === "Cardmarket" ? "bester" : ""}"><div class="l">Cardmarket Trend</div><div class="w">${eur(cm.trend)}</div><div class="z">ab ${eur(cm.ab)} (jeder Zustand)</div></div>
          <div class="kachel ${bester === "eBay" ? "bester" : ""}"><div class="l">eBay günstigstes</div><div class="w">${ebayMin ? eur(ebayMin.gesamt) : "–"}</div><div class="z">${ebayMin ? "Sofort-Kaufen inkl. Versand" : beobachtet ? (daten.ebay_aktiv ? "kein passendes Angebot" : "eBay noch nicht eingerichtet") : "nur für beobachtete Karten"}</div></div>
          <div class="kachel"><div class="l">Ø verkauft</div><div class="w">${eur(cm.avg7)}</div><div class="z">7 Tage · 30 Tage ${eur(cm.avg30)} · gestern ${eur(cm.avg1)}</div></div>
          <div class="kachel"><div class="l">TCGplayer (USA)</div><div class="w">${usd(k.tcgplayer_usd)}</div><div class="z">Marktpreis</div></div>
        </div>
        ${bester && preise.length === 2 ? `<p>Günstiger gerade auf <b>${bester}</b> – Unterschied ${eur(Math.abs(preise[0][1] - preise[1][1]))}.</p>` : ""}
        ${k.wunschpreis ? `<p>Dein Wunschpreis: <b>${eur(k.wunschpreis)}</b>${cm.trend ? ` (${prozent((k.wunschpreis / cm.trend - 1) * 100)} zum Trend)` : ""}</p>` : ""}
        <div class="links">
          <a href="${cmLink}" target="_blank" rel="noopener">Auf Cardmarket ansehen ↗</a>
          <a href="${ebaySuche}" target="_blank" rel="noopener">eBay: günstigste zuerst ↗</a>
          <a href="${ebayVerkauft}" target="_blank" rel="noopener">eBay: verkaufte Angebote ↗</a>
        </div>
      </div>
    </div>

    <div class="d-abschnitt">
      <h3>Preisverlauf &amp; Ausblick</h3>
      <div class="diagramm" id="diagramm"></div>
      <div class="legende">
        <span><i style="background:var(--akzent)"></i>Cardmarket-Trend</span>
        <span><i style="background:var(--ebay)"></i>eBay günstigstes Angebot</span>
        <span><i style="background:var(--prognose)"></i>Ausblick mit Spanne</span>
      </div>
      ${prog ? `<div class="ausblick">
        <div class="kachel"><div class="l">in 30 Tagen</div><div class="w">${eur(prog.p30.wert)}</div><div class="z">Spanne ${eur(prog.p30.unten)} – ${eur(prog.p30.oben)}</div></div>
        <div class="kachel"><div class="l">in 90 Tagen</div><div class="w">${eur(prog.p90.wert)}</div><div class="z">Spanne ${eur(prog.p90.unten)} – ${eur(prog.p90.oben)}</div></div>
        <div class="kachel"><div class="l">Tendenz</div><div class="w ${prog.tendenz >= 0 ? "plus" : "minus"}">${prozent(prog.tendenz)}</div><div class="z">auf 90 Tage</div></div>
      </div>` : ""}
      <p class="klein">${verlaufHinweis(verlauf, punkte, k)} Der Ausblick schreibt den bisherigen Trend gedämpft fort – Reprints, neue Sets oder Hypes kann er nicht vorhersehen.</p>
    </div>

    ${beobachtet ? `<div class="d-abschnitt">
      <h3>Aktuelle eBay-Angebote</h3>
      ${angebote.length ? `<table class="tabelle"><tbody>${angebote.map((a) => `<tr>
        <td><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.titel)}</a><br><span class="klein">${esc(a.art)}${a.art === "Auktion" && a.gebote != null ? ` · ${a.gebote} Gebote` : ""}${a.zustand ? " · " + esc(a.zustand) : ""}${a.land ? " · " + esc(a.land) : ""}${a.eingestellt ? " · seit " + datum(a.eingestellt) : ""}</span></td>
        <td class="r ausblenden">${eur(a.preis)}<br><span class="klein">+ ${eur(a.versand)}</span></td>
        <td class="r"><b>${eur(a.gesamt)}</b>${a.grund ? '<br><span class="marke">günstig</span>' : ""}</td></tr>`).join("")}</tbody></table>`
        : `<p class="hinweis">${daten.ebay_aktiv ? "Beim letzten Abruf gab es kein passendes Angebot." : "eBay ist noch nicht eingerichtet (siehe Anleitung im Projekt)."} <a href="${ebaySuche}" target="_blank" rel="noopener">Direkt auf eBay suchen ↗</a></p>`}
    </div>` : `<div class="d-abschnitt">
      <h3>Beobachten &amp; benachrichtigt werden</h3>
      <p>Diese Karte wird noch nicht beobachtet. Füge diesen Eintrag in <a href="https://github.com/nick084412/finanz-update/edit/main/pokemon/beobachten.json" target="_blank" rel="noopener">beobachten.json</a> unter <code>"karten"</code> ein (Wunschpreis anpassen). Ab dann werden eBay-Angebote abgerufen, der Verlauf aufgezeichnet und du bekommst Push-Nachrichten.</p>
      <pre class="eintrag">${esc(eintrag)}</pre>
      <button class="knopf" type="button" id="kopieren">Eintrag kopieren</button>
    </div>`}`;

  zeichne($("#diagramm"), punkte, prog, k.release);
  const knopf = $("#kopieren");
  if (knopf) knopf.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(eintrag + ","); knopf.textContent = "Kopiert ✓"; } catch (e) { knopf.textContent = "Bitte von Hand kopieren"; }
  });
}

function verlaufHinweis(verlauf, punkte, k) {
  const echt = punkte.filter((p) => !p.geschaetzt);
  const seit = echt.length ? datum(echt[0].datum) : null;
  const rel = k.release ? `Release war am ${datum(k.release)}. ` : "";
  if (!verlauf) return `${rel}Für nicht beobachtete Karten zeigt das Diagramm nur die Cardmarket-Durchschnitte der letzten 30 Tage.`;
  return `${rel}Aufgezeichnet seit ${seit} (${echt.length} Tageswerte); hellere Punkte am Anfang sind aus den Cardmarket-Durchschnitten geschätzt.`;
}

/* ------------------------------------------------------------------ Verlauf & Prognose */
function punkteAus(verlauf, cm) {
  if (verlauf?.punkte?.length) {
    return verlauf.punkte.filter((p) => p.trend).map((p) => ({ ...p, t: +new Date(p.datum) }));
  }
  const heute = new Date(); heute.setUTCHours(0, 0, 0, 0);
  const p = [];
  const add = (tage, wert) => wert && p.push({ t: +heute - tage * TAG, datum: new Date(+heute - tage * TAG).toISOString().slice(0, 10), trend: wert, geschaetzt: true });
  add(15, cm.avg30); add(4, cm.avg7); add(1, cm.avg1);
  if (cm.trend) p.push({ t: +heute, datum: heute.toISOString().slice(0, 10), trend: cm.trend });
  return p;
}

/* Gedämpfte log-lineare Fortschreibung: Steigung aus den letzten 180 Tagen,
   jeder weitere Tag wirkt etwas schwächer (φ = 0,985), Spanne wächst mit √Zeit. */
function prognose(punkte) {
  if (punkte.length < 2) return null;
  const ende = punkte[punkte.length - 1];
  const basis = punkte.filter((p) => p.t >= ende.t - 180 * TAG);
  const xs = basis.map((p) => (p.t - ende.t) / TAG);
  const ys = basis.map((p) => Math.log(p.trend));
  const n = xs.length;
  const mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n;
  let sxy = 0, sxx = 0;
  for (let i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) ** 2; }
  let steigung = sxx ? sxy / sxx : 0;
  const reste = xs.map((x, i) => ys[i] - (my + steigung * (x - mx)));
  let sigma = Math.sqrt(reste.reduce((a, r) => a + r * r, 0) / Math.max(1, n - 2));
  const wenig = basis.filter((p) => !p.geschaetzt).length < 14;
  if (wenig) steigung *= 0.5; // wenig Daten → vorsichtiger
  steigung = Math.max(-0.01, Math.min(0.01, steigung)); // höchstens ±1 %/Tag
  sigma = Math.max(sigma, wenig ? 0.06 : 0.03);
  const phi = 0.985, start = Math.log(ende.trend);
  const reihe = [];
  let summe = 0;
  for (let h = 0; h <= 90; h++) {
    if (h > 0) summe += phi ** h;
    const mitte = start + steigung * summe;
    const breite = 1.28 * sigma * Math.sqrt(1 + h / 15);
    if (h % 3 === 0 || h === 30 || h === 90) reihe.push({ t: ende.t + h * TAG, wert: Math.exp(mitte), unten: Math.exp(mitte - breite), oben: Math.exp(mitte + breite), h });
  }
  const bei = (h) => reihe.find((r) => r.h === h);
  return { reihe, p30: bei(30), p90: bei(90), tendenz: (bei(90).wert / ende.trend - 1) * 100 };
}

function zeichne(ziel, punkte, prog, release) {
  if (!punkte.length) { ziel.innerHTML = '<p class="hinweis" style="padding:20px">Keine Preisdaten vorhanden.</p>'; return; }
  const B = 800, H = 320, L = 62, R = 16, O = 16, U = 34;
  const alle = [...punkte.map((p) => p.t), ...(prog ? prog.reihe.map((r) => r.t) : [])];
  const werte = [...punkte.map((p) => p.trend), ...punkte.filter((p) => p.ebay).map((p) => p.ebay), ...(prog ? prog.reihe.flatMap((r) => [r.unten, r.oben]) : [])];
  let t0 = Math.min(...alle), t1 = Math.max(...alle);
  if (t1 - t0 < 7 * TAG) t0 = t1 - 7 * TAG;
  let y0 = Math.min(...werte), y1 = Math.max(...werte);
  const puffer = (y1 - y0) * 0.08 || y1 * 0.1;
  y0 = Math.max(0, y0 - puffer); y1 += puffer;
  const x = (t) => L + ((t - t0) / (t1 - t0)) * (B - L - R);
  const y = (v) => O + (1 - (v - y0) / (y1 - y0)) * (H - O - U);
  const linie = (arr, f) => arr.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(f(p)).toFixed(1)}`).join("");

  let svg = `<svg viewBox="0 0 ${B} ${H}" role="img" aria-label="Preisverlauf">`;
  for (let i = 0; i <= 4; i++) {
    const v = y0 + ((y1 - y0) * i) / 4;
    svg += `<line x1="${L}" x2="${B - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end" font-size="12" fill="var(--subtle)">${eur(v, v < 10 ? 2 : 0)}</text>`;
  }
  const spanne = (t1 - t0) / TAG;
  const schritte = 6;
  for (let i = 0; i <= schritte; i++) {
    const t = t0 + ((t1 - t0) * i) / schritte;
    const text = new Date(t).toLocaleDateString("de-DE", spanne > 400 ? { month: "short", year: "2-digit" } : { day: "2-digit", month: "short" });
    svg += `<text x="${x(t)}" y="${H - 10}" text-anchor="middle" font-size="12" fill="var(--subtle)">${text}</text>`;
  }
  if (release && +new Date(release) >= t0) {
    const rx = x(+new Date(release));
    svg += `<line x1="${rx}" x2="${rx}" y1="${O}" y2="${H - U}" stroke="var(--line-strong)" stroke-dasharray="2 4"/><text x="${rx + 4}" y="${O + 12}" font-size="11" fill="var(--subtle)">Release</text>`;
  }
  const heute = punkte[punkte.length - 1].t;
  if (prog) {
    const r = prog.reihe;
    svg += `<path d="${linie(r, (p) => p.oben)}${[...r].reverse().map((p) => `L${x(p.t).toFixed(1)},${y(p.unten).toFixed(1)}`).join("")}Z" fill="var(--prognose)" opacity=".14"/>`;
    svg += `<path d="${linie(r, (p) => p.wert)}" fill="none" stroke="var(--prognose)" stroke-width="2.5" stroke-dasharray="6 5"/>`;
    svg += `<line x1="${x(heute)}" x2="${x(heute)}" y1="${O}" y2="${H - U}" stroke="var(--line-strong)"/><text x="${x(heute) + 4}" y="${H - U - 6}" font-size="11" fill="var(--subtle)">heute</text>`;
  }
  svg += `<path d="${linie(punkte, (p) => p.trend)}" fill="none" stroke="var(--akzent)" stroke-width="2.5" stroke-linejoin="round"/>`;
  punkte.forEach((p) => { svg += `<circle cx="${x(p.t)}" cy="${y(p.trend)}" r="${punkte.length > 60 ? 0 : 3.5}" fill="var(--akzent)" opacity="${p.geschaetzt ? 0.45 : 1}"/>`; });
  punkte.filter((p) => p.ebay).forEach((p) => { svg += `<circle cx="${x(p.t)}" cy="${y(p.ebay)}" r="3.5" fill="var(--ebay)"/>`; });
  svg += `<line id="zeiger" y1="${O}" y2="${H - U}" stroke="var(--muted)" stroke-width="1" visibility="hidden"/><rect x="${L}" y="${O}" width="${B - L - R}" height="${H - O - U}" fill="transparent" id="fang"/></svg>`;
  ziel.innerHTML = svg + '<div class="tipp" hidden></div>';

  const ziele = [...punkte.map((p) => ({ t: p.t, text: `<b>${datum(p.t)}</b><br>Cardmarket ${eur(p.trend)}${p.ebay ? `<br>eBay ab ${eur(p.ebay)}` : ""}${p.geschaetzt ? "<br><i>geschätzt</i>" : ""}` })),
    ...(prog ? prog.reihe.slice(1).map((r) => ({ t: r.t, text: `<b>${datum(r.t)}</b> · Ausblick<br>${eur(r.wert)} (${eur(r.unten)} – ${eur(r.oben)})` })) : [])];
  const svgEl = ziel.querySelector("svg"), tipp = ziel.querySelector(".tipp"), zeiger = ziel.querySelector("#zeiger");
  const bewege = (ev) => {
    const box = svgEl.getBoundingClientRect();
    const px = ((ev.clientX - box.left) / box.width) * B;
    const t = t0 + ((px - L) / (B - L - R)) * (t1 - t0);
    const z = ziele.reduce((a, b) => (Math.abs(b.t - t) < Math.abs(a.t - t) ? b : a));
    const zx = x(z.t);
    zeiger.setAttribute("x1", zx); zeiger.setAttribute("x2", zx); zeiger.setAttribute("visibility", "visible");
    tipp.innerHTML = z.text; tipp.hidden = false;
    const links = (zx / B) * box.width;
    tipp.style.left = Math.min(Math.max(8, links - tipp.offsetWidth / 2), box.width - tipp.offsetWidth + 8) + "px";
    tipp.style.top = "8px";
  };
  svgEl.addEventListener("pointermove", bewege);
  svgEl.addEventListener("pointerdown", bewege);
  svgEl.addEventListener("pointerleave", () => { tipp.hidden = true; zeiger.setAttribute("visibility", "hidden"); });
}

ladeListe();
const start = new URLSearchParams(location.search).get("karte");
if (start) oeffne(start);
