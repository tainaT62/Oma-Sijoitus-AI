"""
Gunicorn-asetukset tuotantoajoon.

Käyttö:
    gunicorn --config gunicorn.conf.py wsgi:sovellus
"""

import multiprocessing
import os

# ─── Verkko ───────────────────────────────────────────────────
# Oletuksena vain loopback: liikenne kulkee Nginxin kautta, eikä
# sovellus ole suoraan internetiin auki. Sovelluksessa EI ole vielä
# autentikaatiota (ks. Phase 3B), joten tämä on tärkeää.
bind = os.getenv("GUNICORN_BIND", "127.0.0.1:5000")
backlog = 128

# ─── Workerit ─────────────────────────────────────────────────
# Oletus on 1 worker + threadit, EI CPU-pohjaista worker-määrää.
#
# Syy: sovellus pitää tilaa prosessin muistissa (market_data-,
# sentiment-, news-, dashboard- ja ai_score-välimuistit) ja kirjoittaa
# yhteen SQLite-tiedostoon. Useampi worker
#   - pirstoisi välimuistit, jolloin sama data haettaisiin moneen kertaan
#   - moninkertaistaisi Binance-API-kutsut ja veisi kohti rate limitiä
#   - lisäisi SQLite-kirjoituskilpailua
# Rinnakkaisuus hoidetaan threadeilla, koska kuormitus on IO-sidonnaista
# (HTTP-kutsut Binanceen, RSS-syötteisiin ja OpenAI:hin).
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "8"))

# ─── Aikakatkaisut ────────────────────────────────────────────
# /api/dashboard tekee kylmällä välimuistilla kymmeniä peräkkäisiä
# Binance-kutsuja ja voi kestää kymmeniä sekunteja. Oletusaikakatkaisu
# (30 s) tappaisi workerin kesken pyynnön.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5

# ─── Prosessimalli ────────────────────────────────────────────
# preload_app = False on tarkoituksellinen.
#
# Preloadatessa app.py importattaisiin masterissa ennen forkkaamista,
# jolloin scheduler käynnistyisi masterissa – APSchedulerin threadit
# eivät kuitenkaan säily forkin yli, joten taustatehtävät eivät ajaisi
# lainkaan. Ilman preloadia jokainen worker importtaa sovelluksen itse
# ja scheduler-lukko (services/scheduler.py) valitsee niistä yhden.
preload_app = False

# ─── Lokitus ──────────────────────────────────────────────────
# systemd ottaa stdout/stderr talteen journaliin.
accesslog = os.getenv("GUNICORN_ACCESSLOG", "-")
errorlog = os.getenv("GUNICORN_ERRORLOG", "-")
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms'

# ─── Prosessin nimi ───────────────────────────────────────────
proc_name = "oma-sijoitus-ai"
