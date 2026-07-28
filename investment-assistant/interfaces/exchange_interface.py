"""
Exchange-rajapinta (TULEVA OMINAISUUS).
Abstrakti perusluokka eri kryptopörsseille.

Tulevat toteutukset:
- BinanceExchangeClient(ExchangeInterface)
- KrakenExchangeClient(ExchangeInterface)
- CoinbaseExchangeClient(ExchangeInterface)

SOLID: Open/Closed – uudet pörssit lisätään ilman olemassa olevan koodin muuttamista.
"""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass


@dataclass
class Kynttila:
    """OHLCV-kynttilädata."""
    aikaleima: int
    avaus: float
    korkein: float
    matalin: float
    sulku: float
    volyymi: float


@dataclass
class Tilauskirja:
    """Tilauskirja (order book)."""
    symboli: str
    ostot: list   # [(hinta, maara), ...]
    myynnit: list # [(hinta, maara), ...]
    aikaleima: int


class ExchangeInterface(ABC):
    """
    Abstrakti kryptopörssi-rajapinta.
    Tarjoaa yhtenäisen API:n kaikille pörsseille.
    """

    @abstractmethod
    def hae_hinta(self, symboli: str) -> Optional[float]:
        """Hakee symbolin nykyisen hinnan."""

    @abstractmethod
    def hae_kaikki_hinnat(self) -> dict:
        """Hakee kaikkien symbolien hinnat."""

    @abstractmethod
    def hae_kynttilat(
        self, symboli: str, aikaväli: str, maara: int = 200
    ) -> list:
        """Hakee kynttilädatan (OHLCV)."""

    @abstractmethod
    def hae_tilauskirja(self, symboli: str, syvyys: int = 20) -> Tilauskirja:
        """Hakee tilauskirjan."""

    @abstractmethod
    def hae_24h_tilastot(self, symboli: str) -> dict:
        """Hakee 24h hintamuutoksen, volyymin jne."""

    @abstractmethod
    def hae_tili_saldot(self) -> list:
        """Hakee tilin saldot (vaatii API-avaimet)."""

    @abstractmethod
    def laheta_toimeksianto(
        self,
        symboli: str,
        puoli: str,  # "buy" tai "sell"
        maara: float,
        hinta: Optional[float] = None
    ) -> dict:
        """
        Lähettää toimeksiannon.
        HUOM: Vaatii kirjoitusoikeudet – käytä varoen!
        """


class BinanceExchangeAdapter(ExchangeInterface):
    """
    Binance-adaptori ExchangeInterface:lle.
    Käyttää olemassa olevaa BinanceService:ä.

    TODO: Täydennä täysi toteutus kun kaupankäynti otetaan käyttöön.
    """

    def __init__(self, binance_service):
        self._binance = binance_service

    def hae_hinta(self, symboli: str) -> Optional[float]:
        return self._binance.hae_symbolin_hinta(symboli)

    def hae_kaikki_hinnat(self) -> dict:
        return self._binance.hae_kaikki_hinnat()

    def hae_kynttilat(self, symboli: str, aikaväli: str, maara: int = 200) -> list:
        try:
            if not self._binance.client:
                return []
            return self._binance.client.get_klines(
                symbol=symboli, interval=aikaväli, limit=maara
            )
        except Exception:
            return []

    def hae_tilauskirja(self, symboli: str, syvyys: int = 20) -> Tilauskirja:
        # TODO: Toteuta
        return Tilauskirja(symboli=symboli, ostot=[], myynnit=[], aikaleima=0)

    def hae_24h_tilastot(self, symboli: str) -> dict:
        tulos = self._binance.hae_24h_tilastot(symboli)
        return tulos or {}

    def hae_tili_saldot(self) -> list:
        tili = self._binance.hae_tili_info()
        return tili.get("balances", []) if tili else []

    def laheta_toimeksianto(self, symboli, puoli, maara, hinta=None) -> dict:
        # TURVALLISUUS: Kaupankäynti estetty v1/v2
        return {"ok": False, "virhe": "Kaupankäynti ei käytössä tässä versiossa"}
