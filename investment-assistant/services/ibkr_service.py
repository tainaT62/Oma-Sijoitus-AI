"""
Interactive Brokers -yhteys: osakkeet, ETF:t ja rahastot.

TURVALLISUUS – LUE TÄMÄ ENNEN MUOKKAAMISTA
------------------------------------------
Tässä rajapinnassa EI OLE eikä siihen saa lisätä toimeksiantometodeja.
Ei osta(), ei myy(), ei peruuta(). Järjestelmä on analyysityökalu:
käyttäjä tekee kaikki toimeksiannot itse.

Rajapinta on tarkoituksella vain luku (positiot, käteinen, tilitiedot).
Näin kaupankäynti on rakenteellisesti mahdotonta – ei pelkän lipun
varassa, jonka voi vahingossa kääntää.

TILAT (config.IBKR_MODE)
------------------------
  mock  Esimerkkidata. Koko ketju – salkkuanalyysi, suositukset,
        raportti – toimii ilman IBKR-tunnuksia.
  live  Oikea yhteys TWS:ään tai IB Gatewayhin. Vaatii ib_insync-
        kirjaston, joka EI ole riippuvuuksissa ennen kuin tila otetaan
        käyttöön.
  off   Ei IBKR-omistuksia lainkaan; vain krypto huomioidaan.
"""

from datetime import datetime

from config import config
from utils.logger import logger


# Omaisuusluokat
OSAKE = "osake"
ETF = "etf"
RAHASTO = "rahasto"


class IBKRPositio(dict):
    """
    Yksi IBKR-positio. dict-pohjainen, jotta se sarjallistuu suoraan
    JSONiksi ja sopii olemassa olevien palveluiden kanssa yhteen.
    """

    def __init__(self, symboli, nimi, tyyppi, maara, hankintahinta,
                 markkinahinta, valuutta="EUR", porssi="", sektori=""):
        super().__init__(
            symboli=symboli,
            nimi=nimi,
            tyyppi=tyyppi,
            maara=maara,
            hankintahinta=hankintahinta,      # keskihankintahinta / kpl
            markkinahinta=markkinahinta,
            valuutta=valuutta,
            porssi=porssi,
            sektori=sektori,
            lahde="IBKR",
        )


# ─── Mock-toteutus ────────────────────────────────────────────


class MockIBKRClient:
    """
    Esimerkkidata kehitystä varten.

    Tarkoitus on, että kaikki IBKR:stä riippuva koodi voidaan kirjoittaa
    ja testata valmiiksi ennen tunnusten saamista. Data on realistisen
    muotoista muttei todellista.
    """

    def __init__(self):
        self.yhdistetty = True

    def hae_positiot(self) -> list:
        return [
            IBKRPositio("AAPL", "Apple Inc.", OSAKE, 12, 168.40, 214.20,
                        "USD", "NASDAQ", "Teknologia"),
            IBKRPositio("NVDA", "NVIDIA Corp.", OSAKE, 9, 78.10, 168.90,
                        "USD", "NASDAQ", "Teknologia"),
            IBKRPositio("TSLA", "Tesla Inc.", OSAKE, 6, 245.00, 198.30,
                        "USD", "NASDAQ", "Kuluttaja"),
            IBKRPositio("VWCE", "Vanguard FTSE All-World UCITS", ETF, 40, 112.50, 128.75,
                        "EUR", "XETRA", "Globaali"),
            IBKRPositio("IWDA", "iShares Core MSCI World", ETF, 18, 88.20, 96.40,
                        "EUR", "AEB", "Globaali"),
        ]

    def hae_kassa(self) -> dict:
        return {"EUR": 1250.00, "USD": 310.00}

    def hae_tili_info(self) -> dict:
        return {"tilinumero": "DU0000000 (mock)", "tyyppi": "demo"}


# ─── Live-toteutus (integraatiopiste) ─────────────────────────


