"""
Ilmoitusrajapinta (TULEVA OMINAISUUS).
Abstrakti perusluokka eri ilmoituskanavilla.

Tulevat toteutukset:
- TelegramNotifier(NotificationInterface)
- EmailNotifier(NotificationInterface)
- SlackNotifier(NotificationInterface)
- PushNotifier(NotificationInterface)
"""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class IlmoitusTaso(Enum):
    """Ilmoituksen tärkeysaste."""
    INFO = "info"
    VAROITUS = "varoitus"
    KRIITTINEN = "kriittinen"
    SUOSITUS = "suositus"


@dataclass
class Ilmoitus:
    """Ilmoitusobjekti."""
    otsikko: str
    viesti: str
    taso: IlmoitusTaso = IlmoitusTaso.INFO
    symboli: Optional[str] = None
    lisatiedot: Optional[dict] = None


class NotificationInterface(ABC):
    """
    Abstrakti ilmoitusrajapinta.
    Kaikki ilmoituskanavat toteuttavat tämän.
    """

    @abstractmethod
    def laheta(self, ilmoitus: Ilmoitus) -> bool:
        """Lähettää ilmoituksen. Palauttaa True jos onnistui."""

    @abstractmethod
    def laheta_raportti(self, raportti_teksti: str) -> bool:
        """Lähettää päivittäisen raportin."""

    @abstractmethod
    def laheta_suositus(
        self,
        symboli: str,
        toiminto: str,
        luottamus: int,
        perustelut: list
    ) -> bool:
        """Lähettää sijoitussuosituksen hyväksymistä varten."""

    @abstractmethod
    def on_toiminnassa(self) -> bool:
        """Tarkistaa, onko ilmoituskanava toiminnassa."""


class TelegramNotifier(NotificationInterface):
    """
    Telegram-ilmoitukset.
    TODO: Toteuta täysin kun TELEGRAM_BOT_TOKEN ja TELEGRAM_CHAT_ID lisätään.
    """

    def __init__(self, bot_token: str, chat_id: str):
        self._token = bot_token
        self._chat_id = chat_id
        self._toiminnassa = bool(bot_token and chat_id)

    def laheta(self, ilmoitus: Ilmoitus) -> bool:
        if not self._toiminnassa:
            return False
        # TODO: Toteuta requests.post Telegram Bot API:iin
        # url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        # data = {"chat_id": self._chat_id, "text": f"{ilmoitus.otsikko}\n{ilmoitus.viesti}", "parse_mode": "Markdown"}
        # requests.post(url, json=data)
        return False

    def laheta_raportti(self, raportti_teksti: str) -> bool:
        if not self._toiminnassa:
            return False
        # TODO: Lähetä markdown-muotoinen raportti
        return False

    def laheta_suositus(self, symboli, toiminto, luottamus, perustelut) -> bool:
        if not self._toiminnassa:
            return False
        # TODO: Muotoile suositus ja lähetä inline-napeilla (KYLLÄ/EI)
        return False

    def on_toiminnassa(self) -> bool:
        return self._toiminnassa


class KonsoleIlmoittaja(NotificationInterface):
    """
    Konsoli-ilmoittaja kehitysympäristöä varten.
    Kirjoittaa ilmoitukset lokiin.
    """

    def laheta(self, ilmoitus: Ilmoitus) -> bool:
        from utils.logger import logger
        logger.info(f"[ILMOITUS] {ilmoitus.taso.value.upper()}: {ilmoitus.otsikko} – {ilmoitus.viesti}")
        return True

    def laheta_raportti(self, raportti_teksti: str) -> bool:
        from utils.logger import logger
        logger.info(f"[RAPORTTI]\n{raportti_teksti[:500]}...")
        return True

    def laheta_suositus(self, symboli, toiminto, luottamus, perustelut) -> bool:
        from utils.logger import logger
        logger.info(f"[SUOSITUS] {symboli}: {toiminto} ({luottamus}%) – {', '.join(perustelut[:3])}")
        return True

    def on_toiminnassa(self) -> bool:
        return True
