"""
Kuukausibudjetti ja pääoman allokointi.

Kaksi tehtävää:
  1. Pitää kirjaa kuukauden sijoitusbudjetista ja siitä, paljonko on
     jäljellä.
  2. Jakaa jäljellä oleva budjetti omaisuusluokkiin markkinatilanteen
     mukaan.

HUOM – mistä "jo sijoitettu tässä kuussa" tulee
------------------------------------------------
Järjestelmä ei tee toimeksiantoja eikä siksi voi tietää, mitä olet
ostanut. Toteutuneet ostot kirjataan budget_spend-tauluun joko
API:n kautta (POST /api/budjetti) tai kutsumalla kirjaa_sijoitus().
Ilman kirjauksia "jo sijoitettu" on 0 € ja koko budjetti näyttää
olevan käytettävissä.
"""

from datetime import datetime
from typing import Optional

from config import config
from utils.logger import logger
from services import database as db

KRYPTO, OSAKE, ETF, RAHASTO = "krypto", "osake", "etf", "rahasto"

# Tavoiteallokaatio normaalissa markkinatilanteessa.
PERUSALLOKAATIO = {ETF: 0.40, OSAKE: 0.30, KRYPTO: 0.30}

# Markkinariskin tasot
RISKI_NORMAALI = "normaali"
RISKI_KOHONNUT = "kohonnut"
RISKI_KORKEA = "korkea"
RISKI_AARIMMAINEN = "äärimmäinen"


