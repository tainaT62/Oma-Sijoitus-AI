"""
Suositusmoottori.
Yhdistää teknisen analyysin, sentimentin, uutiset ja salkun tilanteen
yhdeksi perustelluksi sijoitussuositukseksi.

TÄRKEÄÄ: Tämä on analyysityökalu, ei kaupankäyntibotti.
Kaikki toimeksiannot vaativat käyttäjän eksplisiittisen hyväksynnän.
"""

import time
from typing import Optional
from utils.logger import logger
from config import config
from services.technical_analysis import technical_analysis_service
from services.sentiment import sentiment_service
from services.news_service import news_service
from services.ai_engine import ai_engine


# Riskiluokat
RISKILUOKAT = {
    "matala": {"kynnys": 0.3, "kuvaus": "Matala riski"},
    "keskitaso": {"kynnys": 0.6, "kuvaus": "Keskitasoinen riski"},
    "korkea": {"kynnys": 1.0, "kuvaus": "Korkea riski"}
}

# Symbolit, joita analysoidaan oletuksena (kun salkkudata ei ole saatavilla)
OLETUSSYMBOLIT = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


class RecommendationEngine:
    """
    Suositusmoottori – analysoi ja tuottaa suosituksia.
    """

    def __init__(self):
        self._cache: dict = {}
        self._cache_aika: float = 0.0
        self._cache_ttl: int = config.RECOMMENDATION_CACHE_TTL

    def _cache_vanhentunut(self) -> bool:
        return (time.time() - self._cache_aika) > self._cache_ttl

    def _laske_luottamusprosentti(
        self,
        tekniset_pisteet: int,
        sentimentti_pisteet: float,
        uutissentimentti_pisteet: float
    ) -> int:
        """
        Laskee suosituksen luottamusprosentin 0–100.
        Yhdistää tekniset, sentimentti- ja uutisanalyysit.
        """
        # Normalisoi pisteet 0–100 asteikolla
        # Tekniset pisteet: tyypillisesti -6..6 → 0..100
        tech_normalisoitu = min(100, max(0, (tekniset_pisteet + 6) / 12 * 100))

        # Sentimentti: -1..1 → 0..100
        sentiment_normalisoitu = (sentimentti_pisteet + 1) / 2 * 100

        # Uutissentimentti: -1..1 → 0..100
        uutis_normalisoitu = (uutissentimentti_pisteet + 1) / 2 * 100

        # Painotettu keskiarvo
        luottamus = (
            tech_normalisoitu * 0.5 +
            sentiment_normalisoitu * 0.3 +
            uutis_normalisoitu * 0.2
        )

        # Vähimmäisluottamus 35%, enimmäis 92% (ei koskaan 100% varmuutta)
        return int(min(92, max(35, luottamus)))

    def _maarita_riski(
        self,
        atr: Optional[float],
        hinta: float,
        volatiliteetti_pisteet: float
    ) -> str:
        """Määrittää riskiluokan."""
        if atr is None or hinta == 0:
            return "Keskitasoinen riski"

        # ATR suhteessa hintaan (%) = volatiliteetti
        atr_prosentti = (atr / hinta) * 100

        if atr_prosentti < 2:
            return "Matala riski"
        elif atr_prosentti < 5:
            return "Keskitasoinen riski"
        else:
            return "Korkea riski"

    def analysoi_symboli(self, symboli: str) -> dict:
        """
        Tekee täydellisen analyysin yksittäiselle symbolille.
        Palauttaa suosituksen perusteluineen.
        """
        logger.info(f"Analysoidaan symboli: {symboli}")

        try:
            # 1. Tekninen analyysi
            tech = technical_analysis_service.analysoi(symboli, "1h")

            # 2. Sentimentti
            sentimentti = sentiment_service.hae_kokonaissentimentti()

            # 3. Uutiset
            otsikot = news_service.hae_otsikot_analyysiin(15)
            symboli_uutiset = news_service.hae_symbolin_uutiset(symboli, 3)

            # 4. Laske suositus
            if not tech.get("ok"):
                return {
                    "ok": False,
                    "symboli": symboli,
                    "virhe": tech.get("virhe", "Tekninen analyysi epäonnistui")
                }

            tekninen_suositus = tech.get("tekninen_suositus", "PIDÄ")
            tekniset_pisteet = tech.get("pisteet", 0)
            sentimentti_pisteet = sentimentti.get("kokonaispisteet", 0)
            uutissentimentti_pisteet = sentimentti.get(
                "uutissentimentti", {}
            ).get("pisteytys", 0) or 0

            # Suuntapisteet (tekninen painotettu eniten)
            suuntapisteet = (
                tekniset_pisteet * 0.6 +
                sentimentti_pisteet * 2 * 0.25 +
                uutissentimentti_pisteet * 2 * 0.15
            )

            # Päätoiminto
            if suuntapisteet >= 1.5:
                toiminto = "OSTA"
                toiminto_vari = "success"
            elif suuntapisteet <= -1.5:
                toiminto = "MYY"
                toiminto_vari = "danger"
            else:
                toiminto = "PIDÄ"
                toiminto_vari = "warning"

            # Luottamusprosentti
            luottamus = self._laske_luottamusprosentti(
                tekniset_pisteet, sentimentti_pisteet, uutissentimentti_pisteet
            )

            # Riskiluokka
            riski = self._maarita_riski(
                tech.get("atr"),
                tech.get("nykyinen_hinta", 0),
                abs(sentimentti_pisteet)
            )

            # Perustelut
            perustelut = []
            for signaali in tech.get("signaalit", []):
                if signaali.get("suunta") == toiminto.lower() or signaali.get("suunta") == "neutraali":
                    perustelut.append(signaali["signaali"])

            fg_arvo = sentimentti.get("fear_greed", {}).get("arvo")
            fg_luokka = sentimentti.get("fear_greed", {}).get("luokka", "")
            if fg_arvo:
                perustelut.append(f"Fear & Greed Index: {fg_arvo} ({fg_luokka})")

            uutisluokka = sentimentti.get("uutissentimentti", {}).get("luokka", "")
            if uutisluokka:
                perustelut.append(f"Uutissentimentti: {uutisluokka}")

            # Stop loss / Take profit ehdotukset (ATR-pohjainen)
            hinta = tech.get("nykyinen_hinta", 0)
            atr = tech.get("atr")
            stop_loss = None
            take_profit = None

            if hinta and atr:
                if toiminto == "OSTA":
                    stop_loss = round(hinta - 2 * atr, 4)
                    take_profit = round(hinta + 3 * atr, 4)
                elif toiminto == "MYY":
                    stop_loss = round(hinta + 2 * atr, 4)
                    take_profit = round(hinta - 3 * atr, 4)

            tulos = {
                "ok": True,
                "symboli": symboli,
                "toiminto": toiminto,
                "toiminto_vari": toiminto_vari,
                "luottamus_prosentti": luottamus,
                "riski": riski,
                "perustelut": perustelut[:6],  # Max 6 perustelua
                "nykyinen_hinta": hinta,
                "stop_loss_ehdotus": stop_loss,
                "take_profit_ehdotus": take_profit,
                "tekninen_data": {
                    "rsi": tech.get("rsi"),
                    "macd_suunta": tech.get("macd", {}).get("suunta"),
                    "ema_trendi": tech.get("ema", {}).get("trendi"),
                    "atr": atr
                },
                "sentimentti": {
                    "fear_greed": fg_arvo,
                    "fear_greed_luokka": fg_luokka,
                    "kokonaisluokka": sentimentti.get("kokonaisluokka")
                },
                "liittyvat_uutiset": symboli_uutiset[:3],
                "generoitu": time.time(),
                # TURVALLISUUS: Muistutetaan, että käyttäjän hyväksyntä vaaditaan
                "vaatii_hyvaksynnan": True,
                "vastuuvapauslauseke": (
                    "Tämä on automaattinen analyysi, ei sijoitusneuvonta. "
                    "Tee aina oma tutkimuksesi ennen sijoituspäätöksiä."
                )
            }

            logger.info(
                f"Suositus {symboli}: {toiminto} "
                f"(luottamus: {luottamus}%, riski: {riski})"
            )
            return tulos

        except Exception as e:
            logger.error(f"Virhe suosituksen generoinnissa ({symboli}): {e}", exc_info=True)
            return {"ok": False, "symboli": symboli, "virhe": str(e)}

    def hae_suositukset(
        self,
        symbolit: Optional[list] = None,
        pakota_paivitys: bool = False
    ) -> list:
        """
        Analysoi kaikki annetut symbolit ja palauttaa suositukset listana.
        Järjestää luottamusprosentin mukaan.
        """
        if not pakota_paivitys and not self._cache_vanhentunut() and self._cache.get("suositukset"):
            return self._cache["suositukset"]

        kaytetyt_symbolit = symbolit or OLETUSSYMBOLIT
        logger.info(f"Generoidaan suositukset {len(kaytetyt_symbolit)} symbolille...")

        suositukset = []
        for symboli in kaytetyt_symbolit[:6]:  # Max 6 symbolia kerrallaan
            suositus = self.analysoi_symboli(symboli)
            if suositus.get("ok"):
                suositukset.append(suositus)

        # Järjestä luottamusprosentin mukaan
        suositukset.sort(key=lambda x: x.get("luottamus_prosentti", 0), reverse=True)

        self._cache["suositukset"] = suositukset
        self._cache_aika = time.time()

        return suositukset

    def hae_paras_suositus(self, symbolit: Optional[list] = None) -> Optional[dict]:
        """Palauttaa korkeimman luottamuksen omaavan suosituksen."""
        suositukset = self.hae_suositukset(symbolit)
        if suositukset:
            return suositukset[0]
        return None


