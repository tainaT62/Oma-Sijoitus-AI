"""
Portfolio Score 0–100.

Kokoaa kuusi osatekijää yhdeksi luvuksi, joka kertoo salkun kunnon
yhdellä silmäyksellä. Jokainen osatekijä palauttaa 0–100 (suurempi =
parempi) ja niistä lasketaan painotettu keskiarvo.

Kaikki syötteet tulevat olemassa olevilta palveluilta – tässä ei haeta
dataa eikä tehdä sijoituspäätöksiä, vain pisteytetään nykytila.
"""


from config import config
from utils.logger import logger

PAINOT = {
    "hajautus":       0.25,
    "riski":          0.20,
    "allokaatio":     0.20,
    "kassavaranto":   0.15,
    "markkinatilanne": 0.10,
    "budjetti":       0.10,
}

# Käteisen tavoitehaarukka salkusta
KASSA_MIN, KASSA_IHANNE, KASSA_MAX = 5.0, 12.0, 25.0


def _hajautus(positiot: list) -> dict:
    """Suurin yksittäinen paino ja positioiden määrä."""
    if not positiot:
        return {"pisteet": 0, "selitys": "Ei omistuksia"}

    osuudet = [p.get("osuus_prosentti", 0) or 0 for p in positiot]
    suurin = max(osuudet)
    maksimi = config.MAX_POSITION_PROSENTTI

    # Suurin positio: tavoitteessa täydet pisteet, ylitys vähentää.
    if suurin <= maksimi:
        keskittyma = 100.0
    else:
        keskittyma = max(0.0, 100.0 - (suurin - maksimi) * 3)

    # Positioiden määrä: 8+ riittää hyvään hajautukseen.
    maara_pisteet = min(100.0, len(positiot) / 8 * 100)

    pisteet = keskittyma * 0.65 + maara_pisteet * 0.35
    return {
        "pisteet": int(round(pisteet)),
        "suurin_positio_prosentti": round(suurin, 1),
        "positioita": len(positiot),
        "selitys": f"Suurin positio {suurin:.1f} %, {len(positiot)} positiota",
    }


def _riski(positiot: list) -> dict:
    """Painotettu keskiarvo positioiden riskipisteistä (käännettynä)."""
    if not positiot:
        return {"pisteet": 50, "selitys": "Ei omistuksia"}

    yhteisarvo = sum(p.get("arvo") or 0 for p in positiot)
    if yhteisarvo <= 0:
        return {"pisteet": 50, "selitys": "Arvoa ei saatavilla"}

    painotettu = sum(
        (p.get("riskipisteet") or 50) * ((p.get("arvo") or 0) / yhteisarvo)
        for p in positiot
    )
    # riskipisteet: suuri = riskisempi -> käännetään
    return {
        "pisteet": int(round(100 - painotettu)),
        "keskimaarainen_riski": round(painotettu, 1),
        "selitys": f"Painotettu riskitaso {painotettu:.0f}/100",
    }


def _allokaatio(luokkajakauma: dict, tavoite: dict) -> dict:
    """Kuinka lähellä nykyjakauma on tavoitetta."""
    if not luokkajakauma:
        return {"pisteet": 50, "selitys": "Jakaumaa ei saatavilla"}

    poikkeamat, erittely = [], {}
    for luokka, tavoiteosuus in tavoite.items():
        nyt = luokkajakauma.get(luokka, {}).get("osuus_prosentti", 0.0)
        tavoite_pros = tavoiteosuus * 100
        poikkeama = nyt - tavoite_pros
        poikkeamat.append(abs(poikkeama))
        erittely[luokka] = {
            "nyt_prosentti": round(nyt, 1),
            "tavoite_prosentti": round(tavoite_pros, 1),
            "poikkeama": round(poikkeama, 1),
            "tila": "ylipaino" if poikkeama > 5 else
                    "alipaino" if poikkeama < -5 else "tavoitteessa",
        }

    ka_poikkeama = sum(poikkeamat) / len(poikkeamat) if poikkeamat else 0
    pisteet = max(0.0, 100.0 - ka_poikkeama * 2.5)
    return {
        "pisteet": int(round(pisteet)),
        "erittely": erittely,
        "keskipoikkeama": round(ka_poikkeama, 1),
        "selitys": f"Keskipoikkeama tavoitteesta {ka_poikkeama:.1f} pp",
    }


