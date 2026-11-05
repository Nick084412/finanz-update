# Finanz-Update

Tägliches Briefing für die Finanzberatung: https://nick084412.github.io/finanz-update/

- `daten/` – eine Datei je Ausgabe (Tag: JJJJ-MM-TT.json, Woche: JJJJ-KWnn.json)
- `bauen.py` + `style.css` – bauen die Webseite im freigegebenen Design nach `docs/`
- `docs/` – die Webseite (GitHub Pages)
- `.github/workflows/benachrichtigung.yml` – Push-Nachricht über ntfy (Kanal finanz-update-od6997pb)

Die Ausgaben erstellt eine Claude-Cloud-Routine (Mo–Fr 7 Uhr, So 8 Uhr).

## Pokémon-Kartenpreise

Seite: https://nick084412.github.io/finanz-update/pokemon/

- `pokemon/beobachten.json` – beobachtete Karten mit Wunschpreis (Euro inkl. Versand) und eBay-Suchbegriff
- `pokemon/abrufen.py` – holt Cardmarket-Preise (TCGdex-API) und eBay.de-Angebote (eBay-Browse-API), schreibt `docs/pokemon/daten.json` und den Verlauf `docs/pokemon/verlauf/<id>.json`
- `.github/workflows/pokemon.yml` – läuft alle 2 Stunden, Push über ntfy (Kanal pokemon-preise-k7m2xq9d)
- Meldung bei Angeboten unter dem Wunschpreis oder `rabatt_prozent` unter dem Cardmarket-Trend

eBay einrichten: unter https://developer.ebay.com ein kostenloses Konto anlegen, eine App (Production) erstellen,
dann im Repository unter Settings → Secrets and variables → Actions `EBAY_CLIENT_ID` (App ID) und `EBAY_CLIENT_SECRET` (Cert ID) eintragen.
