# Version 1.0 — Personal AI Portfolio Manager

Henkilökohtainen sijoitusanalyysijärjestelmä: seuraa salkkua kahdessa
brokerissa, analysoi markkinat ja lähettää yhden Telegram-raportin
aamussa.

---

## Turvallisuusmalli

Tämä on tärkein suunnitteluperiaate, ei jälkikäteen lisätty rajoitus.

**Kaupankäynti on rakenteellisesti mahdotonta.**
Brokerirajapinnoissa (`ibkr_service`, `binance`) ei ole
toimeksiantometodeja lainkaan – ei `osta`, `myy`, `place_order` eikä
mitään vastaavaa. Kyse ei ole pois kytketystä lipusta, jonka voi
vahingossa kääntää: metodeja ei yksinkertaisesti ole olemassa.
`services/trading.py` on säilytetty dokumentoituna kieltopintana, joka
kirjaa ja hylkää kutsut.

IBKR-yhteys avataan `readonly=True`. Binance-avaimelle riittää
`Enable Reading`.

**Sovellus on suojattu oletuksena.** Suojaus toteutetaan
`before_request`-käsittelijässä, joten myöhemmin lisätty reitti on
automaattisesti suojattu. Julkisia ovat vain kirjautumissivu ja
staattiset tiedostot.

**Suositukset ovat informatiivisia.** Käyttäjä tekee kaikki päätökset ja
toimeksiannot itse.

---

## Uudet ominaisuudet

### Monibrokerinen salkku
Krypto (Binance) ja osakkeet/ETF:t/rahastot (IBKR) yhtenä salkkuna.
Positiokohtaisesti arvo, tuotto, osuus, volatiliteetti, riskipisteet ja
hajautusvaikutus. Perusvaluutta EUR; kurssi Binancen EURUSDT-parista,
joten erillistä valuutta-API:a ei tarvita.

### Automaattinen kauppojen havainnointi
Peräkkäisiä tilannekuvia vertaamalla järjestelmä tunnistaa ostot,
lisäykset, osittaiset ja täydet myynnit. Havaitut ostot päivittävät
kuukausibudjetin itse. Muutoksen arvo haetaan ensisijaisesti
toteutuneesta kauppahinnasta (Binance `get_my_trades`), toissijaisesti
markkinahinnasta – käytetty lähde tallennetaan jokaiseen tapahtumaan.
Suhteellinen 0,5 %:n kynnys suodattaa pölysaldot ja pyöristykset.

### Neljä suositusluokkaa
`BUY` (ehdotettu summa), `HOLD`, `REDUCE` (myytävä osuus), `SELL` —
kaikissa luottamusprosentti, AI Score, riski ja perustelut.

### Kuukausibudjetti
Suositukset eivät koskaan ylitä jäljellä olevaa budjettia. Jos ehdotukset
ylittäisivät sen, ne hylätään kokonaan ja tapahtuma kirjataan virheenä.
Budjetin loputtua sallitaan vain korvaava osto, joka rahoitetaan
myynnistä vapautuvalla pääomalla.

### Markkinatilanteeseen mukautuva allokaatio
Lähtökohta 40 % ETF / 30 % osakkeet / 30 % krypto. Krypton yliarvostus
puolittaa kryptaosuuden, kohonnut riski pienentää kaikkia osuuksia ja
äärimmäinen riski estää ostot kokonaan.

### Brokerien käteinen erillään
Kryptaa voi ostaa vain Binance-käteisellä, osakkeita ja ETF:iä vain
IBKR-käteisellä. Saldoja ei yhdistetä missään vaiheessa.

### Portfolio Score
0–100 kuudesta osatekijästä: hajautus (25 %), riski (20 %), allokaatio
(20 %), kassavaranto (15 %), markkinatilanne (10 %), budjetin käyttö
(10 %). Heikoin osatekijä nostetaan esiin raportin alussa.

### Päivittäinen Telegram-raportti
Portfolio Score, markkinakatsaus, allokaatio tavoitteeseen verrattuna,
havaitut muutokset, kuukausibudjetti, suositukset omaisuusluokittain ja
watchlistin viisi kiinnostavinta kohdetta. Yksi viesti vuorokaudessa,
4096 merkin raja huomioiden.

### Tuotantoinfrastruktuuri
Gunicorn, systemd-yksikkö suojauksineen, Nginx-kokoonpano TLS:llä,
ProxyFix, salasanakirjautuminen, CSRF, kirjautumisyritysten rajoitus,
turvaotsakkeet.

---

## Arkkitehtuuri

```
Binance ──┐
          ├──► portfolio_service ──► portfolio_score
IBKR ─────┘          │
                     ▼
              sync_service ──► budget_service
                     │              │
                     └──────┬───────┘
                            ▼
                 recommendation_engine
                            │
                            ▼
                  telegram_formatter
```

Kerrokset: brokerit → salkku → synkronointi ja budjetti → suositukset →
esitys. Analyysipalvelut (`technical_analysis`, `sentiment`,
`news_service`, `ai_score`, `risk_manager`) ovat jaettuja ja
välimuistitettuja.

---

## Tunnetut rajoitukset

1. Osakkeiden ja ETF:ien tekninen analyysi puuttuu — ei hintahistoriaa
   ennen IBKR-yhteyttä. Suositukset perustuvat position tunnuslukuihin,
   ja raportti kertoo tämän.
2. Osakkeiden allokaatio on 0 € kunnes markkinadataa on saatavilla.
3. IBKR-data on esimerkkidataa `mock`-tilassa.
4. Kryptan hankintahintaa ei ole → tuottoprosentti puuttuu.
5. IBKR-kauppojen arvotus käyttää markkinahintaa.
6. Aiempia suosituksia ei käytetä analyysin syötteenä.
7. Kirjautumisrajoitin on prosessin muistissa.
8. Automaattitestejä ei ole; validointi on tehty ajamalla.

---

## Version 2 -tiekartta

1. **IBKR live** — positiot, hintahistoria, `ib.fills()`. Avaa
   osakkeiden teknisen analyysin, todelliset osakesuositukset ja
   täyden 40/30/30-allokaation.
2. **Automaattitestit ja CI** — indikaattorimatematiikka, suositussäännöt,
   synkronoinnin diffilogiikka, suojauskerros.
3. **Suositusten oppiminen** — toteutuneiden suositusten seuranta ja
   painotusten säätö tuloksen perusteella.
4. **Kryptan hankintahinta** kauppahistoriasta → todelliset tuotot.
5. **Dashboardin laajennus** — Portfolio Score, budjetti ja havaitut
   muutokset selainkäyttöliittymään.

---

*Automaattinen analyysi, ei sijoitusneuvontaa.*
