"""
Kaupankäyntipalvelu – PYSYVÄSTI ESTETTY.

Tämä ei ole keskeneräinen ominaisuus vaan tietoinen suunnitteluratkaisu.
Järjestelmä on analyysityökalu: se tuottaa suosituksia, jotka käyttäjä
toteuttaa itse. Automaattista kaupankäyntiä ei ole eikä sitä lisätä.

Moduuli säilytetään dokumentoituna kieltopintana: jos joku kutsuu
osta()- tai myy()-metodia, se kirjautuu lokiin ja palauttaa virheen.
Brokerirajapinnoissa (ibkr_service, binance) ei ole toimeksiantometodeja
lainkaan, joten kaupankäynti on rakenteellisesti mahdotonta.
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
