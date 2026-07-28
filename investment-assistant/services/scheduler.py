"""
Taustaprosessien scheduler.
Päivittää markkinadatan, uutiset, sentimentin ja AI-analyysit automaattisesti.

Aikataulu:
- 5 min:  markkinadata + portfoliosnapshot
- 15 min: uutiset + sentimentti
- 60 min: AI-analyysi + AI Score -pisteet + suositukset
- 1/pv:   päivittäinen raportti (klo 08:00)
"""

import time
from utils.logger import logger

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    APSCHEDULER_SAATAVILLA = True
except ImportError:
    APSCHEDULER_SAATAVILLA = False
    logger.warning("APScheduler ei asennettu – automaattiset päivitykset eivät toimi")


# ─── Tehtäväfunktiot ──────────────────────────────────────────


def _paivita_markkinadata() -> None:
    """Päivittää markkinadatan ja tallentaa portfoliosnapshot. (5 min)"""
    try:
        from services.market_data import market_data_service
        from services.portfolio import portfolio_service
        from services import database as db

        # Päivitä hinnat
        market_data_service.hae_hinnat(pakota_paivitys=True)

        # Tallenna portfoliosnapshot
        salkku = portfolio_service.hae_salkku(pakota_paivitys=True)
        if salkku.get("ok"):
            db.tallenna_portfolio_snapshot(salkku)

            # Tallenna avainhinnat
            for omistus in salkku.get("omistukset", [])[:10]:
                if not omistus.get("on_stablecoin") and omistus.get("hinta_usdt", 0) > 0:
                    db.tallenna_markkinahinta(
                        f"{omistus['valuutta']}USDT",
                        omistus["hinta_usdt"],
                        omistus.get("muutos_24h")
                    )

        logger.debug("Markkinadata päivitetty (scheduler)")

    except Exception as e:
        logger.error(f"Scheduler: markkinadata päivitys epäonnistui: {e}")


def _paivita_uutiset_ja_sentimentti() -> None:
    """Päivittää uutiset ja sentimentin. (15 min)"""
    try:
        from services.news_service import news_service
        from services.sentiment import sentiment_service
        from services import database as db

        # Uutiset
        news_service.hae_uutiset(pakota_paivitys=True)

        # Sentimentti
        sentimentti = sentiment_service.hae_kokonaissentimentti(pakota_paivitys=True)
        if sentimentti.get("ok"):
            db.tallenna_sentimentti(sentimentti)

        logger.debug("Uutiset ja sentimentti päivitetty (scheduler)")

    except Exception as e:
        logger.error(f"Scheduler: uutiset/sentimentti päivitys epäonnistui: {e}")


def _paivita_ai_analyysit() -> None:
    """Päivittää AI-analyysit, pisteet ja suositukset. (60 min)"""
    try:
        from services.technical_analysis import technical_analysis_service
        from services.sentiment import sentiment_service
        from services.news_service import news_service
        from services.ai_engine import ai_engine
        from services.ai_score import ai_score_service
        from services.watchlist import watchlist_service
        from services.recommendation_engine import recommendation_engine
        from services import database as db

        # BTC tekninen analyysi
        btc_tech = technical_analysis_service.analysoi("BTCUSDT", "4h")
        sentimentti = sentiment_service.hae_kokonaissentimentti()
        otsikot = news_service.hae_otsikot_analyysiin(15)

        # AI-analyysi
        ai_analyysi = ai_engine.analysoi_markkinat(btc_tech, sentimentti, otsikot)
        if ai_analyysi.get("ok"):
            db.tallenna_ai_analyysi(ai_analyysi)

        # AI Score -pisteet kaikille watchlist-kohteille
        watchlist = watchlist_service.hae_watchlist()
        symbolit = [k["symboli"] for k in watchlist if k.get("tyyppi") == "crypto"]
        if symbolit:
            ai_score_service.laske_kaikki_pisteet(symbolit[:6])

        # Suositukset
        recommendation_engine.hae_suositukset(
            symbolit=symbolit[:4], pakota_paivitys=True
        )

        logger.debug("AI-analyysit päivitetty (scheduler)")

    except Exception as e:
        logger.error(f"Scheduler: AI-analyysit päivitys epäonnistui: {e}")


