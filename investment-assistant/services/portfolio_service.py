"""
Yhdistetty salkkupalvelu: krypto (Binance) + osakkeet/ETF:t/rahastot (IBKR).

Kokoaa molempien lähteiden omistukset yhdeksi salkuksi ja laskee jokaiselle
positiolle:
  - nykyarvo perusvaluutassa
  - tuotto / tappio (kun hankintahinta on tiedossa)
  - osuus salkusta
  - volatiliteetti
  - riskipisteet
  - hajautusvaikutus

Tämä moduuli EI korvaa services/portfolio.py:tä. Se käyttää sitä
kryptaosuuteen, jolloin dashboard ja päiväraportti toimivat entiseen
tapaan. Uusi kerros on lisäys, ei uudelleenkirjoitus.
"""

from datetime import datetime
from typing import Optional

from config import config
from utils.logger import logger

from services.portfolio import portfolio_service as binance_portfolio
from services.ibkr_service import ibkr_service, OSAKE, ETF, RAHASTO
from services.market_data import market_data_service

KRYPTO = "krypto"
KATEINEN = "kateinen"

# Omaisuusluokkien perusriski 0–100 (suurempi = riskisempi).
# Käytetään, kun kohteelle ei saada laskettua volatiliteettia.
LUOKAN_PERUSRISKI = {
    KRYPTO: 75,
    OSAKE: 50,
    ETF: 30,
    RAHASTO: 30,
    KATEINEN: 0,
}


