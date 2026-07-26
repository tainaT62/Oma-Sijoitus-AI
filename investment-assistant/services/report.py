"""
Raportointipalvelu (TULEVA OMINAISUUS - ei käytössä vielä).
Tämä moduuli on varaus tulevaa raportointia varten.

Seuraavassa versiossa lisätään:
- PDF-raporttien luonti
- Sähköpostiraportointi
- Telegram-ilmoitukset
- Historiallinen suorituskykyanalyysi
- Veroraportointi
"""

from utils.logger import logger


class ReportService:
    """
    Raportointipalvelu.
    HUOM: Raportointi ei käytössä ensimmäisessä versiossa.
    """

    def __init__(self):
        logger.info("Raportointipalvelu alustettu (ei aktiivinen tässä versiossa)")

    def luo_paivittainen_raportti(self, salkku_data: dict) -> str:
        """
        Luo päivittäisen yhteenvetoraportin.
        TULEVA OMINAISUUS
        """
        logger.info("Päivittäinen raportti pyydetty (ei vielä käytössä)")
        return "Raportointi lisätään seuraavassa versiossa"

    def laheta_telegram_ilmoitus(self, viesti: str) -> bool:
        """
        Lähettää ilmoituksen Telegram-botilla.
        TULEVA OMINAISUUS
        """
        logger.info("Telegram-ilmoitus pyydetty (ei vielä käytössä)")
        return False

    def vie_csv(self, salkku_data: dict, tiedostopolku: str) -> bool:
        """
        Vie salkun tiedot CSV-tiedostoon.
        TULEVA OMINAISUUS
        """
        logger.info("CSV-vienti pyydetty (ei vielä käytössä)")
        return False


# Globaali instanssi
report_service = ReportService()
