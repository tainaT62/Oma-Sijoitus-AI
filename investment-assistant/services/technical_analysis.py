"""
Tekninen analyysi -palvelu.
Laskee tekniset indikaattorit Binance-datasta.

Indikaattorit:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- EMA 20, 50, 200 (Exponential Moving Average)
- Bollinger Bands
- ATR (Average True Range)
- VWAP (Volume Weighted Average Price)
- Volume Trend
"""

import math
from typing import Optional
from binance.client import Client
from utils.logger import logger
from services.binance import binance_service


# ─── Apufunktiot ──────────────────────────────────────────────


def _ema(arvot: list, periodi: int) -> list:
    """Laskee eksponentiaalisen liukuvan keskiarvon (EMA)."""
    if len(arvot) < periodi:
        return []
    kerroin = 2 / (periodi + 1)
    ema_lista = [sum(arvot[:periodi]) / periodi]
    for arvo in arvot[periodi:]:
        ema_lista.append(arvo * kerroin + ema_lista[-1] * (1 - kerroin))
    # Täydennä alussa olevat puuttuvat arvot
    padding = [None] * (periodi - 1)
    return padding + ema_lista


def _sma(arvot: list, periodi: int) -> list:
    """Laskee yksinkertaisen liukuvan keskiarvon (SMA)."""
    tulos = []
    for i in range(len(arvot)):
        if i < periodi - 1:
            tulos.append(None)
        else:
            ikkuna = arvot[i - periodi + 1:i + 1]
            tulos.append(sum(ikkuna) / periodi)
    return tulos


def _keskihajonta(arvot: list, periodi: int) -> list:
    """Laskee liukuvan keskihajonnan."""
    tulos = []
    for i in range(len(arvot)):
        if i < periodi - 1:
            tulos.append(None)
        else:
            ikkuna = arvot[i - periodi + 1:i + 1]
            ka = sum(ikkuna) / periodi
            varianssi = sum((x - ka) ** 2 for x in ikkuna) / periodi
            tulos.append(math.sqrt(varianssi))
    return tulos


# ─── Indikaattorit ────────────────────────────────────────────


def laske_rsi(sulkuhinnat: list, periodi: int = 14) -> Optional[float]:
    """
    Laskee RSI:n (Relative Strength Index).
    Arvo 0-100. Alle 30 = ylimyyty, yli 70 = yliostettu.
    """
    if len(sulkuhinnat) < periodi + 1:
        return None
    muutokset = [sulkuhinnat[i] - sulkuhinnat[i - 1] for i in range(1, len(sulkuhinnat))]
    nousut = [max(m, 0) for m in muutokset]
    laskut = [abs(min(m, 0)) for m in muutokset]

    # Alkuperäinen Wilder's RS
    avg_nousu = sum(nousut[:periodi]) / periodi
    avg_lasku = sum(laskut[:periodi]) / periodi

    for i in range(periodi, len(nousut)):
        avg_nousu = (avg_nousu * (periodi - 1) + nousut[i]) / periodi
        avg_lasku = (avg_lasku * (periodi - 1) + laskut[i]) / periodi

    if avg_lasku == 0:
        return 100.0
    rs = avg_nousu / avg_lasku
    return round(100 - (100 / (1 + rs)), 2)


def laske_macd(
    sulkuhinnat: list,
    nopea: int = 12,
    hidas: int = 26,
    signaali: int = 9
) -> dict:
    """
    Laskee MACD:n.
    Palauttaa: macd-arvo, signaaliviiva, histogrammi, suunta.
    """
    if len(sulkuhinnat) < hidas + signaali:
        return {"arvo": None, "signaali": None, "histogrammi": None, "suunta": None}

    ema_nopea = _ema(sulkuhinnat, nopea)
    ema_hidas = _ema(sulkuhinnat, hidas)

    # MACD-viiva
    macd_viiva = []
    for i in range(len(sulkuhinnat)):
        n = ema_nopea[i]
        h = ema_hidas[i]
        if n is not None and h is not None:
            macd_viiva.append(n - h)
        else:
            macd_viiva.append(None)

    # Signaaliviiva (EMA macd-viivasta)
    macd_arvot = [v for v in macd_viiva if v is not None]
    if len(macd_arvot) < signaali:
        return {"arvo": None, "signaali": None, "histogrammi": None, "suunta": None}

    signaali_viiva = _ema(macd_arvot, signaali)

    macd_arvo = macd_arvot[-1] if macd_arvot else None
    sig_arvo = signaali_viiva[-1] if signaali_viiva else None
    hist = (macd_arvo - sig_arvo) if (macd_arvo is not None and sig_arvo is not None) else None

    suunta = None
    if hist is not None:
        if hist > 0:
            suunta = "nouseva"
        elif hist < 0:
            suunta = "laskeva"
        else:
            suunta = "neutraali"

    return {
        "arvo": round(macd_arvo, 4) if macd_arvo is not None else None,
        "signaali": round(sig_arvo, 4) if sig_arvo is not None else None,
        "histogrammi": round(hist, 4) if hist is not None else None,
        "suunta": suunta
    }


def laske_ema_tasot(sulkuhinnat: list) -> dict:
    """
    Laskee EMA 20, 50 ja 200.
    Palauttaa arvot ja niiden suhteet toisiinsa.
    """
    ema20_lista = _ema(sulkuhinnat, 20)
    ema50_lista = _ema(sulkuhinnat, 50)
    ema200_lista = _ema(sulkuhinnat, 200)

    ema20 = next((v for v in reversed(ema20_lista) if v is not None), None)
    ema50 = next((v for v in reversed(ema50_lista) if v is not None), None)
    ema200 = next((v for v in reversed(ema200_lista) if v is not None), None)
    hinta = sulkuhinnat[-1] if sulkuhinnat else None

    trendi = "tuntematon"
    if ema20 and ema50 and ema200 and hinta:
        if hinta > ema20 > ema50 > ema200:
            trendi = "vahva_nousu"
        elif hinta < ema20 < ema50 < ema200:
            trendi = "vahva_lasku"
        elif ema20 > ema50:
            trendi = "nousu"
        elif ema20 < ema50:
            trendi = "lasku"
        else:
            trendi = "neutraali"

    return {
        "ema20": round(ema20, 4) if ema20 else None,
        "ema50": round(ema50, 4) if ema50 else None,
        "ema200": round(ema200, 4) if ema200 else None,
        "trendi": trendi,
        "hinta_ema20_ylapuolella": (hinta > ema20) if (hinta and ema20) else None,
        "hinta_ema50_ylapuolella": (hinta > ema50) if (hinta and ema50) else None,
        "hinta_ema200_ylapuolella": (hinta > ema200) if (hinta and ema200) else None
    }


def laske_bollinger_bands(
    sulkuhinnat: list, periodi: int = 20, kerrroin: float = 2.0
) -> dict:
    """
    Laskee Bollinger Bands.
    Palauttaa: yläkaista, keskikaista (SMA), alakaista, leveys, sijainti.
    """
    if len(sulkuhinnat) < periodi:
        return {"ylakaista": None, "keskikaista": None, "alakaista": None,
                "leveys": None, "sijainti_prosentti": None}

    sma_lista = _sma(sulkuhinnat, periodi)
    std_lista = _keskihajonta(sulkuhinnat, periodi)

    sma = sma_lista[-1]
    std = std_lista[-1]
    hinta = sulkuhinnat[-1]

    if sma is None or std is None:
        return {"ylakaista": None, "keskikaista": None, "alakaista": None,
                "leveys": None, "sijainti_prosentti": None}

    ylakaista = sma + kerrroin * std
    alakaista = sma - kerrroin * std
    leveys = ((ylakaista - alakaista) / sma * 100) if sma != 0 else 0

    # Missä kohtaa kaistaa hinta on (0% = alakaista, 100% = yläkaista)
    if ylakaista != alakaista:
        sijainti = (hinta - alakaista) / (ylakaista - alakaista) * 100
    else:
        sijainti = 50.0

    return {
        "ylakaista": round(ylakaista, 4),
        "keskikaista": round(sma, 4),
        "alakaista": round(alakaista, 4),
        "leveys_prosentti": round(leveys, 2),
        "sijainti_prosentti": round(sijainti, 1),
        "ylikuumentunut": sijainti > 80,
        "ylimyyty": sijainti < 20
    }


def laske_atr(korkeat: list, matalat: list, sulkuhinnat: list, periodi: int = 14) -> Optional[float]:
    """
    Laskee ATR:n (Average True Range).
    Mittaa volatiliteetin absoluuttisena lukuna.
    """
    if len(sulkuhinnat) < periodi + 1:
        return None

    tr_lista = []
    for i in range(1, len(sulkuhinnat)):
        hl = korkeat[i] - matalat[i]
        hc = abs(korkeat[i] - sulkuhinnat[i - 1])
        lc = abs(matalat[i] - sulkuhinnat[i - 1])
        tr_lista.append(max(hl, hc, lc))

    # Wilder's ATR
    atr = sum(tr_lista[:periodi]) / periodi
    for i in range(periodi, len(tr_lista)):
        atr = (atr * (periodi - 1) + tr_lista[i]) / periodi

    return round(atr, 4)


def laske_vwap(korkeat: list, matalat: list, sulkuhinnat: list, volyymit: list) -> Optional[float]:
    """
    Laskee VWAP:n (Volume Weighted Average Price).
    Käytetään kaikkia saatavilla olevia kynttilöitä.
    """
    if not volyymit or sum(volyymit) == 0:
        return None

    kumulatiivinen_tv = 0.0
    kumulatiivinen_v = 0.0

    for i in range(len(sulkuhinnat)):
        tyypillinen_hinta = (korkeat[i] + matalat[i] + sulkuhinnat[i]) / 3
        kumulatiivinen_tv += tyypillinen_hinta * volyymit[i]
        kumulatiivinen_v += volyymit[i]

    if kumulatiivinen_v == 0:
        return None

    return round(kumulatiivinen_tv / kumulatiivinen_v, 4)


def analysoi_volyymitrendi(volyymit: list, periodi: int = 20) -> dict:
    """
    Analysoi volyymitrendin.
    Palauttaa: suunta, muutos-%, vahvistus.
    """
    if len(volyymit) < periodi:
        return {"suunta": "tuntematon", "muutos_prosentti": None, "vahvistus": None}

    viimeinen_volyyymi = volyymit[-1]
    keskivolyyymi = sum(volyymit[-periodi:]) / periodi
    aiempi_ka = sum(volyymit[-periodi * 2:-periodi]) / periodi if len(volyymit) >= periodi * 2 else keskivolyyymi

    muutos = ((keskivolyyymi - aiempi_ka) / aiempi_ka * 100) if aiempi_ka != 0 else 0

    if muutos > 20:
        suunta = "vahva_nousu"
    elif muutos > 5:
        suunta = "nousu"
    elif muutos < -20:
        suunta = "vahva_lasku"
    elif muutos < -5:
        suunta = "lasku"
    else:
        suunta = "neutraali"

    # Onko viimeisin kynttilä selvästi keskimääräistä suurempi?
    vahvistus = viimeinen_volyyymi > (keskivolyyymi * 1.5)

    return {
        "suunta": suunta,
        "muutos_prosentti": round(muutos, 2),
        "vahvistus": vahvistus,
        "viimeisin_vs_ka": round(viimeinen_volyyymi / keskivolyyymi, 2) if keskivolyyymi != 0 else None
    }


# ─── Pääanalyysi ──────────────────────────────────────────────


