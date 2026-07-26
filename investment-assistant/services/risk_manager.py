"""
Riskienhallintapalvelu (TULEVA OMINAISUUS - ei käytössä vielä).
Tämä moduuli on varaus tulevaa riskianalyysiä varten.

Seuraavassa versiossa lisätään:
- Salkun volatiliteettianalyysi
- Hajautusanalyysi
- Maksimaalinen drawdown -laskenta
- Value at Risk (VaR) laskenta
- Stoppitasojen suositukset
"""

from utils.logger import logger


class RiskManagerService:
    """
    Riskienhallintapalvelu.
    HUOM: Riskianalyysi ei käytössä ensimmäisessä versiossa.
    """

    def __init__(self):
        logger.info("Riskienhallintapalvelu alustettu (ei aktiivinen tässä versiossa)")

    def arvioi_riskit(self, salkku_data: dict) -> dict:
        """
        Arvioi salkun riskitason.
        TULEVA OMINAISUUS
        """
        logger.info("Riskiarviointi pyydetty (ei vielä käytössä)")
        return {
            "riskitaso": "ei_laskettu",
            "viesti": "Riskianalyysi lisätään seuraavassa versiossa"
        }

    def tarkista_kauppa_riskit(
        self, symboli: str, maara: float, tyyppi: str
    ) -> dict:
        """
        Tarkistaa yksittäisen kaupan riskit ennen toteutusta.
        TULEVA OMINAISUUS
        """
        logger.info(f"Kauppariskitarkistus pyydetty (ei vielä käytössä): {symboli}")
        return {
            "ok": False,
            "viesti": "Riskianalyysi lisätään seuraavassa versiossa"
        }

    def laske_hajautus(self, omistukset: list) -> dict:
        """
        Laskee salkun hajautuksen.
        TULEVA OMINAISUUS
        """
        logger.info("Hajautusanalyysi pyydetty (ei vielä käytössä)")
        return {}


# Globaali instanssi
risk_manager_service = RiskManagerService()
