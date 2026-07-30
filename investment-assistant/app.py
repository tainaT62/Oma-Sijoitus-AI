"""
Henkilökohtainen AI-sijoitusassistentti – v3.0
Institutionaalisen tason analyysijärjestelmä.

Uudet ominaisuudet:
- SQLite-historiatietokanta
- Backtest-moottori
- Watchlist
- AI Score
- Päivittäinen raportti
- Tausta-scheduler
"""

import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from utils.logger import logger
from config import config

# ─── Palvelut ─────────────────────────────────────────────────
from services.binance import binance_service
from services.portfolio import portfolio_service
from services.technical_analysis import technical_analysis_service
from services.sentiment import sentiment_service
from services.news_service import news_service
from services.recommendation_engine import recommendation_engine
from services.risk_manager import risk_manager_service
from services.portfolio_optimizer import portfolio_optimizer_service
from services.ai_engine import ai_engine
from services.dashboard import dashboard_service
from services.watchlist import watchlist_service
from services.ai_score import ai_score_service
from services.backtest import backtest_moottori
from services.daily_report import daily_report_service
from services.scheduler import scheduler_service
from services import database as db

# ─── Flask ────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

logger.info("=" * 60)
logger.info("AI-sijoitusassistentti v3.0 käynnistyy...")
logger.info(f"Portti: {config.PORT} | OpenAI: {'✓' if ai_engine.kaytossa else '✗'}")
logger.info("=" * 60)

# Tarkista konfiguraatio
validointi = config.validate()
if not validointi["valid"]:
    for v in validointi["virheet"]:
        logger.warning(f"Konfigurointivaroitus: {v}")

# Käynnistä scheduler
scheduler_service.kaynnista()


# ─── SIVUREITIT ───────────────────────────────────────────────

@app.route("/")
def etusivu():
    """Pääsivu – institutionaalinen dashboard."""
    konfigurointi_ok = config.validate()
    yhteys_tila = {
        "ok": binance_service.yhteys_ok,
        "virhe": binance_service.virheviesti if not binance_service.yhteys_ok else None
    }
    return render_template(
        "dashboard.html",
        yhteys=yhteys_tila,
        konfigurointi=konfigurointi_ok,
        nyt=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        versio="3.0.0",
        ai_kaytossa=ai_engine.kaytossa
    )


@app.route("/portfolio")
def portfolio_sivu():
    """Yksityiskohtainen portfolio-näkymä."""
    salkku = portfolio_service.hae_salkku()
    yhteys_tila = {"ok": binance_service.yhteys_ok, "virhe": binance_service.virheviesti if not binance_service.yhteys_ok else None}
    return render_template("index.html", salkku=salkku, yhteys=yhteys_tila,
        konfigurointi=config.validate(), nyt=datetime.now().strftime("%d.%m.%Y %H:%M:%S"), versio="3.0.0")


# ─── API: DASHBOARD ───────────────────────────────────────────

@app.route("/api/dashboard")
def api_dashboard():
    """Kaikki dashboard-data yhdessä kutsussa."""
    try:
        pakota = request.args.get("pakota", "false").lower() == "true"
        data = dashboard_service.hae_dashboard_data(pakota_paivitys=pakota)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Virhe /api/dashboard: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: PORTFOLIO ───────────────────────────────────────────

