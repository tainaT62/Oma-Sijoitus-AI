"""
OpenAI-analyysipalevu (TULEVA OMINAISUUS - ei käytössä vielä).
Tämä moduuli on varaus tulevaa AI-analyysiä varten.

Seuraavassa versiossa lisätään:
- Salkun AI-analyysi
- Sijoitussuositukset
- Riskiarviointi tekoälyn avulla
- Uutisten sentimenttianalyysi
"""

from utils.logger import logger
from config import config


class OpenAIService:
    """
    OpenAI GPT -analyysipalevu.
    HUOM: Ei käytössä ensimmäisessä versiossa.
    """

    def __init__(self):
        self.kaytossa = False
        logger.info("OpenAI-palvelu alustettu (ei aktiivinen tässä versiossa)")

    def analysoi_salkku(self, salkku_data: dict) -> str:
        """
        Analysoi salkun tekoälyn avulla.
        TULEVA OMINAISUUS - palauttaa tällä hetkellä placeholder-tekstin.
        """
        logger.info("OpenAI-analyysi pyydetty (ei vielä käytössä)")
        return "AI-analyysi lisätään seuraavassa versiossa."

    def analysoi_uutiset(self, uutiset: list) -> str:
        """
        Analysoi markkinauutisten sentimentin.
        TULEVA OMINAISUUS
        """
        logger.info("Uutisanalyysi pyydetty (ei vielä käytössä)")
        return "Uutisanalyysi lisätään seuraavassa versiossa."

    def laadi_suositukset(self, salkku_data: dict, uutiset: list) -> list:
        """
        Luo sijoitussuosituksia AI:n avulla.
        TULEVA OMINAISUUS
        """
        logger.info("Sijoitussuositukset pyydetty (ei vielä käytössä)")
        return []


# Globaali instanssi
openai_service = OpenAIService()
