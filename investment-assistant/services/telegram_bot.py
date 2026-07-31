"""
Telegram-botin vuorovaikutus: inline-napit ja vahvistuskulku.

Telegram on päivittäinen käyttöliittymä. Aamuraportin jokaisessa
toimenpidesuosituksessa on nappi, ja koko kulku tapahtuu chatissa.

KULKU
-----
  1. Raportti sisältää napit  ✅ BUY BTC · ✅ REDUCE VWCE  jne.
  2. Painallus EI toteuta mitään. Se avaa vahvistusdialogin, jossa
     kerrotaan tarkalleen mitä ollaan tekemässä.
  3. Vasta VAHVISTA-painallus kutsuu toteutusta.
  4. Käyttäjä saa kuittauksen onnistumisesta tai virheestä.

TURVA
-----
- Vain määritetystä chatista tulevat painallukset hyväksytään.
- Napin data on lyhyt tunniste; varsinaiset tiedot ovat tietokannassa,
  joten napin sisältöä ei voi muokata toiseksi toimeksiannoksi.
- Toimenpide vanhenee (ACTION_EXPIRY_MINUTES) – eilinen nappi ei laukaise
  kauppaa tämän päivän hinnalla.
- Toimenpide kulutetaan atomisesti: tuplapainallus ei tee kahta kauppaa.
- ENABLE_TRADING=false pysäyttää kulun juuri ennen pörssiä.
"""

import html
import json
import threading
import time
import uuid
from datetime import datetime
from typing import Optional

from config import config
from utils.logger import logger
from services import database as db
from services.telegram_service import telegram_service

# Callback-datan etuliitteet (Telegram rajaa 64 tavuun)
PYYDA_VAHVISTUS = "v"
VAHVISTA = "c"
PERUUTA = "x"

TOIMINNON_KUVAUS = {
    "BUY": "Osta", "SELL": "Myy", "REDUCE": "Kevennä",
}


def _e(x) -> str:
    return html.escape(str(x if x is not None else "–"))


# ─── Näppäimistöt ─────────────────────────────────────────────


def rakenna_raportin_napit(suositukset: list) -> Optional[dict]:
    """
    Luo napit raportin toimenpidesuosituksille ja tallentaa jokaisen
    odottavaksi toimenpiteeksi. HOLD ei saa nappia – se ei vaadi mitään.
    """
    rivit = []
    nyt = time.time()
    vanhenee = nyt + config.ACTION_EXPIRY_MINUTES * 60

    for s in suositukset:
        tyyppi = s.get("toiminto")
        if tyyppi not in ("BUY", "SELL", "REDUCE"):
            continue
        # Osakkeet ja ETF:t toteutetaan itse – IBKR:ään ei lähetetä mitään.
        if s.get("luokka") != "krypto":
            continue

        tunnus = uuid.uuid4().hex[:12]
        tallennettu = db.tallenna_toimenpide({
            "id": tunnus, "luotu": nyt, "vanhenee": vanhenee,
            "tyyppi": tyyppi, "symboli": s.get("symboli"),
            "nimi": s.get("nimi"), "luokka": s.get("luokka"),
            "porssi": "Binance",
            "summa": s.get("ehdotettu_summa"),
            "maara": s.get("myytava_maara"),
            "osuus_prosentti": s.get("myyntiosuus_prosentti"),
        })
        if not tallennettu:
            continue

        nimi = (s.get("nimi") or s.get("symboli", "")).replace("USDT", "")
        rivit.append([{
            "text": f"✅ {tyyppi} {nimi}",
            "callback_data": f"{PYYDA_VAHVISTUS}:{tunnus}",
        }])

    return {"inline_keyboard": rivit} if rivit else None


def _vahvistusnapit(tunnus: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ VAHVISTA", "callback_data": f"{VAHVISTA}:{tunnus}"},
        {"text": "❌ PERUUTA", "callback_data": f"{PERUUTA}:{tunnus}"},
    ]]}


# ─── Viestit ──────────────────────────────────────────────────


