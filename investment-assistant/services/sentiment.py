"""
Sentimenttianalyysipalvelu.
Analysoi markkinasentimentin useista lähteistä:
- Fear & Greed Index (alternative.me – ei vaadi API-avainta)
- Uutisten sentimentti (VADER)
- Reddit-sentimentti (TODO: vaatii Reddit API -avaimen)
"""

import time
import requests
from typing import Optional
from utils.logger import logger
from services.news_service import news_service

# VADER-sentimenttianalyysi
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_SAATAVILLA = True
    _analyzer = SentimentIntensityAnalyzer()
except ImportError:
    VADER_SAATAVILLA = False
    _analyzer = None
    logger.warning("vaderSentiment ei asennettu – uutissentimentti ei saatavilla")


# ─── Fear & Greed Index ───────────────────────────────────────

FEAR_GREED_API_URL = "https://api.alternative.me/fng/"

FEAR_GREED_KUVAUKSET = {
    "Extreme Fear": "Äärimmäinen pelko",
    "Fear": "Pelko",
    "Neutral": "Neutraali",
    "Greed": "Ahneus",
    "Extreme Greed": "Äärimmäinen ahneus"
}


def hae_fear_greed_index() -> dict:
    """
    Hakee Fear & Greed Index -arvon alternative.me API:sta.
    Ilmainen API, ei vaadi avainta.
    Palauttaa arvon 0 (äärimmäinen pelko) – 100 (äärimmäinen ahneus).
    """
    try:
        vastaus = requests.get(FEAR_GREED_API_URL, timeout=10, params={"limit": 2})
        vastaus.raise_for_status()
        data = vastaus.json()

        merkinta = data["data"][0]
        arvo = int(merkinta["value"])
        luokka_en = merkinta["value_classification"]
        luokka_fi = FEAR_GREED_KUVAUKSET.get(luokka_en, luokka_en)

        # Eilinen arvo vertailua varten
        eilinen = None
        eilinen_luokka = None
        if len(data["data"]) > 1:
            eilinen = int(data["data"][1]["value"])
            eilinen_luokka = FEAR_GREED_KUVAUKSET.get(
                data["data"][1]["value_classification"],
                data["data"][1]["value_classification"]
            )

        # Väri UI:ta varten
        if arvo <= 25:
            vari = "danger"
        elif arvo <= 45:
            vari = "warning"
        elif arvo <= 55:
            vari = "secondary"
        elif arvo <= 75:
            vari = "success"
        else:
            vari = "success"

        muutos = (arvo - eilinen) if eilinen is not None else None

        logger.debug(f"Fear & Greed Index: {arvo} ({luokka_fi})")

        return {
            "ok": True,
            "arvo": arvo,
            "luokka": luokka_fi,
            "luokka_en": luokka_en,
            "eilinen_arvo": eilinen,
            "eilinen_luokka": eilinen_luokka,
            "muutos": muutos,
            "vari": vari,
            "aikaleima": merkinta.get("timestamp")
        }

    except requests.exceptions.Timeout:
        logger.warning("Fear & Greed API aikakatkaisu")
        return {"ok": False, "virhe": "API-aikakatkaisu", "arvo": None}

    except requests.exceptions.ConnectionError:
        logger.warning("Fear & Greed API ei tavoitettavissa")
        return {"ok": False, "virhe": "Yhteysvirhe", "arvo": None}

    except Exception as e:
        logger.error(f"Virhe Fear & Greed -haussa: {e}", exc_info=True)
        return {"ok": False, "virhe": str(e), "arvo": None}


# ─── Uutissentimentti ─────────────────────────────────────────


def analysoi_uutissentimentti(otsikot: list) -> dict:
    """
    Analysoi uutisotsikoiden sentimentin VADER-mallilla.
    Palauttaa: pisteet -1..1, luokka, positiiviset/negatiiviset/neutraalit.
    """
    if not VADER_SAATAVILLA or not otsikot:
        return {
            "ok": False,
            "virhe": "VADER ei saatavilla tai ei otsikoita",
            "pisteytys": None,
            "luokka": "tuntematon"
        }

    try:
        pisteet_lista = []
        positiiviset = 0
        negatiiviset = 0
        neutraalit = 0

        for otsikko in otsikot:
            pisteet = _analyzer.polarity_scores(otsikko)
            compound = pisteet["compound"]
            pisteet_lista.append(compound)

            if compound >= 0.05:
                positiiviset += 1
            elif compound <= -0.05:
                negatiiviset += 1
            else:
                neutraalit += 1

        ka_pisteytys = sum(pisteet_lista) / len(pisteet_lista) if pisteet_lista else 0

        if ka_pisteytys >= 0.1:
            luokka = "positiivinen"
        elif ka_pisteytys <= -0.1:
            luokka = "negatiivinen"
        else:
            luokka = "neutraali"

        return {
            "ok": True,
            "pisteytys": round(ka_pisteytys, 3),
            "luokka": luokka,
            "positiiviset": positiiviset,
            "negatiiviset": negatiiviset,
            "neutraalit": neutraalit,
            "analysoituja_otsikoita": len(otsikot)
        }

    except Exception as e:
        logger.error(f"Virhe uutissentimentissä: {e}", exc_info=True)
        return {"ok": False, "virhe": str(e), "pisteytys": None, "luokka": "tuntematon"}


# ─── Reddit-sentimentti ───────────────────────────────────────


