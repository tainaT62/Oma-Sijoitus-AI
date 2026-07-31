"""
SQLite-historiatietokanta.
Tallentaa kaiken analytiikkaa varten: salkku, suositukset, sentimentti, AI-pisteet.

SOLID: Single Responsibility – vain tietokantatoiminnot.
"""

import sqlite3
import json
import os
import time
from datetime import datetime, date
from typing import Optional
from utils.logger import logger
from config import config

# Tietokannan sijainti
DB_HAKEMISTO = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_POLKU = os.path.join(DB_HAKEMISTO, "assistant.db")


def hae_yhteys() -> sqlite3.Connection:
    """Palauttaa SQLite-yhteyden. Luo tiedoston jos puuttuu."""
    os.makedirs(DB_HAKEMISTO, exist_ok=True)
    # timeout: odota lukon vapautumista sen sijaan että kaadutaan heti
    # "database is locked" -virheeseen.
    yhteys = sqlite3.connect(DB_POLKU, timeout=config.DB_TIMEOUT_SECONDS)
    yhteys.row_factory = sqlite3.Row
    yhteys.execute("PRAGMA journal_mode=WAL")   # Kirjoitussuorituskyky
    yhteys.execute("PRAGMA foreign_keys=ON")
    return yhteys


def alusta_tietokanta() -> None:
    """Luo taulut jos ne eivät ole olemassa."""
    try:
        with hae_yhteys() as db:

            # Salkun arvohistoria
            db.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aikaleima REAL NOT NULL,
                    pvm TEXT NOT NULL,
                    klo TEXT NOT NULL,
                    kokonaisarvo_usdt REAL NOT NULL,
                    omistusten_maara INTEGER NOT NULL,
                    omistukset_json TEXT NOT NULL,  -- JSON: [{valuutta, maara, arvo_usdt}]
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # Päivittäiset tuotot
            db.execute("""
                CREATE TABLE IF NOT EXISTS daily_returns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pvm TEXT UNIQUE NOT NULL,
                    alku_arvo_usdt REAL NOT NULL,
                    loppu_arvo_usdt REAL NOT NULL,
                    tuotto_usdt REAL NOT NULL,
                    tuotto_prosentti REAL NOT NULL,
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # AI-suositukset
            db.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aikaleima REAL NOT NULL,
                    pvm TEXT NOT NULL,
                    symboli TEXT NOT NULL,
                    toiminto TEXT NOT NULL,      -- OSTA / MYY / PIDÄ
                    luottamus INTEGER NOT NULL,
                    riski TEXT NOT NULL,
                    sisaantulohinnat REAL,        -- Hinta suosituksen hetkellä
                    stop_loss REAL,
                    take_profit REAL,
                    perustelut_json TEXT NOT NULL,
                    tekninen_data_json TEXT,
                    toteutunut BOOLEAN DEFAULT 0, -- Onko käyttäjä toteuttanut
                    sulku_hinta REAL,             -- Hinta sulkemisen hetkellä
                    tulos_prosentti REAL,         -- Toteutunut tuotto %
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # Markkinahinnat (tiivis historiatiedosto)
            db.execute("""
                CREATE TABLE IF NOT EXISTS market_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aikaleima REAL NOT NULL,
                    pvm TEXT NOT NULL,
                    klo TEXT NOT NULL,
                    symboli TEXT NOT NULL,
                    hinta REAL NOT NULL,
                    muutos_24h REAL,
                    volyymi_24h REAL,
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # Sentimenttihistoria
            db.execute("""
                CREATE TABLE IF NOT EXISTS sentiment_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aikaleima REAL NOT NULL,
                    pvm TEXT NOT NULL,
                    fear_greed_arvo INTEGER,
                    fear_greed_luokka TEXT,
                    uutissentimentti_pisteet REAL,
                    uutissentimentti_luokka TEXT,
                    reddit_pisteet REAL,
                    kokonaispisteet REAL NOT NULL,
                    kokonaisluokka TEXT NOT NULL,
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # AI-analyysit
            db.execute("""
                CREATE TABLE IF NOT EXISTS ai_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aikaleima REAL NOT NULL,
                    pvm TEXT NOT NULL,
                    analyysi_teksti TEXT NOT NULL,
                    malli TEXT,
                    tokeneita INTEGER,
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # Watchlist
            db.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symboli TEXT UNIQUE NOT NULL,
                    nimi TEXT,
                    tyyppi TEXT DEFAULT 'crypto',   -- crypto / osake / hyodyke / indeksi
                    lisatty_at REAL DEFAULT (unixepoch()),
                    aktiivinen BOOLEAN DEFAULT 1,
                    muistiinpanot TEXT
                )
            """)

            # AI Score -historia
            db.execute("""
                CREATE TABLE IF NOT EXISTS ai_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aikaleima REAL NOT NULL,
                    pvm TEXT NOT NULL,
                    symboli TEXT NOT NULL,
                    kokonaispistemäärä INTEGER NOT NULL,    -- 0-100
                    tekninen_pistemäärä INTEGER,
                    sentimentti_pistemäärä INTEGER,
                    uutis_pistemäärä INTEGER,
                    volatiliteetti_pistemäärä INTEGER,
                    momentum_pistemäärä INTEGER,
                    riski_pistemäärä INTEGER,
                    suositus TEXT,
                    hinta REAL,
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # Päivittäiset raportit
            db.execute("""
                CREATE TABLE IF NOT EXISTS daily_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pvm TEXT UNIQUE NOT NULL,
                    raportti_teksti TEXT NOT NULL,
                    markkinakatsaus TEXT,
                    salkku_arvo REAL,
                    paras_kohde TEXT,
                    suurin_riski TEXT,
                    ai_yhteenveto TEXT,
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # Volatiliteettihistoria
            db.execute("""
                CREATE TABLE IF NOT EXISTS volatility_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aikaleima REAL NOT NULL,
                    pvm TEXT NOT NULL,
                    symboli TEXT NOT NULL,
                    atr REAL,
                    atr_prosentti REAL,
                    bollinger_leveys REAL,
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # Kuukausibudjetin toteutuneet sijoitukset.
            # Järjestelmä ei tee kauppoja, joten se ei voi päätellä mitä on
            # ostettu – käyttäjä kirjaa toteutuneet ostot tänne.
            db.execute("""
                CREATE TABLE IF NOT EXISTS budget_spend (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aikaleima REAL NOT NULL,
                    pvm TEXT NOT NULL,
                    kuukausi TEXT NOT NULL,        -- 'YYYY-MM'
                    symboli TEXT NOT NULL,
                    nimi TEXT,
                    luokka TEXT,                   -- krypto / osake / etf / rahasto
                    summa REAL NOT NULL,           -- perusvaluutassa
                    valuutta TEXT NOT NULL,
                    muistiinpano TEXT,
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # Omistusten tilannekuva synkronointia varten. Vertaamalla
            # peräkkäisiä tilannekuvia havaitaan ostot ja myynnit ilman,
            # että käyttäjän tarvitsee kirjata mitään.
            db.execute("""
                CREATE TABLE IF NOT EXISTS holdings_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aikaleima REAL NOT NULL,
                    pvm TEXT NOT NULL,
                    lahde TEXT NOT NULL,           -- Binance / IBKR
                    symboli TEXT NOT NULL,
                    luokka TEXT,
                    maara REAL NOT NULL,
                    hinta REAL,
                    arvo REAL,
                    valuutta TEXT,
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # Havaitut salkkumuutokset
            db.execute("""
                CREATE TABLE IF NOT EXISTS sync_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aikaleima REAL NOT NULL,
                    pvm TEXT NOT NULL,
                    lahde TEXT NOT NULL,
                    symboli TEXT NOT NULL,
                    luokka TEXT,
                    tapahtuma TEXT NOT NULL,       -- OSTO/LISAYS/OSITTAINEN_MYYNTI/MYYNTI
                    maara_muutos REAL NOT NULL,
                    arvo REAL,
                    valuutta TEXT,
                    hinta_lahde TEXT,              -- kauppahistoria / markkinahinta
                    kirjattu_budjettiin BOOLEAN DEFAULT 0,
                    luotu_at REAL DEFAULT (unixepoch())
                )
            """)

            # Telegram-napeista syntyvät vahvistusta odottavat toimenpiteet.
            # Painallus ei koskaan suorita mitään suoraan: se luo rivin
            # tänne, ja vasta VAHVISTA-painallus kuluttaa sen.
            db.execute("""
                CREATE TABLE IF NOT EXISTS pending_actions (
                    id TEXT PRIMARY KEY,
                    luotu REAL NOT NULL,
                    vanhenee REAL NOT NULL,
                    tyyppi TEXT NOT NULL,          -- BUY / SELL / REDUCE
                    symboli TEXT NOT NULL,
                    nimi TEXT,
                    luokka TEXT,
                    porssi TEXT,
                    summa REAL,                    -- BUY: perusvaluutassa
                    maara REAL,                    -- SELL/REDUCE: kappaleet
                    osuus_prosentti REAL,          -- REDUCE
                    tila TEXT NOT NULL,            -- odottaa/vahvistettu/peruttu/vanhentunut
                    tulos_json TEXT,
                    kasitelty REAL
                )
            """)

            # Indeksit nopeaa hakua varten
            db.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_aikaleima ON portfolio_snapshots(aikaleima)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_symboli ON recommendations(symboli, aikaleima)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_ai_scores_symboli ON ai_scores(symboli, aikaleima)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_aikaleima ON sentiment_history(aikaleima)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_market_prices_symboli ON market_prices(symboli, aikaleima)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_budget_kuukausi ON budget_spend(kuukausi)")

            db.commit()

        logger.info(f"Tietokanta alustettu: {DB_POLKU}")

    except Exception as e:
        logger.error(f"Tietokannan alustus epäonnistui: {e}", exc_info=True)
        raise


# ─── Kirjoitusfunktiot ────────────────────────────────────────


def tallenna_portfolio_snapshot(salkku_data: dict) -> bool:
    """Tallentaa salkun nykytilanteen tietokantaan."""
    try:
        if not salkku_data.get("ok"):
            return False

        nyt = time.time()
        dt = datetime.fromtimestamp(nyt)

        with hae_yhteys() as db:
            db.execute("""
                INSERT INTO portfolio_snapshots
                (aikaleima, pvm, klo, kokonaisarvo_usdt, omistusten_maara, omistukset_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                nyt,
                dt.strftime("%Y-%m-%d"),
                dt.strftime("%H:%M:%S"),
                salkku_data.get("kokonaisarvo_usdt", 0),
                salkku_data.get("omistusten_maara", 0),
                json.dumps([
                    {
                        "valuutta": o["valuutta"],
                        "maara": o["maara"],
                        "arvo_usdt": o["arvo_usdt"],
                        "osuus_prosentti": o.get("osuus_prosentti", 0)
                    }
                    for o in salkku_data.get("omistukset", [])
                ], ensure_ascii=False)
            ))
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Portfoliosnapshot tallennus epäonnistui: {e}")
        return False


def tallenna_paivittainen_tuotto(pvm: str, alku: float, loppu: float) -> bool:
    """Tallentaa päivittäisen tuoton."""
    try:
        tuotto_usdt = loppu - alku
        tuotto_pct = ((loppu - alku) / alku * 100) if alku > 0 else 0

        with hae_yhteys() as db:
            db.execute("""
                INSERT OR REPLACE INTO daily_returns
                (pvm, alku_arvo_usdt, loppu_arvo_usdt, tuotto_usdt, tuotto_prosentti)
                VALUES (?, ?, ?, ?, ?)
            """, (pvm, alku, loppu, tuotto_usdt, tuotto_pct))
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Päivittäinen tuotto tallennus epäonnistui: {e}")
        return False


def tallenna_suositus(suositus: dict) -> Optional[int]:
    """Tallentaa AI-suosituksen. Palauttaa rivin ID:n."""
    try:
        if not suositus.get("ok"):
            return None

        nyt = time.time()
        dt = datetime.fromtimestamp(nyt)

        with hae_yhteys() as db:
            kursori = db.execute("""
                INSERT INTO recommendations
                (aikaleima, pvm, symboli, toiminto, luottamus, riski,
                 sisaantulohinnat, stop_loss, take_profit, perustelut_json, tekninen_data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nyt,
                dt.strftime("%Y-%m-%d"),
                suositus.get("symboli"),
                suositus.get("toiminto"),
                suositus.get("luottamus_prosentti", 0),
                suositus.get("riski", ""),
                suositus.get("nykyinen_hinta"),
                suositus.get("stop_loss_ehdotus"),
                suositus.get("take_profit_ehdotus"),
                json.dumps(suositus.get("perustelut", []), ensure_ascii=False),
                json.dumps(suositus.get("tekninen_data", {}), ensure_ascii=False)
            ))
            db.commit()
            return kursori.lastrowid
    except Exception as e:
        logger.error(f"Suositus tallennus epäonnistui: {e}")
        return None


def tallenna_sentimentti(sentimentti: dict) -> bool:
    """Tallentaa sentimenttidatan."""
    try:
        if not sentimentti.get("ok"):
            return False

        nyt = time.time()
        fg = sentimentti.get("fear_greed", {})
        us = sentimentti.get("uutissentimentti", {})
        reddit = sentimentti.get("reddit", {})

        with hae_yhteys() as db:
            db.execute("""
                INSERT INTO sentiment_history
                (aikaleima, pvm, fear_greed_arvo, fear_greed_luokka,
                 uutissentimentti_pisteet, uutissentimentti_luokka,
                 reddit_pisteet, kokonaispisteet, kokonaisluokka)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nyt,
                datetime.fromtimestamp(nyt).strftime("%Y-%m-%d"),
                fg.get("arvo"),
                fg.get("luokka"),
                us.get("pisteytys"),
                us.get("luokka"),
                reddit.get("pisteytys") if reddit.get("ok") else None,
                sentimentti.get("kokonaispisteet", 0),
                sentimentti.get("kokonaisluokka", "")
            ))
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Sentimentti tallennus epäonnistui: {e}")
        return False


def tallenna_ai_score(symboli: str, score: dict, hinta: Optional[float] = None) -> bool:
    """Tallentaa AI Score -arvon."""
    try:
        nyt = time.time()
        with hae_yhteys() as db:
            db.execute("""
                INSERT INTO ai_scores
                (aikaleima, pvm, symboli, kokonaispistemäärä,
                 tekninen_pistemäärä, sentimentti_pistemäärä, uutis_pistemäärä,
                 volatiliteetti_pistemäärä, momentum_pistemäärä, riski_pistemäärä,
                 suositus, hinta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nyt,
                datetime.fromtimestamp(nyt).strftime("%Y-%m-%d"),
                symboli,
                score.get("kokonaispistemäärä", 0),
                score.get("tekninen", {}).get("pisteet"),
                score.get("sentimentti", {}).get("pisteet"),
                score.get("uutiset", {}).get("pisteet"),
                score.get("volatiliteetti", {}).get("pisteet"),
                score.get("momentum", {}).get("pisteet"),
                score.get("riski", {}).get("pisteet"),
                score.get("suositus"),
                hinta
            ))
            db.commit()
        return True
    except Exception as e:
        logger.error(f"AI Score tallennus epäonnistui: {e}")
        return False


def tallenna_ai_analyysi(analyysi: dict) -> bool:
    """Tallentaa AI-analyysin."""
    try:
        if not analyysi.get("ok"):
            return False
        nyt = time.time()
        with hae_yhteys() as db:
            db.execute("""
                INSERT INTO ai_analyses (aikaleima, pvm, analyysi_teksti, malli, tokeneita)
                VALUES (?, ?, ?, ?, ?)
            """, (
                nyt,
                datetime.fromtimestamp(nyt).strftime("%Y-%m-%d"),
                analyysi.get("analyysi", ""),
                analyysi.get("malli"),
                analyysi.get("tokeneita_kaytetty")
            ))
            db.commit()
        return True
    except Exception as e:
        logger.error(f"AI-analyysi tallennus epäonnistui: {e}")
        return False


def tallenna_markkinahinta(symboli: str, hinta: float, muutos_24h: Optional[float] = None) -> bool:
    """Tallentaa markkinahinnan."""
    try:
        nyt = time.time()
        dt = datetime.fromtimestamp(nyt)
        with hae_yhteys() as db:
            db.execute("""
                INSERT INTO market_prices (aikaleima, pvm, klo, symboli, hinta, muutos_24h)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (nyt, dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M"), symboli, hinta, muutos_24h))
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Markkinahinta tallennus epäonnistui ({symboli}): {e}")
        return False


def tallenna_paivittainen_raportti(pvm: str, raportti: dict) -> bool:
    """Tallentaa päivittäisen raportin."""
    try:
        with hae_yhteys() as db:
            db.execute("""
                INSERT OR REPLACE INTO daily_reports
                (pvm, raportti_teksti, markkinakatsaus, salkku_arvo, paras_kohde, suurin_riski, ai_yhteenveto)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                pvm,
                raportti.get("raportti_teksti", ""),
                raportti.get("markkinakatsaus", ""),
                raportti.get("salkku_arvo"),
                raportti.get("paras_kohde"),
                raportti.get("suurin_riski"),
                raportti.get("ai_yhteenveto", "")
            ))
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Päivittäinen raportti tallennus epäonnistui: {e}")
        return False


# ─── Lukufunktiot ─────────────────────────────────────────────


def hae_portfolio_historia(paivia: int = 30) -> list:
    """Hakee salkun arvohistorian N viime päivältä."""
    try:
        raja = time.time() - paivia * 86400
        with hae_yhteys() as db:
            rivit = db.execute("""
                SELECT pvm, klo, kokonaisarvo_usdt, omistusten_maara
                FROM portfolio_snapshots
                WHERE aikaleima >= ?
                ORDER BY aikaleima ASC
            """, (raja,)).fetchall()
        return [dict(r) for r in rivit]
    except Exception as e:
        logger.error(f"Portfolio-historia haku epäonnistui: {e}")
        return []


def hae_paivittaiset_tuotot(paivia: int = 30) -> list:
    """Hakee päivittäiset tuotot."""
    try:
        with hae_yhteys() as db:
            rivit = db.execute("""
                SELECT pvm, alku_arvo_usdt, loppu_arvo_usdt, tuotto_usdt, tuotto_prosentti
                FROM daily_returns
                ORDER BY pvm DESC LIMIT ?
            """, (paivia,)).fetchall()
        return [dict(r) for r in rivit]
    except Exception as e:
        logger.error(f"Päivittäiset tuotot haku epäonnistui: {e}")
        return []


def hae_suositushistoria(symboli: Optional[str] = None, maara: int = 50) -> list:
    """Hakee suositushistorian."""
    try:
        with hae_yhteys() as db:
            if symboli:
                rivit = db.execute("""
                    SELECT * FROM recommendations
                    WHERE symboli = ? ORDER BY aikaleima DESC LIMIT ?
                """, (symboli, maara)).fetchall()
            else:
                rivit = db.execute("""
                    SELECT * FROM recommendations
                    ORDER BY aikaleima DESC LIMIT ?
                """, (maara,)).fetchall()
        return [dict(r) for r in rivit]
    except Exception as e:
        logger.error(f"Suositushistoria haku epäonnistui: {e}")
        return []


def hae_sentimenttihistoria(paivia: int = 30) -> list:
    """Hakee sentimenttihistorian."""
    try:
        raja = time.time() - paivia * 86400
        with hae_yhteys() as db:
            rivit = db.execute("""
                SELECT pvm, fear_greed_arvo, fear_greed_luokka,
                       uutissentimentti_pisteet, kokonaispisteet, kokonaisluokka
                FROM sentiment_history
                WHERE aikaleima >= ?
                ORDER BY aikaleima ASC
            """, (raja,)).fetchall()
        return [dict(r) for r in rivit]
    except Exception as e:
        logger.error(f"Sentimenttihistoria haku epäonnistui: {e}")
        return []


def hae_viimeisimmät_ai_pisteet() -> list:
    """Hakee viimeisimmät AI-pisteet kaikille symboleille."""
    try:
        with hae_yhteys() as db:
            rivit = db.execute("""
                SELECT s1.*
                FROM ai_scores s1
                INNER JOIN (
                    SELECT symboli, MAX(aikaleima) as max_aika
                    FROM ai_scores GROUP BY symboli
                ) s2 ON s1.symboli = s2.symboli AND s1.aikaleima = s2.max_aika
                ORDER BY s1.kokonaispistemäärä DESC
            """).fetchall()
        return [dict(r) for r in rivit]
    except Exception as e:
        logger.error(f"AI-pisteet haku epäonnistui: {e}")
        return []


def hae_tanaan_raportti() -> Optional[dict]:
    """Hakee tämän päivän raportin."""
    try:
        tanaan = date.today().isoformat()
        with hae_yhteys() as db:
            rivi = db.execute("""
                SELECT * FROM daily_reports WHERE pvm = ?
            """, (tanaan,)).fetchone()
        return dict(rivi) if rivi else None
    except Exception as e:
        logger.error(f"Päivän raportti haku epäonnistui: {e}")
        return None


def hae_tietokannan_tilastot() -> dict:
    """Hakee tietokannan tilastot."""
    try:
        with hae_yhteys() as db:
            snapshots = db.execute("SELECT COUNT(*) as n FROM portfolio_snapshots").fetchone()["n"]
            suositukset = db.execute("SELECT COUNT(*) as n FROM recommendations").fetchone()["n"]
            sentimentit = db.execute("SELECT COUNT(*) as n FROM sentiment_history").fetchone()["n"]
            ai_pisteet = db.execute("SELECT COUNT(*) as n FROM ai_scores").fetchone()["n"]
            watchlist = db.execute("SELECT COUNT(*) as n FROM watchlist WHERE aktiivinen=1").fetchone()["n"]
        return {
            "portfolio_snapshots": snapshots,
            "suosituksia": suositukset,
            "sentimenttiriveja": sentimentit,
            "ai_pisteet_riveja": ai_pisteet,
            "watchlist_kohteita": watchlist,
            "db_polku": DB_POLKU
        }
    except Exception as e:
        logger.error(f"Tietokannan tilastot haku epäonnistui: {e}")
        return {}


# ─── Kuukausibudjetti ─────────────────────────────────────────


def kirjaa_budjettisijoitus(symboli: str, summa: float, valuutta: str,
                            nimi: str = "", luokka: str = "",
                            muistiinpano: str = "") -> Optional[int]:
    """Kirjaa toteutuneen oston kuluvan kuukauden budjettiin."""
    try:
        nyt = time.time()
        dt = datetime.fromtimestamp(nyt)
        with hae_yhteys() as db:
            kursori = db.execute("""
                INSERT INTO budget_spend
                (aikaleima, pvm, kuukausi, symboli, nimi, luokka, summa, valuutta, muistiinpano)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nyt, dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m"),
                  symboli.upper(), nimi or symboli.upper(), luokka,
                  float(summa), valuutta.upper(), muistiinpano))
            db.commit()
            return kursori.lastrowid
    except Exception as e:
        logger.error(f"Budjettisijoituksen kirjaus epäonnistui: {e}")
        return None


def hae_kuukauden_sijoitukset(kuukausi: Optional[str] = None) -> list:
    """Palauttaa kuukauden kirjatut ostot. kuukausi = 'YYYY-MM'."""
    try:
        kk = kuukausi or datetime.now().strftime("%Y-%m")
        with hae_yhteys() as db:
            rivit = db.execute("""
                SELECT * FROM budget_spend WHERE kuukausi = ?
                ORDER BY aikaleima DESC
            """, (kk,)).fetchall()
        return [dict(r) for r in rivit]
    except Exception as e:
        logger.error(f"Kuukauden sijoitusten haku epäonnistui: {e}")
        return []


def hae_kuukauden_summa(kuukausi: Optional[str] = None) -> float:
    """Palauttaa kuukauden kirjattujen ostojen yhteissumman."""
    try:
        kk = kuukausi or datetime.now().strftime("%Y-%m")
        with hae_yhteys() as db:
            rivi = db.execute(
                "SELECT COALESCE(SUM(summa), 0) AS s FROM budget_spend WHERE kuukausi = ?",
                (kk,)
            ).fetchone()
        return float(rivi["s"] or 0.0)
    except Exception as e:
        logger.error(f"Kuukauden summan haku epäonnistui: {e}")
        return 0.0


def poista_budjettisijoitus(rivi_id: int) -> bool:
    """Poistaa virheellisen kirjauksen."""
    try:
        with hae_yhteys() as db:
            db.execute("DELETE FROM budget_spend WHERE id = ?", (rivi_id,))
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Budjettikirjauksen poisto epäonnistui: {e}")
        return False


# ─── Telegram-toimenpiteet ────────────────────────────────────


def tallenna_toimenpide(tiedot: dict) -> bool:
    """Tallentaa vahvistusta odottavan toimenpiteen."""
    try:
        with hae_yhteys() as db:
            db.execute("""
                INSERT OR REPLACE INTO pending_actions
                (id, luotu, vanhenee, tyyppi, symboli, nimi, luokka, porssi,
                 summa, maara, osuus_prosentti, tila)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'odottaa')
            """, (tiedot["id"], tiedot["luotu"], tiedot["vanhenee"],
                  tiedot["tyyppi"], tiedot["symboli"], tiedot.get("nimi"),
                  tiedot.get("luokka"), tiedot.get("porssi"),
                  tiedot.get("summa"), tiedot.get("maara"),
                  tiedot.get("osuus_prosentti")))
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Toimenpiteen tallennus epäonnistui: {e}")
        return False


def hae_toimenpide(toimenpide_id: str) -> Optional[dict]:
    try:
        with hae_yhteys() as db:
            rivi = db.execute(
                "SELECT * FROM pending_actions WHERE id = ?", (toimenpide_id,)
            ).fetchone()
        return dict(rivi) if rivi else None
    except Exception as e:
        logger.error(f"Toimenpiteen haku epäonnistui: {e}")
        return None


def merkitse_toimenpide(toimenpide_id: str, tila: str,
                        tulos_json: Optional[str] = None) -> bool:
    """
    Merkitsee toimenpiteen käsitellyksi. Palauttaa False, jos rivi oli jo
    käsitelty – tämä on idempotenssisuoja tuplapainalluksille.
    """
    try:
        with hae_yhteys() as db:
            kursori = db.execute("""
                UPDATE pending_actions
                SET tila = ?, tulos_json = ?, kasitelty = ?
                WHERE id = ? AND tila = 'odottaa'
            """, (tila, tulos_json, time.time(), toimenpide_id))
            db.commit()
            return kursori.rowcount > 0
    except Exception as e:
        logger.error(f"Toimenpiteen merkintä epäonnistui: {e}")
        return False


def hae_telegram_offset() -> int:
    """Viimeksi käsitelty update_id long pollingia varten."""
    try:
        with hae_yhteys() as db:
            db.execute("CREATE TABLE IF NOT EXISTS bot_state "
                       "(avain TEXT PRIMARY KEY, arvo TEXT)")
            rivi = db.execute(
                "SELECT arvo FROM bot_state WHERE avain = 'tg_offset'"
            ).fetchone()
            db.commit()
        return int(rivi["arvo"]) if rivi else 0
    except Exception as e:
        logger.error(f"Telegram-offsetin haku epäonnistui: {e}")
        return 0


def tallenna_telegram_offset(offset: int) -> None:
    try:
        with hae_yhteys() as db:
            db.execute("CREATE TABLE IF NOT EXISTS bot_state "
                       "(avain TEXT PRIMARY KEY, arvo TEXT)")
            db.execute("INSERT OR REPLACE INTO bot_state VALUES ('tg_offset', ?)",
                       (str(offset),))
            db.commit()
    except Exception as e:
        logger.error(f"Telegram-offsetin tallennus epäonnistui: {e}")


# ─── Salkun synkronointi ──────────────────────────────────────


def tallenna_holdings_snapshot(positiot: list) -> bool:
    """Tallentaa nykyiset omistukset vertailua varten."""
    try:
        nyt = time.time()
        pvm = datetime.fromtimestamp(nyt).strftime("%Y-%m-%d")
        with hae_yhteys() as db:
            for p in positiot:
                db.execute("""
                    INSERT INTO holdings_snapshots
                    (aikaleima, pvm, lahde, symboli, luokka, maara, hinta, arvo, valuutta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nyt, pvm, p.get("lahde", "?"), p.get("symboli", "?"),
                      p.get("luokka"), float(p.get("maara") or 0),
                      p.get("markkinahinta"), p.get("arvo"), p.get("valuutta")))
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Holdings-snapshotin tallennus epäonnistui: {e}")
        return False


def hae_viimeisin_holdings_snapshot() -> dict:
    """
    Palauttaa viimeisimmän tilannekuvan muodossa
    {(lahde, symboli): {maara, hinta, arvo, luokka}}.
    Tyhjä dict tarkoittaa, ettei vertailukohtaa vielä ole.
    """
    try:
        with hae_yhteys() as db:
            rivi = db.execute(
                "SELECT MAX(aikaleima) AS a FROM holdings_snapshots"
            ).fetchone()
            if not rivi or rivi["a"] is None:
                return {}
            rivit = db.execute(
                "SELECT * FROM holdings_snapshots WHERE aikaleima = ?", (rivi["a"],)
            ).fetchall()
        return {
            (r["lahde"], r["symboli"]): {
                "maara": r["maara"], "hinta": r["hinta"],
                "arvo": r["arvo"], "luokka": r["luokka"],
                "aikaleima": r["aikaleima"],
            }
            for r in rivit
        }
    except Exception as e:
        logger.error(f"Holdings-snapshotin haku epäonnistui: {e}")
        return {}


def tallenna_sync_tapahtuma(lahde: str, symboli: str, tapahtuma: str,
                            maara_muutos: float, arvo: Optional[float],
                            valuutta: str, hinta_lahde: str,
                            luokka: str = "", kirjattu: bool = False) -> Optional[int]:
    """Tallentaa havaitun salkkumuutoksen."""
    try:
        nyt = time.time()
        with hae_yhteys() as db:
            kursori = db.execute("""
                INSERT INTO sync_events
                (aikaleima, pvm, lahde, symboli, luokka, tapahtuma,
                 maara_muutos, arvo, valuutta, hinta_lahde, kirjattu_budjettiin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nyt, datetime.fromtimestamp(nyt).strftime("%Y-%m-%d"),
                  lahde, symboli, luokka, tapahtuma, maara_muutos, arvo,
                  valuutta, hinta_lahde, 1 if kirjattu else 0))
            db.commit()
            return kursori.lastrowid
    except Exception as e:
        logger.error(f"Sync-tapahtuman tallennus epäonnistui: {e}")
        return None


def hae_sync_tapahtumat(maara: int = 20) -> list:
    try:
        with hae_yhteys() as db:
            rivit = db.execute(
                "SELECT * FROM sync_events ORDER BY aikaleima DESC LIMIT ?", (maara,)
            ).fetchall()
        return [dict(r) for r in rivit]
    except Exception as e:
        logger.error(f"Sync-tapahtumien haku epäonnistui: {e}")
        return []


# ─── Watchlist-funktiot ───────────────────────────────────────


def hae_watchlist() -> list:
    """Hakee kaikki aktiiviset watchlist-kohteet."""
    try:
        with hae_yhteys() as db:
            rivit = db.execute("""
                SELECT * FROM watchlist WHERE aktiivinen=1 ORDER BY lisatty_at ASC
            """).fetchall()
        return [dict(r) for r in rivit]
    except Exception as e:
        logger.error(f"Watchlist haku epäonnistui: {e}")
        return []


def lisaa_watchlistiin(symboli: str, nimi: str = "", tyyppi: str = "crypto") -> bool:
    """Lisää kohteen watchlistiin."""
    try:
        with hae_yhteys() as db:
            db.execute("""
                INSERT OR REPLACE INTO watchlist (symboli, nimi, tyyppi, aktiivinen)
                VALUES (?, ?, ?, 1)
            """, (symboli.upper(), nimi or symboli.upper(), tyyppi))
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Watchlist lisäys epäonnistui ({symboli}): {e}")
        return False


def poista_watchlistista(symboli: str) -> bool:
    """Poistaa kohteen watchlistista (pehmeä poisto)."""
    try:
        with hae_yhteys() as db:
            db.execute(
                "UPDATE watchlist SET aktiivinen=0 WHERE symboli=?",
                (symboli.upper(),)
            )
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Watchlist poisto epäonnistui ({symboli}): {e}")
        return False


# ─── Alustus ──────────────────────────────────────────────────

# Alusta tietokanta sovelluksen käynnistyksen yhteydessä
try:
    alusta_tietokanta()
except Exception as e:
    logger.error(f"Kriittinen virhe: tietokannan alustus epäonnistui: {e}")
