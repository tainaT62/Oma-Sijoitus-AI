"""
Henkilökohtainen AI-sijoitusassistentti
Pääsovellustiedosto - Flask-web-käyttöliittymä Binance-salkulle

Versio 1.0 - Vain lukuominaisuudet (ei kauppoja)
"""

import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from utils.logger import logger
from config import config
from services.binance import binance_service
from services.portfolio import portfolio_service

# Luo Flask-sovellus
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

logger.info("=" * 60)
logger.info("Henkilökohtainen AI-sijoitusassistentti käynnistyy...")
logger.info(f"Portti: {config.PORT}")
logger.info(f"Debug-tila: {config.DEBUG}")
logger.info("=" * 60)

# Tarkista konfiguraatio käynnistyessä
validointi = config.validate()
if not validointi["valid"]:
    for virhe in validointi["virheet"]:
        logger.warning(f"Konfigurointivaroitus: {virhe}")


# ─── Reitit ───────────────────────────────────────────────────


@app.route("/")
def etusivu():
    """
    Etusivu - näyttää salkun kokonaistilanteen.
    """
    try:
        # Hae salkkudata
        salkku = portfolio_service.hae_salkku()

        # Yhteyden tila
        yhteys_tila = {
            "ok": binance_service.yhteys_ok,
            "virhe": binance_service.virheviesti if not binance_service.yhteys_ok else None
        }

        # Konfigurointivaroitukset
        konfigurointi_ok = config.validate()

        return render_template(
            "index.html",
            salkku=salkku,
            yhteys=yhteys_tila,
            konfigurointi=konfigurointi_ok,
            nyt=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            versio="1.0.0"
        )

    except Exception as e:
        logger.error(f"Virhe etusivun latauksessa: {e}", exc_info=True)
        return render_template(
            "index.html",
            salkku={"ok": False, "virhe": str(e), "omistukset": [], "kokonaisarvo_usdt": 0},
            yhteys={"ok": False, "virhe": str(e)},
            konfigurointi={"valid": False, "virheet": [str(e)]},
            nyt=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            versio="1.0.0"
        )


@app.route("/api/salkku")
def api_salkku():
    """
    JSON API -päätetpiste salkun tiedoille.
    Parametri: ?pakota=true päivittää datan välimuistista riippumatta.
    """
    try:
        pakota = request.args.get("pakota", "false").lower() == "true"
        salkku = portfolio_service.hae_salkku(pakota_paivitys=pakota)
        return jsonify(salkku)

    except Exception as e:
        logger.error(f"Virhe API-kutsussa /api/salkku: {e}", exc_info=True)
        return jsonify({
            "ok": False,
            "virhe": f"Palvelinvirhe: {str(e)}"
        }), 500


@app.route("/api/yhteys")
def api_yhteys():
    """
    Testaa Binance-yhteyden toimivuuden.
    """
    try:
        tulos = binance_service.testaa_yhteys()
        return jsonify(tulos)

    except Exception as e:
        logger.error(f"Virhe API-kutsussa /api/yhteys: {e}", exc_info=True)
        return jsonify({
            "ok": False,
            "viesti": f"Palvelinvirhe: {str(e)}"
        }), 500


@app.route("/api/paivita", methods=["POST"])
def api_paivita():
    """
    Pakottaa kaikkien tietojen päivityksen välimuistista.
    """
    try:
        logger.info("Manuaalinen tietojen päivitys käynnistetty")
        salkku = portfolio_service.hae_salkku(pakota_paivitys=True)
        return jsonify({
            "ok": True,
            "viesti": "Tiedot päivitetty onnistuneesti",
            "paivitysaika": salkku.get("paivitysaika")
        })

    except Exception as e:
        logger.error(f"Virhe API-kutsussa /api/paivita: {e}", exc_info=True)
        return jsonify({
            "ok": False,
            "virhe": f"Päivitys epäonnistui: {str(e)}"
        }), 500


@app.route("/terveys")
def terveys():
    """
    Terveydenttila-päätetpiste (health check).
    """
    return jsonify({
        "tila": "toimii",
        "versio": "1.0.0",
        "binance_yhteys": binance_service.yhteys_ok,
        "aika": datetime.now().isoformat()
    })


# ─── Virheenkäsittelijät ──────────────────────────────────────


@app.errorhandler(404)
def sivu_ei_loydy(e):
    """404 - Sivua ei löydy."""
    logger.warning(f"404-virhe: {request.url}")
    return render_template("index.html",
        salkku={"ok": False, "virhe": "Sivua ei löydy", "omistukset": []},
        yhteys={"ok": False, "virhe": ""},
        konfigurointi={"valid": True, "virheet": []},
        nyt=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        versio="1.0.0"
    ), 404


@app.errorhandler(500)
def palvelinvirhe(e):
    """500 - Palvelinvirhe."""
    logger.error(f"500-virhe: {e}", exc_info=True)
    return jsonify({"virhe": "Sisäinen palvelinvirhe"}), 500


# ─── Käynnistys ───────────────────────────────────────────────


if __name__ == "__main__":
    logger.info(f"Flask-palvelin käynnistyy osoitteessa http://0.0.0.0:{config.PORT}")
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )
