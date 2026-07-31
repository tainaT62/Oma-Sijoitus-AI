"""
AI Score -palvelu.
Laskee jokaiselle kohteelle pistemäärän 0–100 institutionaalisen
analyysin perusteella.

Pisteiden komponentit (painot):
- Tekninen analyysi:  30%
- Sentimentti:        20%
- Uutiset:            15%
- Volatiliteetti:     15%
- Momentum:           10%
- Riski:              10%
"""

import time
from utils.logger import logger
from config import config
from services.technical_analysis import technical_analysis_service
from services.sentiment import sentiment_service
from services.news_service import news_service
from services import database as db


# Painot yhteensä = 1.0
PAINOT = {
    "tekninen":       0.30,
    "sentimentti":    0.20,
    "uutiset":        0.15,
    "volatiliteetti": 0.15,
    "momentum":       0.10,
    "riski":          0.10,
}


class AIScoreService:
    """
    Laskee kattavan AI Score -pistemäärän jokaiselle seurattavalle kohteelle.
    """

    def __init__(self):
        self._cache: dict = {}
        self._cache_ajat: dict = {}
        self._cache_ttl: int = config.AI_SCORE_CACHE_TTL

    # ─── Osapisteet ────────────────────────────────────────

    def _tekninen_pisteet(self, tech_data: dict) -> dict:
        """Laskee tekniset pisteet 0–100."""
        if not tech_data.get("ok"):
            return {"pisteet": 50, "selitys": "Ei dataa"}

        pisteet_raw = tech_data.get("pisteet", 0)
        rsi = tech_data.get("rsi")
        bb = tech_data.get("bollinger_bands", {})
        trendi = tech_data.get("ema", {}).get("trendi", "neutraali")

        # Pisteet: -6..6 → 0..100
        base = min(100, max(0, (pisteet_raw + 6) / 12 * 100))

        # RSI-bonus/malus
        if rsi:
            if rsi < 30:   base = min(100, base + 10)   # ylimyyty = ostosignaali
            elif rsi > 70: base = max(0, base - 10)      # yliostettu = varoitus

        # BB-paikan bonus
        bb_sijainti = bb.get("sijainti_prosentti", 50)
        if bb.get("ylimyyty"):   base = min(100, base + 5)
        elif bb.get("ylikuumentunut"): base = max(0, base - 5)

        # Trendivahvistus
        if trendi == "vahva_nousu": base = min(100, base + 8)
        elif trendi == "vahva_lasku": base = max(0, base - 8)

        selitys = f"RSI {rsi:.0f}" if rsi else ""
        if trendi not in ["neutraali", "tuntematon"]:
            selitys += f", trendi: {trendi}"

        return {
            "pisteet": round(base),
            "selitys": selitys or "Neutraali",
            "rsi": rsi,
            "trendi": trendi,
            "macd_suunta": tech_data.get("macd", {}).get("suunta")
        }

    def _sentimentti_pisteet(self, sentimentti_data: dict) -> dict:
        """Laskee sentimenttipisteet 0–100."""
        if not sentimentti_data.get("ok"):
            return {"pisteet": 50, "selitys": "Ei dataa"}

        fg_arvo = sentimentti_data.get("fear_greed", {}).get("arvo")
        kokonaispisteet = sentimentti_data.get("kokonaispisteet", 0)

        # Fear & Greed: invertoitu käyrä (äärimmäinen pelko = ostosignaali)
        if fg_arvo is not None:
            # Äärimmäinen pelko (0-25) → korkeat pisteet (75-100)
            # Äärimmäinen ahneus (75-100) → matalat pisteet (0-25)
            # Neutraali (50) → 50 pistettä
            fg_pisteet = 100 - fg_arvo
            # Mutta liian korkea ahneus ei ole vaarallinen, tasaa hieman
            fg_pisteet = 30 + fg_pisteet * 0.4

        else:
            fg_pisteet = 50

        # Kokonaissentimentti: -1..1 → 0..100
        sent_pisteet = (kokonaispisteet + 1) / 2 * 100

        # Painotettu keskiarvo: FG 60%, muut 40%
        pisteet = fg_pisteet * 0.6 + sent_pisteet * 0.4

        fg_luokka = sentimentti_data.get("fear_greed", {}).get("luokka", "")
        return {
            "pisteet": round(min(100, max(0, pisteet))),
            "fear_greed_arvo": fg_arvo,
            "fear_greed_luokka": fg_luokka,
            "selitys": f"F&G: {fg_arvo} ({fg_luokka})" if fg_arvo else "F&G ei saatavilla"
        }

    def _uutis_pisteet(self, symboli: str, sentimentti_data: dict) -> dict:
        """Laskee uutisanalyysipisteet 0–100."""
        us = sentimentti_data.get("uutissentimentti", {})
        pisteytys = us.get("pisteytys", 0) or 0

        # -1..1 → 0..100
        pisteet = (pisteytys + 1) / 2 * 100

        # Symbolin omat uutiset
        try:
            symbolin_uutiset = news_service.hae_symbolin_uutiset(symboli, 5)
            if symbolin_uutiset:
                pisteet = min(100, pisteet + 5)  # Bonus jos omia uutisia löytyy
        except Exception:
            pass

        return {
            "pisteet": round(min(100, max(0, pisteet))),
            "pisteytys": pisteytys,
            "luokka": us.get("luokka", "neutraali"),
            "selitys": f"Uutissentimentti: {us.get('luokka', 'neutraali')}"
        }

    def _volatiliteetti_pisteet(self, tech_data: dict) -> dict:
        """
        Laskee volatiliteettipisteet 0–100.
        Matala volatiliteetti = parempi (vakaampi kohde).
        Erittäin korkea volatiliteetti = riski, mutta myös mahdollisuus.
        """
        if not tech_data.get("ok"):
            return {"pisteet": 50, "selitys": "Ei dataa"}

        atr = tech_data.get("atr")
        hinta = tech_data.get("nykyinen_hinta", 0)
        bb = tech_data.get("bollinger_bands", {})
        bb_leveys = bb.get("leveys_prosentti", 10)

        if atr and hinta and hinta > 0:
            atr_pct = (atr / hinta) * 100
            # ATR% alle 2% = 80 pistettä (matala volatiliteetti)
            # ATR% 2-5% = 60 pistettä
            # ATR% 5-10% = 40 pistettä
            # ATR% yli 10% = 20 pistettä
            if atr_pct < 2:   vol_pisteet = 80
            elif atr_pct < 5: vol_pisteet = 60
            elif atr_pct < 10: vol_pisteet = 40
            else: vol_pisteet = 20
        else:
            vol_pisteet = 50
            atr_pct = None

        return {
            "pisteet": vol_pisteet,
            "atr_prosentti": round(atr_pct, 2) if atr_pct else None,
            "bb_leveys": bb_leveys,
            "selitys": f"ATR: {atr_pct:.1f}%" if atr_pct else "ATR ei saatavilla"
        }

    def _momentum_pisteet(self, tech_data: dict) -> dict:
        """
        Laskee momentum-pisteet 0–100.
        Vahva nousutrendi EMA:issa = korkeat pisteet.
        """
        if not tech_data.get("ok"):
            return {"pisteet": 50, "selitys": "Ei dataa"}

        ema = tech_data.get("ema", {})
        trendi = ema.get("trendi", "neutraali")
        macd = tech_data.get("macd", {})
        macd_suunta = macd.get("suunta", "neutraali")
        vt = tech_data.get("volyymitrendi", {})
        vol_suunta = vt.get("suunta", "neutraali")

        pisteet = 50  # Neutraali lähtökohta

        # EMA-trendi
        trendi_pisteet = {
            "vahva_nousu": 30, "nousu": 15,
            "neutraali": 0,
            "lasku": -15, "vahva_lasku": -30
        }
        pisteet += trendi_pisteet.get(trendi, 0)

        # MACD
        if macd_suunta == "nouseva": pisteet += 10
        elif macd_suunta == "laskeva": pisteet -= 10

        # Volyymi
        if vol_suunta in ["vahva_nousu", "nousu"]: pisteet += 10
        elif vol_suunta in ["vahva_lasku", "lasku"]: pisteet -= 5

        return {
            "pisteet": round(min(100, max(0, pisteet))),
            "trendi": trendi,
            "macd_suunta": macd_suunta,
            "vol_suunta": vol_suunta,
            "selitys": f"Trendi: {trendi}, MACD: {macd_suunta}"
        }

    def _riski_pisteet(self, tech_data: dict, sentimentti_data: dict) -> dict:
        """
        Laskee riskipisteet 0–100.
        Korkeat pisteet = matala riski (haluttu).
        """
        pisteet = 70  # Hyvä lähtökohta

        if tech_data.get("ok"):
            bb = tech_data.get("bollinger_bands", {})
            if bb.get("ylikuumentunut"): pisteet -= 15  # Ylikuumentunut = riski
            rsi = tech_data.get("rsi")
            if rsi:
                if rsi > 75: pisteet -= 10  # Erittäin yliostettu
                elif rsi < 25: pisteet += 10  # Erittäin ylimyyty = mahdollisuus

        if sentimentti_data.get("ok"):
            fg = sentimentti_data.get("fear_greed", {}).get("arvo")
            if fg:
                if fg > 80: pisteet -= 10  # Äärimmäinen ahneus = riski
                elif fg < 20: pisteet += 5  # Äärimmäinen pelko = matala riski

        return {
            "pisteet": round(min(100, max(0, pisteet))),
            "selitys": "Riskianalyysi"
        }

    # ─── Pääfunktio ────────────────────────────────────────

    def laske_ai_score(self, symboli: str, pakota_paivitys: bool = False) -> dict:
        """
        Laskee täydellisen AI Score -pistemäärän symbolille.
        """
        cache_avain = symboli

        if not pakota_paivitys and cache_avain in self._cache:
            if (time.time() - self._cache_ajat.get(cache_avain, 0)) < self._cache_ttl:
                return self._cache[cache_avain]

        try:
            logger.debug(f"Lasketaan AI Score: {symboli}")

            # Hae data
            tech = technical_analysis_service.analysoi(symboli, "4h")
            sentimentti = sentiment_service.hae_kokonaissentimentti()

            # Laske osapisteet
            tekninen = self._tekninen_pisteet(tech)
            sent = self._sentimentti_pisteet(sentimentti)
            uutiset = self._uutis_pisteet(symboli.replace("USDT", ""), sentimentti)
            vol = self._volatiliteetti_pisteet(tech)
            momentum = self._momentum_pisteet(tech)
            riski = self._riski_pisteet(tech, sentimentti)

            # Kokonaispistemäärä (painotettu)
            kokonaispistemäärä = round(
                tekninen["pisteet"] * PAINOT["tekninen"] +
                sent["pisteet"] * PAINOT["sentimentti"] +
                uutiset["pisteet"] * PAINOT["uutiset"] +
                vol["pisteet"] * PAINOT["volatiliteetti"] +
                momentum["pisteet"] * PAINOT["momentum"] +
                riski["pisteet"] * PAINOT["riski"]
            )

            # Suositus pistemäärän perusteella
            if kokonaispistemäärä >= 70:
                suositus = "OSTA"
                suositus_vari = "success"
            elif kokonaispistemäärä >= 55:
                suositus = "TARKKAILE"
                suositus_vari = "info"
            elif kokonaispistemäärä >= 40:
                suositus = "PIDÄ"
                suositus_vari = "warning"
            else:
                suositus = "VARO"
                suositus_vari = "danger"

            tulos = {
                "ok": True,
                "symboli": symboli,
                "kokonaispistemäärä": kokonaispistemäärä,
                "suositus": suositus,
                "suositus_vari": suositus_vari,
                "hinta": tech.get("nykyinen_hinta"),
                "komponentit": {
                    "tekninen": tekninen,
                    "sentimentti": sent,
                    "uutiset": uutiset,
                    "volatiliteetti": vol,
                    "momentum": momentum,
                    "riski": riski
                },
                "painot": PAINOT,
                "laskettu": time.time()
            }

            # Tallenna tietokantaan
            db.tallenna_ai_score(symboli, {
                "kokonaispistemäärä": kokonaispistemäärä,
                "tekninen": tekninen,
                "sentimentti": sent,
                "uutiset": uutiset,
                "volatiliteetti": vol,
                "momentum": momentum,
                "riski": riski,
                "suositus": suositus
            }, hinta=tech.get("nykyinen_hinta"))

            self._cache[cache_avain] = tulos
            self._cache_ajat[cache_avain] = time.time()

            logger.debug(f"AI Score {symboli}: {kokonaispistemäärä}/100 ({suositus})")
            return tulos

        except Exception as e:
            logger.error(f"Virhe AI Score laskennassa ({symboli}): {e}", exc_info=True)
            return {"ok": False, "symboli": symboli, "virhe": str(e), "kokonaispistemäärä": 0}

    def laske_kaikki_pisteet(self, symbolit: list) -> list:
        """Laskee AI Scoren kaikille annetuille symboleille."""
        pisteet = []
        for symboli in symbolit:
            score = self.laske_ai_score(symboli)
            if score.get("ok"):
                pisteet.append(score)
        pisteet.sort(key=lambda x: x.get("kokonaispistemäärä", 0), reverse=True)
        return pisteet


# Globaali instanssi
ai_score_service = AIScoreService()
