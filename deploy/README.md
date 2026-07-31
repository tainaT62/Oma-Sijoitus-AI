# Tuotantoasennus – Ubuntu VPS

Tämä hakemisto sisältää tuotantoajon tiedostot. Sovellus ajetaan
Gunicornilla systemd-palveluna.

Arkkitehtuuri:

```
Internet --HTTPS--> Nginx (443) --HTTP--> Gunicorn (127.0.0.1:5000) --> Flask
```

Gunicorn ei kuuntele koskaan julkista osoitetta. TLS päättyy Nginxiin.

---

## Vaatimukset

| | |
|---|---|
| Käyttöjärjestelmä | Ubuntu 22.04 LTS tai 24.04 LTS |
| Python | 3.10+ (22.04 = 3.10, 24.04 = 3.12) |
| Riippuvuudet | `investment-assistant/requirements.txt` |

---

## 1. Käyttäjä ja hakemistot

```bash
sudo adduser --system --group --home /opt/oma-sijoitus-ai sijoitus
sudo mkdir -p /opt/oma-sijoitus-ai
sudo chown sijoitus:sijoitus /opt/oma-sijoitus-ai
```

## 2. Koodi ja virtuaaliympäristö

```bash
sudo -u sijoitus git clone https://github.com/tainaT62/Oma-Sijoitus-AI.git /opt/oma-sijoitus-ai
sudo -u sijoitus python3 -m venv /opt/oma-sijoitus-ai/.venv
sudo -u sijoitus /opt/oma-sijoitus-ai/.venv/bin/pip install --upgrade pip
sudo -u sijoitus /opt/oma-sijoitus-ai/.venv/bin/pip install -r /opt/oma-sijoitus-ai/investment-assistant/requirements.txt
```

`requirements.txt` on riippuvuuksien **ainoa** lähde. Juuren
`pyproject.toml` peilaa sitä; älä asenna sen pohjalta.

## 3. Ympäristömuuttujat

Salaisuudet pidetään pois repositoriosta ja pois systemd-unitista.

```bash
sudo mkdir -p /etc/oma-sijoitus-ai
sudo cp /opt/oma-sijoitus-ai/investment-assistant/.env.example /etc/oma-sijoitus-ai/env
sudo nano /etc/oma-sijoitus-ai/env      # lisää oikeat avaimet
sudo chown root:sijoitus /etc/oma-sijoitus-ai/env
sudo chmod 0640 /etc/oma-sijoitus-ai/env
```

Binance-avaimelle annetaan **vain lukuoikeudet**. Sovellus ei tee
kauppoja, ja kaupankäynti on estetty koodissa.

### Pakolliset turvallisuusarvot

Sovellus **ei käynnisty** ilman näitä – tarkistus tehdään heti
käynnistyksessä eikä sitä voi ohittaa.

**`SECRET_KEY`** – allekirjoittaa istuntoevästeen:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**`APP_PASSWORD_HASH`** – salasanan tiiviste. Selkotekstistä salasanaa
ei tallenneta minnekään. Komento kysyy salasanan, joten se ei päädy
komentohistoriaan:

```bash
python3 -c "from werkzeug.security import generate_password_hash as g; import getpass; print(g(getpass.getpass()))"
```

Jos komento kaatuu virheeseen `module 'hashlib' has no attribute
'scrypt'`, Pythonin OpenSSL ei tue scryptiä. Käytä silloin:
`g(getpass.getpass(), method="pbkdf2:sha256")`. Ubuntun oletus-Python
tukee scryptiä.

Sovellus hylkää käynnistyksen myös, jos `SECRET_KEY` on tunnettu
oletusarvo, alle 32 merkkiä, tai jos `APP_PASSWORD_HASH` näyttää
selkotekstiseltä salasanalta.

## 4. Palvelu

```bash
sudo cp /opt/oma-sijoitus-ai/deploy/oma-sijoitus-ai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now oma-sijoitus-ai
sudo systemctl status oma-sijoitus-ai
```

Lokit:

```bash
sudo journalctl -u oma-sijoitus-ai -f
```

## 5. Toiminnan tarkistus

Kaikki reitit vaativat kirjautumisen, joten pelkkä `curl` palauttaa
401:n. Se on oikea tulos ja riittää elossaolon toteamiseen:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/api/scheduler
# 401 = palvelu vastaa ja suojaus on päällä
```

Kirjautuneena (evästeistunto) `/api/scheduler` palauttaa
`"kaynnissa": true` ja neljä tehtävää. Selaimella: avaa
`http://127.0.0.1:5000/`, joka ohjaa kirjautumissivulle.

---

## Scheduler ja worker-määrä

Taustascheduler käynnistyy **täsmälleen yhdessä prosessissa**. Varmistus
on kaksitasoinen:

