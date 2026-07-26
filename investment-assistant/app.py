"""
Henkilökohtainen AI-sijoitusassistentti
Flask-sovellus – reitit ja API-päätepisteet

Versio 2.0 – Täysi analyysijärjestelmä (ei kauppoja)
"""

import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from utils.logger import logger
from config import config
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

# ─── Flask-sovellus ───────────────────────────────────────────

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

logger.info("=" * 60)
logger.info("AI-sijoitusassistentti v2.0 käynnistyy...")
logger.info(f"Portti: {config.PORT}")
logger.info(f"OpenAI: {'käytössä' if ai_engine.kaytossa else 'ei käytössä'}")
logger.info("=" * 60)

# Tarkista konfiguraatio
validointi = config.validate()
if not validointi["valid"]:
    for v in validointi["virheet"]:
        logger.warning(f"Konfigurointivaroitus: {v}")


# ─── Sivureitit ───────────────────────────────────────────────


@app.route("/")
def etusivu():
    """Pääsivu – moderni dashboard."""
    try:
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
            versio="2.0.0",
            ai_kaytossa=ai_engine.kaytossa
        )
    except Exception as e:
        logger.error(f"Virhe etusivun latauksessa: {e}", exc_info=True)
        return f"<h1>Palvelinvirhe</h1><p>{e}</p>", 500


@app.route("/portfolio")
def portfolio_sivu():
    """Vanha portfolio-näkymä (yhteensopivuus)."""
    try:
        salkku = portfolio_service.hae_salkku()
        yhteys_tila = {
            "ok": binance_service.yhteys_ok,
            "virhe": binance_service.virheviesti if not binance_service.yhteys_ok else None
        }
        konfigurointi_ok = config.validate()
        return render_template(
            "index.html",
            salkku=salkku,
            yhteys=yhteys_tila,
            konfigurointi=konfigurointi_ok,
            nyt=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            versio="2.0.0"
        )
    except Exception as e:
        logger.error(f"Virhe portfolio-sivun latauksessa: {e}", exc_info=True)
        return f"<h1>Palvelinvirhe</h1><p>{e}</p>", 500


# ─── API-päätepisteet ─────────────────────────────────────────


@app.route("/api/dashboard")
def api_dashboard():
    """
    Palauttaa kaiken dashboardin tarvitseman datan yhdessä kutsussa.
    Parametri: ?pakota=true päivittää kaikki välimuistit.
    """
    try:
        pakota = request.args.get("pakota", "false").lower() == "true"
        data = dashboard_service.hae_dashboard_data(pakota_paivitys=pakota)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Virhe /api/dashboard: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/api/portfolio")
def api_portfolio():
    """
    Palauttaa salkun tiedot.
    Parametri: ?pakota=true pakottaa päivityksen.
    """
    try:
        pakota = request.args.get("pakota", "false").lower() == "true"
        salkku = portfolio_service.hae_salkku(pakota_paivitys=pakota)
        return jsonify(salkku)
    except Exception as e:
        logger.error(f"Virhe /api/portfolio: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/api/technical")
def api_technical():
    """
    Palauttaa teknisen analyysin annetulle symbolille.
    Parametri: ?symboli=BTCUSDT&aikaväli=1h
    """
    try:
        symboli = request.args.get("symboli", "BTCUSDT").upper()
        aikavali = request.args.get("aikaväli", "1h")
        tulos = technical_analysis_service.analysoi(symboli, aikavali)
        return jsonify(tulos)
    except Exception as e:
        logger.error(f"Virhe /api/technical: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/api/sentiment")
def api_sentiment():
    """
    Palauttaa markkinasentimentin (Fear & Greed, uutiset, Reddit).
    """
    try:
        pakota = request.args.get("pakota", "false").lower() == "true"
        tulos = sentiment_service.hae_kokonaissentimentti(pakota_paivitys=pakota)
        return jsonify(tulos)
    except Exception as e:
        logger.error(f"Virhe /api/sentiment: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/api/news")
