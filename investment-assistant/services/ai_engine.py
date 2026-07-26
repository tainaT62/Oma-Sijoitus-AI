"""
AI-analyysimoottorit – OpenAI GPT -pohjainen markkina-analyysi.
Yhdistää teknisen analyysin, sentimentin ja uutiset yhdeksi analyysiksi.

Vaatii: OPENAI_API_KEY ympäristömuuttujana
"""

import time
import json
from typing import Optional
from utils.logger import logger
from config import config

# OpenAI-kirjasto
try:
    from openai import OpenAI
    OPENAI_SAATAVILLA = True
except ImportError:
    OPENAI_SAATAVILLA = False
    logger.warning("openai-kirjasto ei asennettu")


class AIEngine:
    """
    OpenAI GPT -pohjainen analyysimootori.
    Muodostaa luonnollisen kielen analyysin markkinadatasta.
    """

    def __init__(self):
        self.client: Optional[object] = None
        self.kaytossa = False
        self._cache: dict = {}
        self._cache_aika: float = 0.0
        self._cache_ttl: int = 30 * 60  # 30 minuuttia

        self._alusta()

    def _alusta(self):
        """Alustaa OpenAI-yhteyden."""
        if not OPENAI_SAATAVILLA:
            logger.warning("OpenAI-kirjasto ei saatavilla")
            return

        if not config.OPENAI_API_KEY:
            logger.info("OPENAI_API_KEY puuttuu – AI-analyysi ei käytössä")
            return

        try:
            self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            self.kaytossa = True
            logger.info("OpenAI AI-moottori alustettu onnistuneesti")
        except Exception as e:
            logger.error(f"OpenAI-alustus epäonnistui: {e}")

    def _cache_vanhentunut(self, avain: str) -> bool:
        """Tarkistaa, onko välimuisti vanhentunut."""
        if avain not in self._cache:
            return True
        return (time.time() - self._cache_aika) > self._cache_ttl

    def _rakenna_konteksti(
        self,
        tekninen_data: dict,
        sentimentti_data: dict,
        uutisotsikot: list,
        salkku_data: Optional[dict] = None
    ) -> str:
        """Rakentaa kontekstin AI-analyysille."""
        osat = []

        # Tekninen analyysi
        if tekninen_data.get("ok"):
            symboli = tekninen_data.get("symboli", "BTC")
            hinta = tekninen_data.get("nykyinen_hinta", 0)
            rsi = tekninen_data.get("rsi")
            macd = tekninen_data.get("macd", {})
            ema = tekninen_data.get("ema", {})
            bb = tekninen_data.get("bollinger_bands", {})
            suositus = tekninen_data.get("tekninen_suositus", "PIDÄ")

            osat.append(f"""TEKNINEN ANALYYSI ({symboli}):
- Nykyinen hinta: ${hinta:,.2f}
- RSI: {rsi if rsi else 'ei saatavilla'}
- MACD suunta: {macd.get('suunta', 'ei saatavilla')}
- EMA-trendi: {ema.get('trendi', 'ei saatavilla')}
- Bollinger sijainti: {bb.get('sijainti_prosentti', 'ei saatavilla')}%
- Tekninen suositus: {suositus}""")

        # Sentimentti
        if sentimentti_data.get("ok"):
            fg = sentimentti_data.get("fear_greed", {})
            uutissentimentti = sentimentti_data.get("uutissentimentti", {})

            osat.append(f"""MARKKINASENTIMENTTI:
- Fear & Greed Index: {fg.get('arvo', 'ei saatavilla')} / 100 ({fg.get('luokka', '')})
- Uutissentimentti: {uutissentimentti.get('luokka', 'ei saatavilla')}
- Kokonaissentimentti: {sentimentti_data.get('kokonaisluokka', 'ei saatavilla')}""")

        # Uutiset
        if uutisotsikot:
            otsikot_teksti = "\n".join(f"- {o}" for o in uutisotsikot[:8])
            osat.append(f"""VIIMEISIMMÄT UUTIOTSIKOT:
{otsikot_teksti}""")

        # Salkku
        if salkku_data and salkku_data.get("ok"):
            kokonaisarvo = salkku_data.get("kokonaisarvo_usdt", 0)
            omistukset = salkku_data.get("omistukset", [])[:5]
            omistusteksti = "\n".join(
                f"- {o['valuutta']}: ${o['arvo_usdt']:,.2f} ({o.get('osuus_prosentti', 0):.1f}%)"
                for o in omistukset
            )
            osat.append(f"""SALKKU:
- Kokonaisarvo: ${kokonaisarvo:,.2f} USDT
- Suurimmat omistukset:
{omistusteksti}""")

        return "\n\n".join(osat)

    def analysoi_markkinat(
        self,
        tekninen_data: dict,
        sentimentti_data: dict,
        uutisotsikot: list,
        salkku_data: Optional[dict] = None
    ) -> dict:
        """
        Generoi AI-analyysin markkinatilanteesta.
        Palauttaa suomenkielisen analyysin ja suositukset.
        """
        cache_avain = "markkina-analyysi"

        # Käytä välimuistia
        if not self._cache_vanhentunut(cache_avain):
            logger.debug("Palautetaan AI-analyysi välimuistista")
            return self._cache[cache_avain]

        # Tarkista, onko OpenAI käytössä
        if not self.kaytossa or not self.client:
            return self._fallback_analyysi(tekninen_data, sentimentti_data)

        try:
            logger.info("Generoidaan AI-markkina-analyysi OpenAI:lla...")

            konteksti = self._rakenna_konteksti(
                tekninen_data, sentimentti_data, uutisotsikot, salkku_data
            )

            vastaus = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Olet kokenut kryptovaluuttamarkkinoiden analyytikko. "
                            "Analysoit markkinatilannetta teknisen analyysin, sentimentin ja uutisten pohjalta. "
                            "Kirjoitat suomeksi. Olet tarkka, analyyttinen ja rehellinen epävarmuuksista. "
                            "Et anna suoria kaupankäyntisuosituksia – autat käyttäjää ymmärtämään markkinatilannetta. "
                            "Vastaukset ovat ytimekkäitä (max 3 kappaletta)."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"""Analysoi alla oleva markkinatilanne ja kirjoita lyhyt (2-3 kappaletta) analyysi suomeksi.
Mainitse tärkeimmät tekijät ja mahdolliset riskit.

{konteksti}

Kirjoita selkeä, ammattimainen analyysi."""
                    }
                ],
                max_tokens=600,
                temperature=0.7
            )

            analyysi_teksti = vastaus.choices[0].message.content.strip()

            tulos = {
                "ok": True,
                "analyysi": analyysi_teksti,
                "malli": config.OPENAI_MODEL,
                "tokeneita_kaytetty": vastaus.usage.total_tokens if vastaus.usage else None,
                "generoitu": time.time(),
                "ai_kaytossa": True
            }

            self._cache[cache_avain] = tulos
            self._cache_aika = time.time()

            logger.info("AI-analyysi generoitu onnistuneesti")
            return tulos

        except Exception as e:
            logger.error(f"Virhe AI-analyysissä: {e}", exc_info=True)
            return self._fallback_analyysi(tekninen_data, sentimentti_data)

    def generoi_paivan_yhteenveto(
        self,
        kaikki_data: dict
    ) -> dict:
        """
        Generoi päivän yhteenvedon kaikesta datasta.
        """
        if not self.kaytossa or not self.client:
            return {
                "ok": False,
                "yhteenveto": "AI-analyysi ei käytössä (OPENAI_API_KEY puuttuu)",
                "ai_kaytossa": False
            }

        try:
            yhteenveto_prompt = f"""Sinulla on seuraavat markkinatiedot tältä päivältä:

Fear & Greed Index: {kaikki_data.get('fear_greed_arvo', 'ei saatavilla')}
Markkinasentimentti: {kaikki_data.get('sentimentti', 'ei saatavilla')}
BTC tekninen suositus: {kaikki_data.get('btc_suositus', 'ei saatavilla')}
Uutistunnelma: {kaikki_data.get('uutistunnelma', 'ei saatavilla')}

Kirjoita ytimekäs (2-3 lausetta) päivittäinen markkinakatsaus suomeksi.
Ole rehellinen epävarmuuksista. Älä lupaa tuottoja."""

            vastaus = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Olet kryptovaluuttamarkkinoiden analyytikko. Kirjoitat suomeksi."},
                    {"role": "user", "content": yhteenveto_prompt}
                ],
                max_tokens=300,
                temperature=0.6
            )

            return {
                "ok": True,
                "yhteenveto": vastaus.choices[0].message.content.strip(),
                "ai_kaytossa": True
            }

        except Exception as e:
            logger.error(f"Virhe päivän yhteenvedon generoinnissa: {e}")
            return {"ok": False, "yhteenveto": "AI-yhteenveto epäonnistui", "ai_kaytossa": True}

    def _fallback_analyysi(self, tekninen_data: dict, sentimentti_data: dict) -> dict:
        """
        Yksinkertainen analyysi ilman OpenAI:ta, kun API-avain puuttuu.
        """
        osat = []

        # Tekninen tilanne
        if tekninen_data.get("ok"):
            rsi = tekninen_data.get("rsi")
            suositus = tekninen_data.get("tekninen_suositus", "PIDÄ")
            trendi = tekninen_data.get("ema", {}).get("trendi", "tuntematon")

            if rsi:
                if rsi < 30:
                    osat.append(f"RSI ({rsi:.0f}) osoittaa ylimyyntitilanteen.")
                elif rsi > 70:
                    osat.append(f"RSI ({rsi:.0f}) osoittaa yliostotilanteen.")
                else:
                    osat.append(f"RSI ({rsi:.0f}) on neutraalilla alueella.")

            osat.append(f"EMA-trendi: {trendi}. Tekninen signaali: {suositus}.")

        # Sentimentti
        if sentimentti_data.get("ok"):
            fg = sentimentti_data.get("fear_greed", {})
            if fg.get("arvo"):
                osat.append(f"Fear & Greed Index: {fg['arvo']} – {fg.get('luokka', '')}.")

        analyysi_teksti = (
            " ".join(osat) if osat
            else "Lisää OPENAI_API_KEY ympäristömuuttujiin saadaksesi täyden AI-analyysin."
        )

        return {
            "ok": True,
            "analyysi": analyysi_teksti,
            "malli": "sääntöpohjainen (ei OpenAI)",
            "tokeneita_kaytetty": 0,
            "generoitu": time.time(),
            "ai_kaytossa": False
        }


# Globaali instanssi
ai_engine = AIEngine()
