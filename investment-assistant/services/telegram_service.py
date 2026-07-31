"""
Telegram-ilmoitukset.

Lähettää yhden ilmoituksen aamulla, kun päivittäinen analyysi on ajettu.
Sisältö tulee sellaisenaan olemassa olevalta suositusmoottorilta ja
AI Score -palvelulta – tässä moduulissa ei ole omaa sijoituslogiikkaa,
vain valinta, muotoilu ja lähetys.

Jos Telegram-tunnuksia ei ole asetettu, moduuli on hiljaa pois käytöstä
eikä vaikuta sovelluksen toimintaan mitenkään.
"""

import html
from datetime import datetime
from typing import Optional

import requests

from config import config
from utils.logger import logger


TELEGRAM_API = "https://api.telegram.org"
AIKAKATKAISU_S = 15


class TelegramService:
    """Ohut kääre Telegram Bot API:n sendMessage-kutsulle."""

    def __init__(self):
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.kaytossa = bool(self.token and self.chat_id)

        if self.kaytossa:
            logger.info("Telegram-ilmoitukset käytössä")
        else:
            logger.info(
                "Telegram-ilmoitukset pois käytöstä "
                "(TELEGRAM_BOT_TOKEN tai TELEGRAM_CHAT_ID puuttuu)"
            )

    def laheta(self, teksti: str) -> dict:
        """
        Lähettää viestin. Ei koskaan nosta poikkeusta – lähetyksen
        epäonnistuminen ei saa kaataa taustatehtävää.
        """
        if not self.kaytossa:
            return {"ok": False, "virhe": "Telegram ei käytössä", "ohitettu": True}

        try:
            vastaus = requests.post(
                f"{TELEGRAM_API}/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": teksti,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=AIKAKATKAISU_S,
            )

            if vastaus.status_code == 200 and vastaus.json().get("ok"):
                logger.info("Telegram-ilmoitus lähetetty")
                return {"ok": True}

            # Telegramin virhekuvaus talteen, mutta EI tokenia lokiin.
            try:
                kuvaus = vastaus.json().get("description", vastaus.text[:200])
            except Exception:
                kuvaus = vastaus.text[:200]
            logger.error(f"Telegram-lähetys epäonnistui ({vastaus.status_code}): {kuvaus}")
            return {"ok": False, "virhe": kuvaus, "status": vastaus.status_code}

        except requests.exceptions.Timeout:
            logger.error("Telegram-lähetys aikakatkaistiin")
            return {"ok": False, "virhe": "Aikakatkaisu"}
        except Exception as e:
            logger.error(f"Telegram-lähetys epäonnistui: {e}")
            return {"ok": False, "virhe": str(e)}

    def testaa_yhteys(self) -> dict:
        """Tarkistaa tunnukset getMe-kutsulla. Ei lähetä viestiä."""
        if not self.kaytossa:
            return {"ok": False, "virhe": "Telegram ei käytössä"}
        try:
            v = requests.get(f"{TELEGRAM_API}/bot{self.token}/getMe", timeout=AIKAKATKAISU_S)
            d = v.json()
            if d.get("ok"):
                return {"ok": True, "botti": d.get("result", {}).get("username")}
            return {"ok": False, "virhe": d.get("description", "tuntematon virhe")}
        except Exception as e:
            return {"ok": False, "virhe": str(e)}


# ─── Muotoilu ─────────────────────────────────────────────────


def _raha(arvo: Optional[float]) -> str:
    if arvo is None:
        return "–"
    if arvo >= 100:
        return f"${arvo:,.2f}"
    return f"${arvo:,.4f}".rstrip("0").rstrip(".")


def _pros(arvo: Optional[float]) -> str:
    if arvo is None:
        return "–"
    return f"{arvo:+.1f} %"


def _muutos_prosentteina(hinta: Optional[float], taso: Optional[float]) -> Optional[float]:
    """Tason etäisyys nykyhinnasta prosentteina."""
    if not hinta or taso is None or hinta == 0:
        return None
    return (taso - hinta) / hinta * 100