def api_news():
    """
    Palauttaa viimeisimmät kryptouutiset.
    Parametri: ?symboli=BTC hakee symbolin uutiset
    """
    try:
        symboli = request.args.get("symboli", None)
        pakota = request.args.get("pakota", "false").lower() == "true"

        if symboli:
            uutiset = news_service.hae_symbolin_uutiset(symboli.upper(), maara=10)
        else:
            uutiset = news_service.hae_uutiset(pakota_paivitys=pakota)

        return jsonify({
            "ok": True,
            "uutiset": uutiset[:20],
            "maara": len(uutiset),
            "cache_tiedot": news_service.hae_cache_tiedot()
        })
    except Exception as e:
        logger.error(f"Virhe /api/news: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/api/recommendation")
def api_recommendation():
    """
    Palauttaa sijoitussuositukset.
    Parametri: ?symbolit=BTCUSDT,ETHUSDT
    """
    try:
        symbolit_param = request.args.get("symbolit", None)
        symbolit = symbolit_param.upper().split(",") if symbolit_param else None
        pakota = request.args.get("pakota", "false").lower() == "true"

        suositukset = recommendation_engine.hae_suositukset(
            symbolit=symbolit,
            pakota_paivitys=pakota
        )
        return jsonify({
            "ok": True,
            "suositukset": suositukset,
            "maara": len(suositukset),
            "vastuuvapauslauseke": (
                "Nämä ovat automaattisia analyysejä, eivät sijoitusneuvoja. "
                "Tee aina oma tutkimuksesi."
            )
        })
    except Exception as e:
        logger.error(f"Virhe /api/recommendation: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/api/analysis")
def api_analysis():
    """
    Palauttaa AI-pohjaisen markkina-analyysin.
    """
    try:
        btc_tech = technical_analysis_service.analysoi("BTCUSDT", "4h")
        sentimentti = sentiment_service.hae_kokonaissentimentti()
        otsikot = news_service.hae_otsikot_analyysiin(15)
        salkku = portfolio_service.hae_salkku()

        analyysi = ai_engine.analysoi_markkinat(
            btc_tech, sentimentti, otsikot, salkku
        )
        return jsonify(analyysi)
    except Exception as e:
        logger.error(f"Virhe /api/analysis: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/api/yhteys")
def api_yhteys():
    """Testaa Binance-yhteyden."""
    try:
        tulos = binance_service.testaa_yhteys()
        return jsonify(tulos)
    except Exception as e:
        logger.error(f"Virhe /api/yhteys: {e}", exc_info=True)
        return jsonify({"ok": False, "viesti": str(e)}), 500


@app.route("/api/paivita", methods=["POST"])
def api_paivita():
    """Pakottaa kaikkien tietojen päivityksen."""
    try:
        logger.info("Manuaalinen kokonaispäivitys käynnistetty")
        data = dashboard_service.hae_dashboard_data(pakota_paivitys=True)
        return jsonify({
            "ok": True,
            "viesti": "Kaikki tiedot päivitetty",
            "latausaika_s": data.get("latausaika_s")
        })
    except Exception as e:
        logger.error(f"Virhe /api/paivita: {e}", exc_info=True)
        return jsonify({"ok": False, "virhe": str(e)}), 500


@app.route("/terveys")
def terveys():
    """Health check."""
    return jsonify({
        "tila": "toimii",
        "versio": "2.0.0",
        "binance": binance_service.yhteys_ok,
        "openai": ai_engine.kaytossa,
        "aika": datetime.now().isoformat()
    })


# ─── Virheenkäsittelijät ──────────────────────────────────────


@app.errorhandler(404)
def ei_loydy(e):
    return jsonify({"virhe": "Sivua ei löydy"}), 404


@app.errorhandler(500)
def palvelinvirhe(e):
    logger.error(f"500-virhe: {e}", exc_info=True)
    return jsonify({"virhe": "Sisäinen palvelinvirhe"}), 500


# ─── Käynnistys ───────────────────────────────────────────────


if __name__ == "__main__":
    logger.info(f"Palvelin käynnistyy: http://0.0.0.0:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
