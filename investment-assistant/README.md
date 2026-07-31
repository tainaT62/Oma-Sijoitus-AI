# Oma-Sijoitus-AI — henkilökohtainen sijoitusanalyysijärjestelmä

Yhden käyttäjän työkalu, joka analysoi salkun ja markkinat sekä lähettää
**yhden Telegram-raportin aamussa** suosituksineen.

> **Järjestelmä ei tee kauppoja eikä voi tehdä.** Se on analyysityökalu.
> Kaikki toimeksiannot teet itse. Brokerirajapinnoissa ei ole
> toimeksiantometodeja lainkaan – kaupankäynti on rakenteellisesti
> mahdotonta, ei vain pois kytkettynä.

---

## Ominaisuudet

**Salkku**
- Krypto Binancesta, osakkeet/ETF:t/rahastot IBKR:stä yhtenä salkkuna
- Positiokohtaisesti: arvo, tuotto, osuus, volatiliteetti, riskipisteet,
  hajautusvaikutus
- Brokerien käteinen pidetään erillään

**Automaattinen synkronointi**
- Havaitsee ostot, lisäykset, osittaiset ja täydet myynnit vertaamalla
  peräkkäisiä tilannekuvia
- Päivittää kuukausibudjetin itse – mitään ei tarvitse kirjata käsin
- Arvottaa muutoksen ensisijaisesti toteutuneesta kauppahinnasta

**Suositukset** — BUY / HOLD / REDUCE / SELL, luottamusprosentti,
AI Score, riski, odotettu tuotto, stop loss, take profit, perustelut

**Kuukausibudjetti** — suositukset eivät koskaan ylitä jäljellä olevaa
budjettia; allokaatio 40 % ETF / 30 % osakkeet / 30 % krypto säätyy
markkinatilanteen mukaan

**Portfolio Score** 0–100: hajautus, riski, allokaatio, kassavaranto,
markkinatilanne, budjetin käyttö

**Analyysi** — RSI, MACD, EMA 20/50/200, Bollinger, ATR, VWAP,
volyymitrendi · Fear & Greed · uutissentimentti (VADER) · Reddit ·
valinnainen OpenAI-yhteenveto

**Web-käyttöliittymä** — salasanasuojattu dashboard, kaaviot, historia

---

## Arkkitehtuuri

```
   Binance ────────┐
   (krypto)        │
                   ▼
   IBKR ──────► portfolio_service ──► portfolio_score
   (osake/ETF)     │
                   ▼
             sync_service ──► budget_service
             (kauppojen        (kuukausibudjetti,
              havainnointi)     allokaatio)
                   │                 │
                   └────────┬────────┘
                            ▼
                  recommendation_engine
                  BUY / HOLD / REDUCE / SELL
                            │
                            ▼
                    telegram_formatter
                  yksi raportti / vuorokausi
```

Tukipalvelut: `technical_analysis`, `sentiment`, `news_service`,
`ai_score`, `risk_manager`, `portfolio_optimizer`, `watchlist`,
`backtest`, `database`, `scheduler`, `security`.

---

## Asennus

Vaatimukset: **Python 3.10+** (Ubuntu 22.04 = 3.10, 24.04 = 3.12).

```bash
git clone https://github.com/tainaT62/Oma-Sijoitus-AI.git
cd Oma-Sijoitus-AI/investment-assistant
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` on riippuvuuksien **ainoa** lähde; juuren
`pyproject.toml` peilaa sitä.

---

## Konfiguraatio

```bash
cp .env.example .env
chmod 600 .env
```

### Pakolliset

Sovellus **ei käynnisty** ilman näitä.

| Muuttuja | Kuvaus |
|---|---|
| `SECRET_KEY` | Istuntoevästeen allekirjoitus, ≥ 32 merkkiä |
| `APP_PASSWORD_HASH` | Kirjautumissalasanan tiiviste |

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
python3 -c "from werkzeug.security import generate_password_hash as g; import getpass; print(g(getpass.getpass()))"
```

Jos jälkimmäinen kaatuu virheeseen `hashlib has no attribute 'scrypt'`,
lisää `method="pbkdf2:sha256"`.

### Keskeiset valinnaiset

| Muuttuja | Oletus | Kuvaus |
|---|---|---|
| `BINANCE_API_KEY` / `BINANCE_SECRET_KEY` | – | Vain lukuoikeudet |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | – | Ilman näitä ilmoitukset pois |
| `OPENAI_API_KEY` | – | Ilman: sääntöpohjainen analyysi |
| `MONTHLY_BUDGET` | `200` | Kuukausibudjetti |
| `BASE_CURRENCY` | `EUR` | Raportointivaluutta |
| `MAX_POSITION_PROSENTTI` | `25` | REDUCE-kynnys |
| `IBKR_MODE` | `mock` | `mock` / `live` / `off` |
| `SESSION_COOKIE_SECURE` | `true` | `false` vain paikallisessa HTTP-testissä |
| `TRUSTED_PROXY_COUNT` | `0` | `1` Nginxin takana |
| `ENABLE_SCHEDULER` | `true` | Taustatehtävät |

Kaikki välimuistien elinajat, ostoehdotusten rajat ja Gunicornin
asetukset ovat myös ympäristömuuttujia – ks. `.env.example` ja
`config.py`. Koodissa ei ole kovakoodattuja arvoja.

---

## Paikallinen ajo

```bash
SESSION_COOKIE_SECURE=false python3 app.py
```

Avaa <http://127.0.0.1:5000> – ohjaa kirjautumissivulle.

`SESSION_COOKIE_SECURE=false` on välttämätön paikallisessa HTTP-ajossa:
muuten selain ei tallenna evästettä ja kirjautuminen epäonnistuu
hiljaisesti. Tuotannossa arvo on `true`.

---

## Tuotantoasennus

Ubuntu VPS, Gunicorn + systemd + Nginx + TLS: **[deploy/README.md](../deploy/README.md)**.

```
Internet --HTTPS--> Nginx (443) --HTTP--> Gunicorn (127.0.0.1:5000)
```

Gunicorn ei kuuntele julkista osoitetta koskaan.

---

## Scheduler

| Tehtävä | Väli |
|---|---|
| Markkinadata, salkkusnapshot, **synkronointi** | 5 min |
| Uutiset ja sentimentti | 15 min |
| AI-analyysit ja AI Score | 60 min |
| **Päiväraportti + Telegram** | klo 08:00 |

Scheduler käynnistyy **täsmälleen yhdessä prosessissa**:
`ENABLE_SCHEDULER` ja tiedostolukko (`data/scheduler.lock`). Lukko
vapautuu prosessin kuollessa, joten tehtävät siirtyvät toiselle
workerille itsestään.

---

## Telegram

1. `@BotFather` → `/newbot` → token
2. Lähetä botille yksi viesti
3. Hae chat_id:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['result'][0]['message']['chat']['id'])"
```