def _vahvistusteksti(t: dict) -> str:
    tyyppi = t["tyyppi"]
    nimi = (t.get("nimi") or t["symboli"]).replace("USDT", "")
    rivit = [f"<b>{_e(TOIMINNON_KUVAUS.get(tyyppi, tyyppi))} {_e(nimi)}</b>", ""]

    if tyyppi == "BUY":
        rivit.append(f"Summa:  <b>{t['summa']:.2f} {config.BASE_CURRENCY}</b>")
    elif tyyppi == "REDUCE":
        rivit.append(f"Myydään: <b>{t.get('osuus_prosentti')} %</b> positiosta")
        if t.get("maara"):
            rivit.append(f"Määrä:  {t['maara']:.8f}".rstrip("0").rstrip("."))
    else:
        rivit.append("Myydään: <b>koko positio</b>")
        if t.get("maara"):
            rivit.append(f"Määrä:  {t['maara']:.8f}".rstrip("0").rstrip("."))

    rivit.append(f"Pörssi: {_e(t.get('porssi', 'Binance'))}")
    rivit.append("")

    if not config.ENABLE_TRADING:
        rivit.append("⚠️ <i>Kaupankäynti on pois käytöstä. Vahvistus näyttää "
                     "mitä tapahtuisi, mutta toimeksiantoa ei lähetetä.</i>")
    else:
        rivit.append("<i>Vahvistus lähettää markkinatoimeksiannon heti.</i>")

    return "\n".join(rivit)


def _tulosteksti(t: dict, tulos: dict) -> str:
    nimi = (t.get("nimi") or t["symboli"]).replace("USDT", "")
    tyyppi = t["tyyppi"]

    if not tulos.get("ok"):
        return (f"❌ <b>{_e(tyyppi)} {_e(nimi)} epäonnistui</b>\n\n"
                f"<code>{_e(tulos.get('virhe', 'tuntematon virhe'))}</code>")

    if tulos.get("simuloitu"):
        rivit = [f"🔵 <b>{_e(tyyppi)} {_e(nimi)} – simuloitu</b>", ""]
        if tulos.get("quote_summa"):
            rivit.append(f"Olisi ostettu: {tulos['quote_summa']:.2f} USDT")
        if tulos.get("maara"):
            rivit.append(f"Olisi myyty:   {tulos['maara']}")
        rivit += ["", "⚠️ <i>ENABLE_TRADING=false – Binanceen ei lähetetty mitään.</i>",
                  "<i>Voit tehdä kaupan itse Binancessa.</i>"]
        return "\n".join(rivit)

    rivit = [f"✅ <b>{_e(tyyppi)} {_e(nimi)} toteutettu</b>", ""]
    if tulos.get("maara"):
        rivit.append(f"Määrä:      {tulos['maara']}")
    if tulos.get("quote_summa"):
        rivit.append(f"Arvo:       {tulos['quote_summa']:.2f} USDT")
    if tulos.get("keskihinta"):
        rivit.append(f"Keskihinta: {tulos['keskihinta']:.6f}".rstrip("0").rstrip("."))
    if tulos.get("toimeksianto_id"):
        rivit.append(f"Tilaus:     <code>{tulos['toimeksianto_id']}</code>")
    rivit.append("")
    rivit.append("<i>Salkku päivittyy seuraavassa synkronoinnissa.</i>")
    return "\n".join(rivit)


# ─── Callbackien käsittely ────────────────────────────────────


