"""
Salkun automaattinen synkronointi.

Vertaa nykyistä salkkua edelliseen tilannekuvaan ja päättelee, mitä on
ostettu tai myyty. Havaitut ostot kirjataan kuukausibudjettiin
automaattisesti – käyttäjän ei tarvitse kirjata mitään käsin.

ARVOTTAMINEN
------------
Muutoksen euromääräinen arvo haetaan ensisijaisesti brokerin
kauppahistoriasta (toteutunut kauppahinta). Jos sitä ei saada,
käytetään määrän muutosta kerrottuna nykyisellä markkinahinnalla.
Kumpi lähdettä käytettiin, tallennetaan tapahtumaan (hinta_lahde),
jotta arvion tarkkuus on jäljitettävissä.

TURVALLISUUS
------------
Vain luku. Tämä moduuli ei tee toimeksiantoja eikä sillä ole
mahdollisuutta niihin – se ainoastaan lukee salkun tilan ja
kauppahistorian.
"""

import time
from datetime import datetime
from typing import Optional

from config import config
from utils.logger import logger
from services import database as db

# Tapahtumatyypit
UUSI = "OSTO"
LISAYS = "LISAYS"
OSITTAINEN_MYYNTI = "OSITTAINEN_MYYNTI"
MYYNTI = "MYYNTI"

# Määrän suhteellinen muutos, jota pienempiä ei pidetä kauppana.
# Suojaa pyöristyksiltä, korkotuotoilta ja pölysaldoilta.
KYNNYS = 0.005      # 0,5 %