def _kassavaranto(kateinen: float, kokonaisarvo: float) -> dict:
    if kokonaisarvo <= 0:
        return {"pisteet": 50, "selitys": "Salkun arvoa ei saatavilla"}

    osuus = kateinen / kokonaisarvo * 100
    if KASSA_MIN <= osuus <= KASSA_MAX:
        # Täydet pisteet ihannearvossa, lievä lasku reunoja kohti
        etaisyys = abs(osuus - KASSA_IHANNE)
        pisteet = max(70.0, 100.0 - etaisyys * 2)
        tila = "sopiva"
    elif osuus < KASSA_MIN:
        pisteet = max(0.0, osuus / KASSA_MIN * 70)
        tila = "liian pieni"
    else:
        pisteet = max(30.0, 70.0 - (osuus - KASSA_MAX))
        tila = "suuri – tuottamatonta pääomaa"

    return {
        "pisteet": int(round(pisteet)),
        "osuus_prosentti": round(osuus, 1),
        "tila": tila,
        "selitys": f"Käteistä {osuus:.1f} % ({tila})",
    }


def _markkinatilanne(markkinatila: dict) -> dict:
    taso = markkinatila.get("riskitaso", "normaali")
    pisteet = {"normaali": 85, "kohonnut": 60, "korkea": 35, "äärimmäinen": 15}.get(taso, 50)
    return {
        "pisteet": pisteet,
        "riskitaso": taso,
        "selitys": f"Markkinariski: {taso}",
    }


def _budjetti(budjetti: dict) -> dict:
    """
    Budjetin käyttö kuukauden aikana. Sekä käyttämättä jättäminen että
    kuukauden alussa loppuun käyttäminen laskevat pisteitä.
    """
    from datetime import datetime
    import calendar

    kaytetty = budjetti.get("kaytetty_prosentti", 0.0)
    nyt = datetime.now()
    paivia = calendar.monthrange(nyt.year, nyt.month)[1]
    kuukaudesta = nyt.day / paivia * 100

    # Ihanne: budjetin käyttö seuraa kuukauden kulumista.
    poikkeama = abs(kaytetty - kuukaudesta)
    pisteet = max(0.0, 100.0 - poikkeama)
    return {
        "pisteet": int(round(pisteet)),
        "kaytetty_prosentti": round(kaytetty, 1),
        "kuukaudesta_kulunut_prosentti": round(kuukaudesta, 1),
        "selitys": f"Budjetista käytetty {kaytetty:.0f} %, kuukaudesta kulunut {kuukaudesta:.0f} %",
    }


def laske_portfolio_score(salkku: dict, budjetti: dict, markkinatila: dict,
                          tavoiteallokaatio: dict) -> dict:
    """Laskee kokonaispistemäärän ja osatekijät."""
    try:
        positiot = salkku.get("positiot", [])
        osat = {
            "hajautus": _hajautus(positiot),
            "riski": _riski(positiot),
            "allokaatio": _allokaatio(salkku.get("luokkajakauma", {}), tavoiteallokaatio),
            "kassavaranto": _kassavaranto(salkku.get("kateinen", 0.0),
                                          salkku.get("kokonaisarvo", 0.0)),
            "markkinatilanne": _markkinatilanne(markkinatila),
            "budjetti": _budjetti(budjetti),
        }

        kokonais = sum(osat[k]["pisteet"] * PAINOT[k] for k in PAINOT)
        kokonais = int(round(max(0, min(100, kokonais))))

        if kokonais >= 80:
            arvio, vari = "Erinomainen", "success"
        elif kokonais >= 65:
            arvio, vari = "Hyvä", "info"
        elif kokonais >= 50:
            arvio, vari = "Kohtalainen", "warning"
        else:
            arvio, vari = "Heikko", "danger"

        # Heikoin osatekijä nostetaan esiin toimenpiteitä varten
        heikoin = min(osat.items(), key=lambda kv: kv[1]["pisteet"])

        return {
            "ok": True,
            "pisteet": kokonais,
            "arvio": arvio,
            "vari": vari,
            "osatekijat": osat,
            "painot": PAINOT,
            "heikoin_osatekija": {"nimi": heikoin[0], **heikoin[1]},
        }

    except Exception as e:
        logger.error(f"Portfolio Score -laskenta epäonnistui: {e}", exc_info=True)
        return {"ok": False, "virhe": str(e), "pisteet": None}
