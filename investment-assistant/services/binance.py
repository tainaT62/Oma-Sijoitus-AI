"""
Binance API -yhteys.
Vastaa yhteyden muodostamisesta ja tilin perustietojen hakemisesta.
Ensimmäisessä versiossa VAIN lukuoikeudet - ei kauppoja.
"""

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from typing import Optional
from utils.logger import logger
from config import config


class BinanceService:
    """
    Binance API -palvelu.
    Sisältää yhteydenmuodostuksen ja tilin tietojen hakemisen.
    """

    def __init__(self):
        self.client: Optional[Client] = None
        self.yhteys_ok: bool = False
        self.virheviesti: str = ""
        self._alusta_yhteys()

    def _alusta_yhteys(self) -> None:
        """Muodostaa yhteyden Binance API:in."""
        try:
            if not config.BINANCE_API_KEY or not config.BINANCE_SECRET_KEY:
                self.yhteys_ok = False
                self.virheviesti = "Binance API-avaimet puuttuvat. Lisää BINANCE_API_KEY ja BINANCE_SECRET_KEY ympäristömuuttujiin."
                logger.warning("Binance API-avaimet puuttuvat")
                return

            logger.info("Muodostetaan yhteyttä Binance API:in...")

            self.client = Client(
                api_key=config.BINANCE_API_KEY,
                api_secret=config.BINANCE_SECRET_KEY,
                testnet=config.BINANCE_TESTNET
            )

            # Testataan yhteys
            self.client.ping()
            self.yhteys_ok = True
            self.virheviesti = ""
            logger.info("Binance API -yhteys muodostettu onnistuneesti")

        except BinanceAPIException as e:
            self.yhteys_ok = False
            self.virheviesti = f"Binance API -virhe: {e.message} (koodi: {e.status_code})"
            logger.error(f"Binance API -virhe yhteyden muodostamisessa: {e}")

        except BinanceRequestException as e:
            self.yhteys_ok = False
            self.virheviesti = f"Binance pyyntövirhe: {str(e)}"
            logger.error(f"Binance pyyntövirhe: {e}")

        except Exception as e:
            self.yhteys_ok = False
            self.virheviesti = f"Odottamaton virhe: {str(e)}"
            logger.error(f"Odottamaton virhe Binance-yhteydessä: {e}", exc_info=True)

    def testaa_yhteys(self) -> dict:
        """
        Testaa yhteyden toimivuuden.
        Palauttaa dict: {'ok': bool, 'viesti': str, 'palvelinaika': str}
        """
        try:
            if not self.client:
                return {
                    "ok": False,
                    "viesti": self.virheviesti,
                    "palvelinaika": None
                }

            palvelinaika = self.client.get_server_time()
            self.yhteys_ok = True
            self.virheviesti = ""

            return {
                "ok": True,
                "viesti": "Yhteys toimii",
                "palvelinaika": palvelinaika.get("serverTime")
            }

        except BinanceAPIException as e:
            self.yhteys_ok = False
            self.virheviesti = f"Binance API -virhe: {e.message}"
            logger.error(f"Binance API -virhe yhteyden testauksessa: {e}")
            return {"ok": False, "viesti": self.virheviesti, "palvelinaika": None}

        except Exception as e:
            self.yhteys_ok = False
            self.virheviesti = str(e)
            logger.error(f"Virhe yhteyden testauksessa: {e}", exc_info=True)
            return {"ok": False, "viesti": str(e), "palvelinaika": None}

    def hae_tili_info(self) -> Optional[dict]:
        """
        Hakee tilin perustiedot Binancesta.
        Palauttaa tilin tiedot tai None virhetilanteessa.
        """
        try:
            if not self.client or not self.yhteys_ok:
                logger.warning("Yritettiin hakea tilitietoja ilman yhteyttä")
                return None

            tili = self.client.get_account()
            logger.debug("Tilitiedot haettu onnistuneesti")
            return tili

        except BinanceAPIException as e:
            logger.error(f"Binance API -virhe tilitietojen haussa: {e}")
            return None

        except Exception as e:
            logger.error(f"Odottamaton virhe tilitietojen haussa: {e}", exc_info=True)
            return None

    def hae_symbolin_hinta(self, symboli: str) -> Optional[float]:
        """
        Hakee yksittäisen symbolin nykyisen hinnan USDT:ssä.
        Esim. 'BTCUSDT' -> 65000.5
        """
        try:
            if not self.client or not self.yhteys_ok:
                return None

            tulos = self.client.get_symbol_ticker(symbol=symboli)
            hinta = float(tulos.get("price", 0))
            logger.debug(f"Hinta haettu: {symboli} = {hinta} USDT")
            return hinta

        except BinanceAPIException as e:
            # Symbolia ei löydy - ei lokiteta virheenä, koska se on normaalia
            if e.status_code == 400:
                logger.debug(f"Symbolia {symboli} ei löydy Binancesta")
            else:
                logger.error(f"Binance API -virhe hinnan haussa ({symboli}): {e}")
            return None

        except Exception as e:
            logger.error(f"Odottamaton virhe hinnan haussa ({symboli}): {e}", exc_info=True)
            return None

    def hae_kaikki_hinnat(self) -> dict:
        """
        Hakee kaikkien symbolien hinnat Binancesta.
        Palauttaa dict: {'BTCUSDT': 65000.5, 'ETHUSDT': 3500.2, ...}
        """
        try:
            if not self.client or not self.yhteys_ok:
                return {}

            hinnat_lista = self.client.get_all_tickers()
            hinnat = {item["symbol"]: float(item["price"]) for item in hinnat_lista}
            logger.debug(f"Haettiin {len(hinnat)} hintaa Binancesta")
            return hinnat

        except BinanceAPIException as e:
            logger.error(f"Binance API -virhe kaikkien hintojen haussa: {e}")
            return {}

        except Exception as e:
            logger.error(f"Odottamaton virhe kaikkien hintojen haussa: {e}", exc_info=True)
            return {}

    def hae_24h_tilastot(self, symboli: str) -> Optional[dict]:
        """
        Hakee 24h hintamuutoksen prosentteina tietylle symbolille.
        """
        try:
            if not self.client or not self.yhteys_ok:
                return None

            tilastot = self.client.get_ticker(symbol=symboli)
            return {
                "muutos_prosentti": float(tilastot.get("priceChangePercent", 0)),
                "korkein_24h": float(tilastot.get("highPrice", 0)),
                "matalin_24h": float(tilastot.get("lowPrice", 0)),
                "volyymi_24h": float(tilastot.get("volume", 0))
            }

        except BinanceAPIException as e:
            logger.debug(f"24h tilastot eivät saatavilla symbolille {symboli}: {e}")
            return None

        except Exception as e:
            logger.error(f"Virhe 24h tilastojen haussa ({symboli}): {e}", exc_info=True)
            return None


# Globaali instanssi
binance_service = BinanceService()