# Globaali instanssi
recommendation_engine = RecommendationEngine()


# ══════════════════════════════════════════════════════════════
# SALKKUTIETOINEN SUOSITUSKERROS
#
# Yllä oleva moottori arvioi symbolia irrallaan. Tämä kerros ottaa
# huomioon myös nykyisen position: sen koon, tuoton ja vaikutuksen
# hajautukseen. Vasta se mahdollistaa neljä suositusluokkaa.
#
# BUY     kohdetta ei omisteta (tai sitä on vähän) ja signaali on hyvä
# HOLD    positio on kunnossa, ei toimenpiteitä
# REDUCE  positio on liian suuri tai momentum heikkenee -> kevennä osa
# SELL    trendi kääntynyt, laskuriski suuri -> ulos kokonaan
#
# TÄRKEÄÄ: nämä ovat informatiivisia. Järjestelmä ei tee toimeksiantoja.
# ══════════════════════════════════════════════════════════════

BUY, HOLD, REDUCE, SELL = "BUY", "HOLD", "REDUCE", "SELL"


class SalkkuSuositusmoottori:
    """Muodostaa BUY/HOLD/REDUCE/SELL-suositukset salkun tilanteen pohjalta."""

    def __init__(self):
        self._cache: dict = {}
        self._cache_aika: float = 0.0
        self._cache_ttl: int = config.RECOMMENDATION_CACHE_TTL

    # ─── Apurit ───────────────────────────────────────────────

    def _tekninen_signaali(self, symboli: str, luokka: str) -> dict:
        """
        Hakee teknisen signaalin. Saatavilla vain kryptalle: osakkeille ja
        ETF:ille ei ole hintahistorialähdettä ennen kuin IBKR-yhteys on
        elossa (ks. ibkr_service.py, integraatiopiste 2).
        """
        from services.portfolio_service import KRYPTO
        if luokka != KRYPTO:
            return {"ok": False, "syy": "ei hintahistoriaa ennen IBKR-yhteyttä"}
        try:
            return technical_analysis_service.analysoi(symboli, "4h")
        except Exception as e:
            return {"ok": False, "syy": str(e)}

    def _ai_pisteet(self, symboli: str, luokka: str) -> Optional[int]:
        from services.portfolio_service import KRYPTO
        if luokka != KRYPTO:
            return None
        try:
            from services.ai_score import ai_score_service
            s = ai_score_service.laske_ai_score(symboli)
            return s.get("kokonaispistemäärä") if s.get("ok") else None
        except Exception:
            return None

    def _luottamus(self, tech: dict, sentimentti: dict, lisavarmuus: int = 0) -> int:
        """
        Luottamusprosentti. Kun teknistä dataa ei ole, luottamus perustuu
        position omiin tunnuslukuihin ja on tarkoituksella maltillisempi.
        """
        if not tech.get("ok"):
            return max(35, min(80, 55 + lisavarmuus))
        return recommendation_engine._laske_luottamusprosentti(
            tech.get("pisteet", 0),
            sentimentti.get("kokonaispisteet", 0),
            sentimentti.get("uutissentimentti", {}).get("pisteytys", 0) or 0,
        )

    # ─── Omistetun position arviointi ─────────────────────────

    def analysoi_positio(self, positio: dict, sentimentti: dict) -> dict:
        """Palauttaa HOLD / REDUCE / SELL -suosituksen yhdelle positiolle."""
        symboli = positio["symboli"]
        luokka = positio["luokka"]
        osuus = positio.get("osuus_prosentti", 0)
        tuotto_pct = positio.get("tuotto_prosentti")

        tech = self._tekninen_signaali(symboli, luokka)
        pisteet = tech.get("pisteet", 0) if tech.get("ok") else 0
        trendi = tech.get("ema", {}).get("trendi") if tech.get("ok") else None
        rsi = tech.get("rsi") if tech.get("ok") else None

        maksimi = config.MAX_POSITION_PROSENTTI
        perustelut = []
        toiminto = HOLD
        myyntiosuus = None

        # 1. Trendin kääntyminen -> SELL
        if tech.get("ok") and pisteet <= -3 and trendi in ("vahva_lasku", "lasku"):
            toiminto = SELL
            perustelut.append("Trendin kääntyminen vahvistui")
            perustelut.append(f"EMA-trendi: {trendi}")
            if rsi:
                perustelut.append(f"RSI {rsi:.0f}")

        # 2. Liian suuri positio -> REDUCE
        elif osuus > maksimi:
            toiminto = REDUCE
            myyntiosuus = int(round((osuus - maksimi) / osuus * 100))
            myyntiosuus = max(10, min(75, myyntiosuus))
            perustelut.append(f"Positio kasvanut liian suureksi ({osuus:.1f} % salkusta)")
            perustelut.append(f"Suositus enintään {maksimi:.0f} % – riskikeskittymä")
            if positio.get("hajautusvaikutus", {}).get("arvio"):
                perustelut.append(positio["hajautusvaikutus"]["arvio"].capitalize())

        # 3. Momentum heikkenee -> REDUCE
        elif tech.get("ok") and pisteet <= -1:
            toiminto = REDUCE
            myyntiosuus = 25
            perustelut.append("Momentum heikkenee")
            if trendi:
                perustelut.append(f"EMA-trendi: {trendi}")
            if rsi and rsi > 70:
                perustelut.append(f"RSI yliostettu ({rsi:.0f})")

        # 4. Muutoin HOLD
        else:
            if tech.get("ok"):
                perustelut.append("Trendi pysyy terveenä")
                if trendi:
                    perustelut.append(f"EMA-trendi: {trendi}")
            else:
                perustelut.append("Positio tasapainossa salkussa")
            if tuotto_pct is not None:
                perustelut.append(f"Tuotto {tuotto_pct:+.1f} %")
            perustelut.append("Ei toimenpiteitä")

        # Luottamus: iso poikkeama maksimipainosta lisää varmuutta
        lisa = int(min(20, max(0, osuus - maksimi))) if osuus > maksimi else 0
        luottamus = self._luottamus(tech, sentimentti, lisa)

        return {
            "ok": True,
            "toiminto": toiminto,
            "symboli": symboli,
            "nimi": positio.get("nimi", symboli),
            "luokka": luokka,
            "myyntiosuus_prosentti": myyntiosuus,
            "luottamus_prosentti": luottamus,
            "riski": self._riskiteksti(positio.get("riskipisteet")),
            "riskipisteet": positio.get("riskipisteet"),
            "ai_pisteet": self._ai_pisteet(symboli, luokka),
            "osuus_prosentti": osuus,
            "arvo": positio.get("arvo"),
            "tuotto_prosentti": tuotto_pct,
            "volatiliteetti_prosentti": positio.get("volatiliteetti_prosentti"),
            "perustelut": perustelut[:4],
            "tekninen_saatavilla": tech.get("ok", False),
            "vaatii_hyvaksynnan": True,
        }

    # ─── Uuden ostokohteen arviointi ──────────────────────────

    def analysoi_ostokohde(self, symboli: str, luokka: str, nimi: str,
                           sentimentti: dict, kaytettavissa: float,
                           korvaava: bool = False) -> Optional[dict]:
        """
        Palauttaa BUY-suosituksen, tai None jos signaali ei riitä tai
        käytettävissä oleva summa alittaa minimin.

        `kaytettavissa` on tälle ostolle varattu enimmäissumma – se tulee
        kuukausibudjetin allokaatiosta, ei käteisestä. Näin suositus ei
        voi koskaan ylittää budjettia.
        """
        tech = self._tekninen_signaali(symboli, luokka)
        if not tech.get("ok"):
            return None

        pisteet = tech.get("pisteet", 0)
        if pisteet < 2:                      # vain selkeät ostosignaalit
            return None

        summa = min(config.MAX_OSTOEHDOTUS, kaytettavissa)
        if summa < config.MIN_OSTOEHDOTUS:
            return None
        summa = round(summa / 5) * 5         # tasoitetaan viiteen
        if summa > kaytettavissa:            # pyöristys ei saa ylittää rajaa
            summa = int(kaytettavissa // 5) * 5
        if summa < config.MIN_OSTOEHDOTUS:
            return None

        perustelut = []
        trendi = tech.get("ema", {}).get("trendi")
        rsi = tech.get("rsi")
        if trendi in ("vahva_nousu", "nousu"):
            perustelut.append("Vahva momentum")
        if rsi and rsi < 40:
            perustelut.append(f"RSI ylimyyty ({rsi:.0f})")
        if sentimentti.get("kokonaisluokka") == "positiivinen":
            perustelut.append("Positiivinen sentimentti")
        fg = sentimentti.get("fear_greed", {}).get("arvo")
        if fg is not None:
            perustelut.append(f"Fear & Greed {fg}")
        atr, hinta = tech.get("atr"), tech.get("nykyinen_hinta")
        atr_pct = (atr / hinta * 100) if atr and hinta else None
        if atr_pct and atr_pct < 5:
            perustelut.append("Riski hyväksyttävä")

        return {
            "ok": True,
            "toiminto": BUY,
            "symboli": symboli,
            "nimi": nimi,
            "luokka": luokka,
            "ehdotettu_summa": summa,
            "valuutta": config.BASE_CURRENCY,
            "luottamus_prosentti": self._luottamus(tech, sentimentti),
            "riski": recommendation_engine._maarita_riski(atr, hinta or 0, 0),
            "ai_pisteet": self._ai_pisteet(symboli, luokka),
            "nykyinen_hinta": hinta,
            "stop_loss_ehdotus": round(hinta - 2 * atr, 4) if hinta and atr else None,
            "take_profit_ehdotus": round(hinta + 3 * atr, 4) if hinta and atr else None,
            "volatiliteetti_prosentti": round(atr_pct, 2) if atr_pct else None,
            "perustelut": perustelut[:4] or ["Tekninen signaali positiivinen"],
            "tekninen_saatavilla": True,
            "korvaava": korvaava,
            "vaatii_hyvaksynnan": True,
        }

    @staticmethod
    def _riskiteksti(pisteet: Optional[int]) -> str:
        if pisteet is None:
            return "Ei arviota"
        if pisteet >= 70:
            return "Korkea riski"
        if pisteet >= 45:
            return "Keskitasoinen riski"
        return "Matala riski"

    # ─── Koko salkun suositukset ──────────────────────────────

    def hae_salkkusuositukset(self, pakota_paivitys: bool = False) -> dict:
        """
        Muodostaa suositukset koko salkulle:
          - jokaiselle omistukselle HOLD / REDUCE / SELL
          - ostokohteille BUY (watchlistista, joita ei vielä omisteta)
        """
        import time
        if not pakota_paivitys and self._cache and \
                (time.time() - self._cache_aika) < self._cache_ttl:
            return self._cache

        try:
            from services.portfolio_service import yhdistetty_portfolio_service, KRYPTO

            salkku = yhdistetty_portfolio_service.hae_salkku(pakota_paivitys=pakota_paivitys)
            if not salkku.get("ok"):
                return {"ok": False, "virhe": salkku.get("virhe", "Salkkua ei saatu")}

            sentimentti = sentiment_service.hae_kokonaissentimentti()

            # Omistukset
            omistukset = []
            for p in salkku.get("positiot", []):
                try:
                    omistukset.append(self.analysoi_positio(p, sentimentti))
                except Exception as e:
                    logger.error(f"Position analyysi epäonnistui ({p.get('symboli')}): {e}")

            # ─── Kuukausibudjetti ja allokaatio ───────────────
            from services.budget_service import budget_service
            btc_tech = technical_analysis_service.analysoi("BTCUSDT", "4h")
            kateinen_lahteittain = salkku.get("kateinen_lahteittain", {})
            budjettitilanne = budget_service.hae_budjettitilanne(
                sentimentti, btc_tech, kateinen_lahteittain
            )
            allokaatio = budjettitilanne["allokaatio"]

            # Luokkakohtaiset budjetit, joita kulutetaan ostoja tehtäessä.
            luokkabudjetit = dict(allokaatio.get("osuudet", {}))

            # SELL vapauttaa pääomaa: korvaavat ostot rahoitetaan sillä,
            # eikä niitä lasketa kuukausibudjettiin.
            myynnit = [s for s in omistukset if s["toiminto"] == SELL]
            korvaava_paaoma = sum(s.get("arvo") or 0.0 for s in myynnit)

            # Ostokohteet watchlistista, joita ei jo omisteta
            omistetut = {p["symboli"] for p in salkku.get("positiot", [])}
            ostot = []
            ohitetut = []
            try:
                from services.watchlist import watchlist_service
                for kohde in watchlist_service.hae_watchlist()[:8]:
                    symboli = kohde["symboli"]
                    if symboli in omistetut:
                        continue

                    # Kryptaa voi ostaa vain Binance-käteisellä.
                    binance_kassa = kateinen_lahteittain.get("binance", 0.0)
                    saatavilla = min(luokkabudjetit.get(KRYPTO, 0.0), binance_kassa)
                    korvaava = False

                    # Budjetti lopussa -> sallitaan vain korvaava osto,
                    # joka rahoitetaan myynnistä vapautuvalla pääomalla.
                    if saatavilla < config.MIN_OSTOEHDOTUS:
                        if korvaava_paaoma >= config.MIN_OSTOEHDOTUS:
                            saatavilla, korvaava = korvaava_paaoma, True
                        else:
                            ohitetut.append(symboli)
                            continue

                    ehdotus = self.analysoi_ostokohde(
                        symboli, KRYPTO, kohde.get("nimi", symboli),
                        sentimentti, saatavilla, korvaava=korvaava,
                    )
                    if not ehdotus:
                        continue

                    summa = ehdotus["ehdotettu_summa"]
                    if korvaava:
                        korvaava_paaoma -= summa
                    else:
                        luokkabudjetit[KRYPTO] = luokkabudjetit.get(KRYPTO, 0.0) - summa
                    ostot.append(ehdotus)
            except Exception as e:
                logger.error(f"Ostokohteiden haku epäonnistui: {e}")

            ostot.sort(key=lambda x: x["luottamus_prosentti"], reverse=True)

            # ─── Käteistilanne ostojen jälkeen ────────────────
            ostot_yhteensa = sum(o["ehdotettu_summa"] for o in ostot if not o.get("korvaava"))
            budjetti = budjettitilanne["budjetti"]
            kassa = salkku.get("kateinen", 0.0)

            kassatilanne = {
                "kuukausibudjetti": budjetti["kuukausibudjetti"],
                "sijoitettu_taman_kuun": budjetti["sijoitettu"],
                "jaljella_budjetista": budjetti["jaljella"],
                "kateinen_nyt": round(kassa, 2),
                "kateinen_lahteittain": kateinen_lahteittain,
                "ehdotetut_ostot": round(ostot_yhteensa, 2),
                "varaus": round(max(0.0, budjetti["jaljella"] - ostot_yhteensa), 2),
                "kateinen_ostojen_jalkeen": round(kassa - ostot_yhteensa, 2),
                "valuutta": config.BASE_CURRENCY,
            }

            # Budjetti ei saa koskaan ylittyä.
            if ostot_yhteensa > budjetti["jaljella"] + 0.01:
                logger.error(
                    f"Budjetti ylittyi ({ostot_yhteensa} > {budjetti['jaljella']}) – "
                    "ostoehdotukset hylätään turvasyistä"
                )
                ostot, ostot_yhteensa = [], 0.0
                kassatilanne["ehdotetut_ostot"] = 0.0
                kassatilanne["varaus"] = budjetti["jaljella"]

            # Portfolio Score kaikista osatekijöistä
            from services.portfolio_score import laske_portfolio_score
            portfolio_score = laske_portfolio_score(
                salkku=salkku,
                budjetti=budjettitilanne["budjetti"],
                markkinatila=budjettitilanne["markkinatila"],
                tavoiteallokaatio=budjettitilanne["tavoiteallokaatio"],
            )

            kaikki = ostot + omistukset
            tulos = {
                "ok": True,
                "salkku": salkku,
                "sentimentti": sentimentti,
                "budjetti": budjetti,
                "markkinatila": budjettitilanne["markkinatila"],
                "allokaatio": allokaatio,
                "kassatilanne": kassatilanne,
                "markkinakatsaus": budjettitilanne.get("markkinakatsaus"),
                "portfolio_score": portfolio_score,
                "suositukset": kaikki,
                "ostot": ostot,
                "omistukset": omistukset,
                "ohitetut_budjetin_vuoksi": ohitetut,
                "yhteenveto": {
                    t: sum(1 for s in kaikki if s["toiminto"] == t)
                    for t in (BUY, HOLD, REDUCE, SELL)
                },
                "generoitu": time.time(),
                "vastuuvapauslauseke": (
                    "Automaattinen analyysi, ei sijoitusneuvontaa. "
                    "Järjestelmä ei tee toimeksiantoja – päätökset tekee käyttäjä."
                ),
            }

            self._cache = tulos
            self._cache_aika = time.time()
            logger.info(f"Salkkusuositukset: {tulos['yhteenveto']}")
            return tulos

        except Exception as e:
            logger.error(f"Salkkusuositusten muodostus epäonnistui: {e}", exc_info=True)
            return {"ok": False, "virhe": str(e)}


# Globaali instanssi
salkku_suositusmoottori = SalkkuSuositusmoottori()