1. `ENABLE_SCHEDULER` (oletus `true`) kytkee sen kokonaan päälle/pois.
2. Tiedostolukko `data/scheduler.lock` (flock) varmistaa, että vaikka
   workereita olisi useita, vain yksi ajaa taustatehtävät. Lukko
   vapautuu automaattisesti prosessin kuollessa, joten scheduler siirtyy
   itsestään toiselle workerille.

`gunicorn.conf.py` käyttää oletuksena **1 workeria ja 8 threadia**. Tämä
on tarkoituksellista: sovellus pitää välimuistit prosessin muistissa ja
kirjoittaa yhteen SQLite-tiedostoon. Useampi worker pirstoisi
välimuistit ja moninkertaistaisi Binance-kutsut. Kuormitus on
IO-sidonnaista, joten threadit riittävät rinnakkaisuuteen.

---

## Ympäristömuuttujat

| Muuttuja | Oletus | Kuvaus |
|---|---|---|
| `BINANCE_API_KEY` | – | Pakollinen, vain luku |
| `BINANCE_SECRET_KEY` | – | Pakollinen |
| `OPENAI_API_KEY` | – | Valinnainen; ilman tätä käytetään sääntöpohjaista analyysia |
| `SECRET_KEY` | – | Aseta satunnaiseksi |
| `ENABLE_SCHEDULER` | `true` | Taustatehtävät päälle/pois |
| `SCHEDULER_LOCK_PATH` | `data/scheduler.lock` | Yksinoikeuslukon sijainti |
| `GUNICORN_BIND` | `127.0.0.1:5000` | Kuunneltava osoite |
| `GUNICORN_WORKERS` | `1` | Ks. yllä ennen kasvattamista |
| `GUNICORN_THREADS` | `8` | |
| `GUNICORN_TIMEOUT` | `120` | `/api/dashboard` voi olla hidas kylmällä välimuistilla |
| `APP_PASSWORD_HASH` | – | **Pakollinen.** Salasanan tiiviste |
| `SESSION_LIFETIME_HOURS` | `12` | Istunnon elinikä |
| `SESSION_COOKIE_SECURE` | `true` | Pidä true. `false` vain paikallisessa HTTP-testissä |
| `LOGIN_MAX_ATTEMPTS` | `5` | Epäonnistuneet yritykset ennen lukitusta |
| `LOGIN_LOCKOUT_MINUTES` | `15` | Lukituksen kesto |
| `TRUSTED_PROXY_COUNT` | `0` | `1` Nginxin takana, muuten `0`. Ks. kohta 6.4 |

`FLASK_DEBUG` **ei saa** olla `true` tuotannossa – se avaa Werkzeugin
debuggerin, joka mahdollistaa koodin ajon etänä.

---

## 6. Käänteisproxy ja TLS

Ilman TLS:ää salasana kulkisi selkotekstinä. Tee tämä ennen kuin avaat
palvelimen internetiin.

### 6.1 Verkkotunnus

Osoita verkkotunnuksen A-tietue (ja AAAA, jos IPv6) VPS:n IP-osoitteeseen
ja odota, että nimipalvelu on levinnyt.

### 6.2 Nginx

```bash
sudo apt install -y nginx
sudo cp /opt/oma-sijoitus-ai/deploy/nginx-oma-sijoitus-ai.conf \
        /etc/nginx/sites-available/oma-sijoitus-ai
sudo ln -s /etc/nginx/sites-available/oma-sijoitus-ai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
```

Korvaa `sijoitus.esimerkki.fi` omalla verkkotunnuksellasi (2 kohtaa).