def muotoile_suositusilmoitus(suositus: dict, ai_pisteet: Optional[int] = None) -> str:
    """
    Rakentaa päivän ilmoituksen.

    Kaikki luvut tulevat suositusmoottorilta. Odotettu tuotto lasketaan
    moottorin omasta take profit -ehdotuksesta suhteessa nykyhintaan –
    uutta sijoituslogiikkaa ei lisätä.
    """
    e = html.escape

    symboli = suositus.get("symboli", "?")
    nimi = symboli.replace("USDT", "")
    toiminto = suositus.get("toiminto", "PIDÄ")

    # Moottorin OSTA -> BUY, kaikki muu -> WAIT.
    if toiminto == "OSTA":
        otsake, merkki = "OSTA (BUY)", "🟢"
    else:
        otsake, merkki = "ODOTA (WAIT)", "🟡"

    hinta = suositus.get("nykyinen_hinta")
    sl = suositus.get("stop_loss_ehdotus")
    tp = suositus.get("take_profit_ehdotus")

    odotettu = _muutos_prosentteina(hinta, tp)
    sl_muutos = _muutos_prosentteina(hinta, sl)

    rivit = [
        f"📊 <b>Päivän sijoitusidea</b>",
        f"<i>{datetime.now().strftime('%d.%m.%Y')}</i>",
        "",
        f"{merkki} <b>{e(nimi)}</b> — <b>{e(otsake)}</b>",
        "",
        f"Luottamus:       <b>{suositus.get('luottamus_prosentti', '–')} %</b>",
        f"AI Score:        <b>{ai_pisteet if ai_pisteet is not None else '–'}</b>/100",
        f"Riski:           {e(str(suositus.get('riski', '–')))}",
        f"Odotettu tuotto: <b>{_pros(odotettu)}</b>",
        "",
        f"Hinta:           {_raha(hinta)}",
        f"Stop Loss:       {_raha(sl)}"
        + (f"  ({_pros(sl_muutos)})" if sl_muutos is not None else ""),
        f"Take Profit:     {_raha(tp)}"
        + (f"  ({_pros(odotettu)})" if odotettu is not None else ""),
    ]

    # ODOTA-suosituksille moottori ei tuota SL/TP-tasoja. Ei keksitä niitä.
    if sl is None and tp is None:
        rivit.append("")
        rivit.append(
            "<i>Stop Loss ja Take Profit lasketaan vain OSTA-signaalille.</i>"
        )

    perustelut = suositus.get("perustelut") or []
    if perustelut:
        rivit.append("")
        rivit.append("<b>Perustelut</b>")
        for p in perustelut[:3]:
            rivit.append(f"• {e(str(p))}")

    rivit.append("")
    rivit.append("<i>Automaattinen analyysi, ei sijoitusneuvontaa.</i>")

    return "\n".join(rivit)


def muotoile_virheilmoitus(virhe: str) -> str:
    """Ilmoitus, kun päivittäinen analyysi epäonnistuu."""
    return (
        "⚠️ <b>Päivittäinen analyysi epäonnistui</b>\n"
        f"<i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>\n\n"
        f"<code>{html.escape(str(virhe)[:400])}</code>\n\n"
        "Tänään ei lähetetä sijoitusideaa. Tarkista lokit."
    )


# ─── Päivän ilmoituksen kokoaminen ────────────────────────────


def valitse_suositus(suositukset: list) -> Optional[dict]:
    """
    Valitsee ilmoitettavan suosituksen:
      1. korkeimman luottamuksen OSTA
      2. jos OSTA-suosituksia ei ole, korkeimman luottamuksen muu
    """
    if not suositukset:
        return None

    ostot = [s for s in suositukset if s.get("toiminto") == "OSTA"]
    joukko = ostot or suositukset
    return max(joukko, key=lambda s: s.get("luottamus_prosentti", 0))


def laheta_paivan_ilmoitus() -> dict:
    """
    Kokoaa ja lähettää päivän ilmoituksen olemassa olevien palveluiden
    tuottamasta datasta. Kutsutaan schedulerista raportin generoinnin
    jälkeen.
    """
    if not telegram_service.kaytossa:
        return {"ok": False, "ohitettu": True, "virhe": "Telegram ei käytössä"}

    # Tuodaan tässä, jotta moduulien väliset riippuvuudet pysyvät kevyinä.
    from services.recommendation_engine import recommendation_engine
    from services.ai_score import ai_score_service

    # Olemassa oleva moottori; välimuisti estää turhat Binance-kutsut.
    suositukset = recommendation_engine.hae_suositukset()
    suositus = valitse_suositus(suositukset)

    if not suositus:
        logger.warning("Telegram: ei suosituksia – ilmoitusta ei lähetetä")
        return telegram_service.laheta(
            muotoile_virheilmoitus("Suosituksia ei saatu muodostettua.")
        )

    # AI Score samalle symbolille (välimuistista, jos tuore).
    ai_pisteet = None
    try:
        score = ai_score_service.laske_ai_score(suositus["symboli"])
        if score.get("ok"):
            ai_pisteet = score.get("kokonaispistemäärä")
    except Exception as e:
        logger.warning(f"Telegram: AI Scorea ei saatu ({e})")

    viesti = muotoile_suositusilmoitus(suositus, ai_pisteet)
    return telegram_service.laheta(viesti)


# Globaali instanssi
telegram_service = TelegramService()