class LiveIBKRClient:
    """
    Oikea IBKR-yhteys.

    Aktivointi tunnusten saamisen jälkeen:
      1. pip install ib_insync   (lisää myös requirements.txt:hen)
      2. Käynnistä TWS tai IB Gateway ja salli API-yhteydet
         (Configuration -> API -> Enable ActiveX and Socket Clients)
      3. Aseta IBKR_MODE=live ja IBKR_PORT
         (7496 = TWS live, 7497 = TWS paper, 4001 = Gateway live)
      4. Toteuta alla merkityt kohdat

    Metodien nimet ja paluuarvojen muoto ovat samat kuin mockissa, joten
    muuta koodia ei tarvitse koskea.
    """

    def __init__(self):
        self.yhdistetty = False
        self._ib = None

    def yhdista(self) -> bool:
        try:
            from ib_insync import IB          # noqa: F401
        except ImportError:
            logger.error(
                "IBKR_MODE=live mutta ib_insync puuttuu. "
                "Asenna: pip install ib_insync"
            )
            return False

        # INTEGRAATIOPISTE 1 – yhteys
        #   self._ib = IB()
        #   self._ib.connect(config.IBKR_HOST, config.IBKR_PORT,
        #                    clientId=config.IBKR_CLIENT_ID, readonly=True)
        #   self.yhdistetty = self._ib.isConnected()
        #
        # HUOM: readonly=True on tarkoituksellinen ja se on säilytettävä.
        logger.warning(
            "LiveIBKRClient: yhteyttä ei ole vielä toteutettu. "
            "Katso integraatiopisteet services/ibkr_service.py:ssä."
        )
        return False

    def hae_positiot(self) -> list:
        # INTEGRAATIOPISTE 2 – positiot
        #   for p in self._ib.positions():
        #       c = p.contract
        #       tyyppi = {"STK": OSAKE, "FUND": RAHASTO}.get(c.secType, ETF)
        #       ... palauta IBKRPositio(...)
        # Markkinahinta: self._ib.reqTickers(contract)[0].marketPrice()
        raise NotImplementedError("IBKR live -positiot: ks. integraatiopiste 2")

    def hae_kassa(self) -> dict:
        # INTEGRAATIOPISTE 3 – käteinen
        #   for v in self._ib.accountValues():
        #       if v.tag == "CashBalance" and v.currency != "BASE":
        #           kassa[v.currency] = float(v.value)
        raise NotImplementedError("IBKR live -kassa: ks. integraatiopiste 3")

    def hae_tili_info(self) -> dict:
        # INTEGRAATIOPISTE 4 – tilitiedot
        raise NotImplementedError("IBKR live -tilitiedot: ks. integraatiopiste 4")


# ─── Palvelu ──────────────────────────────────────────────────


class IBKRService:
    """
    Vain luku -rajapinta IBKR-omistuksiin.
    Ei sisällä kaupankäyntimetodeja eikä niitä saa lisätä.
    """

    def __init__(self):
        self.tila = config.IBKR_MODE
        self.client = None
        self.yhteys_ok = False
        self.virheviesti = ""
        self._alusta()

    def _alusta(self) -> None:
        if self.tila == "off":
            self.virheviesti = "IBKR pois käytöstä (IBKR_MODE=off)"
            logger.info("IBKR pois käytöstä")
            return

        if self.tila == "live":
            self.client = LiveIBKRClient()
            self.yhteys_ok = self.client.yhdista()
            if not self.yhteys_ok:
                self.virheviesti = "IBKR live -yhteys epäonnistui"
            return

        # Oletus: mock
        self.client = MockIBKRClient()
        self.yhteys_ok = True
        logger.info("IBKR: mock-tila – esimerkkidata käytössä (ei oikeita omistuksia)")

    @property
    def on_mock(self) -> bool:
        return self.tila == "mock" and self.yhteys_ok

    def hae_positiot(self) -> list:
        """Palauttaa positiot, tai tyhjän listan jos yhteyttä ei ole."""
        if not self.yhteys_ok or not self.client:
            return []
        try:
            return self.client.hae_positiot()
        except NotImplementedError as e:
            logger.warning(f"IBKR-positioita ei saatavilla: {e}")
            return []
        except Exception as e:
            logger.error(f"IBKR-positioiden haku epäonnistui: {e}")
            return []

    def hae_kassa(self) -> dict:
        """Palauttaa käteisen valuutoittain, esim. {'EUR': 1250.0}."""
        if not self.yhteys_ok or not self.client:
            return {}
        try:
            return self.client.hae_kassa()
        except NotImplementedError as e:
            logger.warning(f"IBKR-kassaa ei saatavilla: {e}")
            return {}
        except Exception as e:
            logger.error(f"IBKR-kassan haku epäonnistui: {e}")
            return {}

    def hae_tila(self) -> dict:
        return {
            "tila": self.tila,
            "yhteys_ok": self.yhteys_ok,
            "on_mock": self.on_mock,
            "virhe": self.virheviesti or None,
            "tarkistettu": datetime.now().isoformat(),
        }


# Globaali instanssi
ibkr_service = IBKRService()