class TechnicalAnalysisService:
    """Teknisen analyysin pääluokka."""

    def _hae_klines(self, symboli: str, aikaväli: str = "1h", maara: int = 250) -> Optional[list]:
        """Hakee kynttilädatan Binancesta."""
        try:
            if not binance_service.client or not binance_service.yhteys_ok:
                return None

            klines = binance_service.client.get_klines(
                symbol=symboli,
                interval=aikaväli,
                limit=maara
            )
            return klines
        except Exception as e:
            logger.error(f"Virhe klines-datan haussa ({symboli}): {e}")
            return None

    def analysoi(self, symboli: str, aikaväli: str = "1h") -> dict:
        """
        Tekee täydellisen teknisen analyysin symbolille.
        Symboli esim: 'BTCUSDT', 'ETHUSDT'
        """
        try:
            klines = self._hae_klines(symboli, aikaväli, 250)

            if not klines:
                return {
                    "ok": False,
                    "virhe": f"Ei dataa symbolille {symboli}",
                    "symboli": symboli
                }

            # Purka data
            avaamishinnat = [float(k[1]) for k in klines]
            korkeat = [float(k[2]) for k in klines]
            matalat = [float(k[3]) for k in klines]
            sulkuhinnat = [float(k[4]) for k in klines]
            volyymit = [float(k[5]) for k in klines]
            nykyinen_hinta = sulkuhinnat[-1]

            # Laske indikaattorit
            rsi = laske_rsi(sulkuhinnat)
            macd = laske_macd(sulkuhinnat)
            ema_tasot = laske_ema_tasot(sulkuhinnat)
            bb = laske_bollinger_bands(sulkuhinnat)
            atr = laske_atr(korkeat, matalat, sulkuhinnat)
            vwap = laske_vwap(korkeat, matalat, sulkuhinnat, volyymit)
            volyymitrendi = analysoi_volyymitrendi(volyymit)

            # Kokonaisarvio
            signaalit = []
            pisteet = 0  # positiivinen = osta, negatiivinen = myy

            if rsi is not None:
                if rsi < 30:
                    signaalit.append({"signaali": "RSI ylimyyty", "suunta": "osta", "arvo": rsi})
                    pisteet += 2
                elif rsi > 70:
                    signaalit.append({"signaali": "RSI yliostettu", "suunta": "myy", "arvo": rsi})
                    pisteet -= 2
                elif 40 <= rsi <= 60:
                    signaalit.append({"signaali": "RSI neutraali", "suunta": "neutraali", "arvo": rsi})

            if macd.get("suunta") == "nouseva":
                signaalit.append({"signaali": "MACD nouseva", "suunta": "osta", "arvo": macd.get("histogrammi")})
                pisteet += 1
            elif macd.get("suunta") == "laskeva":
                signaalit.append({"signaali": "MACD laskeva", "suunta": "myy", "arvo": macd.get("histogrammi")})
                pisteet -= 1

            if ema_tasot.get("trendi") in ["vahva_nousu", "nousu"]:
                signaalit.append({"signaali": f"EMA-trendi: {ema_tasot['trendi']}", "suunta": "osta"})
                pisteet += 2 if ema_tasot["trendi"] == "vahva_nousu" else 1
            elif ema_tasot.get("trendi") in ["vahva_lasku", "lasku"]:
                signaalit.append({"signaali": f"EMA-trendi: {ema_tasot['trendi']}", "suunta": "myy"})
                pisteet -= 2 if ema_tasot["trendi"] == "vahva_lasku" else 1

            if bb.get("ylimyyty"):
                signaalit.append({"signaali": "Bollinger: hinta alakaistalla", "suunta": "osta"})
                pisteet += 1
            elif bb.get("ylikuumentunut"):
                signaalit.append({"signaali": "Bollinger: hinta yläkaistalla", "suunta": "myy"})
                pisteet -= 1

            if vwap and nykyinen_hinta > vwap:
                signaalit.append({"signaali": "Hinta VWAP:n yläpuolella", "suunta": "osta"})
                pisteet += 1
            elif vwap and nykyinen_hinta < vwap:
                signaalit.append({"signaali": "Hinta VWAP:n alapuolella", "suunta": "myy"})
                pisteet -= 1

            if volyymitrendi.get("suunta") in ["vahva_nousu", "nousu"]:
                signaalit.append({"signaali": "Volyymi kasvussa", "suunta": "osta"})
                pisteet += 1

            # Tekninen suositus
            if pisteet >= 3:
                tech_suositus = "OSTA"
                voimakkuus = "vahva"
            elif pisteet >= 1:
                tech_suositus = "OSTA"
                voimakkuus = "heikko"
            elif pisteet <= -3:
                tech_suositus = "MYY"
                voimakkuus = "vahva"
            elif pisteet <= -1:
                tech_suositus = "MYY"
                voimakkuus = "heikko"
            else:
                tech_suositus = "PIDÄ"
                voimakkuus = "neutraali"

            logger.info(f"Tekninen analyysi valmis: {symboli} → {tech_suositus} (pisteet: {pisteet})")

            return {
                "ok": True,
                "symboli": symboli,
                "aikaväli": aikaväli,
                "nykyinen_hinta": nykyinen_hinta,
                "rsi": rsi,
                "macd": macd,
                "ema": ema_tasot,
                "bollinger_bands": bb,
                "atr": atr,
                "vwap": vwap,
                "volyymitrendi": volyymitrendi,
                "signaalit": signaalit,
                "pisteet": pisteet,
                "tekninen_suositus": tech_suositus,
                "voimakkuus": voimakkuus
            }

        except Exception as e:
            logger.error(f"Virhe teknisessä analyysissä ({symboli}): {e}", exc_info=True)
            return {"ok": False, "virhe": str(e), "symboli": symboli}


# Globaali instanssi
technical_analysis_service = TechnicalAnalysisService()