### 6.3 Varmenne

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d sijoitus.esimerkki.fi
sudo systemctl status certbot.timer     # automaattinen uusinta
```

Certbot lisää varmennepolut itse. Testaa uusinta:
`sudo certbot renew --dry-run`.

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 6.4 Sovelluksen asetukset proxya varten

Lisää `/etc/oma-sijoitus-ai/env`:

```
TRUSTED_PROXY_COUNT=1
SESSION_COOKIE_SECURE=true
```

```bash
sudo systemctl restart oma-sijoitus-ai
```

> ⚠️ **`TRUSTED_PROXY_COUNT` ja Nginx kuuluvat yhteen.**
> Arvo `1` ilman Nginxiä tarkoittaa, että kuka tahansa voi väärentää
> `X-Forwarded-For`-otsakkeen ja kiertää kirjautumisrajoituksen.
> Nginx-kokoonpano ylikirjoittaa otsakkeen, joten yhdessä ne ovat
> turvallisia. Ilman proxya arvo on `0`.

### 6.5 Palomuuri

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

Porttia 5000 **ei** avata: Gunicorn kuuntelee vain loopbackia.

### 6.6 Tarkistus

```bash
curl -sI http://sijoitus.esimerkki.fi        | head -1   # 301
curl -sI https://sijoitus.esimerkki.fi/kirjaudu | head -1   # 200
curl -s -o /dev/null -w '%{http_code}\n' https://sijoitus.esimerkki.fi/api/scheduler   # 401
curl -sI https://sijoitus.esimerkki.fi/kirjaudu | grep -i strict-transport
```

Tarkista journalista, että sovellus näkee oikean asiakas-IP:n eikä
`127.0.0.1`:tä:

```bash
sudo journalctl -u oma-sijoitus-ai | grep Kirjautuminen
```

---

## Autentikaatio ja istunnot

Kaikki reitit ovat suojattuja oletuksena (*fail closed*): suojaus
toteutetaan `before_request`-käsittelijässä, jolloin myöhemmin lisätty
reitti on automaattisesti suojattu. Julkisia ovat vain kirjautumissivu
ja staattiset tiedostot.

- Kirjautumaton API-kutsu -> `401` + JSON.
- Kirjautumaton sivupyyntö -> `302` kirjautumissivulle.
- Istuntoeväste: `HttpOnly`, `SameSite=Lax`, `Secure` (oletus),
  allekirjoitettu `SECRET_KEY`:llä ja vanhenee itsestään.
- Tilaa muuttavat pyynnöt (POST/PUT/PATCH/DELETE) vaativat
  CSRF-tokenin `X-CSRF-Token`-otsakkeessa tai lomakekentässä.
- Kirjautumisyritykset rajoitetaan IP-kohtaisesti. Rajoitin on
  prosessin muistissa, joten se toimii yhden workerin oletusajossa;
  useammalla workerilla raja on worker-kohtainen.

Uloskirjautuminen on POST-lomake, jotta pelkkä linkin avaaminen ei
päätä istuntoa.

---

## Päivitys

```bash
sudo -u sijoitus git -C /opt/oma-sijoitus-ai pull
sudo -u sijoitus /opt/oma-sijoitus-ai/.venv/bin/pip install -r /opt/oma-sijoitus-ai/investment-assistant/requirements.txt
sudo systemctl restart oma-sijoitus-ai
```

## Varmuuskopiot

Kaikki historia on yhdessä tiedostossa: `investment-assistant/data/assistant.db`.
Se ei ole versionhallinnassa. Ota siitä varmuuskopio erikseen, esim.

```bash
sqlite3 /opt/oma-sijoitus-ai/investment-assistant/data/assistant.db ".backup /var/backups/assistant-$(date +%F).db"
```

---

## Vianetsintä

**Palvelu ei käynnisty.** Unit käyttää tiukkoja suojauksia. Jos
käynnistys epäonnistuu heti, kokeile poistaa ensin
`MemoryDenyWriteExecute=true` ja sen jälkeen `SystemCallFilter`-rivit –
ne ovat yleisimmät syyt käännettyjen riippuvuuksien kanssa.

**Käynnistys jää jumiin ja aikakatkaistaan.** Unit käyttää
`Type=notify`, joka odottaa Gunicornin readiness-viestiä. Jos se ei tule,
vaihda `Type=exec`.

**`/api/scheduler` palauttaa `kaynnissa: false`.** Jos workereita on
enemmän kuin yksi, pyyntö osui workeriin joka ei omista lukkoa. Se on
odotettua. Tarkista journalista rivi `Scheduler käynnistetty
onnistuneesti (pid …)` – niitä pitää olla täsmälleen yksi.

**Kirjoitusoikeusvirheet.** `ProtectSystem=strict` tekee tiedostojärjestelmästä
vain luettavan. `data/` ja `logs/` on sallittu `ReadWritePaths`-riveillä;
jos siirrät ne muualle, päivitä unit vastaavasti.

**Kirjautuminen ei onnistu: lomake palaa aina takaisin.** Todennäköisin
syy on `SESSION_COOKIE_SECURE=true` yhdistettynä salaamattomaan
HTTP-yhteyteen – selain ei silloin tallenna evästettä lainkaan, joten
istuntoa ei synny. Oikea korjaus on ottaa TLS käyttöön. Pelkässä
paikallisessa testissä voi käyttää `SESSION_COOKIE_SECURE=false`, mutta
sitä ei saa jättää päälle tuotannossa.

**Kirjautuminen lukittu.** Viisi epäonnistunutta yritystä lukitsee
15 minuutiksi. Lukitus on prosessin muistissa, joten palvelun
uudelleenkäynnistys `sudo systemctl restart oma-sijoitus-ai` nollaa sen.

**Salasanan vaihto.** Luo uusi tiiviste, päivitä `APP_PASSWORD_HASH`
tiedostoon `/etc/oma-sijoitus-ai/env` ja käynnistä palvelu uudelleen.
Vaihda samalla `SECRET_KEY`, jos haluat mitätöidä avoimet istunnot.
