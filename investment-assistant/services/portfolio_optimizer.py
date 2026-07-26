"""
Salkkuoptimointipalvelu.
Analysoi nykyisen salkun ja ehdottaa parannuksia.

Analysoi:
- Liian suuri BTC-paino
- Liian pieni käteispaino
- Puuttuvat sektorit
- Tasapainotusehdotukset
"""

from utils.logger import logger
from config import config


# ─── Kryptosektorit ───────────────────────────────────────────

SEKTORIKARTTA = {
    "Layer 1": ["BTC", "ETH", "SOL", "ADA", "AVAX", "DOT", "ATOM", "NEAR", "APT", "SUI"],
    "Layer 2 / Scaling": ["MATIC", "ARB", "OP", "IMX", "STRK", "MANTA"],
    "DeFi": ["UNI", "AAVE", "CRV", "MKR", "COMP", "SUSHI", "YFI", "GMX", "DYDX"],
    "Stablecoinit": ["USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USDP"],
    "Exchange tokens": ["BNB", "OKB", "CRO", "FTT", "KCS"],
    "Gaming / Metaverse": ["AXS", "SAND", "MANA", "ENJ", "GALA", "IMX"],
    "AI / Data": ["FET", "OCEAN", "AGIX", "TAO", "RENDER", "WLD"],
    "Meme": ["DOGE", "SHIB", "PEPE", "FLOKI", "BONK", "WIF"],
    "Oracle / Infra": ["LINK", "BAND", "API3", "VET", "QNT"],
}


def maarita_sektori(valuutta: str) -> str:
    """Määrittää kryptovaluutan sektorin."""
    for sektori, valuutat in SEKTORIKARTTA.items():
        if valuutta.upper() in valuutat:
            return sektori
    return "Muut"


# ─── Optimoijapääluokka ───────────────────────────────────────


