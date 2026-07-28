"""
Watchlist-palvelu.
Hallitsee seurattavia kohteita ja hakee niille analyysit.

Tuetut tyypit: crypto (Binance), osakkeet/indeksit/hyödykkeet (TODO: ulkoinen API)
"""

import time
from typing import Optional
from utils.logger import logger
from services import database as db
from services.market_data import market_data_service
from services.technical_analysis import technical_analysis_service

# Oletusseurattavat kohteet
OLETUSKOHTEET = [
    {"symboli": "BTCUSDT",  "nimi": "Bitcoin",  "tyyppi": "crypto"},
    {"symboli": "ETHUSDT",  "nimi": "Ethereum", "tyyppi": "crypto"},
    {"symboli": "SOLUSDT",  "nimi": "Solana",   "tyyppi": "crypto"},
    {"symboli": "BNBUSDT",  "nimi": "BNB",      "tyyppi": "crypto"},
    {"symboli": "XRPUSDT",  "nimi": "XRP",      "tyyppi": "crypto"},
    {"symboli": "ADAUSDT",  "nimi": "Cardano",  "tyyppi": "crypto"},
    {"symboli": "AVAXUSDT", "nimi": "Avalanche","tyyppi": "crypto"},
    {"symboli": "DOTUSDT",  "nimi": "Polkadot", "tyyppi": "crypto"},
]

# Ei-krypto kohteet – tarvitsevat ulkoisen API:n
ULKOISET_KOHTEET = [
    {"symboli": "SPX",    "nimi": "S&P 500",   "tyyppi": "indeksi"},
    {"symboli": "NDX",    "nimi": "NASDAQ 100", "tyyppi": "indeksi"},
    {"symboli": "XAUUSD", "nimi": "Kulta",      "tyyppi": "hyodyke"},
]


class WatchlistService:
    """
    Watchlist-palvelu.
    Hallitsee seurattavia kohteita ja hakee hinnat/analyysit.
    """

    def __init__(self):
        self._cache: dict = {}
        self._cache_aika: float = 0.0
        self._cache_ttl: int = 5 * 60  # 5 minuuttia
        self._alusta_oletuskohteet()

    def _alusta_oletuskohteet(self) -> None:
        """Lisää oletuskohteet tietokantaan jos watchlist on tyhjä."""
        try:
            nykyinen = db.hae_watchlist()
            if not nykyinen:
                logger.info("Alustetaan oletusseurattavat kohteet...")
                for kohde in OLETUSKOHTEET:
                    db.lisaa_watchlistiin(
                        kohde["symboli"], kohde["nimi"], kohde["tyyppi"]
                    )
                logger.info(f"Lisätty {len(OLETUSKOHTEET)} oletuskohdetta")
        except Exception as e:
            logger.error(f"Oletuskohteiden alustus epäonnistui: {e}")

    def hae_watchlist(self) -> list:
        """Palauttaa watchlistin tietokannasta."""
        return db.hae_watchlist()

    def lisaa(self, symboli: str, nimi: str = "", tyyppi: str = "crypto") -> dict:
        """Lisää kohteen watchlistiin."""
        symboli = symboli.upper().strip()
        if not symboli.endswith("USDT") and tyyppi == "crypto":
            symboli = symboli + "USDT"

        ok = db.lisaa_watchlistiin(symboli, nimi or symboli, tyyppi)
        if ok:
            self._cache = {}  # Tyhjennä välimuisti
            logger.info(f"Lisätty watchlistiin: {symboli}")
        return {"ok": ok, "symboli": symboli}

    def poista(self, symboli: str) -> dict:
        """Poistaa kohteen watchlistista."""
        ok = db.poista_watchlistista(symboli.upper())
        if ok:
            self._cache = {}
            logger.info(f"Poistettu watchlistista: {symboli}")
        return {"ok": ok, "symboli": symboli.upper()}

    def hae_hinnat_kaikille(self) -> dict:
        """Hakee nykyiset hinnat kaikille watchlist-kohteille."""
        kohteet = self.hae_watchlist()
        hinnat = market_data_service.hae_hinnat()
        tulos = {}

        for kohde in kohteet:
            symboli = kohde["symboli"]
            tyyppi = kohde.get("tyyppi", "crypto")

            if tyyppi == "crypto":
                hinta = hinnat.get(symboli)
                if hinta is None:
                    # Yritä hakea suoraan
                    puhdas = symboli.replace("USDT", "")
                    hinta = market_data_service.hae_usdt_hinta(puhdas)
                muutos = None
                try:
                    from services.market_data import market_data_service as mds
                    muutos = mds.hae_24h_muutos(symboli.replace("USDT", ""))
                except Exception:
                    pass

                tulos[symboli] = {
                    "hinta": hinta,
                    "muutos_24h": muutos,
                    "tyyppi": tyyppi,
                    "nimi": kohde.get("nimi", symboli)
                }
            else:
                # TODO: Ulkoinen API (Yahoo Finance, Alpha Vantage, jne.)
                tulos[symboli] = {
                    "hinta": None,
                    "muutos_24h": None,
                    "tyyppi": tyyppi,
                    "nimi": kohde.get("nimi", symboli),
                    "huomio": "Ulkoinen API tarvitaan – TODO"
                }

        return tulos

    def hae_watchlist_analyysi(self, pakota_paivitys: bool = False) -> list:
        """
        Hakee kaikki watchlist-kohteet hinnoilla.
        """
        if not pakota_paivitys and self._cache.get("analyysi") and \
                (time.time() - self._cache_aika) < self._cache_ttl:
            return self._cache["analyysi"]

        kohteet = self.hae_watchlist()
        hinnat = self.hae_hinnat_kaikille()
        tulos = []

        for kohde in kohteet:
            symboli = kohde["symboli"]
            hintadata = hinnat.get(symboli, {})
            tulos.append({
                **kohde,
                "hinta": hintadata.get("hinta"),
                "muutos_24h": hintadata.get("muutos_24h"),
                "huomio": hintadata.get("huomio")
            })

        self._cache["analyysi"] = tulos
        self._cache_aika = time.time()
        return tulos


# Globaali instanssi
watchlist_service = WatchlistService()
