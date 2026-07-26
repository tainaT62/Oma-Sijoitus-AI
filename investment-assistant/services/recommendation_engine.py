"""
Suositusmoottori.
Yhdistää teknisen analyysin, sentimentin, uutiset ja salkun tilanteen
yhdeksi perustelluksi sijoitussuositukseksi.

TÄRKEÄÄ: Tämä on analyysityökalu, ei kaupankäyntibotti.
Kaikki toimeksiannot vaativat käyttäjän eksplisiittisen hyväksynnän.
"""

import time
from typing import Optional
from utils.logger import logger
from services.technical_analysis import technical_analysis_service
from services.sentiment import sentiment_service
from services.news_service import news_service
from services.ai_engine import ai_engine
from services.risk_manager import RiskManagerService


# Riskiluokat
RISKILUOKAT = {
    "matala": {"kynnys": 0.3, "kuvaus": "Matala riski"},
    "keskitaso": {"kynnys": 0.6, "kuvaus": "Keskitasoinen riski"},
    "korkea": {"kynnys": 1.0, "kuvaus": "Korkea riski"}
}

# Symbolit, joita analysoidaan oletuksena (kun salkkudata ei ole saatavilla)
OLETUSSYMBOLIT = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


class RecommendationEngine:
    """
    Suositusmoottori – analysoi ja tuottaa suosituksia.
    """

    def __init__(self):
        self._cache: dict = {}
        self._cache_aika: float = 0.0
        self._cache_ttl: int = 15 * 60  # 15 minuuttia

    def _cache_vanhentunut(self) -> bool:
        return (time.time() - self._cache_aika) > self._cache_ttl

    def _laske_luottamusprosentti(
        self,
        tekniset_pisteet: int,
        sentimentti_pisteet: float,
        uutissentimentti_pisteet: float
    ) -> int:
        """
        Laskee suosituksen luottamusprosentin 0–100.
        Yhdistää tekniset, sentimentti- ja uutisanalyysit.
        """
        # Normalisoi pisteet 0–100 asteikolla
        # Tekniset pisteet: tyypillisesti -6..6 → 0..100
        tech_normalisoitu = min(100, max(0, (tekniset_pisteet + 6) / 12 * 100))

        # Sentimentti: -1..1 → 0..100
        sentiment_normalisoitu = (sentimentti_pisteet + 1) / 2 * 100

        # Uutissentimentti: -1..1 → 0..100
        uutis_normalisoitu = (uutissentimentti_pisteet + 1) / 2 * 100

        # Painotettu keskiarvo
        luottamus = (
            tech_normalisoitu * 0.5 +
            sentiment_normalisoitu * 0.3 +
            uutis_normalisoitu * 0.2
        )

        # Vähimmäisluottamus 35%, enimmäis 92% (ei koskaan 100% varmuutta)
        return int(min(92, max(35, luottamus)))

    def _maarita_riski(
        self,
        atr: Optional[float],
        hinta: float,
        volatiliteetti_pisteet: float
    ) -> str:
        """Määrittää riskiluokan."""
        if atr is None or hinta == 0:
            return "Keskitasoinen riski"

        # ATR suhteessa hintaan (%) = volatiliteetti
        atr_prosentti = (atr / hinta) * 100

        if atr_prosentti < 2:
            return "Matala riski"
        elif atr_prosentti < 5:
            return "Keskitasoinen riski"
        else:
            return "Korkea riski"

    def analysoi_symboli(self, symboli: str) -> dict:
        """
        Tekee täydellisen analyysin yksittäiselle symbolille.
        Palauttaa suosituksen perusteluineen.
        """
        logger.info(f"Analysoidaan symboli: {symboli}")

        try:
            # 1. Tekninen analyysi
            tech = technical_analysis_service.analysoi(symboli, "1h")

            # 2. Sentimentti
            sentimentti = sentiment_service.hae_kokonaissentimentti()

            # 3. Uutiset
            otsikot = news_service.hae_otsikot_analyysiin(15)
            symboli_uutiset = news_service.hae_symbolin_uutiset(symboli, 3)

            # 4. Laske suositus
            if not tech.get("ok"):
                return {
                    "ok": False,
                    "symboli": symboli,
                    "virhe": tech.get("virhe", "Tekninen analyysi epäonnistui")
                }

            tekninen_suositus = tech.get("tekninen_suositus", "PIDÄ")
            tekniset_pisteet = tech.get("pisteet", 0)
            sentimentti_pisteet = sentimentti.get("kokonaispisteet", 0)
            uutissentimentti_pisteet = sentimentti.get(
                "uutissentimentti", {}
            ).get("pisteytys", 0) or 0

            # Suuntapisteet (tekninen painotettu eniten)
            suuntapisteet = (
                tekniset_pisteet * 0.6 +
                sentimentti_pisteet * 2 * 0.25 +
                uutissentimentti_pisteet * 2 * 0.15
            )

            # Päätoiminto
            if suuntapisteet >= 1.5:
                toiminto = "OSTA"
                toiminto_vari = "success"
            elif suuntapisteet <= -1.5:
                toiminto = "MYY"
                toiminto_vari = "danger"
            else:
                toiminto = "PIDÄ"
                toiminto_vari = "warning"

            # Luottamusprosentti
            luottamus = self._laske_luottamusprosentti(
                tekniset_pisteet, sentimentti_pisteet, uutissentimentti_pisteet
            )

            # Riskiluokka
            riski = self._maarita_riski(
                tech.get("atr"),
                tech.get("nykyinen_hinta", 0),
                abs(sentimentti_pisteet)
            )

            # Perustelut
            perustelut = []
            for signaali in tech.get("signaalit", []):
                if signaali.get("suunta") == toiminto.lower() or signaali.get("suunta") == "neutraali":
                    perustelut.append(signaali["signaali"])

            fg_arvo = sentimentti.get("fear_greed", {}).get("arvo")
            fg_luokka = sentimentti.get("fear_greed", {}).get("luokka", "")
            if fg_arvo:
                perustelut.append(f"Fear & Greed Index: {fg_arvo} ({fg_luokka})")

            uutisluokka = sentimentti.get("uutissentimentti", {}).get("luokka", "")
            if uutisluokka:
                perustelut.append(f"Uutissentimentti: {uutisluokka}")

            # Stop loss / Take profit ehdotukset (ATR-pohjainen)
            hinta = tech.get("nykyinen_hinta", 0)
            atr = tech.get("atr")
            stop_loss = None
            take_profit = None

            if hinta and atr:
                if toiminto == "OSTA":
                    stop_loss = round(hinta - 2 * atr, 4)
                    take_profit = round(hinta + 3 * atr, 4)
                elif toiminto == "MYY":
                    stop_loss = round(hinta + 2 * atr, 4)
                    take_profit = round(hinta - 3 * atr, 4)

            tulos = {
                "ok": True,
                "symboli": symboli,
                "toiminto": toiminto,
                "toiminto_vari": toiminto_vari,
                "luottamus_prosentti": luottamus,
                "riski": riski,
                "perustelut": perustelut[:6],  # Max 6 perustelua
                "nykyinen_hinta": hinta,
                "stop_loss_ehdotus": stop_loss,
                "take_profit_ehdotus": take_profit,
                "tekninen_data": {
                    "rsi": tech.get("rsi"),
                    "macd_suunta": tech.get("macd", {}).get("suunta"),
                    "ema_trendi": tech.get("ema", {}).get("trendi"),
                    "atr": atr
                },
                "sentimentti": {
                    "fear_greed": fg_arvo,
                    "fear_greed_luokka": fg_luokka,
                    "kokonaisluokka": sentimentti.get("kokonaisluokka")
                },
                "liittyvat_uutiset": symboli_uutiset[:3],
                "generoitu": time.time(),
                # TURVALLISUUS: Muistutetaan, että käyttäjän hyväksyntä vaaditaan
                "vaatii_hyvaksynnan": True,
                "vastuuvapauslauseke": (
                    "Tämä on automaattinen analyysi, ei sijoitusneuvonta. "
                    "Tee aina oma tutkimuksesi ennen sijoituspäätöksiä."
                )
            }

            logger.info(
                f"Suositus {symboli}: {toiminto} "
                f"(luottamus: {luottamus}%, riski: {riski})"
            )
            return tulos

        except Exception as e:
            logger.error(f"Virhe suosituksen generoinnissa ({symboli}): {e}", exc_info=True)
            return {"ok": False, "symboli": symboli, "virhe": str(e)}

    def hae_suositukset(
        self,
        symbolit: Optional[list] = None,
        pakota_paivitys: bool = False
    ) -> list:
        """
        Analysoi kaikki annetut symbolit ja palauttaa suositukset listana.
        Järjestää luottamusprosentin mukaan.
        """
        if not pakota_paivitys and not self._cache_vanhentunut() and self._cache.get("suositukset"):
            return self._cache["suositukset"]

        kaytetyt_symbolit = symbolit or OLETUSSYMBOLIT
        logger.info(f"Generoidaan suositukset {len(kaytetyt_symbolit)} symbolille...")

        suositukset = []
        for symboli in kaytetyt_symbolit[:6]:  # Max 6 symbolia kerrallaan
            suositus = self.analysoi_symboli(symboli)
            if suositus.get("ok"):
                suositukset.append(suositus)

        # Järjestä luottamusprosentin mukaan
        suositukset.sort(key=lambda x: x.get("luottamus_prosentti", 0), reverse=True)

        self._cache["suositukset"] = suositukset
        self._cache_aika = time.time()

        return suositukset

    def hae_paras_suositus(self, symbolit: Optional[list] = None) -> Optional[dict]:
        """Palauttaa korkeimman luottamuksen omaavan suosituksen."""
        suositukset = self.hae_suositukset(symbolit)
        if suositukset:
            return suositukset[0]
        return None


# Globaali instanssi
recommendation_engine = RecommendationEngine()