class PortfolioOptimizerService:
    """
    Analysoi nykyisen salkun ja antaa optimointiehdotuksia.
    """

    # Tavoiteallokaatiot (prosenttia)
    TAVOITE_ALLOKAATIO = {
        "BTC": {"min": 20, "max": 50, "suositus": 35},
        "ETH": {"min": 10, "max": 30, "suositus": 20},
        "Altcoinit": {"min": 20, "max": 50, "suositus": 30},
        "Stablecoinit": {"min": 10, "max": 25, "suositus": 15}
    }

    def analysoi_salkku(self, omistukset: list, kokonaisarvo_usdt: float) -> dict:
        """
        Analysoi salkun hajautuksen ja antaa optimointiehdotukset.
        """
        try:
            if not omistukset or kokonaisarvo_usdt <= 0:
                return {
                    "ok": False,
                    "virhe": "Ei omistuksia tai salkku on tyhjä"
                }

            # ─── Sektorianalyysi ──────────────────────────────

            sektorijakauma = {}
            for omistus in omistukset:
                valuutta = omistus["valuutta"]
                sektori = maarita_sektori(valuutta)
                arvo = omistus.get("arvo_usdt", 0)

                if sektori not in sektorijakauma:
                    sektorijakauma[sektori] = {"arvo_usdt": 0, "valuutat": []}

                sektorijakauma[sektori]["arvo_usdt"] += arvo
                sektorijakauma[sektori]["valuutat"].append(valuutta)

            # Lisää osuusprosentit
            for sektori, tiedot in sektorijakauma.items():
                tiedot["osuus_prosentti"] = round(
                    (tiedot["arvo_usdt"] / kokonaisarvo_usdt) * 100, 1
                )

            # ─── Allokaatioanalyysi ───────────────────────────

            btc_osuus = next(
                (o["osuus_prosentti"] for o in omistukset if o["valuutta"] == "BTC"),
                0
            )
            eth_osuus = next(
                (o["osuus_prosentti"] for o in omistukset if o["valuutta"] == "ETH"),
                0
            )
            stable_osuus = sum(
                o["osuus_prosentti"] for o in omistukset
                if o.get("on_stablecoin", False)
            )

            # ─── Ehdotukset ───────────────────────────────────

            ehdotukset = []
            varoitukset = []

            # BTC-tarkistus
            btc_tavoite = self.TAVOITE_ALLOKAATIO["BTC"]
            if btc_osuus > btc_tavoite["max"]:
                varoitukset.append(f"BTC-paino liian suuri ({btc_osuus:.1f}%)")
                ehdotukset.append({
                    "tyyppi": "varoitus",
                    "kategoria": "BTC",
                    "viesti": f"BTC-paino ({btc_osuus:.1f}%) ylittää suosituksen ({btc_tavoite['max']}%)",
                    "toimenpide": f"Harkitse BTC:n vähentämistä {btc_tavoite['suositus']}%:iin ja sijoita altcoineihin tai stablecoineihin"
                })
            elif btc_osuus < btc_tavoite["min"]:
                varoitukset.append(f"BTC-paino pieni ({btc_osuus:.1f}%)")
                ehdotukset.append({
                    "tyyppi": "info",
                    "kategoria": "BTC",
                    "viesti": f"BTC-paino ({btc_osuus:.1f}%) alle suosituksen ({btc_tavoite['min']}%)",
                    "toimenpide": "BTC on perinteisesti turvasatama – harkitse osuuden kasvattamista"
                })

            # ETH-tarkistus
            eth_tavoite = self.TAVOITE_ALLOKAATIO["ETH"]
            if eth_osuus < eth_tavoite["min"]:
                ehdotukset.append({
                    "tyyppi": "info",
                    "kategoria": "ETH",
                    "viesti": f"ETH-paino pieni ({eth_osuus:.1f}%)",
                    "toimenpide": "Ethereum on DeFi-ekosysteemin perusta – harkitse allokaation kasvattamista"
                })

            # Stablecoin-tarkistus
            stable_tavoite = self.TAVOITE_ALLOKAATIO["Stablecoinit"]
            if stable_osuus < stable_tavoite["min"]:
                varoitukset.append(f"Käteisreservi pieni ({stable_osuus:.1f}%)")
                ehdotukset.append({
                    "tyyppi": "varoitus",
                    "kategoria": "Stablecoinit",
                    "viesti": f"Stablecoin-osuus ({stable_osuus:.1f}%) alle suosituksen ({stable_tavoite['min']}%)",
                    "toimenpide": f"Pidä vähintään {stable_tavoite['suositus']}% stablecoineina – tarjoaa joustavuutta ostomahdollisuuksien hyödyntämiseen"
                })
            elif stable_osuus > stable_tavoite["max"]:
                ehdotukset.append({
                    "tyyppi": "info",
                    "kategoria": "Stablecoinit",
                    "viesti": f"Stablecoin-osuus korkea ({stable_osuus:.1f}%)",
                    "toimenpide": "Suuri käteisreservi on turvallista, mutta voit menettää nousupotentiaalia"
                })

            # Sektoritarkistus – puuttuvat sektorit
            salkun_sektorit = set(sektorijakauma.keys())
            suositeltavat_sektorit = {"Layer 1", "DeFi", "Stablecoinit"}
            puuttuvat = suositeltavat_sektorit - salkun_sektorit

            if puuttuvat:
                ehdotukset.append({
                    "tyyppi": "info",
                    "kategoria": "Hajautus",
                    "viesti": f"Puuttuvat sektorit: {', '.join(puuttuvat)}",
                    "toimenpide": "Hajautus useille sektoreille vähentää riskiä yksittäisen sektorin laskussa"
                })

            # Liian monta pienpositiota
            pienet_positiot = [o for o in omistukset if o.get("osuus_prosentti", 0) < 1]
            if len(pienet_positiot) > 5:
                ehdotukset.append({
                    "tyyppi": "info",
                    "kategoria": "Positioiden määrä",
                    "viesti": f"{len(pienet_positiot)} positiota alle 1% – pirstaleinen salkku",
                    "toimenpide": "Harkitse pienten positioiden yhdistämistä tai poistamista"
                })

            # ─── Kokonaistulos ────────────────────────────────

            pistemäärä = max(0, 10 - len(varoitukset) * 2 - len([e for e in ehdotukset if e["tyyppi"] == "info"]))

            return {
                "ok": True,
                "pistemäärä": pistemäärä,  # 0-10
                "allokaatio": {
                    "btc_prosentti": round(btc_osuus, 1),
                    "eth_prosentti": round(eth_osuus, 1),
                    "stable_prosentti": round(stable_osuus, 1),
                    "muut_prosentti": round(100 - btc_osuus - eth_osuus - stable_osuus, 1)
                },
                "sektorijakauma": sektorijakauma,
                "varoitukset": varoitukset,
                "ehdotukset": ehdotukset,
                "tasapaino_arvio": (
                    "Hyvin hajautettu" if pistemäärä >= 8
                    else "Kohtalainen hajautus" if pistemäärä >= 5
                    else "Heikko hajautus"
                )
            }

        except Exception as e:
            logger.error(f"Virhe salkkuoptimoinnissa: {e}", exc_info=True)
            return {"ok": False, "virhe": str(e)}


# Globaali instanssi
portfolio_optimizer_service = PortfolioOptimizerService()
