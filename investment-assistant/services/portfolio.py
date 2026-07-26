"""
Salkkupalvelu.
Laskee salkun arvon ja näyttää omistukset.
"""

from datetime import datetime
from typing import Optional
from utils.logger import logger
from config import config
from services.binance import binance_service
from services.market_data import market_data_service


class PortfolioService:
    """
    Salkkupalvelu.
    Hakee Binancen Spot-lompakon saldon ja laskee salkun kokonaisarvon.
    """

    def hae_salkku(self, pakota_paivitys: bool = False) -> dict:
        """
        Hakee koko salkun tiedot.
        Palauttaa dict omistuksista ja kokonaisarvosta.
        """
        try:
            logger.info("Haetaan salkkutiedot...")

            # Tarkista yhteys
            if not binance_service.yhteys_ok:
                return {
                    "ok": False,
                    "virhe": binance_service.virheviesti,
                    "omistukset": [],
                    "kokonaisarvo_usdt": 0.0,
                    "paivitysaika": datetime.now().isoformat()
                }

            # Hae tilitiedot
            tili = binance_service.hae_tili_info()
            if not tili:
                return {
                    "ok": False,
                    "virhe": "Tilitietojen hakeminen epäonnistui",
                    "omistukset": [],
                    "kokonaisarvo_usdt": 0.0,
                    "paivitysaika": datetime.now().isoformat()
                }

            # Päivitä markkinahinnat
            market_data_service.hae_hinnat(pakota_paivitys=pakota_paivitys)

            # Käsittele saldot
            omistukset = []
            kokonaisarvo_usdt = 0.0

            for saldo in tili.get("balances", []):
                valuutta = saldo["asset"]
                vapaa = float(saldo["free"])
                lukittu = float(saldo["locked"])
                yhteensa = vapaa + lukittu

                # Ohita tyhjät saldot
                if yhteensa <= 0:
                    continue

                # Hae hinta
                hinta_usdt = market_data_service.hae_usdt_hinta(valuutta)

                if hinta_usdt is None:
                    # Omistus, jolle ei löydy hintaa
                    arvo_usdt = 0.0
                    hinta_usdt = 0.0
                    hinta_tuntematon = True
                else:
                    arvo_usdt = yhteensa * hinta_usdt
                    hinta_tuntematon = False

                # Ohita hyvin pienet saldot
                if arvo_usdt < config.MIN_BALANCE_USDT and hinta_usdt > 0:
                    continue

                # Hae 24h muutos
                muutos_24h = None
                if valuutta not in config.STABLECOINS:
                    muutos_24h = market_data_service.hae_24h_muutos(valuutta)

                kokonaisarvo_usdt += arvo_usdt

                omistukset.append({
                    "valuutta": valuutta,
                    "maara": yhteensa,
                    "vapaa": vapaa,
                    "lukittu": lukittu,
                    "hinta_usdt": hinta_usdt,
                    "arvo_usdt": arvo_usdt,
                    "muutos_24h": muutos_24h,
                    "hinta_tuntematon": hinta_tuntematon,
                    "on_stablecoin": valuutta in config.STABLECOINS
                })

            # Järjestä arvon mukaan laskevaan järjestykseen
            omistukset.sort(key=lambda x: x["arvo_usdt"], reverse=True)

            # Laske osuudet prosentteina
            if kokonaisarvo_usdt > 0:
                for omistus in omistukset:
                    omistus["osuus_prosentti"] = (
                        omistus["arvo_usdt"] / kokonaisarvo_usdt * 100
                    )
            else:
                for omistus in omistukset:
                    omistus["osuus_prosentti"] = 0.0

            logger.info(
                f"Salkku haettu: {len(omistukset)} omistusta, "
                f"kokonaisarvo {kokonaisarvo_usdt:.2f} USDT"
            )

            return {
                "ok": True,
                "virhe": None,
                "omistukset": omistukset,
                "kokonaisarvo_usdt": kokonaisarvo_usdt,
                "omistusten_maara": len(omistukset),
                "paivitysaika": datetime.now().isoformat(),
                "cache_tiedot": market_data_service.hae_cache_tiedot()
            }

        except Exception as e:
            logger.error(f"Odottamaton virhe salkun haussa: {e}", exc_info=True)
            return {
                "ok": False,
                "virhe": f"Odottamaton virhe: {str(e)}",
                "omistukset": [],
                "kokonaisarvo_usdt": 0.0,
                "paivitysaika": datetime.now().isoformat()
            }


# Globaali instanssi
portfolio_service = PortfolioService()
