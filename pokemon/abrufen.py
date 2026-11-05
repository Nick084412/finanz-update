#!/usr/bin/env python3
"""Ruft Preise für die beobachteten Pokémon-Karten ab.

- Cardmarket-Preise (Trend, Ab-Preis, Ø 1/7/30 Tage) über die freie TCGdex-API
- eBay.de-Angebote über die eBay Browse API (nur wenn EBAY_CLIENT_ID und EBAY_CLIENT_SECRET gesetzt sind)
- schreibt den Preisverlauf nach docs/pokemon/verlauf/<id>.json (ein Punkt pro Tag)
- schreibt docs/pokemon/daten.json für die Webseite
- schickt eine ntfy-Push-Nachricht, wenn ein günstiges Angebot neu auftaucht

Aufruf: python3 pokemon/abrufen.py   (ohne Push: --ohne-push)
"""
import base64
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
LISTE = WURZEL / "pokemon" / "beobachten.json"
GEMELDET = WURZEL / "pokemon" / "gemeldet.json"
AUSGABE = WURZEL / "docs" / "pokemon"
VERLAUF = AUSGABE / "verlauf"

TCGDEX = "https://api.tcgdex.net/v2/de"
EBAY = "https://api.ebay.com"
EBAY_KATEGORIE = "183454"  # Sammelkartenspiele > Einzelkarten
SEITE = os.environ.get("SEITE", "https://nick084412.github.io/finanz-update/pokemon/")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

# Angebote mit diesen Wörtern im Titel sind meist nicht die gesuchte Karte
AUSSCHLUSS = re.compile(
    r"\b(psa|bgs|cgc|beckett|graded|grade|gegradet|proxy|fake|custom|orica|replica|nachdruck|"
    r"japan|japanese|japanisch|jpn|jp|korean|koreanisch|chinese|chinesisch|"
    r"sammlung|konvolut|lot|bundle|display|booster|sleeve|h[uü]lle|toploader|metal|gold\s*metal)\b",
    re.I,
)


def hole_json(url, kopf=None, daten=None):
    anfrage = urllib.request.Request(url, data=daten, headers={"User-Agent": "pokemon-preise/1.0", **(kopf or {})})
    with urllib.request.urlopen(anfrage, timeout=40) as antwort:
        return json.loads(antwort.read().decode("utf-8"))


def lade(pfad, standard):
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return standard


