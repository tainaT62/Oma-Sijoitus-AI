"""
Riskienhallintapalvelu.
Laskee position koon, stop lossin, take profitin ja hajautuksen.
"""

from typing import Optional
from utils.logger import logger
from config import config


class RiskManagerService:
    """
    Laskee riskit ja position koot yksittäisille kaupoille.
    """

    # Oletusriskiparametrit
    MAX_RISKI_PER_KAUPPA_PROSENTTI = 2.0    # 2% salkun arvosta per kauppa
    MAX_POSITIO_PROSENTTI = 25.0             # 25% salkun arvosta per positio
    MIN_KASSAN_OSUUS_PROSENTTI = 10.0        # Pidä aina 10% käteistä
    TAVOITE_STOP_LOSS_KERROIN = 2.0          # ATR × 2 = stop loss etäisyys
    TAVOITE_TAKE_PROFIT_KERROIN = 3.0        # ATR × 3 = take profit etäisyys (1:1.5 RR)

    def laske_position_koko(
        self,
        salkun_arvo_usdt: float,
        hinta: float,
        stop_loss: float,
        max_riski_prosentti: Optional[float] = None
    ) -> dict:
        """
        Laskee suositeltavan position koon riskiprosentin perusteella.

        Kaava: Position koko = (Salkun arvo × Riskinotto%) / (Hinta - Stop loss)
        """
        try:
            max_riski = max_riski_prosentti or self.MAX_RISKI_PER_KAUPPA_PROSENTTI
            stop_etaisyys = abs(hinta - stop_loss)

            if stop_etaisyys == 0 or hinta == 0 or salkun_arvo_usdt == 0:
                return {"ok": False, "virhe": "Virheelliset syötteet"}

            # Maksimiriski rahassa
            max_riski_usdt = salkun_arvo_usdt * (max_riski / 100)

            # Kappaleiden määrä
            kappaleet = max_riski_usdt / stop_etaisyys

            # Positioarvo
            positioarvo_usdt = kappaleet * hinta

            # Tarkista, ettei ylitä maksimipositiota
            max_positio_usdt = salkun_arvo_usdt * (self.MAX_POSITIO_PROSENTTI / 100)
            if positioarvo_usdt > max_positio_usdt:
                positioarvo_usdt = max_positio_usdt
                kappaleet = positioarvo_usdt / hinta

            osuus_salkusta = (positioarvo_usdt / salkun_arvo_usdt) * 100

            return {
                "ok": True,
                "kappaleet": round(kappaleet, 6),
                "positioarvo_usdt": round(positioarvo_usdt, 2),
                "osuus_salkusta_prosentti": round(osuus_salkusta, 2),
                "max_tappio_usdt": round(max_riski_usdt, 2),
                "max_tappio_prosentti": max_riski,
                "stop_etaisyys_usdt": round(stop_etaisyys, 4),
                "stop_etaisyys_prosentti": round((stop_etaisyys / hinta) * 100, 2)
            }

        except Exception as e:
            logger.error(f"Virhe position koon laskennassa: {e}")
            return {"ok": False, "virhe": str(e)}

    def laske_stop_loss_take_profit(
        self,
        hinta: float,
        atr: float,
        suunta: str = "long"
    ) -> dict:
        """
        Laskee ATR-pohjaisen stop lossin ja take profitin.
        suunta: 'long' tai 'short'
        """
        if hinta <= 0 or atr <= 0:
            return {"ok": False, "virhe": "Virheelliset syötteet"}

        try:
            sl_etaisyys = atr * self.TAVOITE_STOP_LOSS_KERROIN
            tp_etaisyys = atr * self.TAVOITE_TAKE_PROFIT_KERROIN

            if suunta == "long":
                stop_loss = hinta - sl_etaisyys
                take_profit = hinta + tp_etaisyys
            else:  # short
                stop_loss = hinta + sl_etaisyys
                take_profit = hinta - tp_etaisyys

            riski_tuotto_suhde = tp_etaisyys / sl_etaisyys if sl_etaisyys > 0 else 0

            return {
                "ok": True,
                "stop_loss": round(stop_loss, 4),
                "take_profit": round(take_profit, 4),
                "sl_etaisyys_usdt": round(sl_etaisyys, 4),
                "tp_etaisyys_usdt": round(tp_etaisyys, 4),
                "sl_etaisyys_prosentti": round((sl_etaisyys / hinta) * 100, 2),
                "tp_etaisyys_prosentti": round((tp_etaisyys / hinta) * 100, 2),
                "riski_tuotto_suhde": round(riski_tuotto_suhde, 2),
                "atr_kaytetty": atr
            }

        except Exception as e:
            logger.error(f"Virhe SL/TP-laskennassa: {e}")
            return {"ok": False, "virhe": str(e)}

    def arvioi_salkun_riskit(self, omistukset: list, kokonaisarvo_usdt: float) -> dict:
        """
        Arvioi koko salkun riskitason hajautuksen perusteella.
        """
        try:
            if not omistukset or kokonaisarvo_usdt <= 0:
                return {"ok": False, "virhe": "Ei omistuksia"}

            # Suurin yksittäinen positio
            suurin_positio = max(omistukset, key=lambda x: x.get("arvo_usdt", 0))
            suurin_osuus = suurin_positio.get("osuus_prosentti", 0)

            # Käteisosuus (USDT + stablecoinit)
            kauppa_osuus = sum(
                o.get("osuus_prosentti", 0)
                for o in omistukset
                if o.get("on_stablecoin", False)
            )

            # BTC-dominanssi
            btc_osuus = next(
                (o.get("osuus_prosentti", 0) for o in omistukset if o["valuutta"] == "BTC"),
                0
            )

            # Riskiarviot
            varoitukset = []
            suositukset_lista = []

            if suurin_osuus > 50:
                varoitukset.append(f"Liian suuri yksittäinen positio: {suurin_positio['valuutta']} ({suurin_osuus:.1f}%)")
                suositukset_lista.append(f"Harkitse {suurin_positio['valuutta']}-position pienentämistä alle 50%:iin")

            if kauppa_osuus < self.MIN_KASSAN_OSUUS_PROSENTTI:
                varoitukset.append(f"Käteisreservi pieni: {kauppa_osuus:.1f}% (suositus ≥ {self.MIN_KASSAN_OSUUS_PROSENTTI}%)")
                suositukset_lista.append(f"Pidä vähintään {self.MIN_KASSAN_OSUUS_PROSENTTI}% käteistä tai stablecoineina")

            if btc_osuus > 60:
                varoitukset.append(f"BTC-paino korkea: {btc_osuus:.1f}%")

            if len(omistukset) < 3:
                varoitukset.append("Hajautus heikko – alle 3 omistusta")
                suositukset_lista.append("Harkitse hajautusta useampaan kryptovaluuttaan")

            # Kokonaisriskitaso
            if len(varoitukset) >= 3:
                riskitaso = "Korkea"
                riskivari = "danger"
            elif len(varoitukset) >= 1:
                riskitaso = "Keskitasoinen"
                riskivari = "warning"
            else:
                riskitaso = "Matala"
                riskivari = "success"

            return {
                "ok": True,
                "riskitaso": riskitaso,
                "riskivari": riskivari,
                "varoitukset": varoitukset,
                "suositukset": suositukset_lista,
                "tilastot": {
                    "suurin_positio_valuutta": suurin_positio["valuutta"],
                    "suurin_positio_osuus": round(suurin_osuus, 1),
                    "kauppa_osuus_prosentti": round(kauppa_osuus, 1),
                    "btc_osuus_prosentti": round(btc_osuus, 1),
                    "omistusten_maara": len(omistukset)
                }
            }

        except Exception as e:
            logger.error(f"Virhe salkun riskiarvioinnissa: {e}", exc_info=True)
            return {"ok": False, "virhe": str(e)}


# Globaali instanssi
risk_manager_service = RiskManagerService()