def _generoi_paivaraportti() -> None:
    """Generoi päivittäisen raportin (klo 08:00)."""
    try:
        from services.daily_report import daily_report_service
        daily_report_service.generoi_raportti(pakota_paivitys=True)
        logger.info("Päivittäinen raportti generoitu (scheduler)")
    except Exception as e:
        logger.error(f"Scheduler: päiväraportin generointi epäonnistui: {e}")


# ─── Scheduler-hallinta ───────────────────────────────────────


class SchedulerService:
    """
    Hallitsee taustatehtäviä APSchedulerin avulla.
    """

    def __init__(self):
        self._scheduler = None
        self._kaynnissa = False

    def kaynnista(self) -> bool:
        """Käynnistää schedulerin."""
        if not APSCHEDULER_SAATAVILLA:
            logger.warning("APScheduler ei saatavilla – scheduler ei käynnisty")
            return False

        if self._kaynnissa:
            logger.warning("Scheduler on jo käynnissä")
            return True

        try:
            self._scheduler = BackgroundScheduler(
                timezone="Europe/Helsinki",
                job_defaults={"coalesce": True, "max_instances": 1}
            )

            # 5 minuutin välein: markkinadata
            self._scheduler.add_job(
                _paivita_markkinadata,
                trigger=IntervalTrigger(minutes=5),
                id="markkinadata",
                name="Markkinadata + Portfolio snapshot",
                replace_existing=True
            )

            # 15 minuutin välein: uutiset + sentimentti
            self._scheduler.add_job(
                _paivita_uutiset_ja_sentimentti,
                trigger=IntervalTrigger(minutes=15),
                id="uutiset_sentimentti",
                name="Uutiset ja sentimentti",
                replace_existing=True
            )

            # 60 minuutin välein: AI-analyysit
            self._scheduler.add_job(
                _paivita_ai_analyysit,
                trigger=IntervalTrigger(hours=1),
                id="ai_analyysit",
                name="AI-analyysit ja pisteet",
                replace_existing=True
            )

            # Päivittäinen raportti klo 08:00
            self._scheduler.add_job(
                _generoi_paivaraportti,
                trigger=CronTrigger(hour=8, minute=0),
                id="paivaraportti",
                name="Päivittäinen raportti",
                replace_existing=True
            )

            self._scheduler.start()
            self._kaynnissa = True
            logger.info("Scheduler käynnistetty onnistuneesti")
            logger.info("  • Markkinadata: 5 min välein")
            logger.info("  • Uutiset/sentimentti: 15 min välein")
            logger.info("  • AI-analyysit: 60 min välein")
            logger.info("  • Päiväraportti: klo 08:00")
            return True

        except Exception as e:
            logger.error(f"Schedulerin käynnistys epäonnistui: {e}", exc_info=True)
            return False

    def pysayta(self) -> None:
        """Pysäyttää schedulerin."""
        if self._scheduler and self._kaynnissa:
            self._scheduler.shutdown(wait=False)
            self._kaynnissa = False
            logger.info("Scheduler pysäytetty")

    def hae_tila(self) -> dict:
        """Palauttaa schedulerin tilan."""
        if not APSCHEDULER_SAATAVILLA:
            return {"kaynnissa": False, "virhe": "APScheduler ei asennettu"}

        if not self._scheduler or not self._kaynnissa:
            return {"kaynnissa": False, "tehtavia": []}

        tehtavat = []
        for job in self._scheduler.get_jobs():
            seuraava = job.next_run_time
            tehtavat.append({
                "id": job.id,
                "nimi": job.name,
                "seuraava_ajo": seuraava.isoformat() if seuraava else None
            })

        return {
            "kaynnissa": True,
            "apscheduler_saatavilla": APSCHEDULER_SAATAVILLA,
            "tehtavia": tehtavat
        }


# Globaali instanssi
scheduler_service = SchedulerService()