class TelegramBot:
    """Kuuntelee nappipainalluksia ja ohjaa vahvistuskulun."""

    def __init__(self):
        self._saie: Optional[threading.Thread] = None
        self._aja = False

    # -- yksittäinen painallus --

    def kasittele_callback(self, callback: dict) -> None:
        callback_id = callback.get("id", "")
        data = callback.get("data", "")
        viesti = callback.get("message") or {}
        chat_id = str((viesti.get("chat") or {}).get("id", ""))

        # Vain oma chat saa painaa nappeja.
        if chat_id != str(config.TELEGRAM_CHAT_ID):
            logger.warning(f"Callback tuntemattomasta chatista: {chat_id}")
            telegram_service.vastaa_callbackiin(callback_id, "Ei oikeuksia")
            return

        try:
            toiminto, _, tunnus = data.partition(":")
        except Exception:
            telegram_service.vastaa_callbackiin(callback_id, "Virheellinen data")
            return

        t = db.hae_toimenpide(tunnus)
        if not t:
            telegram_service.vastaa_callbackiin(callback_id, "Toimenpidettä ei löydy")
            return

        viesti_id = viesti.get("message_id")

        # Vanhentunut tai jo käsitelty
        if t["tila"] != "odottaa":
            telegram_service.vastaa_callbackiin(callback_id, "Jo käsitelty")
            telegram_service.muokkaa_viestia(
                viesti_id, f"<i>Toimenpide oli jo käsitelty ({_e(t['tila'])}).</i>")
            return
        if time.time() > t["vanhenee"]:
            db.merkitse_toimenpide(tunnus, "vanhentunut")
            telegram_service.vastaa_callbackiin(callback_id, "Vanhentunut")
            telegram_service.muokkaa_viestia(
                viesti_id,
                "<i>Toimenpide vanheni. Hinta on voinut muuttua – "
                "odota seuraavaa raporttia.</i>")
            return

        if toiminto == PYYDA_VAHVISTUS:
            telegram_service.vastaa_callbackiin(callback_id)
            telegram_service.laheta(_vahvistusteksti(t), _vahvistusnapit(tunnus))

        elif toiminto == PERUUTA:
            db.merkitse_toimenpide(tunnus, "peruttu")
            telegram_service.vastaa_callbackiin(callback_id, "Peruttu")
            telegram_service.muokkaa_viestia(viesti_id, "<i>Peruttu. Mitään ei tehty.</i>")

        elif toiminto == VAHVISTA:
            self._toteuta(t, tunnus, callback_id, viesti_id)

        else:
            telegram_service.vastaa_callbackiin(callback_id, "Tuntematon toiminto")

    def _toteuta(self, t: dict, tunnus: str, callback_id: str, viesti_id: int) -> None:
        # Kuluta toimenpide ATOMISESTI ennen toteutusta: jos käyttäjä
        # painaa kahdesti, vain ensimmäinen menee läpi.
        if not db.merkitse_toimenpide(tunnus, "vahvistettu"):
            telegram_service.vastaa_callbackiin(callback_id, "Jo käsitelty")
            return

        telegram_service.vastaa_callbackiin(
            callback_id,
            "Toteutetaan…" if config.ENABLE_TRADING else "Simuloidaan…")
        telegram_service.muokkaa_viestia(viesti_id, "<i>Käsitellään…</i>")

        try:
            from services.trading import order_service
            from services.portfolio_service import yhdistetty_portfolio_service as ups

            # SELL/REDUCE tarvitsee todellisen määrän salkusta.
            if t["tyyppi"] in ("SELL", "REDUCE") and not t.get("maara"):
                salkku = ups.hae_salkku()
                positio = next(
                    (p for p in salkku.get("positiot", [])
                     if p["symboli"] == t["symboli"]), None)
                if not positio:
                    raise ValueError("Positiota ei löydy salkusta")
                maara = float(positio.get("maara") or 0)
                if t["tyyppi"] == "REDUCE" and t.get("osuus_prosentti"):
                    maara = maara * float(t["osuus_prosentti"]) / 100.0
                t = {**t, "maara": maara}

            eur_usd = ups.hae_salkku().get("eur_usd")
            tulos = order_service.toteuta(t, eur_usd=eur_usd)

        except Exception as e:
            logger.error(f"Toimenpiteen toteutus epäonnistui: {e}", exc_info=True)
            tulos = {"ok": False, "virhe": str(e)}

        db.merkitse_toimenpide(tunnus, "vahvistettu", json.dumps(tulos, default=str))
        telegram_service.muokkaa_viestia(viesti_id, _tulosteksti(t, tulos))

    # -- pollaussilmukka --

    def _silmukka(self) -> None:
        offset = db.hae_telegram_offset()
        logger.info("Telegram-kuuntelu käynnistetty (long polling)")

        while self._aja:
            try:
                paivitykset = telegram_service.hae_paivitykset(
                    offset, config.TELEGRAM_POLL_TIMEOUT)
                for u in paivitykset:
                    offset = max(offset, u.get("update_id", 0) + 1)
                    if "callback_query" in u:
                        self.kasittele_callback(u["callback_query"])
                if paivitykset:
                    db.tallenna_telegram_offset(offset)
            except Exception as e:
                logger.error(f"Telegram-kuuntelu: {e}")
                time.sleep(5)

    def kaynnista(self) -> bool:
        if not config.TELEGRAM_POLLING or not telegram_service.kaytossa:
            logger.info("Telegram-kuuntelu pois käytöstä")
            return False
        if self._saie and self._saie.is_alive():
            return True
        self._aja = True
        self._saie = threading.Thread(target=self._silmukka, daemon=True,
                                      name="telegram-bot")
        self._saie.start()
        return True

    def pysayta(self) -> None:
        self._aja = False


# Globaali instanssi
telegram_bot = TelegramBot()