class BudgetService:
    """Kuukausibudjetin seuranta ja allokointi."""

    # ─── Budjetin tila ────────────────────────────────────────

    def hae_kuukauden_tila(self) -> dict:
        """Kuukausibudjetti, käytetty osuus ja jäljellä oleva summa."""
        kuukausi = datetime.now().strftime("%Y-%m")
        budjetti = config.MONTHLY_BUDGET
        sijoitettu = db.hae_kuukauden_summa(kuukausi)
        jaljella = max(0.0, budjetti - sijoitettu)

        return {
            "kuukausi": kuukausi,
            "kuukausibudjetti": round(budjetti, 2),
            "sijoitettu": round(sijoitettu, 2),
            "jaljella": round(jaljella, 2),
            "kaytetty_prosentti": round(sijoitettu / budjetti * 100, 1) if budjetti > 0 else 0.0,
            "valuutta": config.BASE_CURRENCY,
            "kirjauksia": len(db.hae_kuukauden_sijoitukset(kuukausi)),
        }

    def kirjaa_sijoitus(self, symboli: str, summa: float, nimi: str = "",
                        luokka: str = "", muistiinpano: str = "") -> dict:
        """Kirjaa toteutuneen oston kuluvalle kuukaudelle."""
        try:
            summa = float(summa)
        except (TypeError, ValueError):
            return {"ok": False, "virhe": "Summa ei ole luku"}
        if summa <= 0:
            return {"ok": False, "virhe": "Summan on oltava positiivinen"}

        rivi_id = db.kirjaa_budjettisijoitus(
            symboli=symboli, summa=summa, valuutta=config.BASE_CURRENCY,
            nimi=nimi, luokka=luokka, muistiinpano=muistiinpano,
        )
        if rivi_id is None:
            return {"ok": False, "virhe": "Kirjaus epäonnistui"}

        tila = self.hae_kuukauden_tila()
        logger.info(f"Budjettikirjaus: {symboli} {summa} {config.BASE_CURRENCY}")
        return {"ok": True, "id": rivi_id, "budjetti": tila}

    # ─── Markkinatilanne ──────────────────────────────────────

    def arvioi_markkinatila(self, sentimentti: dict,
                            btc_tech: Optional[dict] = None) -> dict:
        """
        Arvioi markkinatilanteen käytettävissä olevista signaaleista.

        Rajoitus: osakemarkkinoiden tilaa ei voida arvioida, koska
        indeksidataa ei ole ennen IBKR-yhteyttä. Se raportoidaan
        rehellisesti "ei dataa" -tilana eikä arvata.
        """
        fg = (sentimentti.get("fear_greed") or {}).get("arvo")
        sent_luokka = sentimentti.get("kokonaisluokka", "neutraali")

        krypto_yliarvostettu = fg is not None and fg >= 75
        krypto_aliarvostettu = fg is not None and fg <= 25

        # Riskitaso
        riski = RISKI_NORMAALI
        syyt = []

        if fg is not None and fg >= 85:
            riski = RISKI_KORKEA
            syyt.append(f"Fear & Greed {fg} – äärimmäinen ahneus")
        elif krypto_yliarvostettu:
            riski = RISKI_KOHONNUT
            syyt.append(f"Fear & Greed {fg} – ahneus")

        if btc_tech and btc_tech.get("ok"):
            trendi = btc_tech.get("ema", {}).get("trendi")
            if trendi == "vahva_lasku":
                riski = RISKI_KORKEA if riski != RISKI_AARIMMAINEN else riski
                syyt.append("BTC vahvassa laskutrendissä")
            atr, hinta = btc_tech.get("atr"), btc_tech.get("nykyinen_hinta")
            if atr and hinta:
                atr_pct = atr / hinta * 100
                if atr_pct > 10:
                    riski = RISKI_AARIMMAINEN
                    syyt.append(f"Volatiliteetti poikkeuksellisen korkea ({atr_pct:.1f} %)")

        if sent_luokka == "negatiivinen" and riski == RISKI_KORKEA:
            riski = RISKI_AARIMMAINEN
            syyt.append("Sentimentti negatiivinen samanaikaisesti")

        return {
            "riskitaso": riski,
            "syyt": syyt,
            "fear_greed": fg,
            "sentimentti": sent_luokka,
            "krypto_yliarvostettu": krypto_yliarvostettu,
            "krypto_aliarvostettu": krypto_aliarvostettu,
            # Osakemarkkinoiden arviointi vaatii indeksidatan (IBKR).
            "osakemarkkina": "ei dataa – vaatii IBKR-yhteyden",
            "osta_sallittu": riski != RISKI_AARIMMAINEN,
        }

    # ─── Allokointi ───────────────────────────────────────────

    def laske_allokaatio(self, jaljella: float, markkinatila: dict,
                         kateinen_lahteittain: Optional[dict] = None) -> dict:
        """
        Jakaa jäljellä olevan budjetin omaisuusluokkiin.

        Säännöt:
          - lähtökohta 40 % ETF, 30 % osakkeet, 30 % krypto
          - krypto yliarvostettu -> kryptaosuus puolitetaan, vapautuva
            osuus jää käteisvaraukseen
          - riski korkea -> kaikkia osuuksia pienennetään, varaus kasvaa
          - riski äärimmäinen -> ei ostoja lainkaan
        """
        if jaljella <= 0:
            return {
                "jaettava": 0.0, "osuudet": {}, "varaus": 0.0,
                "peruste": "Kuukausibudjetti on käytetty loppuun",
                "ostot_sallittu": False,
            }

        if not markkinatila.get("osta_sallittu", True):
            return {
                "jaettava": 0.0, "osuudet": {}, "varaus": round(jaljella, 2),
                "peruste": "Markkinariski äärimmäinen – suositellaan HOLD, ei ostoja",
                "ostot_sallittu": False,
            }

        osuudet = dict(PERUSALLOKAATIO)
        perusteet = []

        if markkinatila.get("krypto_yliarvostettu"):
            vapautuu = osuudet[KRYPTO] * 0.5
            osuudet[KRYPTO] -= vapautuu
            perusteet.append("Krypto yliarvostettu – kryptaosuus puolitettu")

        riski = markkinatila.get("riskitaso")
        if riski == RISKI_KORKEA:
            for k in osuudet:
                osuudet[k] *= 0.5
            perusteet.append("Markkinariski korkea – ostoja pienennetty puoleen")
        elif riski == RISKI_KOHONNUT:
            for k in osuudet:
                osuudet[k] *= 0.75
            perusteet.append("Markkinariski kohonnut – ostoja pienennetty")

        if markkinatila.get("krypto_aliarvostettu"):
            perusteet.append("Krypto aliarvostettu (pelko) – kryptaosuus säilytetty")

        # Osakemarkkinaa ei voida arvioida -> osakeosuus jätetään varaukseen,
        # koska ostoehdotusta ei voi perustella ilman dataa.
        if markkinatila.get("osakemarkkina", "").startswith("ei dataa"):
            perusteet.append("Osakemarkkinadataa ei saatavilla – osakeosuus varaukseen")
            osuudet[OSAKE] = 0.0

        summat = {k: round(jaljella * v, 2) for k, v in osuudet.items() if v > 0}

        # Brokerien käteistä ei sekoiteta: kryptaa voi ostaa vain
        # Binance-käteisellä, osakkeita ja ETF:iä vain IBKR-käteisellä.
        if kateinen_lahteittain:
            binance = kateinen_lahteittain.get("binance", 0.0)
            ibkr = kateinen_lahteittain.get("ibkr", 0.0)
            rajoitettu = []

            if KRYPTO in summat and summat[KRYPTO] > binance:
                summat[KRYPTO] = round(max(0.0, binance), 2)
                rajoitettu.append("krypto rajattu Binance-käteiseen")

            ibkr_luokat = [k for k in (ETF, OSAKE, RAHASTO) if k in summat]
            ibkr_yhteensa = sum(summat[k] for k in ibkr_luokat)
            if ibkr_yhteensa > ibkr and ibkr_yhteensa > 0:
                kerroin = max(0.0, ibkr) / ibkr_yhteensa
                for k in ibkr_luokat:
                    summat[k] = round(summat[k] * kerroin, 2)
                rajoitettu.append("osake/ETF rajattu IBKR-käteiseen")

            summat = {k: v for k, v in summat.items() if v >= 0.01}
            if rajoitettu:
                perusteet.extend(rajoitettu)

        jaettu = sum(summat.values())
        varaus = round(jaljella - jaettu, 2)

        return {
            "jaettava": round(jaettu, 2),
            "osuudet": summat,
            "osuudet_prosentteina": {k: round(v * 100, 1) for k, v in osuudet.items() if v > 0},
            "varaus": varaus,
            "peruste": "; ".join(perusteet) if perusteet else "Normaali markkinatilanne",
            "ostot_sallittu": jaettu > 0,
        }

    # ─── Kooste ───────────────────────────────────────────────

    def hae_budjettitilanne(self, sentimentti: dict,
                            btc_tech: Optional[dict] = None,
                            kateinen_lahteittain: Optional[dict] = None) -> dict:
        """Budjetti + markkinatilanne + allokaatio yhtenä pakettina."""
        tila = self.hae_kuukauden_tila()
        markkinatila = self.arvioi_markkinatila(sentimentti, btc_tech)
        allokaatio = self.laske_allokaatio(
            tila["jaljella"], markkinatila, kateinen_lahteittain
        )
        return {
            "budjetti": tila,
            "markkinatila": markkinatila,
            "allokaatio": allokaatio,
            "markkinakatsaus": self.muodosta_markkinakatsaus(markkinatila, btc_tech),
            "tavoiteallokaatio": PERUSALLOKAATIO,
        }

    def muodosta_markkinakatsaus(self, markkinatila: dict,
                                 btc_tech: Optional[dict] = None) -> str:
        """
        Yhden kappaleen markkinakatsaus käytettävissä olevista signaaleista.
        Ei keksi dataa: osakemarkkinoiden puuttuminen todetaan ääneen.
        """
        osat = []
        fg = markkinatila.get("fear_greed")
        if fg is not None:
            if fg <= 25:
                osat.append(f"Kryptomarkkinoilla vallitsee pelko (Fear & Greed {fg}), "
                            "mikä on historiallisesti tarkoittanut matalampia "
                            "hintatasoja mutta myös kohonnutta epävarmuutta.")
            elif fg >= 75:
                osat.append(f"Kryptomarkkinoilla vallitsee ahneus (Fear & Greed {fg}), "
                            "mikä nostaa korjausriskiä lyhyellä aikavälillä.")
            else:
                osat.append(f"Kryptomarkkinoiden tunnelma on neutraali "
                            f"(Fear & Greed {fg}).")

        if btc_tech and btc_tech.get("ok"):
            trendi = btc_tech.get("ema", {}).get("trendi", "")
            rsi = btc_tech.get("rsi")
            kuvaus = {"vahva_nousu": "vahvassa nousutrendissä",
                      "nousu": "lievässä nousussa",
                      "neutraali": "sivuttaisliikkeessä",
                      "lasku": "lievässä laskussa",
                      "vahva_lasku": "vahvassa laskutrendissä"}.get(trendi, "epäselvässä trendissä")
            lause = f"Bitcoin on {kuvaus}"
            if rsi:
                lause += f", RSI {rsi:.0f}"
            osat.append(lause + ".")

        taso = markkinatila.get("riskitaso", "normaali")
        if taso != "normaali":
            syyt = "; ".join(markkinatila.get("syyt", []))
            osat.append(f"Kokonaisriski on {taso}" + (f" ({syyt})." if syyt else "."))
        else:
            osat.append("Kokonaisriski on normaalilla tasolla.")

        # Rehellisyys osakemarkkinoista
        osat.append("Osakemarkkinoiden analyysi on rajallinen: indeksidataa ei ole "
                    "käytettävissä ennen IBKR-yhteyden aktivointia, joten osakkeiden "
                    "arviot perustuvat vain positioiden omiin tunnuslukuihin.")
        return " ".join(osat)


# Globaali instanssi
budget_service = BudgetService()
