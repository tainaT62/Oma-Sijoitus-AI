"""
Toimeksiantojen toteutus – AINOA paikka koko järjestelmässä, joka voi
lähettää kaupan pörssiin.

TURVAMALLI
----------
1. Mikään ei tapahdu automaattisesti. Jokainen toimeksianto vaatii kaksi
   erillistä painallusta Telegramissa: ensin toiminto, sitten VAHVISTA.
2. `ENABLE_TRADING` on oletuksena false. Silloin koko kulku toimii
   normaalisti, mutta pörssiin ei lähetetä mitään ja vastaus kertoo
   selvästi, että kaupankäynti on pois käytöstä.
3. `MAX_ORDER_VALUE` rajaa yksittäisen toimeksiannon koon.
4. Vain Binance. IBKR-rajapinnassa ei ole toimeksiantometodeja eikä
   niitä lisätä – osakkeet ja ETF:t toteutetaan itse.

Jos tämä tiedosto poistetaan, järjestelmä palaa täysin vain luku
-tilaan: mikään muu moduuli ei kutsu pörssin kirjoitusrajapintoja.
"""

import math
from typing import Optional

from config import config
from utils.logger import logger
from services.binance import binance_service


class OrderService:
    """Toteuttaa vahvistetun toimeksiannon – tai simuloi sen."""

    def __init__(self):
        self.kaytossa = config.ENABLE_TRADING
        if self.kaytossa:
            logger.warning(
                "KAUPANKÄYNTI KÄYTÖSSÄ (ENABLE_TRADING=true) – "
                "vahvistetut toimeksiannot lähetetään Binanceen"
            )
        else:
            logger.info(
                "Kaupankäynti pois käytöstä (ENABLE_TRADING=false) – "
                "toimeksiannot simuloidaan"
            )

    # ─── Pörssin säännöt ──────────────────────────────────────

    def _symbolin_saannot(self, symboli: str) -> dict:
        """
        Hakee symbolin kaupankäyntisäännöt: askelkoko, minimimäärä ja
        minimiarvo. Ilman näitä Binance hylkää toimeksiannon.
        """
        try:
            info = binance_service.client.get_symbol_info(symboli)
            if not info:
                return {}
            saannot = {}
            for f in info.get("filters", []):
                if f["filterType"] == "LOT_SIZE":
                    saannot["step"] = float(f["stepSize"])
                    saannot["min_maara"] = float(f["minQty"])
                elif f["filterType"] in ("MIN_NOTIONAL", "NOTIONAL"):
                    saannot["min_arvo"] = float(f.get("minNotional", 0) or 0)
            return saannot
        except Exception as e:
            logger.error(f"Symbolin sääntöjen haku epäonnistui ({symboli}): {e}")
            return {}

    @staticmethod
    def _pyorista_askeleeseen(maara: float, step: float) -> float:
        """Pyöristää määrän alaspäin pörssin sallimaan askeleeseen."""
        if not step:
            return maara
        tarkkuus = int(round(-math.log10(step))) if step < 1 else 0
        pyoristetty = math.floor(maara / step) * step
        return round(pyoristetty, max(0, tarkkuus))

    # ─── Toteutus ─────────────────────────────────────────────

    def toteuta(self, toimenpide: dict, eur_usd: Optional[float] = None) -> dict:
        """
        Toteuttaa vahvistetun toimenpiteen.

        `toimenpide` on pending_actions-rivi: tyyppi, symboli, summa
        (BUY, perusvaluutassa) tai maara (SELL/REDUCE, kappaleina).

        Palauttaa aina dictin – ei koskaan nosta poikkeusta, jotta
        Telegram-kulku voi kertoa tuloksen käyttäjälle.
        """
        tyyppi = toimenpide.get("tyyppi")
        symboli = toimenpide.get("symboli")

        try:
            if tyyppi == "BUY":
                return self._osta(toimenpide, eur_usd)
            if tyyppi in ("SELL", "REDUCE"):
                return self._myy(toimenpide)
            return {"ok": False, "virhe": f"Tuntematon toimenpide: {tyyppi}"}
        except Exception as e:
            logger.error(f"Toimeksiannon toteutus epäonnistui ({symboli}): {e}",
                         exc_info=True)
            return {"ok": False, "virhe": str(e)}

    def _osta(self, t: dict, eur_usd: Optional[float]) -> dict:
        symboli = t["symboli"]
        summa = float(t.get("summa") or 0)

        if summa <= 0:
            return {"ok": False, "virhe": "Ostosumma puuttuu"}
        if summa > config.MAX_ORDER_VALUE:
            return {"ok": False,
                    "virhe": f"Summa {summa} ylittää rajan {config.MAX_ORDER_VALUE}"}

        # Perusvaluutta -> USDT (Binancen quote-valuutta)
        if config.BASE_CURRENCY == "EUR":
            if not eur_usd:
                return {"ok": False, "virhe": "EUR/USD-kurssia ei saatavilla"}
            quote_summa = round(summa * eur_usd, 2)
        else:
            quote_summa = round(summa, 2)

        saannot = self._symbolin_saannot(symboli) if self.kaytossa else {}
        min_arvo = saannot.get("min_arvo", 0)
        if min_arvo and quote_summa < min_arvo:
            return {"ok": False,
                    "virhe": f"Summa alittaa pörssin minimin ({min_arvo} USDT)"}

        if not self.kaytossa:
            return self._simuloitu({
                "symboli": symboli, "puoli": "BUY",
                "quote_summa": quote_summa, "summa": summa,
            })

        # Market-osto quote-määrällä: kerrotaan paljonko rahaa käytetään,
        # ei montako kappaletta – näin summa on tarkasti hallinnassa.
        tulos = binance_service.client.create_order(
            symbol=symboli, side="BUY", type="MARKET",
            quoteOrderQty=quote_summa,
        )
        return self._muotoile_tulos(tulos, symboli, "BUY")

    def _myy(self, t: dict) -> dict:
        symboli = t["symboli"]
        maara = float(t.get("maara") or 0)

        if maara <= 0:
            return {"ok": False, "virhe": "Myyntimäärä puuttuu"}

        saannot = self._symbolin_saannot(symboli) if self.kaytossa else {}
        step = saannot.get("step")
        if step:
            maara = self._pyorista_askeleeseen(maara, step)
            if maara < saannot.get("min_maara", 0):
                return {"ok": False,
                        "virhe": f"Määrä alittaa pörssin minimin ({saannot['min_maara']})"}

        if not self.kaytossa:
            return self._simuloitu({
                "symboli": symboli, "puoli": "SELL", "maara": maara,
                "osuus_prosentti": t.get("osuus_prosentti"),
            })

        tulos = binance_service.client.create_order(
            symbol=symboli, side="SELL", type="MARKET", quantity=maara,
        )
        return self._muotoile_tulos(tulos, symboli, "SELL")

    # ─── Vastaukset ───────────────────────────────────────────

    @staticmethod
    def _simuloitu(tiedot: dict) -> dict:
        """Kuivaharjoitus: sama rakenne kuin oikealla toteutuksella."""
        logger.info(
            f"SIMULOITU toimeksianto (ENABLE_TRADING=false): "
            f"{tiedot['puoli']} {tiedot['symboli']}"
        )
        return {
            "ok": True,
            "simuloitu": True,
            "kaupankaynti_pois": True,
            "symboli": tiedot["symboli"],
            "puoli": tiedot["puoli"],
            "quote_summa": tiedot.get("quote_summa"),
            "maara": tiedot.get("maara"),
            "viesti": "Kaupankäynti on pois käytöstä – toimeksiantoa ei lähetetty.",
        }

    @staticmethod
    def _muotoile_tulos(tulos: dict, symboli: str, puoli: str) -> dict:
        """Poimii Binancen vastauksesta olennaisen."""
        fills = tulos.get("fills") or []
        toteutunut_maara = float(tulos.get("executedQty", 0) or 0)
        toteutunut_arvo = float(tulos.get("cummulativeQuoteQty", 0) or 0)
        keskihinta = (toteutunut_arvo / toteutunut_maara) if toteutunut_maara else None

        logger.info(
            f"Toimeksianto toteutettu: {puoli} {symboli} "
            f"{toteutunut_maara} @ {keskihinta}"
        )
        return {
            "ok": tulos.get("status") in ("FILLED", "PARTIALLY_FILLED"),
            "simuloitu": False,
            "symboli": symboli,
            "puoli": puoli,
            "tila": tulos.get("status"),
            "toimeksianto_id": tulos.get("orderId"),
            "maara": toteutunut_maara,
            "quote_summa": toteutunut_arvo,
            "keskihinta": keskihinta,
            "osatoteutuksia": len(fills),
        }


# Globaali instanssi
order_service = OrderService()
