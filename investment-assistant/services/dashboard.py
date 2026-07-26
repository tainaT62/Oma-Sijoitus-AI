"""
Dashboard-palvelu.
Kokoaa kaiken datan yhteen dashboard-näkymää varten.
"""

import time
from utils.logger import logger
from services.portfolio import portfolio_service
from services.technical_analysis import technical_analysis_service
from services.sentiment import sentiment_service
from services.news_service import news_service
from services.recommendation_engine import recommendation_engine
from services.risk_manager import risk_manager_service
from services.portfolio_optimizer import portfolio_optimizer_service
from services.ai_engine import ai_engine


class DashboardService:
    """
    Kokoaa kaikki tiedot yhteen dashboard-kyselyä varten.
    """

    def __init__(self):
        self._cache: dict = {}
        self._cache_aika: float = 0.0
        self._cache_ttl: int = 60  # 1 minuutti

    def _cache_vanhentunut(self) -> bool:
        return (time.time() - self._cache_aika) > self._cache_ttl

    def hae_dashboard_data(self, pakota_paivitys: bool = False) -> dict:
        """
        Hakee kaikki dashboard-tiedot:
        - Salkku
        - Markkinasentimentti
        - Tekniset indikaattorit (BTC, ETH)
        - Suositukset
        - Uutiset
        - AI-analyysi
        - Riskiarvio
        - Salkkuoptimointi
        """
        if not pakota_paivitys and not self._cache_vanhentunut() and self._cache:
            return self._cache

        logger.info("Koostetaan dashboard-data...")
        aloitus = time.time()

        # ─── 1. Salkku ────────────────────────────────────────
        salkku = portfolio_service.hae_salkku(pakota_paivitys=pakota_paivitys)

        # ─── 2. Sentimentti ───────────────────────────────────
        sentimentti = sentiment_service.hae_kokonaissentimentti(
            pakota_paivitys=pakota_paivitys
        )

        # ─── 3. Tekninen analyysi (BTC ja ETH) ───────────────
        btc_tech = technical_analysis_service.analysoi("BTCUSDT", "4h")
        eth_tech = technical_analysis_service.analysoi("ETHUSDT", "4h")

        # ─── 4. Uutiset ───────────────────────────────────────
        uutiset = news_service.hae_uutiset(pakota_paivitys=pakota_paivitys)

        # ─── 5. Suositukset ───────────────────────────────────
        # Analysoi omistetut symbolit tai oletussymbolit
        omistukset = salkku.get("omistukset", []) if salkku.get("ok") else []
        analysoitavat = []

        for o in omistukset:
            if not o.get("on_stablecoin") and o.get("arvo_usdt", 0) > 1:
                symboli = f"{o['valuutta']}USDT"
                analysoitavat.append(symboli)

        if not analysoitavat:
            analysoitavat = ["BTCUSDT", "ETHUSDT"]

        suositukset = recommendation_engine.hae_suositukset(
            symbolit=analysoitavat[:4],
            pakota_paivitys=pakota_paivitys
        )
        paras_suositus = suositukset[0] if suositukset else None

        # ─── 6. Riskiarvio ────────────────────────────────────
        riskiarvio = {}
        if salkku.get("ok") and omistukset:
            riskiarvio = risk_manager_service.arvioi_salkun_riskit(
                omistukset,
                salkku.get("kokonaisarvo_usdt", 0)
            )

        # ─── 7. Salkkuoptimointi ──────────────────────────────
        optimointi = {}
        if salkku.get("ok") and omistukset:
            optimointi = portfolio_optimizer_service.analysoi_salkku(
                omistukset,
                salkku.get("kokonaisarvo_usdt", 0)
            )

        # ─── 8. AI-analyysi ───────────────────────────────────
        otsikot = news_service.hae_otsikot_analyysiin(15)
        ai_analyysi = ai_engine.analysoi_markkinat(
            btc_tech,
            sentimentti,
            otsikot,
            salkku if salkku.get("ok") else None
        )

        # ─── Koosta dashboard ─────────────────────────────────

        kesto = round(time.time() - aloitus, 2)
        logger.info(f"Dashboard koostettu {kesto}s:ssa")

        tulos = {
            "ok": True,
            "salkku": salkku,
            "sentimentti": sentimentti,
            "tekniset": {
                "btc": btc_tech,
                "eth": eth_tech
            },
            "uutiset": uutiset[:15],
            "suositukset": suositukset,
            "paras_suositus": paras_suositus,
            "riskiarvio": riskiarvio,
            "optimointi": optimointi,
            "ai_analyysi": ai_analyysi,
            "latausaika_s": kesto,
            "paivitysaika": time.time()
        }

        self._cache = tulos
        self._cache_aika = time.time()

        return tulos


# Globaali instanssi
dashboard_service = DashboardService()
