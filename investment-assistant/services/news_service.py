"""
Uutispalvelu.
Kerää kryptouutiset RSS-syötteistä ja valinnaisen uutis-API:n kautta.
"""

import time
from datetime import datetime, timezone
from utils.logger import logger
from config import config

# Feedparser RSS-lukemiseen
try:
    import feedparser
    FEEDPARSER_SAATAVILLA = True
except ImportError:
    FEEDPARSER_SAATAVILLA = False
    logger.warning("feedparser ei asennettu – uutiset eivät ole saatavilla")


# ─── RSS-lähteet ──────────────────────────────────────────────

RSS_LAHTEET = [
    {
        "nimi": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "kieli": "en"
    },
    {
        "nimi": "CoinTelegraph",
        "url": "https://cointelegraph.com/rss",
        "kieli": "en"
    },
    {
        "nimi": "Decrypt",
        "url": "https://decrypt.co/feed",
        "kieli": "en"
    },
    {
        "nimi": "Bitcoin Magazine",
        "url": "https://bitcoinmagazine.com/.rss/full/",
        "kieli": "en"
    },
    {
        "nimi": "The Block",
        "url": "https://www.theblock.co/rss.xml",
        "kieli": "en"
    }
]

# Avainsanat, joita käytetään uutisten suodattamiseen
KRIITTISET_AVAINSANAT = [
    "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain",
    "defi", "altcoin", "bull", "bear", "crash", "rally", "sec",
    "regulation", "hack", "binance", "coinbase", "fed", "rate",
    "inflation", "recession", "etf", "halving"
]


class NewsService:
    """
    Uutispalvelu – kerää ja välimuistittaa kryptouutiset.
    """

    def __init__(self):
        self._uutiset_cache: list = []
        self._cache_aika: float = 0.0
        self._cache_ttl: int = config.NEWS_CACHE_TTL

    def _cache_vanhentunut(self) -> bool:
        return (time.time() - self._cache_aika) > self._cache_ttl

    def hae_rss_uutiset(self, lahde: dict, maara: int = 10) -> list:
        """Hakee uutiset yksittäisestä RSS-lähteestä."""
        if not FEEDPARSER_SAATAVILLA:
            return []

        try:
            syote = feedparser.parse(lahde["url"])
            uutiset = []

            for merkinta in syote.entries[:maara]:
                # Julkaisuaika
                julkaisuaika = None
                if hasattr(merkinta, "published_parsed") and merkinta.published_parsed:
                    try:
                        julkaisuaika = datetime(*merkinta.published_parsed[:6], tzinfo=timezone.utc)
                    except Exception:
                        julkaisuaika = datetime.now(timezone.utc)
                else:
                    julkaisuaika = datetime.now(timezone.utc)

                # Kuvaus
                kuvaus = ""
                if hasattr(merkinta, "summary"):
                    kuvaus = merkinta.summary[:300]
                elif hasattr(merkinta, "description"):
                    kuvaus = merkinta.description[:300]

                # Siivoa HTML-tagit kuvauksesta
                import re
                kuvaus = re.sub(r"<[^>]+>", "", kuvaus).strip()

                uutiset.append({
                    "otsikko": merkinta.get("title", ""),
                    "url": merkinta.get("link", ""),
                    "kuvaus": kuvaus,
                    "lahde": lahde["nimi"],
                    "julkaistu": julkaisuaika.isoformat() if julkaisuaika else None,
                    "julkaistu_ts": julkaisuaika.timestamp() if julkaisuaika else 0
                })

            logger.debug(f"Haettu {len(uutiset)} uutista lähteestä {lahde['nimi']}")
            return uutiset

        except Exception as e:
            logger.warning(f"Virhe uutisten haussa lähteestä {lahde['nimi']}: {e}")
            return []

    def suodata_relevantit(self, uutiset: list) -> list:
        """Suodattaa kryptovaluuttaan liittyvät uutiset."""
        relevantit = []
        for uutinen in uutiset:
            teksti = (uutinen.get("otsikko", "") + " " + uutinen.get("kuvaus", "")).lower()
            if any(kw in teksti for kw in KRIITTISET_AVAINSANAT):
                relevantit.append(uutinen)
        return relevantit

    def hae_uutiset(self, pakota_paivitys: bool = False, maara_per_lahde: int = 8) -> list:
        """
        Hakee kaikki uutiset kaikista lähteistä.
        Käyttää välimuistia tehokkuuden parantamiseksi.
        """
        if not pakota_paivitys and not self._cache_vanhentunut() and self._uutiset_cache:
            return self._uutiset_cache

        if not FEEDPARSER_SAATAVILLA:
            logger.warning("feedparser ei saatavilla – uutiset tyhjät")
            return []

        logger.info("Haetaan uutiset RSS-syötteistä...")
        kaikki_uutiset = []

        for lahde in RSS_LAHTEET:
            uutiset = self.hae_rss_uutiset(lahde, maara_per_lahde)
            kaikki_uutiset.extend(uutiset)

        # Järjestä tuoreimmat ensin
        kaikki_uutiset.sort(key=lambda x: x.get("julkaistu_ts", 0), reverse=True)

        # Poista duplikaatit otsikon perusteella
        nahdyt = set()
        uniikit = []
        for u in kaikki_uutiset:
            otsikko_normaali = u["otsikko"].lower().strip()[:50]
            if otsikko_normaali not in nahdyt:
                nahdyt.add(otsikko_normaali)
                uniikit.append(u)

        self._uutiset_cache = uniikit[:50]  # Max 50 uutista
        self._cache_aika = time.time()

        logger.info(f"Uutiset haettu: {len(self._uutiset_cache)} kpl")
        return self._uutiset_cache

    def hae_symbolin_uutiset(self, symboli: str, maara: int = 5) -> list:
        """Hakee tiettyyn kryptovaluuttaan liittyvät uutiset."""
        kaikki = self.hae_uutiset()

        # Poista USDT-pääte
        puhdas_symboli = symboli.replace("USDT", "").replace("BTC", "").lower()

        liittyvat = []
        for u in kaikki:
            teksti = (u.get("otsikko", "") + " " + u.get("kuvaus", "")).lower()
            if puhdas_symboli in teksti or symboli.lower() in teksti:
                liittyvat.append(u)
            if len(liittyvat) >= maara:
                break

        return liittyvat

    def hae_otsikot_analyysiin(self, maara: int = 20) -> list:
        """Palauttaa uutisotsikoiden listan AI-analyysiä varten."""
        uutiset = self.hae_uutiset()
        return [u["otsikko"] for u in uutiset[:maara]]

    def hae_cache_tiedot(self) -> dict:
        """Palauttaa välimuistin tilatiedot."""
        return {
            "uutisia": len(self._uutiset_cache),
            "viimeisin_paivitys": self._cache_aika,
            "ttl_minuuttia": self._cache_ttl // 60,
            "feedparser_saatavilla": FEEDPARSER_SAATAVILLA,
            "lahteet": [l["nimi"] for l in RSS_LAHTEET]
        }


# Globaali instanssi
news_service = NewsService()