Testaa yhteys (ei lähetä viestiä):

```bash
python3 -c "from services.telegram_service import telegram_service as t; print(t.testaa_yhteys())"
```

Ilman tunnuksia ilmoitukset ovat pois päältä eikä se vaikuta muuhun.

---

## Binance

API Managementissa **vain `Enable Reading`**. Ei Spot-kaupankäyntiä,
ei nostoja. Rajoita avain IP-osoitteeseen kun palvelin on pystyssä.

Sovellus käyttää vain lukurajapintoja: saldot, hinnat, kynttilät,
kauppahistoria.

---

## Interactive Brokers

Oletuksena `IBKR_MODE=mock`: rakenne, salkkumatematiikka, pisteytys ja
raportointi toimivat esimerkkidatalla ilman tunnuksia. Raportti merkitsee
mock-datan selvästi.

Live-tilan aktivointi:

```bash
pip install ib_insync          # lisää myös requirements.txt:hen
```

1. Käynnistä TWS tai IB Gateway, salli API-yhteydet
2. `IBKR_MODE=live`, `IBKR_PORT` (7496 TWS live, 7497 paper, 4001 Gateway)
3. Toteuta `services/ibkr_service.py`:n integraatiopisteet 1–4

`readonly=True` on säilytettävä.

---

## API

Kaikki reitit vaativat kirjautumisen. Tilaa muuttavat pyynnöt vaativat
`X-CSRF-Token`-otsakkeen.

| Reitti | Kuvaus |
|---|---|
| `GET /` | Dashboard |
| `GET /api/dashboard` | Koko dashboard-data |
| `GET /api/portfolio` | Salkku |
| `GET /api/budjetti` | Kuukausibudjetti |
| `POST /api/budjetti` | Kirjaa osto **käsin (vain korjauksiin)** |
| `GET /api/sync` | Havaitut salkkumuutokset |
| `POST /api/sync` | Aja synkronointi heti |
| `GET /api/recommendation` | Suositukset |
| `GET /api/ai-score` | AI Score |
| `GET /api/watchlist` | Seurantalista |
| `GET /api/backtest` | Strategiasimulaatio |
| `GET /terveys` | Tila |

---

## Tunnetut rajoitukset

1. **Osakkeiden ja ETF:ien tekninen analyysi puuttuu.** Binance antaa
   kynttilädatan vain kryptalle. Osakesuositukset perustuvat position
   omiin tunnuslukuihin (keskittymä, tuotto, hajautus). Raportti kertoo
   tämän jokaisen tällaisen suosituksen kohdalla.
2. **Osakkeiden allokaatio on 0 €** kunnes IBKR on live: ostoa ei voi
   perustella ilman markkinadataa, joten osuus jää varaukseen.
3. **IBKR-data on esimerkkidataa** `mock`-tilassa.
4. **Kryptan hankintahintaa ei ole** – Binance ei anna sitä ilman
   kauppahistorian rekonstruointia, joten tuottoprosentti puuttuu.
5. **IBKR-kauppojen arvotus** käyttää markkinahintaa; toteutuneet
   kauppahinnat vaativat `ib.fills()`-integraation.
6. **Aiempia suosituksia ei käytetä** analyysin syötteenä.
7. **Kirjautumisrajoitin on prosessin muistissa** – nollautuu
   uudelleenkäynnistyksessä.
8. **Automaattitestejä ei ole.** Validointi on tehty ajamalla.

---

## Turvallisuus

- Kaikki reitit suojattu oletuksena (*fail closed*)
- Istuntoeväste: `HttpOnly`, `SameSite=Lax`, `Secure`
- CSRF tilaa muuttavissa pyynnöissä
- Kirjautumisyritysten rajoitus
- Ei salaisuuksia lokeissa
- Vain luku -brokeriyhteydet, ei toimeksiantometodeja

**Tämä ei ole sijoitusneuvontaa.** Kaikki suositukset ovat
automaattista analyysiä. Vastuu päätöksistä on käyttäjällä.
