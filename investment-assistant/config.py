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

    # --- OpenAI API (valinnainen; ilman avainta sääntöpohjainen analyysi) ---
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

    # --- Käänteisproxy ---
    # Luotettujen käänteisproxyjen määrä sovelluksen edessä.
    #   0 = ProxyFix pois päältä (sovellus ajetaan suoraan)
    #   1 = yksi proxy, esim. Nginx samalla koneella
    #
    # TURVALLISUUS: älä aseta arvoa > 0, ellei edessä TODELLA ole proxya,
    # joka YLIKIRJOITTAA X-Forwarded-For-otsakkeen. Muuten kuka tahansa
    # voi väärentää lähde-IP:n ja kiertää kirjautumisrajoituksen.
    TRUSTED_PROXY_COUNT: int = int(os.getenv("TRUSTED_PROXY_COUNT", "0"))

    # --- Sovelluksen asetukset ---
    # Pienin saldo (USDT), joka näytetään salkussa
    MIN_BALANCE_USDT: float = float(os.getenv("MIN_BALANCE_USDT", "0.01"))

    # Välimuistin elinaika sekunteina (kuinka usein data päivitetään)
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "60"))

    # Teknisen analyysin välimuisti. Sama symboli analysoidaan raportin
    # aikana useasta kohtaa; ilman välimuistia jokainen kutsu hakisi
    # kynttilädatan Binancesta uudelleen.
    TECHNICAL_CACHE_TTL_SECONDS: int = int(os.getenv("TECHNICAL_CACHE_TTL_SECONDS", "300"))

    # SQLite odottaa lukon vapautumista näin kauan ennen virhettä.
    # Scheduler ja web-pyynnöt voivat kirjoittaa samanaikaisesti.
    DB_TIMEOUT_SECONDS: float = float(os.getenv("DB_TIMEOUT_SECONDS", "15"))


    # --- Välimuistien elinajat sekunteina ---
    # Kaikki palvelukohtaiset välimuistit ovat säädettävissä ilman
    # koodimuutosta.
    AI_ENGINE_CACHE_TTL: int = int(os.getenv("AI_ENGINE_CACHE_TTL", "1800"))
    AI_SCORE_CACHE_TTL: int = int(os.getenv("AI_SCORE_CACHE_TTL", "600"))
    NEWS_CACHE_TTL: int = int(os.getenv("NEWS_CACHE_TTL", "900"))
    SENTIMENT_CACHE_TTL: int = int(os.getenv("SENTIMENT_CACHE_TTL", "600"))
    WATCHLIST_CACHE_TTL: int = int(os.getenv("WATCHLIST_CACHE_TTL", "300"))
    RECOMMENDATION_CACHE_TTL: int = int(os.getenv("RECOMMENDATION_CACHE_TTL", "900"))
    PORTFOLIO_CACHE_TTL: int = int(os.getenv("PORTFOLIO_CACHE_TTL", "60"))
    DASHBOARD_CACHE_TTL: int = int(os.getenv("DASHBOARD_CACHE_TTL", "60"))

    # --- Kaupankäynti Telegramista ---
    # OLETUS false. Kun false, koko Telegram-kulku toimii normaalisti
    # (napit, vahvistus, kuittaus) mutta toimeksiantoa EI lähetetä
    # Binanceen – viesti kertoo selvästi että kauppa on pois käytöstä.
    #
    # true edellyttää, että Binance-avaimelle on annettu Spot-
    # kaupankäyntioikeus. Lue README ennen kuin muutat tätä.
    ENABLE_TRADING: bool = os.getenv("ENABLE_TRADING", "false").lower() == "true"

    # Yhden Telegram-napin kautta tehtävän kaupan enimmäiskoko
    # perusvaluutassa. Toinen suojakerros virhepainallusten varalta.
    MAX_ORDER_VALUE: float = float(os.getenv("MAX_ORDER_VALUE", "250"))

    # --- Telegram-botin kuuntelu ---
    # Long polling: ei vaadi julkista HTTPS-osoitetta eikä webhookia.
    TELEGRAM_POLLING: bool = os.getenv("TELEGRAM_POLLING", "true").lower() == "true"
    TELEGRAM_POLL_TIMEOUT: int = int(os.getenv("TELEGRAM_POLL_TIMEOUT", "30"))
    # Vahvistamaton toimenpide vanhenee – vanha nappi ei saa laukaista
    # kauppaa myöhemmin eri hinnalla.
    ACTION_EXPIRY_MINUTES: int = int(os.getenv("ACTION_EXPIRY_MINUTES", "30"))

    # --- Taustascheduler ---
    # Voidaan kytkeä pois, jos taustatehtävät ajetaan erillisessä
    # prosessissa. Vaikka tämä olisi true, scheduler käynnistyy silti
    # vain YHDESSÄ prosessissa kerrallaan (tiedostolukko, ks. scheduler.py).
    ENABLE_SCHEDULER: bool = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"

    # Stablecoinit, joiden arvo on aina 1 USDT
    STABLECOINS: list = ["USDT", "BUSD", "USDC", "DAI", "TUSD", "USDP", "FDUSD"]

    # --- Interactive Brokers (osakkeet, ETF:t, rahastot) ---
    # Kun tunnuksia ei ole, käytetään mock-toteutusta: rakenne ja
    # raportointi toimivat, mutta data on esimerkkidataa. Vaihda
    # IBKR_MODE=live vasta kun TWS/Gateway on käynnissä.
    #   mock = esimerkkidata (oletus)
    #   live = oikea IBKR-yhteys (vaatii ib_insync-kirjaston)
    #   off  = ei IBKR-omistuksia lainkaan
    IBKR_MODE: str = os.getenv("IBKR_MODE", "mock").lower()
    IBKR_HOST: str = os.getenv("IBKR_HOST", "127.0.0.1")
    IBKR_PORT: int = int(os.getenv("IBKR_PORT", "7496"))
    IBKR_CLIENT_ID: int = int(os.getenv("IBKR_CLIENT_ID", "1"))
    IBKR_ACCOUNT: str = os.getenv("IBKR_ACCOUNT", "")

    # --- Salkun perusvaluutta ---
    # Binance on USD-pohjainen, IBKR voi olla EUR-pohjainen. Raportti
    # esitetään yhdessä valuutassa. Kurssi haetaan Binancen EURUSDT-parista,
    # joten ulkoista valuutta-API:a ei tarvita.
    BASE_CURRENCY: str = os.getenv("BASE_CURRENCY", "EUR").upper()

    # --- Suositusten parametrit ---
    # Suurin yksittäisen position osuus salkusta. Ylitys johtaa
    # REDUCE-suositukseen.
    MAX_POSITION_PROSENTTI: float = float(os.getenv("MAX_POSITION_PROSENTTI", "25"))
    # Yhden ostoehdotuksen enimmäiskoko perusvaluutassa.
    MAX_OSTOEHDOTUS: float = float(os.getenv("MAX_OSTOEHDOTUS", "250"))
    # Pienin mielekäs ostoehdotus (alle tämän ei ehdoteta mitään).
    MIN_OSTOEHDOTUS: float = float(os.getenv("MIN_OSTOEHDOTUS", "20"))
    # Kuinka suuri osa käteisestä saa mennä yhteen ostoon.
    OSTO_OSUUS_KASSASTA: float = float(os.getenv("OSTO_OSUUS_KASSASTA", "0.15"))

    # --- Kuukausibudjetti ---
    # Suositukset eivät koskaan ylitä kuukauden jäljellä olevaa budjettia.
    # Toteutuneet ostot kirjataan itse (POST /api/budjetti), koska
    # järjestelmä ei tee toimeksiantoja eikä voi päätellä niitä.
    MONTHLY_BUDGET: float = float(os.getenv("MONTHLY_BUDGET", "200"))

    # --- Telegram-ilmoitukset (valinnainen) ---
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
