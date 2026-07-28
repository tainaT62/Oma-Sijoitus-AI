"""
Backtest-moottori.
Testaa AI:n suosituksia historiallisella datalla.

Kaksi tapaa:
1. Tietokantahistoria: analysoi tallennettujen suositusten toteutunut tulos
2. Strategiasimulatio: simuloi yksinkertaisen strategian historiallisella Binance-datalla

Mittarit:
- Onnistumisprosentti
- Keskimääräinen tuotto
- Suurin tappio (max loss)
- Sharpe-luku
- Max drawdown
"""

import math
import time
from typing import Optional
from utils.logger import logger
from services.binance import binance_service
from services import database as db


class BacktestMoottori:
    """
    Backtest-moottori – testaa strategioita historiallisella datalla.
    """

    def _hae_historia_klines(
        self, symboli: str, aikaväli: str = "1d", maara: int = 365
    ) -> list:
        """Hakee kynttilädatan Binancesta."""
        try:
            if not binance_service.client or not binance_service.yhteys_ok:
                return []
            klines = binance_service.client.get_klines(
                symbol=symboli, interval=aikaväli, limit=maara
            )
            return klines
        except Exception as e:
            logger.warning(f"Klines-haku epäonnistui ({symboli}): {e}")
            return []

    def _laske_sharpe(
        self, tuotot: list, riskiton_tuotto: float = 0.05
    ) -> Optional[float]:
        """
        Laskee Sharpe-luvun.
        Oletusriskitön tuotto: 5% vuodessa → ~0.014% päivässä
        """
        if len(tuotot) < 2:
            return None
        n = len(tuotot)
        ka = sum(tuotot) / n
        varianssi = sum((t - ka) ** 2 for t in tuotot) / (n - 1)
        std = math.sqrt(varianssi) if varianssi > 0 else 0
        if std == 0:
            return None
        riskiton_paivakohtainen = riskiton_tuotto / 365
        sharpe = (ka - riskiton_paivakohtainen) / std * math.sqrt(365)
        return round(sharpe, 3)

    def _laske_max_drawdown(self, paaoman_historia: list) -> float:
        """Laskee suurimman arvonlaskun huipusta."""
        if not paaoman_historia:
            return 0.0
        huippu = paaoman_historia[0]
        max_dd = 0.0
        for arvo in paaoman_historia:
            if arvo > huippu:
                huippu = arvo
            drawdown = (huippu - arvo) / huippu if huippu > 0 else 0
            if drawdown > max_dd:
                max_dd = drawdown
        return round(max_dd * 100, 2)

    def simuloi_yksinkertainen_strategia(
        self,
        symboli: str = "BTCUSDT",
        aikaväli: str = "1d",
        alkupaaoma: float = 10000.0
    ) -> dict:
        """
        Simuloi yksinkertaisen RSI + EMA-strategian historiallisella datalla.

        Strategia:
        - OSTA kun RSI < 35 JA hinta > EMA200
        - MYY kun RSI > 65 TAI hinta < EMA200 × 0.97
        - Stop loss: -5% sisääntulohinnoista
        """
        logger.info(f"Backtest käynnistetään: {symboli}")
        klines = self._hae_historia_klines(symboli, aikaväli, 500)

        if not klines or len(klines) < 210:
            return {
                "ok": False,
                "virhe": "Ei riittävästi historiallista dataa",
                "symboli": symboli
            }

        sulkuhinnat = [float(k[4]) for k in klines]
        volyymit = [float(k[5]) for k in klines]

        # Laske EMA200
        def ema_laske(arvot, p):
            k = 2 / (p + 1)
            e = [sum(arvot[:p]) / p]
            for a in arvot[p:]:
                e.append(a * k + e[-1] * (1 - k))
            return [None] * (p - 1) + e

        def rsi_laske(arvot, p=14):
            muutokset = [arvot[i] - arvot[i-1] for i in range(1, len(arvot))]
            nousut = [max(m, 0) for m in muutokset]
            laskut = [abs(min(m, 0)) for m in muutokset]
            rsit = [None] * p
            avg_n = sum(nousut[:p]) / p
            avg_l = sum(laskut[:p]) / p
            for i in range(p, len(muutokset)):
                avg_n = (avg_n * (p-1) + nousut[i]) / p
                avg_l = (avg_l * (p-1) + laskut[i]) / p
                rs = avg_n / avg_l if avg_l != 0 else 100
                rsit.append(100 - 100 / (1 + rs))
            return rsit

        ema200 = ema_laske(sulkuhinnat, 200)
        rsit = rsi_laske(sulkuhinnat, 14)

        # Simuloi kaupankäynti
        paaoma = alkupaaoma
        positio = 0.0           # Ostettu määrä
        sisaantulohinta = 0.0
        kaupat = []
        paaomahistoria = [alkupaaoma]
        paivatuotot = []
        edellinen_paaoma = alkupaaoma

        for i in range(210, len(sulkuhinnat)):
            hinta = sulkuhinnat[i]
            rsi = rsit[i]
            e200 = ema200[i]

            if rsi is None or e200 is None:
                continue

            # Tarkista stop loss
            if positio > 0 and sisaantulohinta > 0:
                tappio_pct = (hinta - sisaantulohinta) / sisaantulohinta
                if tappio_pct <= -0.05:
                    # Stop loss laukeaa
                    tuotto = positio * hinta - positio * sisaantulohinta
                    paaoma += positio * hinta
                    kaupat.append({
                        "tyyppi": "MYY (SL)",
                        "hinta": hinta,
                        "tuotto_prosentti": round(tappio_pct * 100, 2),
                        "indeksi": i
                    })
                    paivatuotot.append(tappio_pct)
                    positio = 0
                    sisaantulohinta = 0

            # Ostosignaali: RSI < 35 JA hinta > EMA200
            if positio == 0 and rsi < 35 and hinta > e200:
                # Käytä 95% pääomasta
                sijoitus = paaoma * 0.95
                positio = sijoitus / hinta
                sisaantulohinta = hinta
                paaoma -= sijoitus
                kaupat.append({"tyyppi": "OSTA", "hinta": hinta, "indeksi": i})

            # Myyntisignaali: RSI > 65 TAI hinta alle EMA200
            elif positio > 0 and (rsi > 65 or hinta < e200 * 0.97):
                tuotto_pct = (hinta - sisaantulohinta) / sisaantulohinta
                paaoma += positio * hinta
                kaupat.append({
                    "tyyppi": "MYY",
                    "hinta": hinta,
                    "tuotto_prosentti": round(tuotto_pct * 100, 2),
                    "indeksi": i
                })
                paivatuotot.append(tuotto_pct)
                positio = 0
                sisaantulohinta = 0

            # Seuraa päiväkohtainen arvo
            nykyarvo = paaoma + (positio * hinta if positio > 0 else 0)
            paivatuotto = (nykyarvo - edellinen_paaoma) / edellinen_paaoma if edellinen_paaoma > 0 else 0
            paaomahistoria.append(nykyarvo)
            edellinen_paaoma = nykyarvo

        # Sulje avoin positio
        if positio > 0:
            viim_hinta = sulkuhinnat[-1]
            paaoma += positio * viim_hinta
            tuotto_pct = (viim_hinta - sisaantulohinta) / sisaantulohinta
            paivatuotot.append(tuotto_pct)

        # Laske statistiikat
        myyntikaupat = [k for k in kaupat if k["tyyppi"] in ("MYY", "MYY (SL)")]
        onnistuneet = [k for k in myyntikaupat if k.get("tuotto_prosentti", 0) > 0]
        epaonnistuneet = [k for k in myyntikaupat if k.get("tuotto_prosentti", 0) <= 0]

        onnistumisprosentti = (
            len(onnistuneet) / len(myyntikaupat) * 100
            if myyntikaupat else 0
        )

        tuotot_lista = [k.get("tuotto_prosentti", 0) for k in myyntikaupat]
        ka_tuotto = sum(tuotot_lista) / len(tuotot_lista) if tuotot_lista else 0
        suurin_tappio = min(tuotot_lista) if tuotot_lista else 0
        suurin_voitto = max(tuotot_lista) if tuotot_lista else 0

        sharpe = self._laske_sharpe(paivatuotot)
        max_dd = self._laske_max_drawdown(paaomahistoria)

        # Buy & Hold -vertailu
        bah_tuotto = (sulkuhinnat[-1] - sulkuhinnat[210]) / sulkuhinnat[210] * 100

        kokonaistuotto = (paaoma - alkupaaoma) / alkupaaoma * 100

        logger.info(
            f"Backtest valmis {symboli}: {len(myyntikaupat)} kauppaa, "
            f"onnistuminen {onnistumisprosentti:.1f}%, "
            f"kokonaistuotto {kokonaistuotto:.1f}%"
        )

        return {
            "ok": True,
            "symboli": symboli,
            "aikaväli": aikaväli,
            "strategia": "RSI(14) + EMA200",
            "alkupaaoma": alkupaaoma,
            "loppupaaoma": round(paaoma, 2),
            "kokonaistuotto_prosentti": round(kokonaistuotto, 2),
            "onnistumisprosentti": round(onnistumisprosentti, 1),
            "ka_tuotto_per_kauppa_prosentti": round(ka_tuotto, 2),
            "suurin_tappio_prosentti": round(suurin_tappio, 2),
            "suurin_voitto_prosentti": round(suurin_voitto, 2),
            "sharpe_luku": sharpe,
            "max_drawdown_prosentti": max_dd,
            "kauppoja_yhteensa": len(myyntikaupat),
            "onnistuneet": len(onnistuneet),
            "epaonnistuneet": len(epaonnistuneet),
            "buy_and_hold_tuotto_prosentti": round(bah_tuotto, 2),
            "strategia_vs_bah": round(kokonaistuotto - bah_tuotto, 2),
            "viimeisimmat_kaupat": myyntikaupat[-5:]
        }

    def analysoi_tallennetut_suositukset(self) -> dict:
        """
        Analysoi tietokantaan tallennettujen suositusten toteutuneen suorituskyvyn.
        Vaatii historiaa – ensimmäisellä ajolla palauttaa tyhjän tuloksen.
        """
        try:
            suositukset = db.hae_suositushistoria(maara=100)

            if not suositukset:
                return {
                    "ok": True,
                    "viesti": "Ei vielä historiaa – suorituskyky kertyy ajan myötä",
                    "suosituksia_yhteensa": 0,
                    "analysoituja": 0
                }

            # Etsi suositukset, joille on saatavilla sulkuhinta
            analysoitavat = [s for s in suositukset if s.get("tulos_prosentti") is not None]

            if not analysoitavat:
                return {
                    "ok": True,
                    "viesti": f"{len(suositukset)} suositusta tallennettu – sulkuhinnat puuttuvat",
                    "suosituksia_yhteensa": len(suositukset),
                    "analysoituja": 0
                }

            tuotot = [s["tulos_prosentti"] for s in analysoitavat]
            onnistuneet = [t for t in tuotot if t > 0]

            return {
                "ok": True,
                "suosituksia_yhteensa": len(suositukset),
                "analysoituja": len(analysoitavat),
                "onnistumisprosentti": round(len(onnistuneet) / len(tuotot) * 100, 1),
                "ka_tuotto_prosentti": round(sum(tuotot) / len(tuotot), 2),
                "suurin_tappio_prosentti": round(min(tuotot), 2),
                "suurin_voitto_prosentti": round(max(tuotot), 2),
                "sharpe_luku": self._laske_sharpe([t/100 for t in tuotot])
            }

        except Exception as e:
            logger.error(f"Virhe suositusanalyysissä: {e}")
            return {"ok": False, "virhe": str(e)}


# Globaali instanssi
backtest_moottori = BacktestMoottori()
