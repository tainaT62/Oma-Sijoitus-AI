"""
Kaupankäyntipalvelu (TULEVA OMINAISUUS - ei käytössä vielä).
TÄRKEÄÄ: Ensimmäinen versio EI tee kauppoja.

Tämä moduuli on varaus tulevaa kaupankäyntiä varten.
Kaupankäynti vaatii:
1. Käyttäjän eksplisiittisen hyväksynnän (Telegram-viesti)
2. Riskianalyysin hyväksynnän
3. Erillisen vahvistuksen ennen toteutusta
"""

from utils.logger import logger


class TradingService:
    """
    Kaupankäyntipalvelu.
    HUOM: Kaupankäynti on ESTETTY ensimmäisessä versiossa.
    """

    def __init__(self):
        # TURVALLISUUS: Kaupankäynti on oletuksena estetty
        self.kaupat_sallittu = False
        logger.info("Kaupankäyntipalvelu alustettu - KAUPAT ESTETTY (v1)")

    def osta(self, symboli: str, maara: float) -> dict:
        """
        ESTETTY: Osto-operaatio.
        Lisätään seuraavassa versiossa Telegram-hyväksynnällä.
        """
        logger.warning(
            f"Ostoyritys estetty - kaupankäynti ei käytössä: {symboli} {maara}"
        )
        return {
            "ok": False,
            "virhe": "Kaupankäynti ei ole käytössä ensimmäisessä versiossa"
        }

    def myy(self, symboli: str, maara: float) -> dict:
        """
        ESTETTY: Myyntioperaatio.
        Lisätään seuraavassa versiossa Telegram-hyväksynnällä.
        """
        logger.warning(
            f"Myyntiyritys estetty - kaupankäynti ei käytössä: {symboli} {maara}"
        )
        return {
            "ok": False,
            "virhe": "Kaupankäynti ei ole käytössä ensimmäisessä versiossa"
        }

    def hae_avoimet_toimeksiannot(self) -> list:
        """
        Hakee avoimet toimeksiannot.
        TULEVA OMINAISUUS
        """
        logger.info("Avoimet toimeksiannot pyydetty (ei vielä käytössä)")
        return []


# Globaali instanssi
trading_service = TradingService()