@app.route("/api/portfolio")
def api_portfolio():
    try:
        pakota = request.args.get("pakota", "false").lower() == "true"
        return jsonify(portfolio_service.hae_salkku(pakota_paivitys=pakota))
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/api/portfolio/historia")
def api_portfolio_historia():
    """Salkun arvohistoria kaaviolle."""
    try:
        paivia = int(request.args.get("paivia", 30))
        historia = db.hae_portfolio_historia(paivia)
        tuotot = db.hae_paivittaiset_tuotot(paivia)
        return jsonify({"ok": True, "historia": historia, "tuotot": tuotot})
    except Exception as e:
        logger.error(f"Virhe /api/portfolio/historia: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: TEKNINEN ANALYYSI ───────────────────────────────────

@app.route("/api/technical")
def api_technical():
    try:
        symboli = request.args.get("symboli", "BTCUSDT").upper()
        aikavali = request.args.get("aikaväli", "1h")
        return jsonify(technical_analysis_service.analysoi(symboli, aikavali))
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: SENTIMENTTI ─────────────────────────────────────────

@app.route("/api/sentiment")
def api_sentiment():
    try:
        pakota = request.args.get("pakota", "false").lower() == "true"
        return jsonify(sentiment_service.hae_kokonaissentimentti(pakota_paivitys=pakota))
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: UUTISET ─────────────────────────────────────────────

@app.route("/api/news")
def api_news():
    try:
        symboli = request.args.get("symboli", None)
        pakota = request.args.get("pakota", "false").lower() == "true"
        uutiset = (news_service.hae_symbolin_uutiset(symboli.upper(), 10)
                   if symboli else news_service.hae_uutiset(pakota_paivitys=pakota))
        return jsonify({"ok": True, "uutiset": uutiset[:20], "maara": len(uutiset),
                        "cache_tiedot": news_service.hae_cache_tiedot()})
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: SUOSITUKSET ─────────────────────────────────────────

@app.route("/api/recommendation")
def api_recommendation():
    try:
        symbolit_param = request.args.get("symbolit", None)
        symbolit = symbolit_param.upper().split(",") if symbolit_param else None
        pakota = request.args.get("pakota", "false").lower() == "true"
        suositukset = recommendation_engine.hae_suositukset(symbolit=symbolit, pakota_paivitys=pakota)
        return jsonify({"ok": True, "suositukset": suositukset, "maara": len(suositukset)})
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: AI-ANALYYSI ─────────────────────────────────────────

@app.route("/api/analysis")
def api_analysis():
    try:
        btc_tech = technical_analysis_service.analysoi("BTCUSDT", "4h")
        sentimentti = sentiment_service.hae_kokonaissentimentti()
        otsikot = news_service.hae_otsikot_analyysiin(15)
        salkku = portfolio_service.hae_salkku()
        return jsonify(ai_engine.analysoi_markkinat(btc_tech, sentimentti, otsikot, salkku))
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: AI SCORE ────────────────────────────────────────────

@app.route("/api/ai-score")
def api_ai_score():
    """AI Score -pisteet kaikille watchlist-kohteille."""
    try:
        pakota = request.args.get("pakota", "false").lower() == "true"
        watchlist = watchlist_service.hae_watchlist()
        symbolit = [k["symboli"] for k in watchlist if k.get("tyyppi") == "crypto"]

        if not symbolit:
            symbolit = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

        pisteet = ai_score_service.laske_kaikki_pisteet(symbolit[:8])

        # Hae myös DB:n viimeisimmät pisteet
        db_pisteet = db.hae_viimeisimmät_ai_pisteet()

        return jsonify({
            "ok": True,
            "pisteet": pisteet,
            "db_historia": db_pisteet[:10],
            "laskettu": time.time()
        })
    except Exception as e:
        logger.error(f"Virhe /api/ai-score: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: WATCHLIST ───────────────────────────────────────────

@app.route("/api/watchlist", methods=["GET"])
def api_watchlist_hae():
    """Hakee watchlistin hinnoilla."""
    try:
        watchlist = watchlist_service.hae_watchlist_analyysi()
        return jsonify({"ok": True, "watchlist": watchlist, "maara": len(watchlist)})
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/api/watchlist", methods=["POST"])
def api_watchlist_lisaa():
    """Lisää kohteen watchlistiin."""
    try:
        data = request.get_json() or {}
        symboli = data.get("symboli", "").strip()
        nimi = data.get("nimi", "")
        tyyppi = data.get("tyyppi", "crypto")

        if not symboli:
            return jsonify({"ok": False, "virhe": "Symboli puuttuu"}), 400

        tulos = watchlist_service.lisaa(symboli, nimi, tyyppi)
        return jsonify(tulos)
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/api/watchlist/<symboli>", methods=["DELETE"])
def api_watchlist_poista(symboli):
    """Poistaa kohteen watchlistista."""
    try:
        tulos = watchlist_service.poista(symboli)
        return jsonify(tulos)
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: BACKTEST ────────────────────────────────────────────

@app.route("/api/backtest")
def api_backtest():
    """Ajaa backtestin annetulle symbolille."""
    try:
        symboli = request.args.get("symboli", "BTCUSDT").upper()
        alkupaaoma = float(request.args.get("paaoma", 10000))

        # Ensin tarkista tallennettu historia
        historia = backtest_moottori.analysoi_tallennetut_suositukset()

        # Sitten simulaatio
        simulaatio = backtest_moottori.simuloi_yksinkertainen_strategia(
            symboli=symboli, alkupaaoma=alkupaaoma
        )

        return jsonify({
            "ok": True,
            "symboli": symboli,
            "simulaatio": simulaatio,
            "suositushistoria": historia
        })
    except Exception as e:
        logger.error(f"Virhe /api/backtest: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: PÄIVÄRAPORTTI ───────────────────────────────────────

@app.route("/api/raportti")
def api_raportti():
    """Hakee tai generoi päivittäisen raportin."""
    try:
        pakota = request.args.get("pakota", "false").lower() == "true"
        raportti = daily_report_service.generoi_raportti(pakota_paivitys=pakota)
        return jsonify(raportti)
    except Exception as e:
        logger.error(f"Virhe /api/raportti: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: HISTORIA ────────────────────────────────────────────

@app.route("/api/historia/sentimentti")
def api_historia_sentimentti():
    try:
        paivia = int(request.args.get("paivia", 30))
        return jsonify({"ok": True, "data": db.hae_sentimenttihistoria(paivia)})
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/api/historia/suositukset")
def api_historia_suositukset():
    try:
        symboli = request.args.get("symboli", None)
        maara = int(request.args.get("maara", 20))
        return jsonify({"ok": True, "data": db.hae_suositushistoria(symboli, maara)})
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


# ─── API: JÄRJESTELMÄ ─────────────────────────────────────────

@app.route("/api/yhteys")
def api_yhteys():
    return jsonify(binance_service.testaa_yhteys())


@app.route("/api/paivita", methods=["POST"])
def api_paivita():
    try:
        logger.info("Manuaalinen kokonaispäivitys käynnistetty")
        data = dashboard_service.hae_dashboard_data(pakota_paivitys=True)
        return jsonify({"ok": True, "viesti": "Kaikki tiedot päivitetty",
                        "latausaika_s": data.get("latausaika_s")})
    except Exception as e:
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/terveys")
def terveys():
    return jsonify({
        "tila": "toimii", "versio": "3.0.0",
        "binance": binance_service.yhteys_ok,
        "openai": ai_engine.kaytossa,
        "scheduler": scheduler_service.hae_tila().get("kaynnissa", False),
        "tietokanta": db.hae_tietokannan_tilastot(),
        "aika": datetime.now().isoformat()
    })


@app.route("/api/scheduler")
def api_scheduler():
    return jsonify(scheduler_service.hae_tila())


@app.route("/api/db/tilastot")
def api_db_tilastot():
    return jsonify({"ok": True, "tilastot": db.hae_tietokannan_tilastot()})


# ─── VIRHEENKÄSITTELIJÄT ──────────────────────────────────────

@app.errorhandler(404)
def ei_loydy(e):
    return jsonify({"virhe": "Ei löydy"}), 404

@app.errorhandler(500)
def palvelinvirhe(e):
    logger.error(f"500: {e}", exc_info=True)
    return jsonify({"virhe": "Palvelinvirhe"}), 500


# ─── KÄYNNISTYS ───────────────────────────────────────────────

if __name__ == "__main__":
    # HUOM: tämä on Flaskin KEHITYSPALVELIN – vain paikalliseen käyttöön.
    # Tuotannossa: gunicorn --config gunicorn.conf.py wsgi:sovellus
    # Ks. deploy/README.md
    logger.warning("Käynnistetään Flaskin kehityspalvelin – älä käytä tuotannossa")
    logger.info(f"Palvelin: http://{config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
