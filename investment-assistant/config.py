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
    # EI oletusarvoa: puuttuva SECRET_KEY pysäyttää käynnistyksen
    # (ks. tarkista_kriittiset). Oletusavain tarkoittaisi, että kuka
    # tahansa voi väärentää istuntoevästeen.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    PORT: int = int(os.getenv("PORT", "5000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # --- Autentikaatio ---
    # Salasanan tiiviste (werkzeug). Selkotekstistä salasanaa ei
    # tallenneta eikä lueta missään.
    #   python -c "from werkzeug.security import generate_password_hash as g; \
    #              import getpass; print(g(getpass.getpass()))"
    APP_PASSWORD_HASH: str = os.getenv("APP_PASSWORD_HASH", "")

    # Istunnon elinikä tunteina.
    SESSION_LIFETIME_HOURS: int = int(os.getenv("SESSION_LIFETIME_HOURS", "12"))

    # Evästeen Secure-lippu. Oletus true = eväste kulkee vain HTTPS:n yli.
    # Aseta false VAIN paikalliseen HTTP-testaukseen; muuten kirjautuminen
    # ei toimi ennen kuin TLS on käytössä.
    SESSION_COOKIE_SECURE: bool = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"

    # Kirjautumisyritysten rajoitus (per IP, prosessikohtainen).
    LOGIN_MAX_ATTEMPTS: int = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_LOCKOUT_MINUTES: int = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))

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

    @classmethod
    def tarkista_kriittiset(cls) -> None:
        """
        Tarkistaa turvallisuuden kannalta kriittiset asetukset ja
        KESKEYTTÄÄ käynnistyksen, jos jokin puuttuu tai on oletusarvo.

        Tätä ei saa muuttaa varoitukseksi: puutteellisilla asetuksilla
        ajettu sovellus on avoin kenelle tahansa.
        """
        virheet = []

        # ─── SECRET_KEY ───────────────────────────────────────
        # Tunnetut oletus- ja esimerkkiarvot, joita ei saa käyttää.
        KIELLETYT = {
            "muuta-tama-tuotannossa",
            "vaihda-tama-satunnaiseen-merkkijonoon",
            "changeme", "secret", "dev", "test",
        }
        avain = (cls.SECRET_KEY or "").strip()
        if not avain:
            virheet.append(
                "SECRET_KEY puuttuu. Luo se komennolla:\n"
                "      python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        elif avain.lower() in KIELLETYT:
            virheet.append(
                "SECRET_KEY on oletus-/esimerkkiarvo. Istuntoevästeet olisivat "
                "väärennettävissä. Luo uusi:\n"
                "      python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        elif len(avain) < 32:
            virheet.append(
                f"SECRET_KEY on liian lyhyt ({len(avain)} merkkiä, vaaditaan >= 32)."
            )

        # ─── Salasanan tiiviste ───────────────────────────────
        tiiviste = (cls.APP_PASSWORD_HASH or "").strip()
        if not tiiviste:
            virheet.append(
                "APP_PASSWORD_HASH puuttuu – ilman sitä kirjautuminen on mahdotonta. "
                "Luo tiiviste:\n"
                "      python -c \"from werkzeug.security import generate_password_hash as g; "
                "import getpass; print(g(getpass.getpass()))\""
            )
        elif "$" not in tiiviste:
            virheet.append(
                "APP_PASSWORD_HASH ei näytä werkzeug-tiivisteeltä. Älä tallenna "
                "salasanaa selkotekstinä."
            )

        if virheet:
            viestit = "\n".join(f"  - {v}" for v in virheet)
            raise RuntimeError(
                "\n\nKÄYNNISTYS KESKEYTETTY – turvallisuusasetukset puutteelliset:\n"
                f"{viestit}\n\n"
                "Aseta puuttuvat arvot ympäristömuuttujiin tai .env-tiedostoon.\n"
            )


config = Config()