class YhdistettyPortfolioService:
    """Kokoaa salkun kaikista lähteistä ja laskee positiokohtaiset mittarit."""

    def __init__(self):
        self._cache: dict = {}
        self._cache_aika: float = 0.0
        self._cache_ttl: int = config.PORTFOLIO_CACHE_TTL

    # ─── Valuutta ─────────────────────────────────────────────

    def _eur_usd_kurssi(self) -> Optional[float]:
        """
        EUR/USD Binancen EURUSDT-parista. Näin ei tarvita erillistä
        valuutta-API:a. Palauttaa None, jos kurssia ei saada.
        """
        try:
            hinnat = market_data_service.hae_hinnat()
            kurssi = hinnat.get("EURUSDT")
            return float(kurssi) if kurssi else None
        except Exception as e:
            logger.debug(f"EUR/USD-kurssia ei saatu: {e}")
            return None

    def _muunna(self, maara: float, valuutta: str, kurssi: Optional[float]) -> Optional[float]:
        """Muuntaa summan perusvaluuttaan. None jos kurssi puuttuu."""
        valuutta = (valuutta or "USD").upper()
        kohde = config.BASE_CURRENCY

        if valuutta == kohde:
            return maara
        if kurssi is None:
            return None
        if valuutta == "USD" and kohde == "EUR":
            return maara / kurssi
        if valuutta == "EUR" and kohde == "USD":
            return maara * kurssi
        # Muita valuuttoja ei tueta ilman erillistä kurssilähdettä.
        return None

    # ─── Positiokohtaiset mittarit ────────────────────────────

    def _volatiliteetti(self, symboli: str, luokka: str) -> Optional[float]:
        """
        Volatiliteetti ATR%:na. Saatavilla vain kryptalle, jolle on
        kynttilädataa. Muille palautetaan None – arvoa ei keksitä.
        """
        if luokka != KRYPTO:
            return None
        try:
            from services.technical_analysis import technical_analysis_service
            tech = technical_analysis_service.analysoi(symboli, "4h")
            if not tech.get("ok"):
                return None
            atr, hinta = tech.get("atr"), tech.get("nykyinen_hinta")
            if atr and hinta:
                return round(atr / hinta * 100, 2)
        except Exception as e:
            logger.debug(f"Volatiliteettia ei saatu ({symboli}): {e}")
        return None

    def _riskipisteet(self, luokka: str, osuus: float,
                      volatiliteetti: Optional[float]) -> int:
        """
        Position riskipisteet 0–100 (suurempi = riskisempi).

        Kolme tekijää:
          - omaisuusluokan perusriski
          - toteutunut volatiliteetti, jos tiedossa
          - keskittymä: iso osuus salkusta nostaa riskiä
        """
        perus = LUOKAN_PERUSRISKI.get(luokka, 50)

        if volatiliteetti is not None:
            # ATR% 0–10 % -> 0–100
            vol_pisteet = min(100, volatiliteetti * 10)
            perus = perus * 0.5 + vol_pisteet * 0.5

        # Keskittymälisä: yli sallitun maksimin kasvattaa riskiä.
        maksimi = config.MAX_POSITION_PROSENTTI
        if osuus > maksimi:
            perus += min(25, (osuus - maksimi))

        return int(max(0, min(100, round(perus))))

    def _hajautusvaikutus(self, osuus: float, positioita: int) -> dict:
        """
        Kuinka paljon positio heikentää hajautusta.

        Vertailukohtana tasapaino: jos positioita on N, tasapaino olisi
        100/N %. Suhdeluku > 1 tarkoittaa yliedustusta.
        """
        if positioita <= 0:
            return {"suhde": None, "arvio": "ei dataa"}

        tasapaino = 100.0 / positioita
        suhde = osuus / tasapaino if tasapaino > 0 else 0

        if suhde >= 3:
            arvio = "hallitseva – heikentää hajautusta merkittävästi"
        elif suhde >= 1.8:
            arvio = "yliedustettu"
        elif suhde >= 0.6:
            arvio = "tasapainoinen"
        else:
            arvio = "pieni positio"

        return {
            "suhde": round(suhde, 2),
            "tasapainopaino_prosentti": round(tasapaino, 1),
            "arvio": arvio,
        }

    # ─── Lähteet ──────────────────────────────────────────────

    def _krypto_positiot(self, kurssi, pakota) -> tuple:
        """Palauttaa (positiot, kateinen, virhe)."""
        salkku = binance_portfolio.hae_salkku(pakota_paivitys=pakota)
        if not salkku.get("ok"):
            return [], 0.0, salkku.get("virhe")

        positiot, kateinen = [], 0.0
        for o in salkku.get("omistukset", []):
            arvo = self._muunna(o.get("arvo_usdt", 0), "USD", kurssi)
            if o.get("on_stablecoin"):
                kateinen += arvo or 0.0
                continue
            positiot.append({
                "symboli": f"{o['valuutta']}USDT",
                "nimi": o["valuutta"],
                "luokka": KRYPTO,
                "maara": o.get("maara"),
                "markkinahinta": o.get("hinta_usdt"),
                "valuutta": "USD",
                "arvo": arvo,
                "muutos_24h": o.get("muutos_24h"),
                # Binance ei anna hankintahintaa ilman kauppahistorian
                # rekonstruointia, joten tuottoa ei voi laskea.
                "hankintahinta": None,
                "lahde": "Binance",
            })
        return positiot, kateinen, None

    def _ibkr_positiot(self, kurssi) -> tuple:
        positiot, kateinen = [], 0.0
        for p in ibkr_service.hae_positiot():
            arvo = self._muunna(p["markkinahinta"] * p["maara"], p["valuutta"], kurssi)
            positiot.append({
                "symboli": p["symboli"],
                "nimi": p["nimi"],
                "luokka": p["tyyppi"],
                "maara": p["maara"],
                "markkinahinta": p["markkinahinta"],
                "valuutta": p["valuutta"],
                "arvo": arvo,
                "muutos_24h": None,
                "hankintahinta": p.get("hankintahinta"),
                "sektori": p.get("sektori"),
                "lahde": "IBKR",
            })
        for val, maara in ibkr_service.hae_kassa().items():
            m = self._muunna(maara, val, kurssi)
            if m:
                kateinen += m
        return positiot, kateinen

    # ─── Pääfunktio ───────────────────────────────────────────

    def hae_salkku(self, pakota_paivitys: bool = False) -> dict:
        """Kokoaa koko salkun ja laskee positiokohtaiset mittarit."""
        import time
        if not pakota_paivitys and self._cache and \
                (time.time() - self._cache_aika) < self._cache_ttl:
            return self._cache

        try:
            kurssi = self._eur_usd_kurssi()
            positiot, krypto_kateinen, krypto_virhe = self._krypto_positiot(kurssi, pakota_paivitys)
            ibkr_pos, ibkr_kateinen = self._ibkr_positiot(kurssi)
            positiot += ibkr_pos

            # Brokerien käteinen pidetään erillään: Binance-käteisellä voi
            # ostaa vain kryptoa ja IBKR-käteisellä vain osakkeita/ETF:iä.
            # Yhteissummaa käytetään vain raportoinnissa.
            kateinen_lahteittain = {
                "binance": round(krypto_kateinen, 2),
                "ibkr": round(ibkr_kateinen, 2),
            }
            kateinen = krypto_kateinen + ibkr_kateinen
            sijoitettu = sum(p["arvo"] for p in positiot if p["arvo"] is not None)
            kokonaisarvo = sijoitettu + kateinen

            # Osuudet, tuotto ja mittarit
            for p in positiot:
                arvo = p["arvo"] or 0.0
                p["osuus_prosentti"] = round(arvo / kokonaisarvo * 100, 2) if kokonaisarvo > 0 else 0.0

                # Tuotto vain jos hankintahinta tiedossa
                hh, mh, maara = p.get("hankintahinta"), p.get("markkinahinta"), p.get("maara")
                if hh and mh and maara:
                    tuotto_val = (mh - hh) * maara
                    p["tuotto"] = self._muunna(tuotto_val, p["valuutta"], kurssi)
                    p["tuotto_prosentti"] = round((mh - hh) / hh * 100, 2)
                else:
                    p["tuotto"] = None
                    p["tuotto_prosentti"] = None
                    p["tuotto_syy"] = "hankintahinta ei saatavilla"

                p["volatiliteetti_prosentti"] = self._volatiliteetti(p["symboli"], p["luokka"])
                p["riskipisteet"] = self._riskipisteet(
                    p["luokka"], p["osuus_prosentti"], p["volatiliteetti_prosentti"]
                )
                p["hajautusvaikutus"] = self._hajautusvaikutus(
                    p["osuus_prosentti"], len(positiot)
                )

            positiot.sort(key=lambda x: x["arvo"] or 0, reverse=True)

            # Luokkajakauma
            jakauma = {}
            for p in positiot:
                j = jakauma.setdefault(p["luokka"], {"arvo": 0.0, "kpl": 0})
                j["arvo"] += p["arvo"] or 0.0
                j["kpl"] += 1
            if kateinen > 0:
                jakauma[KATEINEN] = {"arvo": kateinen, "kpl": 1}
            for j in jakauma.values():
                j["osuus_prosentti"] = round(j["arvo"] / kokonaisarvo * 100, 1) if kokonaisarvo > 0 else 0.0

            tulos = {
                "ok": True,
                "valuutta": config.BASE_CURRENCY,
                "kokonaisarvo": round(kokonaisarvo, 2),
                "sijoitettu": round(sijoitettu, 2),
                "kateinen": round(kateinen, 2),
                "kateinen_lahteittain": kateinen_lahteittain,
                "positioita": len(positiot),
                "positiot": positiot,
                "luokkajakauma": jakauma,
                "lahteet": {
                    "binance": {"ok": krypto_virhe is None, "virhe": krypto_virhe},
                    "ibkr": ibkr_service.hae_tila(),
                },
                "eur_usd": kurssi,
                "paivitysaika": datetime.now().isoformat(),
            }

            self._cache = tulos
            self._cache_aika = time.time()
            logger.info(
                f"Yhdistetty salkku: {len(positiot)} positiota, "
                f"{kokonaisarvo:.2f} {config.BASE_CURRENCY}"
            )
            return tulos

        except Exception as e:
            logger.error(f"Yhdistetyn salkun haku epäonnistui: {e}", exc_info=True)
            return {"ok": False, "virhe": str(e), "positiot": [],
                    "kokonaisarvo": 0.0, "kateinen": 0.0,
                    "kateinen_lahteittain": {"binance": 0.0, "ibkr": 0.0}}


# Globaali instanssi
yhdistetty_portfolio_service = YhdistettyPortfolioService()
