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

    def laheta(self, teksti: str, nappaimisto: Optional[dict] = None) -> dict:
        """
        Lähettää viestin. Ei koskaan nosta poikkeusta – lähetyksen
        epäonnistuminen ei saa kaataa taustatehtävää.
        """
        if not self.kaytossa:
            return {"ok": False, "virhe": "Telegram ei käytössä", "ohitettu": True}

        try:
            vastaus = requests.post(
                f"{TELEGRAM_API}/bot{self.token}/sendMessage",
                json=self._runko(teksti, nappaimisto),
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

    def _runko(self, teksti: str, nappaimisto: Optional[dict] = None) -> dict:
        runko = {
            "chat_id": self.chat_id,
            "text": teksti,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if nappaimisto:
            runko["reply_markup"] = nappaimisto
        return runko

    def _kutsu(self, metodi: str, runko: dict) -> dict:
        """Yleinen Bot API -kutsu. Ei koskaan nosta poikkeusta."""
        if not self.kaytossa:
            return {"ok": False, "ohitettu": True}
        try:
            v = requests.post(f"{TELEGRAM_API}/bot{self.token}/{metodi}",
                              json=runko, timeout=AIKAKATKAISU_S)
            d = v.json()
            if not d.get("ok"):
                logger.error(f"Telegram {metodi} epäonnistui: {d.get('description')}")
            return d
        except Exception as e:
            logger.error(f"Telegram {metodi} epäonnistui: {e}")
            return {"ok": False, "virhe": str(e)}

    def muokkaa_viestia(self, viesti_id: int, teksti: str,
                        nappaimisto: Optional[dict] = None) -> dict:
        """Korvaa aiemman viestin sisällön – käytetään vahvistusdialogissa."""
        runko = self._runko(teksti, nappaimisto)
        runko["message_id"] = viesti_id
        return self._kutsu("editMessageText", runko)

    def vastaa_callbackiin(self, callback_id: str, teksti: str = "") -> dict:
        """
        Kuittaa napin painallus. Ilman tätä Telegram näyttää napissa
        loputonta latausanimaatiota.
        """
        return self._kutsu("answerCallbackQuery",
                           {"callback_query_id": callback_id, "text": teksti[:200]})

    def hae_paivitykset(self, offset: int, timeout: int) -> list:
        """Long polling: odottaa uusia tapahtumia annetun ajan."""
        if not self.kaytossa:
            return []
        try:
            v = requests.get(
                f"{TELEGRAM_API}/bot{self.token}/getUpdates",
                params={"offset": offset, "timeout": timeout,
                        "allowed_updates": '["callback_query"]'},
                timeout=timeout + 10,
            )
            d = v.json()
            return d.get("result", []) if d.get("ok") else []
        except requests.exceptions.Timeout:
            return []
        except Exception as e:
            logger.debug(f"Telegram-pollaus epäonnistui: {e}")
            return []

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


def laheta_paivaraportti() -> dict:
    """
    Lähettää täyden päiväraportin: salkun tila, suositukset omaisuus-
    luokittain ja watchlist. Yksi viesti vuorokaudessa.
    """
    if not telegram_service.kaytossa:
        return {"ok": False, "ohitettu": True, "virhe": "Telegram ei käytössä"}

    from services.recommendation_engine import salkku_suositusmoottori
    from services.watchlist import watchlist_service
    from services import telegram_formatter as fmt

    # Synkronoi salkku ensin: havaitut ostot päivittävät kuukausibudjetin
    # ennen kuin suositukset lasketaan.
    from services.sync_service import sync_service
    sync = sync_service.synkronoi()

    data = salkku_suositusmoottori.hae_salkkusuositukset(pakota_paivitys=True)
    if not data.get("ok"):
        return telegram_service.laheta(
            fmt.muotoile_virheraportti(data.get("virhe", "Suosituksia ei saatu"))
        )

    data["sync"] = sync if sync.get("ok") else {}
    try:
        data["watchlist"] = watchlist_service.hae_parhaat_mahdollisuudet(5)
    except Exception as e:
        logger.warning(f"Watchlistia ei saatu raporttiin: {e}")
        data["watchlist"] = []

    # Toimenpidenapit: painallus avaa vahvistuksen, ei toteuta mitään.
    from services.telegram_bot import rakenna_raportin_napit
    napit = rakenna_raportin_napit(data.get("suositukset", []))

    return telegram_service.laheta(fmt.muotoile_paivaraportti(data), napit)


def laheta_paivan_ilmoitus() -> dict:
    """
    Vanha yhden sijoitusidean ilmoitus. Säilytetään, koska se toimii
    myös ilman salkkudataa – käytetään varareittinä.
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
