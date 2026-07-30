# Tuotantoasennus – Ubuntu VPS

Tämä hakemisto sisältää tuotantoajon tiedostot. Sovellus ajetaan
Gunicornilla systemd-palveluna.

> ⚠️ **Sovelluksessa ei ole vielä autentikaatiota.** Gunicorn kuuntelee
> oletuksena vain `127.0.0.1:5000`. Älä avaa porttia internetiin ennen
> kuin Phase 3B (autentikaatio + Nginx + TLS) on tehty.

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

```bash
curl -s http://127.0.0.1:5000/terveys | python3 -m json.tool
curl -s http://127.0.0.1:5000/api/scheduler | python3 -m json.tool
```

`/api/scheduler` palauttaa `"kaynnissa": true` ja neljä tehtävää.

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

`FLASK_DEBUG` **ei saa** olla `true` tuotannossa – se avaa Werkzeugin
debuggerin, joka mahdollistaa koodin ajon etänä.

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
