"""
Broker-rajapinta (TULEVA OMINAISUUS).
Abstrakti perusluokka eri välittäjille (Interactive Brokers, Nordnet, jne.)

SOLID-periaatteet:
- Interface Segregation: vain välittäjälle tarvittavat metodit
- Dependency Inversion: kaikki broker-toteutukset riippuvat tästä abstraktiosta

Tulevat toteutukset:
- InteractiveBrokersClient(BrokerInterface)
- NordnetClient(BrokerInterface)
- AlpacaClient(BrokerInterface)
"""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class ToimintoTyyppi(Enum):
    """Kaupankäyntitoimeksiannon tyyppi."""
    OSTA = "osta"
    MYY = "myy"


class ToimeksiantoTila(Enum):
    """Toimeksiannon tila."""
    ODOTTAA = "odottaa"
    VAHVISTETTU = "vahvistettu"
    TOTEUTUNUT = "toteutunut"
    PERUUTETTU = "peruutettu"
    EPAONNISTUNUT = "epaonnistunut"


@dataclass
class Toimeksianto:
    """Kaupankäyntitoimeksianto."""
    symboli: str
    tyyppi: ToimintoTyyppi
    maara: float
    hinta: Optional[float] = None        # None = markkinahinta
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    kommentti: str = ""


@dataclass
class ToimeksiantoVastaus:
    """Toimeksiannon tulos."""
    ok: bool
    toimeksianto_id: Optional[str] = None
    tila: Optional[ToimeksiantoTila] = None
    toteutunut_hinta: Optional[float] = None
    toteutunut_maara: Optional[float] = None
    virhe: Optional[str] = None


class BrokerInterface(ABC):
    """
    Abstrakti broker-rajapinta.

    KÄYTTÖ (tulevaisuudessa):
        class NordnetClient(BrokerInterface):
            def osta(self, toimeksianto): ...
            def myy(self, toimeksianto): ...
            ...
    """

    @abstractmethod
    def yhdista(self) -> bool:
        """Muodostaa yhteyden brokeriin. Palauttaa True jos onnistui."""

    @abstractmethod
    def katkaise_yhteys(self) -> None:
        """Katkaisee yhteyden."""

    @abstractmethod
    def on_yhdistetty(self) -> bool:
        """Tarkistaa, onko yhteys aktiivinen."""

    @abstractmethod
    def osta(self, toimeksianto: Toimeksianto) -> ToimeksiantoVastaus:
        """Lähettää osto-toimeksiannon."""

    @abstractmethod
    def myy(self, toimeksianto: Toimeksianto) -> ToimeksiantoVastaus:
        """Lähettää myyntitoimeksiannon."""

    @abstractmethod
    def peruuta_toimeksianto(self, toimeksianto_id: str) -> bool:
        """Peruuttaa avoimeen toimeksiannon."""

    @abstractmethod
    def hae_avoimet_toimeksiannot(self) -> list:
        """Palauttaa kaikki avoimet toimeksiannot."""

    @abstractmethod
    def hae_tili_saldo(self) -> dict:
        """Palauttaa tilin saldon."""

    @abstractmethod
    def hae_positiot(self) -> list:
        """Palauttaa avoimet positiot."""

    @abstractmethod
    def hae_transaktiohistoria(self, paivia: int = 30) -> list:
        """Palauttaa transaktiohistorian viimeiseltä N päivältä."""


class EiBrokerClient(BrokerInterface):
    """
    Tyhjä broker-toteutus oletuksena – estää kaupankäynnin.
    Käytetään, kun oikeaa brokeria ei ole konfiguroitu.
    """

    def yhdista(self) -> bool:
        return False

    def katkaise_yhteys(self) -> None:
        pass

    def on_yhdistetty(self) -> bool:
        return False

    def osta(self, toimeksianto: Toimeksianto) -> ToimeksiantoVastaus:
        return ToimeksiantoVastaus(
            ok=False, virhe="Broker-yhteyttä ei ole konfiguroitu"
        )

    def myy(self, toimeksianto: Toimeksianto) -> ToimeksiantoVastaus:
        return ToimeksiantoVastaus(
            ok=False, virhe="Broker-yhteyttä ei ole konfiguroitu"
        )

    def peruuta_toimeksianto(self, toimeksianto_id: str) -> bool:
        return False

    def hae_avoimet_toimeksiannot(self) -> list:
        return []

    def hae_tili_saldo(self) -> dict:
        return {}

    def hae_positiot(self) -> list:
        return []

    def hae_transaktiohistoria(self, paivia: int = 30) -> list:
        return []
