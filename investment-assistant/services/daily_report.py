"""
Päivittäinen sijoitusraportti -palvelu.
Generoi kattavan suomenkielisen raportin kaikesta saatavilla olevasta datasta.

Sisältö:
- Markkinakatsaus
- Suurimmat uutiset
- Markkinasentimentti
- Salkun tila
- Riskit
- Kolme parasta ostokohdetta
- Kolme suurinta riskiä
- AI:n yhteenveto
"""

import time
from datetime import datetime, date
from utils.logger import logger
from config import config
from services import database as db
from services.portfolio import portfolio_service
from services.sentiment import sentiment_service
from services.news_service import news_service
from services.technical_analysis import technical_analysis_service
from services.recommendation_engine import recommendation_engine
from services.risk_manager import risk_manager_service
from services.ai_engine import ai_engine


class DailyReportService:
    """Generoi päivittäisen institutionaalisen sijoitusraportin."""

    def _muotoile_otsikko(self, teksti: str, taso: int = 2) -> str:
        prefix = "=" * taso if taso == 1 else "-" * taso
        return f"\n{'=' * 60 if taso == 1 else ''}\n{teksti.upper()}\n{'-' * 40}\n"

    def _generoi_raportti_pohja(
        self,
        salkku: dict,
        sentimentti: dict,
        uutiset: list,
        btc_tech: dict,
        suositukset: list,
        riskiarvio: dict
    ) -> str:
        """Generoi perusraportin ilman OpenAI:ta (aina toimiva)."""

        nyt = datetime.now()
        osat = []

        # ─── Otsikko ──────────────────────────────────────────
        osat.append(
            f"{'=' * 60}\n"
            f"  AI-SIJOITUSASSISTENTTI – PÄIVITTÄINEN RAPORTTI\n"
            f"  {nyt.strftime('%d.%m.%Y %H:%M')}\n"
            f"{'=' * 60}\n"
        )

        # ─── 1. Markkinakatsaus ────────────────────────────────
        osat.append("📊 MARKKINAKATSAUS\n" + "-" * 40)

        fg = sentimentti.get("fear_greed", {})
        if fg.get("ok") and fg.get("arvo") is not None:
            osat.append(f"Fear & Greed Index: {fg['arvo']}/100 – {fg.get('luokka', '')}")
            if fg.get("eilinen_arvo"):
                muutos = fg['arvo'] - fg['eilinen_arvo']
                suunta = "↑" if muutos > 0 else "↓" if muutos < 0 else "→"
                osat.append(f"  Eilen: {fg['eilinen_arvo']} ({suunta} {abs(muutos)} pistettä)")

        if btc_tech.get("ok"):
            hinta = btc_tech.get("nykyinen_hinta", 0)
            rsi = btc_tech.get("rsi")
            trendi = btc_tech.get("ema", {}).get("trendi", "neutraali")
            osat.append(f"\nBitcoin (BTC):")
            osat.append(f"  Hinta: ${hinta:,.2f} USDT")
            if rsi:
                rsi_tila = "ylimyyty" if rsi < 30 else "yliostettu" if rsi > 70 else "neutraali"
                osat.append(f"  RSI (4h): {rsi:.1f} – {rsi_tila}")
            osat.append(f"  EMA-trendi: {trendi}")

        sent_luokka = sentimentti.get("kokonaisluokka", "neutraali")
        sent_pisteet = sentimentti.get("kokonaispisteet", 0)
        osat.append(f"\nKokonaissentimentti: {sent_luokka} ({sent_pisteet:+.2f})")
        osat.append("")

        # ─── 2. Markkinasentimentti ────────────────────────────
        osat.append("🧠 MARKKINASENTIMENTTI\n" + "-" * 40)

        us = sentimentti.get("uutissentimentti", {})
        if us.get("ok"):
            osat.append(f"Uutissentimentti: {us.get('luokka', '–')}")
            osat.append(f"  Positiiviset: {us.get('positiiviset', 0)} | "
                       f"Negatiiviset: {us.get('negatiiviset', 0)} | "
                       f"Neutraalit: {us.get('neutraalit', 0)}")

        reddit = sentimentti.get("reddit", {})
        if reddit.get("ok"):
            osat.append(f"Reddit r/CryptoCurrency: {reddit.get('luokka', '–')} "
                       f"({reddit.get('viesteja', 0)} viestiä analysoitu)")
        osat.append("")

        # ─── 3. Suurimmat uutiset ──────────────────────────────
        osat.append("📰 SUURIMMAT UUTISET\n" + "-" * 40)

        for uutinen in uutiset[:5]:
            osat.append(f"• [{uutinen.get('lahde', '?')}] {uutinen.get('otsikko', '')}")
        osat.append("")

        # ─── 4. Salkun tila ────────────────────────────────────
        osat.append("💼 SALKUN TILA\n" + "-" * 40)

        if salkku.get("ok"):
            arvo = salkku.get("kokonaisarvo_usdt", 0)
            maara = salkku.get("omistusten_maara", 0)
            osat.append(f"Kokonaisarvo: ${arvo:,.2f} USDT")
            osat.append(f"Omistuksia: {maara} kpl")
            osat.append("\nTop 5 omistukset:")
            for o in salkku.get("omistukset", [])[:5]:
                muutos_str = ""
                if o.get("muutos_24h") is not None:
                    m = o["muutos_24h"]
                    muutos_str = f" ({'+' if m >= 0 else ''}{m:.1f}%)"
                osat.append(
                    f"  {o['valuutta']:8s}: ${o['arvo_usdt']:>10,.2f}  "
                    f"({o.get('osuus_prosentti', 0):.1f}%){muutos_str}"
                )
        else:
            osat.append("Salkkudata ei saatavilla (tarkista Binance-yhteys)")
        osat.append("")

        # ─── 5. Riskit ────────────────────────────────────────
        osat.append("⚠️  RISKIANALYYSI\n" + "-" * 40)

        if riskiarvio.get("ok"):
            osat.append(f"Riskitaso: {riskiarvio.get('riskitaso', '–')}")
            varoitukset = riskiarvio.get("varoitukset", [])
            if varoitukset:
                osat.append("Varoitukset:")
                for v in varoitukset:
                    osat.append(f"  ⚠ {v}")
            tilastot = riskiarvio.get("tilastot", {})
            if tilastot:
                osat.append(f"Suurin positio: {tilastot.get('suurin_positio_valuutta', '–')} "
                           f"({tilastot.get('suurin_positio_osuus', 0):.1f}%)")
                osat.append(f"Käteisreservi: {tilastot.get('kauppa_osuus_prosentti', 0):.1f}%")
        osat.append("")

        # ─── 6. Kolme parasta ostokohdetta ────────────────────
        osat.append("✅ KOLME PARASTA OSTOKOHDETTA\n" + "-" * 40)

        osta_suositukset = [s for s in suositukset if s.get("toiminto") == "OSTA"][:3]
        if osta_suositukset:
            for i, s in enumerate(osta_suositukset, 1):
                osat.append(
                    f"{i}. {s['symboli'].replace('USDT','')} – "
                    f"Luottamus: {s.get('luottamus_prosentti', 0)}% | "
                    f"Riski: {s.get('riski', '–')}"
                )
                for p in s.get("perustelut", [])[:3]:
                    osat.append(f"   • {p}")
        else:
            osat.append("Ei selkeitä ostosuosituksia tällä hetkellä.")
        osat.append("")

        # ─── 7. Kolme suurinta riskiä ─────────────────────────
        osat.append("🔴 KOLME SUURINTA RISKIÄ\n" + "-" * 40)

        myy_suositukset = [s for s in suositukset if s.get("toiminto") == "MYY"][:3]
        if myy_suositukset:
            for i, s in enumerate(myy_suositukset, 1):
                osat.append(f"{i}. {s['symboli'].replace('USDT','')} – myyntisignaali")
        else:
            # Näytä korkean riskitason kohteet
            osat.append("• Äärimmäinen ahneus (F&G > 80) voi ennakoida korjausta")
            if btc_tech.get("rsi", 0) and btc_tech.get("rsi", 0) > 70:
                osat.append(f"• BTC RSI yliostettu ({btc_tech['rsi']:.0f})")
            if riskiarvio.get("varoitukset"):
                for v in riskiarvio["varoitukset"][:2]:
                    osat.append(f"• {v}")
        osat.append("")

        # ─── Alatunniste ──────────────────────────────────────
        osat.append("=" * 60)
        osat.append("VASTUUVAPAUSLAUSEKE: Tämä raportti on automaattinen analyysi,")
        osat.append("ei sijoitusneuvonta. Tee aina oma tutkimuksesi ennen")
        osat.append("sijoituspäätöksiä. Kryptovaluutat ovat korkeariskisiä.")
        osat.append("=" * 60)

        return "\n".join(osat)

    def generoi_raportti(self, pakota_paivitys: bool = False) -> dict:
        """
        Generoi päivittäisen raportin.
        Tallentaa sen tietokantaan ja palauttaa strukturoituna datana.
        """
        tanaan = date.today().isoformat()

        # Käytä tallennettua raporttia jos se on jo generoitu tänään
        if not pakota_paivitys:
            tallennettu = db.hae_tanaan_raportti()
            if tallennettu:
                logger.debug("Palautetaan tämän päivän raportti tietokannasta")
                return {
                    "ok": True,
                    "raportti": tallennettu.get("raportti_teksti", ""),
                    "ai_yhteenveto": tallennettu.get("ai_yhteenveto", ""),
                    "pvm": tanaan,
                    "valmis": True
                }

        logger.info("Generoidaan päivittäinen raportti...")

        try:
            # Kerää data
            salkku = portfolio_service.hae_salkku()
            sentimentti = sentiment_service.hae_kokonaissentimentti()
            uutiset = news_service.hae_uutiset()
            btc_tech = technical_analysis_service.analysoi("BTCUSDT", "4h")

            # Suositukset (salkun kohteille)
            omistukset = salkku.get("omistukset", []) if salkku.get("ok") else []
            analysoitavat = [
                f"{o['valuutta']}USDT" for o in omistukset
                if not o.get("on_stablecoin") and o.get("arvo_usdt", 0) > 1
            ]
            if not analysoitavat:
                analysoitavat = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

            suositukset = recommendation_engine.hae_suositukset(
                symbolit=analysoitavat[:5]
            )

            # Riskiarvio
            riskiarvio = {}
            if salkku.get("ok") and omistukset:
                riskiarvio = risk_manager_service.arvioi_salkun_riskit(
                    omistukset, salkku.get("kokonaisarvo_usdt", 0)
                )

            # Generoi raporttiteksti
            raportti_teksti = self._generoi_raportti_pohja(
                salkku, sentimentti, uutiset, btc_tech, suositukset, riskiarvio
            )

            # AI-yhteenveto (jos OpenAI käytettävissä)
            ai_yhteenveto = ""
            otsikot = news_service.hae_otsikot_analyysiin(10)
            ai_analyysi = ai_engine.analysoi_markkinat(btc_tech, sentimentti, otsikot, salkku)
            if ai_analyysi.get("ok"):
                ai_yhteenveto = ai_analyysi.get("analyysi", "")

            # Tallenna tietokantaan
            paras_kohde = None
            osta_suositukset = [s for s in suositukset if s.get("toiminto") == "OSTA"]
            if osta_suositukset:
                paras_kohde = osta_suositukset[0].get("symboli", "")

            db.tallenna_paivittainen_raportti(tanaan, {
                "raportti_teksti": raportti_teksti,
                "markkinakatsaus": f"Fear & Greed: {sentimentti.get('fear_greed', {}).get('arvo', '–')}",
                "salkku_arvo": salkku.get("kokonaisarvo_usdt") if salkku.get("ok") else None,
                "paras_kohde": paras_kohde,
                "suurin_riski": riskiarvio.get("varoitukset", ["–"])[0] if riskiarvio.get("varoitukset") else "–",
                "ai_yhteenveto": ai_yhteenveto
            })

            logger.info(f"Päivittäinen raportti generoitu: {tanaan}")

            return {
                "ok": True,
                "raportti": raportti_teksti,
                "ai_yhteenveto": ai_yhteenveto,
                "pvm": tanaan,
                "valmis": True,
                "paras_kohde": paras_kohde
            }

        except Exception as e:
            logger.error(f"Raportin generointi epäonnistui: {e}", exc_info=True)
            return {"ok": False, "virhe": str(e)}


# Globaali instanssi
daily_report_service = DailyReportService()