def hae_reddit_sentimentti(symboli: str = "BTC") -> dict:
    """
    Hakee Reddit-sentimentin kryptovaluuttasubreddeistä.

    TODO: Tämä vaatii Reddit API -tunnukset:
    - REDDIT_CLIENT_ID
    - REDDIT_CLIENT_SECRET
    - Luo sovellus: https://www.reddit.com/prefs/apps

    Tällä hetkellä käytetään julkista JSON-rajapintaa ilman autentikointia.
    """
    try:
        # Julkinen Reddit API ilman autentikointia (rajoitettu)
        url = f"https://www.reddit.com/r/CryptoCurrency/search.json"
        parametrit = {
            "q": symboli,
            "sort": "new",
            "limit": 25,
            "t": "day"
        }
        otsikot_reddit = requests.get(
            url,
            params=parametrit,
            headers={"User-Agent": "SijoitusAssistentti/1.0"},
            timeout=10
        )

        if otsikot_reddit.status_code != 200:
            return {
                "ok": False,
                "virhe": f"Reddit API virhe: {otsikot_reddit.status_code}",
                "pisteytys": None
            }

        data = otsikot_reddit.json()
        viestit = data.get("data", {}).get("children", [])

        if not viestit:
            return {"ok": True, "pisteytys": 0.0, "luokka": "neutraali", "viesteja": 0}

        otsikot = [v["data"].get("title", "") for v in viestit if v.get("data")]
        sentimentti = analysoi_uutissentimentti(otsikot)

        # Lisää Reddit-kohtaisia tietoja
        sentimentti["lahde"] = "Reddit r/CryptoCurrency"
        sentimentti["viesteja"] = len(viestit)
        sentimentti["symboli"] = symboli

        return sentimentti

    except requests.exceptions.Timeout:
        logger.warning("Reddit API aikakatkaisu")
        return {"ok": False, "virhe": "Reddit-aikakatkaisu", "pisteytys": None}

    except Exception as e:
        logger.warning(f"Virhe Reddit-sentimentissä: {e}")
        return {"ok": False, "virhe": str(e), "pisteytys": None}


# ─── Pääsentimenttipalvelu ────────────────────────────────────


class SentimentService:
    """
    Kokoaa sentimenttidatan kaikista lähteistä.
    """

    def __init__(self):
        self._cache: dict = {}
        self._cache_aika: float = 0.0
        self._cache_ttl: int = 10 * 60  # 10 minuuttia

    def _cache_vanhentunut(self) -> bool:
        return (time.time() - self._cache_aika) > self._cache_ttl

    def hae_kokonaissentimentti(self, pakota_paivitys: bool = False) -> dict:
        """
        Hakee kokonaissentimentin kaikista lähteistä.
        """
        if not pakota_paivitys and not self._cache_vanhentunut() and self._cache:
            return self._cache

        logger.info("Analysoidaan markkinasentimentti...")

        # Fear & Greed Index
        fear_greed = hae_fear_greed_index()

        # Uutissentimentti
        otsikot = news_service.hae_otsikot_analyysiin(25)
        uutissentimentti = analysoi_uutissentimentti(otsikot)

        # Reddit-sentimentti BTC:lle
        reddit_btc = hae_reddit_sentimentti("Bitcoin")

        # Kokonaispisteytys (painotettu)
        # Fear & Greed: 40%, Uutiset: 40%, Reddit: 20%
        kokonaispisteet = 0.0
        luotettavuus = 0

        if fear_greed.get("ok") and fear_greed.get("arvo") is not None:
            # Muunna 0-100 → -1..1
            fg_normaali = (fear_greed["arvo"] - 50) / 50
            kokonaispisteet += fg_normaali * 0.4
            luotettavuus += 40

        if uutissentimentti.get("ok") and uutissentimentti.get("pisteytys") is not None:
            kokonaispisteet += uutissentimentti["pisteytys"] * 0.4
            luotettavuus += 40

        if reddit_btc.get("ok") and reddit_btc.get("pisteytys") is not None:
            kokonaispisteet += reddit_btc["pisteytys"] * 0.2
            luotettavuus += 20

        # Kokonaisluokka
        if kokonaispisteet >= 0.2:
            kokonaisluokka = "positiivinen"
            kokonaisvari = "success"
        elif kokonaispisteet <= -0.2:
            kokonaisluokka = "negatiivinen"
            kokonaisvari = "danger"
        else:
            kokonaisluokka = "neutraali"
            kokonaisvari = "secondary"

        tulos = {
            "ok": True,
            "kokonaispisteet": round(kokonaispisteet, 3),
            "kokonaisluokka": kokonaisluokka,
            "kokonaisvari": kokonaisvari,
            "luotettavuus_prosentti": luotettavuus,
            "fear_greed": fear_greed,
            "uutissentimentti": uutissentimentti,
            "reddit": reddit_btc,
            "analysoitu": time.time()
        }

        self._cache = tulos
        self._cache_aika = time.time()

        logger.info(f"Sentimentti: {kokonaisluokka} (pisteet: {kokonaispisteet:.3f})")
        return tulos

    def hae_markkinatrendi(self) -> str:
        """Palauttaa yksinkertaisen markkinatrendin tekstinä."""
        sentimentti = self.hae_kokonaissentimentti()
        pisteet = sentimentti.get("kokonaispisteet", 0)
        fg_arvo = sentimentti.get("fear_greed", {}).get("arvo")

        if fg_arvo is not None:
            if fg_arvo < 25:
                return "Äärimmäinen pelko – mahdollinen ostomahdollisuus"
            elif fg_arvo < 45:
                return "Pelko – varovaisuus suositeltavaa"
            elif fg_arvo < 55:
                return "Neutraali markkina"
            elif fg_arvo < 75:
                return "Ahneus – nousutrendi"
            else:
                return "Äärimmäinen ahneus – varovaisuus suositeltavaa"
        return "Ei tietoja saatavilla"


# Globaali instanssi
sentiment_service = SentimentService()
