# 📊 Henkilökohtainen AI-sijoitusassistentti

Henkilökohtainen työkalu Binance-salkun seurantaan. Tämä **ei ole** julkinen palvelu – se on tarkoitettu vain omaan käyttöön.

## Versio 1.0 – Ominaisuudet

- ✅ Yhteys Binance API:iin
- ✅ Spot-lompakon saldon haku
- ✅ Kaikkien omistusten näyttäminen
- ✅ Nykyiset markkinahinnat
- ✅ Salkun kokonaisarvon laskeminen
- ✅ 24h hintamuutokset
- ✅ Moderni web-käyttöliittymä (Bootstrap 5)
- ✅ Täysi virheenkäsittely ja lokitus
- ✅ Välimuisti (päivitys 60s välein)

> 🚫 **Ensimmäinen versio EI tee kauppoja.** Kaikki kaupankäyntitoiminnot on estetty.

---

## Käynnistys vaihe vaiheelta

### 1. Siirry oikeaan hakemistoon

```bash
cd investment-assistant
```

### 2. Luo virtuaaliympäristö (suositellaan)

```bash
python -m venv venv
source venv/bin/activate   # Linux / macOS
# tai
venv\Scripts\activate      # Windows
```

### 3. Asenna riippuvuudet

```bash
pip install -r requirements.txt
```

### 4. Lisää API-avaimet

Kopioi `.env.example` tiedostoksi `.env`:

```bash
cp .env.example .env
```

Muokkaa `.env`-tiedostoa ja lisää omat avaimesi:

```env
BINANCE_API_KEY=avaimesi_tähän
BINANCE_SECRET_KEY=salaisavaimesi_tähän
```

### 5. Käynnistä sovellus

```bash
python app.py
```

Avaa selain osoitteeseen: **http://localhost:5000**

---

## Kuinka Binance API-avaimet luodaan

1. Kirjaudu sisään [Binance](https://www.binance.com)-tilillesi
2. Siirry **Profiili → API Management**
3. Klikkaa **"Create API"**
4. Anna avaimelle nimi (esim. "Sijoitusassistentti")
5. **TÄRKEÄÄ – Oikeudet:**
   - ✅ Salli: **"Read info"** (luku)
   - ❌ ÄLÄ salli: Spot-kaupankäynti, nostot tai muut kirjoitusoikeudet
6. Tallenna API Key ja Secret Key `.env`-tiedostoon

> 💡 **Turvallisuusvinkki:** Rajoita API-avaimen IP-osoitteisiin, jos mahdollista.

---

## Kuinka ohjelma toimii

```
Selain → Flask (app.py)
           │
           ├─→ BinanceService    → Binance API (luku)
           │        │
           │        └─→ Tilitiedot, saldot
           │
           ├─→ MarketDataService → Binance API (hinnat)
           │        │
           │        └─→ Kaikki hinnat, 24h muutokset
           │
           └─→ PortfolioService  → Laskee kokonaisarvon
                    │
                    └─→ index.html (näytetään käyttäjälle)
```

### Tiedostorakenne

```
investment-assistant/
├── app.py                  # Flask-sovellus ja reitit
├── config.py               # Konfiguraatio (.env-lataus)
├── requirements.txt        # Python-riippuvuudet
├── README.md               # Tämä tiedosto
├── .env.example            # Esimerkki .env-tiedostosta
├── services/
│   ├── binance.py          # Binance API -yhteys
│   ├── market_data.py      # Markkinahinnat ja välimuisti
│   ├── portfolio.py        # Salkun laskenta
│   ├── openai_service.py   # AI-analyysi (tuleva)
│   ├── trading.py          # Kaupankäynti (tuleva, ESTETTY)
│   ├── risk_manager.py     # Riskienhallinta (tuleva)
│   └── report.py           # Raportointi (tuleva)
├── utils/
│   └── logger.py           # Lokitusjärjestelmä
├── templates/
│   └── index.html          # Web-käyttöliittymä
├── static/
│   └── style.css           # Tyylitiedosto
└── logs/                   # Automaattisesti luotava
    ├── app.log             # Kaikki lokit
    └── errors.log          # Vain virhelokit
```

---

## API-päätepisteet

| Reitti | Metodi | Kuvaus |
|--------|--------|--------|
| `/` | GET | Etusivu – salkun kokonaisnäkymä |
| `/api/salkku` | GET | JSON: salkun tiedot |
| `/api/salkku?pakota=true` | GET | JSON: pakottaa datan päivityksen |
| `/api/yhteys` | GET | JSON: Binance-yhteyden tila |
| `/api/paivita` | POST | Pakottaa kaikkien tietojen päivityksen |
| `/terveys` | GET | JSON: sovelluksen terveydenttila |

---

## Lokitiedostot

Lokit löytyvät `logs/`-hakemistosta:

- `logs/app.log` – Kaikki tapahtumat (DEBUG-taso)
- `logs/errors.log` – Vain virheilmoitukset

---

## Tulevat versiot

Seuraavissa versioissa lisätään:

- 🤖 **OpenAI-analyysi** – GPT-4 analysoi salkun ja antaa suosituksia
- 📰 **Uutisanalyysi** – Markkinauutisten sentimenttianalyysi
- 📈 **Tekninen analyysi** – RSI, MACD, liukuvat keskiarvot
- 🛡️ **Riskianalyysi** – Volatiliteetti, hajautus, VaR
- 📱 **Telegram-hyväksyntä** – Toimeksiantojen hyväksyntä Telegramissa
- 🔄 **Automaattiset toimeksiannot** – Kaupat käyttäjän hyväksynnän jälkeen

---

## Turvallisuus

- API-avaimia ei koskaan kirjoiteta koodiin
- Kaikki tunnukset ladataan `.env`-tiedostosta tai ympäristömuuttujista
- Ensimmäinen versio käyttää vain **lukuoikeuksia** (read-only)
- Kaupankäynti on ohjelmallisesti estetty ensimmäisessä versiossa
- Lisää `.env` `.gitignore`-tiedostoon ennen versionhallintaan siirtämistä!