class SyncService:
    """Havaitsee salkkumuutokset tilannekuvia vertaamalla."""

    def __init__(self):
        self.viimeisin_tulos: dict = {}

    # ─── Arvottaminen ─────────────────────────────────────────

    def _kauppahistoriasta(self, symboli: str, alkaen_ms: int) -> Optional[dict]:
        """
        Yrittää hakea toteutuneet kaupat Binancesta annetun hetken jälkeen.
        Palauttaa {'arvo_usdt': x, 'maara': y} tai None.
        """
        try:
            from services.binance import binance_service
            if not binance_service.client or not binance_service.yhteys_ok:
                return None

            kaupat = binance_service.client.get_my_trades(
                symbol=symboli, startTime=alkaen_ms, limit=100
            )
            if not kaupat:
                return None

            arvo = sum(float(k["quoteQty"]) for k in kaupat if k.get("isBuyer"))
            maara = sum(float(k["qty"]) for k in kaupat if k.get("isBuyer"))
            if maara <= 0:
                return None
            return {"arvo_usdt": arvo, "maara": maara}

        except Exception as e:
            # Yleisin syy: symbolia ei ole tai oikeudet eivät riitä.
            logger.debug(f"Kauppahistoriaa ei saatu ({symboli}): {e}")
            return None

    def _arvota_muutos(self, lahde: str, symboli: str, maara_muutos: float,
                       hinta: Optional[float], edellinen_aika: Optional[float],
                       kurssi: Optional[float]) -> tuple:
        """
        Palauttaa (arvo_perusvaluutassa, hinta_lahde).
        Ensisijaisesti toteutunut kauppahinta, muuten markkinahinta.
        """
        from services.portfolio_service import yhdistetty_portfolio_service as ups

        # 1. Toteutunut kauppa (vain Binance; IBKR:llä ei mockissa historiaa)
        if lahde == "Binance" and edellinen_aika:
            tiedot = self._kauppahistoriasta(symboli, int(edellinen_aika * 1000))
            if tiedot:
                arvo = ups._muunna(tiedot["arvo_usdt"], "USD", kurssi)
                if arvo is not None:
                    return round(arvo, 2), "kauppahistoria"

        # 2. Markkinahinta × määrän muutos
        if hinta:
            valuutta = "USD" if lahde == "Binance" else "EUR"
            arvo = ups._muunna(abs(maara_muutos) * hinta, valuutta, kurssi)
            if arvo is not None:
                return round(arvo, 2), "markkinahinta"

        return None, "ei saatavilla"

    # ─── Synkronointi ─────────────────────────────────────────

    def synkronoi(self, pakota_paivitys: bool = True) -> dict:
        """
        Lukee salkun, vertaa edelliseen tilannekuvaan ja kirjaa muutokset.
        Palauttaa yhteenvedon havaituista tapahtumista.
        """
        try:
            from services.portfolio_service import yhdistetty_portfolio_service as ups
            from services.budget_service import budget_service

            salkku = ups.hae_salkku(pakota_paivitys=pakota_paivitys)
            if not salkku.get("ok"):
                return {"ok": False, "virhe": salkku.get("virhe", "Salkkua ei saatu")}

            positiot = salkku.get("positiot", [])
            kurssi = salkku.get("eur_usd")
            nykyinen = {
                (p.get("lahde", "?"), p["symboli"]): p for p in positiot
            }
            edellinen = db.hae_viimeisin_holdings_snapshot()

            # Ensimmäinen ajo: tallennetaan vertailukohta, ei päätellä kauppoja.
            if not edellinen:
                db.tallenna_holdings_snapshot(positiot)
                logger.info("Synkronointi: perustilannekuva tallennettu (ei vertailua)")
                return {
                    "ok": True, "perustilannekuva": True, "tapahtumia": 0,
                    "tapahtumat": [], "budjettiin_kirjattu": 0.0,
                    "viesti": "Ensimmäinen ajo – vertailukohta luotu",
                }

            tapahtumat = []
            budjettiin = 0.0

            # Kaikki avaimet molemmista
            avaimet = set(nykyinen) | set(edellinen)
            for avain in avaimet:
                lahde, symboli = avain
                uusi = nykyinen.get(avain)
                vanha = edellinen.get(avain)

                uusi_maara = float(uusi.get("maara") or 0) if uusi else 0.0
                vanha_maara = float(vanha.get("maara") or 0) if vanha else 0.0
                muutos = uusi_maara - vanha_maara

                # Suhteellinen kynnys suodattaa pölyn ja pyöristykset
                vertailu = max(abs(vanha_maara), abs(uusi_maara))
                if vertailu == 0 or abs(muutos) / vertailu < KYNNYS:
                    continue

                if vanha_maara == 0:
                    tyyppi = UUSI
                elif uusi_maara == 0:
                    tyyppi = MYYNTI
                elif muutos > 0:
                    tyyppi = LISAYS
                else:
                    tyyppi = OSITTAINEN_MYYNTI

                hinta = (uusi or vanha or {}).get("markkinahinta") or \
                        (vanha or {}).get("hinta")
                arvo, hinta_lahde = self._arvota_muutos(
                    lahde, symboli, muutos, hinta,
                    (vanha or {}).get("aikaleima"), kurssi
                )
                luokka = (uusi or vanha or {}).get("luokka", "")

                # Ostot kuluttavat kuukausibudjettia; myynnit eivät kasvata sitä.
                kirjattu = False
                if tyyppi in (UUSI, LISAYS) and arvo and arvo > 0:
                    tulos = budget_service.kirjaa_sijoitus(
                        symboli=symboli, summa=arvo,
                        nimi=(uusi or {}).get("nimi", symboli),
                        luokka=luokka,
                        muistiinpano=f"automaattinen synkronointi ({hinta_lahde})",
                    )
                    kirjattu = bool(tulos.get("ok"))
                    if kirjattu:
                        budjettiin += arvo

                db.tallenna_sync_tapahtuma(
                    lahde=lahde, symboli=symboli, tapahtuma=tyyppi,
                    maara_muutos=round(muutos, 10), arvo=arvo,
                    valuutta=config.BASE_CURRENCY, hinta_lahde=hinta_lahde,
                    luokka=luokka, kirjattu=kirjattu,
                )
                tapahtumat.append({
                    "lahde": lahde, "symboli": symboli, "tapahtuma": tyyppi,
                    "maara_muutos": round(muutos, 10), "arvo": arvo,
                    "hinta_lahde": hinta_lahde, "kirjattu_budjettiin": kirjattu,
                })

            # Uusi tilannekuva vertailupohjaksi
            db.tallenna_holdings_snapshot(positiot)

            tulos = {
                "ok": True,
                "perustilannekuva": False,
                "tapahtumia": len(tapahtumat),
                "tapahtumat": tapahtumat,
                "budjettiin_kirjattu": round(budjettiin, 2),
                "valuutta": config.BASE_CURRENCY,
                "synkronoitu": datetime.now().isoformat(),
            }
            self.viimeisin_tulos = tulos

            if tapahtumat:
                logger.info(
                    f"Synkronointi: {len(tapahtumat)} muutosta, "
                    f"{budjettiin:.2f} {config.BASE_CURRENCY} budjettiin"
                )
            else:
                logger.debug("Synkronointi: ei muutoksia")
            return tulos

        except Exception as e:
            logger.error(f"Synkronointi epäonnistui: {e}", exc_info=True)
            return {"ok": False, "virhe": str(e)}


# Globaali instanssi
sync_service = SyncService()
