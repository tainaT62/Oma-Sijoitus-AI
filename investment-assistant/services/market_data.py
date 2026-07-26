"""
Markkinadatapalvelu.
Hakee ja välimuistittaa markkinahinnat Binancesta.
"""

import time
from typing import Optional
from utils.logger import logger
from config import config
from services.binance import binance_service


class MarketDataService:
    """
    Markkinadatapalvelu.
    Hakee nykyiset hinnat ja pitää ne välimuistissa tehokkuuden parantamiseksi.
    """

    def __init__(self):
        self._hinnat_cache: dict = {}
        self._cache_aika: float = 0.0

    def _cache_vanhentunut(self) -> bool:
        """Tarkistaa, onko välimuisti vanhentunut."""
        return (time.time() - self._cache_aika) > config.CACHE_TTL_SECONDS

    def hae_hinnat(self, pakota_paivitys: bool = False) -> dict:
        """
        Hakee kaikki markkinahinnat.
        Käyttää välimuistia, jos data on tuoretta.
        """
        if pakota_paivitys or self._cache_vanhentunut() or not self._hinnat_cache:
            logger.info("Päivitetään markkinahinnat Binancesta...")
            uudet_hinnat = binance_service.hae_kaikki_hinnat()

            if uudet_hinnat:
                self._hinnat_cache = uudet_hinnat
                self._cache_aika = time.time()
                logger.info(f"Markkinahinnat päivitetty ({len(uudet_hinnat)} symbolia)")
            else:
                logger.warning("Hintojen haku epäonnistui, käytetään välimuistia")

        return self._hinnat_cache

    def hae_usdt_hinta(self, kryptovaluutta: str) -> Optional[float]:
        """
        Palauttaa kryptovaluutan hinnan USDT:ssä.
        Käsittelee erikoistapaukset (stablecoinit jne.)
        """
        # Stablecoinit = 1 USDT
        if kryptovaluutta in config.STABLECOINS:
            return 1.0

        # Yritetään suoraa USDT-paria
        hinnat = self.hae_hinnat()
        suora_pari = f"{kryptovaluutta}USDT"
        if suora_pari in hinnat:
            return hinnat[suora_pari]

        # Yritetään BTC-kautta
        btc_pari = f"{kryptovaluutta}BTC"
        if btc_pari in hinnat and "BTCUSDT" in hinnat:
            btc_hinta = hinnat["BTCUSDT"]
            krypto_btc_hinta = hinnat[btc_pari]
            return krypto_btc_hinta * btc_hinta

        # Yritetään ETH-kautta
        eth_pari = f"{kryptovaluutta}ETH"
        if eth_pari in hinnat and "ETHUSDT" in hinnat:
            eth_hinta = hinnat["ETHUSDT"]
            krypto_eth_hinta = hinnat[eth_pari]
            return krypto_eth_hinta * eth_hinta

        logger.debug(f"Hintaa ei löydy valuutalle: {kryptovaluutta}")
        return None

    def hae_24h_muutos(self, kryptovaluutta: str) -> Optional[float]:
        """
        Palauttaa 24h hintamuutoksen prosentteina.
        """
        try:
            tilastot = binance_service.hae_24h_tilastot(f"{kryptovaluutta}USDT")
            if tilastot:
                return tilastot.get("muutos_prosentti")
            return None
        except Exception as e:
            logger.debug(f"24h muutos ei saatavilla: {kryptovaluutta}: {e}")
            return None

    def hae_cache_tiedot(self) -> dict:
        """Palauttaa välimuistin tilatiedot."""
        return {
            "viimeisin_paivitys": self._cache_aika,
            "symboleja": len(self._hinnat_cache),
            "ttl_sekuntia": config.CACHE_TTL_SECONDS,
            "vanhenee_sekunnissa": max(
                0,
                config.CACHE_TTL_SECONDS - (time.time() - self._cache_aika)
            ) if self._cache_aika > 0 else 0
        }


# Globaali instanssi
market_data_service = MarketDataService()
