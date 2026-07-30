"""
Sovelluksen konfiguraatio - ladataan ympäristömuuttujista.
API-avaimia ei koskaan kirjoiteta koodiin.
"""

import os
from dotenv import load_dotenv

# Lataa .env-tiedosto jos se on olemassa
load_dotenv()


class Config:
    """Sovelluksen pääkonfiguraatio."""

    # --- Binance API ---
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY", "")

    # Binance testnet (aseta True testausta varten)
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "false").lower() == "true"

    # --- OpenAI API (tuleva ominaisuus) ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # --- Flask ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "muuta-tama-tuotannossa")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    PORT: int = int(os.getenv("PORT", "5000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # --- Sovelluksen asetukset ---
    # Pienin saldo (USDT), joka näytetään salkussa
    MIN_BALANCE_USDT: float = float(os.getenv("MIN_BALANCE_USDT", "0.01"))

    # Välimuistin elinaika sekunteina (kuinka usein data päivitetään)
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "60"))

    # --- Taustascheduler ---
    # Voidaan kytkeä pois, jos taustatehtävät ajetaan erillisessä
    # prosessissa. Vaikka tämä olisi true, scheduler käynnistyy silti
    # vain YHDESSÄ prosessissa kerrallaan (tiedostolukko, ks. scheduler.py).
    ENABLE_SCHEDULER: bool = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"

    # Stablecoinit, joiden arvo on aina 1 USDT
    STABLECOINS: list = ["USDT", "BUSD", "USDC", "DAI", "TUSD", "USDP", "FDUSD"]

    # --- Tulevat ominaisuudet (ei käytössä vielä) ---
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    @classmethod
    def validate(cls) -> dict:
        """
        Tarkistaa, että kaikki pakolliset API-avaimet on asetettu.
        Palauttaa dict: {'valid': bool, 'virheet': list}
        """
        virheet = []

        if not cls.BINANCE_API_KEY:
            virheet.append("BINANCE_API_KEY puuttuu ympäristömuuttujista")

        if not cls.BINANCE_SECRET_KEY:
            virheet.append("BINANCE_SECRET_KEY puuttuu ympäristömuuttujista")

        return {
            "valid": len(virheet) == 0,
            "virheet": virheet
        }


config = Config()