def speichere(pfad, inhalt):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(inhalt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def runde(x):
    return round(float(x), 2) if isinstance(x, (int, float)) and x > 0 else None


# ---------------------------------------------------------------- TCGdex / Cardmarket

_sets = {}


def hole_karte(kid):
    k = hole_json(f"{TCGDEX}/cards/{urllib.parse.quote(kid)}")
    sid = k["set"]["id"]
    if sid not in _sets:
        try:
            _sets[sid] = hole_json(f"{TCGDEX}/sets/{urllib.parse.quote(sid)}")
        except Exception:
            _sets[sid] = {}
    s = _sets[sid]
    preise = k.get("pricing") or {}
    cm = preise.get("cardmarket") or {}
    tp = preise.get("tcgplayer") or {}
    tp_variante = next((v for n, v in tp.items() if isinstance(v, dict) and v.get("marketPrice")), {})
    return {
        "id": k["id"],
        "name": k["name"],
        "set": k["set"]["name"],
        "setId": sid,
        "nummer": k.get("localId", ""),
        "nummerOffiziell": (k["set"].get("cardCount") or {}).get("official"),
        "seltenheit": k.get("rarity", ""),
        "bild": (k.get("image") + "/high.webp") if k.get("image") else None,
        "release": s.get("releaseDate"),
        "cardmarket": {
            "trend": runde(cm.get("trend")),
            "ab": runde(cm.get("low")),
            "durchschnitt": runde(cm.get("avg")),
            "avg1": runde(cm.get("avg1")),
            "avg7": runde(cm.get("avg7")),
            "avg30": runde(cm.get("avg30")),
            "stand": cm.get("updated"),
            "idProduct": cm.get("idProduct"),
        },
        "tcgplayer_usd": runde(tp_variante.get("marketPrice")),
    }


# ---------------------------------------------------------------- eBay

def ebay_token():
    cid, geheim = os.environ.get("EBAY_CLIENT_ID"), os.environ.get("EBAY_CLIENT_SECRET")
    if not cid or not geheim:
        return None
    schluessel = base64.b64encode(f"{cid}:{geheim}".encode()).decode()
    daten = urllib.parse.urlencode({"grant_type": "client_credentials",
                                    "scope": "https://api.ebay.com/oauth/api_scope"}).encode()
    antwort = hole_json(f"{EBAY}/identity/v1/oauth2/token", daten=daten, kopf={
        "Authorization": f"Basic {schluessel}", "Content-Type": "application/x-www-form-urlencoded"})
    return antwort["access_token"]


def passt_nummer(titel, karte):
    """Prüft, ob die Kartennummer (z. B. 199/165) im Titel steht."""
    nr = str(karte["nummer"]).lstrip("0") or "0"
    if not nr.isdigit():
        return nr.lower() in titel.lower()
    gesamt = karte.get("nummerOffiziell")
    if gesamt:
        return re.search(rf"(?<!\d)0*{nr}\s*/\s*0*{gesamt}(?!\d)", titel) is not None
    return re.search(rf"(?<!\d)0*{nr}(?!\d)", titel) is not None


def ebay_suche(token, karte, eintrag):
    suche = eintrag.get("suche") or f"{karte['name']} {karte['nummer']}/{karte.get('nummerOffiziell') or ''}".strip("/ ")
    parameter = urllib.parse.urlencode({
        "q": suche,
        "category_ids": EBAY_KATEGORIE,
        "filter": "buyingOptions:{FIXED_PRICE|AUCTION|BEST_OFFER},priceCurrency:EUR,deliveryCountry:DE",
        "sort": "price",
        "limit": "100",
    })
    antwort = hole_json(f"{EBAY}/buy/browse/v1/item_summary/search?{parameter}", kopf={
        "Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_DE",
        "X-EBAY-C-ENDUSERCTX": "contextualLocation=country=DE,zip=10115", "Accept-Language": "de-DE"})
    angebote = []
    for a in antwort.get("itemSummaries", []):
        titel = a.get("title", "")
        if AUSSCHLUSS.search(titel) or not passt_nummer(titel, karte):
            continue
        preis = float((a.get("price") or {}).get("value") or 0)
        if not preis:
            continue
        versand = 0.0
        for v in a.get("shippingOptions") or []:
            kosten = (v.get("shippingCost") or {}).get("value")
            if kosten is not None:
                versand = float(kosten)
                break
        arten = a.get("buyingOptions") or []
        angebote.append({
            "itemId": a.get("itemId"),
            "titel": titel,
            "preis": round(preis, 2),
            "versand": round(versand, 2),
            "gesamt": round(preis + versand, 2),
            "art": "Auktion" if arten == ["AUCTION"] else "Sofort-Kaufen",
            "gebote": a.get("bidCount"),
            "ende": a.get("itemEndDate"),
            "zustand": a.get("condition"),
            "eingestellt": a.get("itemCreationDate"),
            "url": a.get("itemWebUrl"),
            "bild": (a.get("image") or {}).get("imageUrl"),
            "land": (a.get("itemLocation") or {}).get("country"),
        })
    angebote.sort(key=lambda x: x["gesamt"])
    return angebote


# ---------------------------------------------------------------- Auswertung

def ist_deal(gesamt, karte, eintrag, rabatt):
    trend = karte["cardmarket"]["trend"]
    wunsch = eintrag.get("wunschpreis")
    grund = None
    if wunsch and gesamt <= wunsch:
        grund = f"unter deinem Wunschpreis {wunsch:.2f} €"
    elif trend and gesamt <= trend * (1 - rabatt / 100):
        grund = f"{(1 - gesamt / trend) * 100:.0f} % unter Cardmarket-Trend"
    warnung = bool(trend and gesamt < trend * 0.4)
    return grund, warnung


def verlauf_aktualisieren(karte, ebay_min, heute):
    pfad = VERLAUF / f"{karte['id']}.json"
    v = lade(pfad, None)
    cm = karte["cardmarket"]
    if v is None:
        v = {"id": karte["id"], "punkte": []}
        # Startwerte aus den Cardmarket-Durchschnitten, damit der Verlauf nicht leer beginnt
        for tage, wert in ((15, cm["avg30"]), (4, cm["avg7"]), (1, cm["avg1"])):
            if wert:
                v["punkte"].append({"datum": (heute - dt.timedelta(days=tage)).isoformat(),
                                    "trend": wert, "geschaetzt": True})
    punkt = {"datum": heute.isoformat(), "trend": cm["trend"], "ab": cm["ab"], "avg1": cm["avg1"]}
    if ebay_min is not None:
        punkt["ebay"] = ebay_min
    punkte = [p for p in v["punkte"] if p["datum"] != punkt["datum"]]
    alt = next((p for p in v["punkte"] if p["datum"] == punkt["datum"]), {})
    if ebay_min is None and "ebay" in alt:
        punkt["ebay"] = alt["ebay"]
    elif ebay_min is not None and "ebay" in alt:
        punkt["ebay"] = min(ebay_min, alt["ebay"])  # günstigstes eBay-Angebot des Tages
    punkte.append({k: w for k, w in punkt.items() if w is not None})
    v["punkte"] = sorted(punkte, key=lambda p: p["datum"])
    v["name"], v["set"], v["release"] = karte["name"], karte["set"], karte["release"]
    speichere(pfad, v)


def push(titel, text, klick, tags, prio=4):
    if not NTFY_TOPIC:
        print("  (kein NTFY_TOPIC – keine Push-Nachricht)")
        return
    daten = json.dumps({"topic": NTFY_TOPIC, "title": titel, "message": text, "click": klick,
                        "tags": tags, "priority": prio}).encode()
    urllib.request.urlopen(urllib.request.Request("https://ntfy.sh", data=daten,
                                                  headers={"Content-Type": "application/json"}), timeout=30)


def main():
    ohne_push = "--ohne-push" in sys.argv
    liste = lade(LISTE, {"karten": []})
    rabatt = float(liste.get("rabatt_prozent", 20))
    gemeldet = lade(GEMELDET, {"ids": []})
    schon = set(gemeldet["ids"])
    heute = dt.datetime.now(dt.timezone.utc).date()

    try:
        token = ebay_token()
    except Exception as fehler:
        print("eBay-Anmeldung fehlgeschlagen:", fehler)
        token = None
    print("eBay:", "aktiv" if token else "nicht eingerichtet")

    ergebnis, meldungen = [], []
    for eintrag in liste["karten"]:
        try:
            karte = hole_karte(eintrag["id"])
        except Exception as fehler:
            print(f"{eintrag['id']}: TCGdex-Fehler {fehler}")
            continue
        karte["wunschpreis"] = eintrag.get("wunschpreis")
        karte["deals"] = []
        ebay_min = None
        if token:
            try:
                angebote = ebay_suche(token, karte, eintrag)
                sofort = [a for a in angebote if a["art"] == "Sofort-Kaufen"]
                ebay_min = sofort[0]["gesamt"] if sofort else None
                karte["ebay"] = {"anzahl": len(angebote), "angebote": angebote[:12]}
                for a in sofort:
                    grund, warnung = ist_deal(a["gesamt"], karte, eintrag, rabatt)
                    if not grund:
                        break  # nach Preis sortiert – alles Weitere ist teurer
                    a["grund"], a["warnung"] = grund, warnung
                    karte["deals"].append(a)
                    if a["itemId"] not in schon:
                        schon.add(a["itemId"])
                        gemeldet["ids"].append(a["itemId"])
                        meldungen.append((karte, a, "eBay"))
            except Exception as fehler:
                print(f"{karte['id']}: eBay-Fehler {fehler}")
        # Cardmarket-Trend unter Wunschpreis? (Der Ab-Preis ist oft schlechter Zustand/andere Sprache,
        # deshalb zählt hier der Trendpreis.)
        trend, wunsch = karte["cardmarket"]["trend"], eintrag.get("wunschpreis")
        if trend and wunsch and trend <= wunsch:
            schluessel = f"cm:{karte['id']}:{heute.isoformat()[:7]}"  # höchstens eine Meldung pro Monat
            karte["deals"].append({"titel": f"Cardmarket-Trend {trend:.2f} €", "gesamt": trend,
                                   "url": f"https://www.cardmarket.com/de/Pokemon/Products/Search?searchString={urllib.parse.quote(karte['name'])}",
                                   "grund": f"Marktpreis unter deinem Wunschpreis {wunsch:.2f} €", "quelle": "Cardmarket"})
            if schluessel not in schon:
                schon.add(schluessel)
                gemeldet["ids"].append(schluessel)
                meldungen.append((karte, karte["deals"][-1], "Cardmarket"))
        verlauf_aktualisieren(karte, ebay_min, heute)
        ergebnis.append(karte)
        print(f"{karte['id']:<14} {karte['name']:<20} Trend {karte['cardmarket']['trend']} € · eBay ab {ebay_min} € · Deals {len(karte['deals'])}")

    speichere(AUSGABE / "daten.json", {
        "stand": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "ebay_aktiv": bool(token),
        "rabatt_prozent": rabatt,
        "karten": ergebnis,
    })
    gemeldet["ids"] = gemeldet["ids"][-3000:]
    speichere(GEMELDET, gemeldet)

    for karte, a, quelle in meldungen[:8]:
        titel = f"Günstig: {karte['name']} ({karte['set']}) – {a['gesamt']:.2f} €"
        text = f"{a['grund']}\nCardmarket-Trend: {karte['cardmarket']['trend'] or '–'} €\n{a['titel']}"
        if a.get("warnung"):
            text += "\n⚠️ Sehr weit unter Marktpreis – Verkäufer und Fotos genau prüfen (Fake/Betrug?)"
        print("Meldung:", titel)
        if not ohne_push:
            try:
                push(titel, text, a.get("url") or SEITE, ["moneybag"] if quelle == "eBay" else ["shopping_cart"])
            except Exception as fehler:
                print("  Push fehlgeschlagen:", fehler)


if __name__ == "__main__":
    main()
