"""
Päivittäisen Telegram-raportin muotoilu.

Vastuu on vain esitys: kaikki luvut tulevat sellaisenaan salkkupalvelulta,
suositusmoottorilta ja watchlistilta. Täällä ei lasketa sijoituslogiikkaa.

Telegramin sendMessage hyväksyy enintään 4096 merkkiä. Raportti rakennetaan
osissa ja lyhennetään hallitusti, jos se ylittää rajan – viestiä ei koskaan
katkaista kesken kohteen.
"""

import html
from datetime import datetime
from typing import Optional

from config import config

RAJA = 4096
VARAUS = 120          # tilaa alatunnisteelle ja lyhennysmerkinnälle

# Suositusluokkien esitys
KUVAKKEET = {"BUY": "🟢", "HOLD": "⚪", "REDUCE": "🟠", "SELL": "🔴"}

# Omaisuusluokkien otsikot raportissa, esitysjärjestyksessä
LUOKKAOTSIKOT = [
    ("krypto", "CRYPTO"),
    ("etf", "ETF"),
    ("osake", "STOCKS"),
    ("rahasto", "FUNDS"),
]


def e(x) -> str:
    return html.escape(str(x if x is not None else "–"))


def _raha(arvo: Optional[float], valuutta: Optional[str] = None) -> str:
    if arvo is None:
        return "–"
    val = valuutta or config.BASE_CURRENCY
    merkki = {"EUR": "€", "USD": "$"}.get(val, val)
    if merkki in ("€",):
        return f"{arvo:,.2f} {merkki}".replace(",", " ")
    return f"{merkki}{arvo:,.2f}"


def _pros(arvo: Optional[float], etumerkki: bool = True) -> str:
    if arvo is None:
        return "–"
    return f"{arvo:+.1f} %" if etumerkki else f"{arvo:.1f} %"


# ─── Osat ─────────────────────────────────────────────────────


def _otsikko(salkku: dict, sentimentti: dict) -> str:
    fg = sentimentti.get("fear_greed", {})
    rivit = [
        "📈 <b>HENKILÖKOHTAINEN PÄIVÄRAPORTTI</b>",
        f"<i>{datetime.now().strftime('%d.%m.%Y')}</i>",
        "",
        f"Markkinasentimentti: <b>{e(sentimentti.get('kokonaisluokka', '–'))}</b>",
        f"Fear &amp; Greed:      <b>{e(fg.get('arvo', '–'))}</b>"
        + (f" ({e(fg.get('luokka'))})" if fg.get("luokka") else ""),
        f"Salkun arvo:         <b>{_raha(salkku.get('kokonaisarvo'))}</b>",
        f"Käteinen:            <b>{_raha(salkku.get('kateinen'))}</b>",
    ]
    positioita = salkku.get("positioita")
    if positioita:
        rivit.append(f"Positioita:          <b>{positioita}</b>")
    return "\n".join(rivit)


def _score_osio(data: dict) -> str:
    """Portfolio Score raportin alkuun."""
    sc = data.get("portfolio_score") or {}
    if not sc.get("ok"):
        return ""
    palkki_taydet = round(sc["pisteet"] / 10)
    palkki = "█" * palkki_taydet + "░" * (10 - palkki_taydet)
    rivit = [
        f"<b>PORTFOLIO SCORE  {sc['pisteet']} / 100</b>",
        f"<code>{palkki}</code>  {e(sc.get('arvio'))}",
    ]
    osat = sc.get("osatekijat", {})
    if osat:
        nimet = {"hajautus": "Hajautus", "riski": "Riski", "allokaatio": "Allokaatio",
                 "kassavaranto": "Kassa", "markkinatilanne": "Markkina", "budjetti": "Budjetti"}
        rivit.append(" · ".join(f"{nimet.get(k, k)} {v['pisteet']}"
                                for k, v in osat.items()))
    heikoin = sc.get("heikoin_osatekija")
    if heikoin:
        rivit.append(f"<i>Heikoin: {e(heikoin.get('selitys'))}</i>")
    return "\n".join(rivit)


def _markkinaosio(data: dict) -> str:
    """Markkinakatsaus: sentimentti, F&G, riski ja yhteenvetokappale."""
    sent = data.get("sentimentti", {})
    mt = data.get("markkinatila", {})
    fg = sent.get("fear_greed", {})
    rivit = [
        "═══════════",
        "<b>MARKKINAT</b>",
        "",
        f"Sentimentti:   {e(sent.get('kokonaisluokka', '–'))}",
        f"Fear &amp; Greed: {e(fg.get('arvo', '–'))}"
        + (f" ({e(fg.get('luokka'))})" if fg.get("luokka") else ""),
        f"Markkinariski: {e(mt.get('riskitaso', '–'))}",
    ]
    katsaus = data.get("markkinakatsaus")
    if katsaus:
        rivit += ["", f"<i>{e(katsaus)}</i>"]
    return "\n".join(rivit)


def _allokaatio_osio(data: dict) -> str:
    """Nykyinen allokaatio vs. tavoite, yli-/alipainot selitettynä."""
    sc = data.get("portfolio_score") or {}
    erittely = (sc.get("osatekijat", {}).get("allokaatio", {}) or {}).get("erittely")
    if not erittely:
        return ""
    nimet = {"etf": "ETF", "osake": "Osakkeet", "krypto": "Krypto", "rahasto": "Rahastot"}
    rivit = ["═══════════", "<b>ALLOKAATIO</b>", ""]
    for luokka, d in erittely.items():
        merkki = {"ylipaino": "▲", "alipaino": "▼", "tavoitteessa": "●"}.get(d["tila"], "·")
        rivit.append(
            f"{merkki} {nimet.get(luokka, luokka):9} {d['nyt_prosentti']:>5.1f} %"
            f"  (tavoite {d['tavoite_prosentti']:.0f} %, {d['poikkeama']:+.1f} pp)"
        )
    poikkeavat = [f"{nimet.get(k, k)} {v['tila']}"
                  for k, v in erittely.items() if v["tila"] != "tavoitteessa"]
    if poikkeavat:
        rivit += ["", f"<i>{e(', '.join(poikkeavat))}</i>"]
    return "\n".join(rivit)


def _sync_osio(data: dict) -> str:
    """Automaattisesti havaitut salkkumuutokset."""
    sync = data.get("sync") or {}
    tapahtumat = sync.get("tapahtumat") or []
    if not tapahtumat:
        return ""
    rivit = ["═══════════", "<b>HAVAITUT MUUTOKSET</b>", ""]
    for t in tapahtumat[:6]:
        merkki = "🟢" if t["tapahtuma"] in ("OSTO", "LISAYS") else "🔴"
        arvo = f" {_raha(t.get('arvo'))}" if t.get("arvo") else ""
        rivit.append(f"{merkki} {e(t['tapahtuma'])} {e(t['symboli'])}{arvo}")
        rivit.append(f"   <i>{e(t['hinta_lahde'])}"
                     + (", kirjattu budjettiin" if t.get("kirjattu_budjettiin") else "")
                     + "</i>")
    if sync.get("budjettiin_kirjattu"):
        rivit += ["", f"Budjettiin kirjattu: <b>{_raha(sync['budjettiin_kirjattu'])}</b>"]
    return "\n".join(rivit)


def _budjettiosio(data: dict) -> str:
    """Kuukausibudjetti, allokaatio ja käteistilanne."""
    k = data.get("kassatilanne")
    if not k:
        return ""
    a = data.get("allokaatio", {})
    m = data.get("markkinatila", {})

    rivit = [
        "═══════════",
        "<b>KUUKAUSIBUDJETTI</b>",
        "",
        f"Budjetti:              {_raha(k['kuukausibudjetti'])}",
        f"Sijoitettu tässä kuussa: {_raha(k['sijoitettu_taman_kuun'])}",
        f"Jäljellä:              <b>{_raha(k['jaljella_budjetista'])}</b>",
        "",
        f"Käteinen nyt:          {_raha(k['kateinen_nyt'])}",
        f"Ehdotetut ostot:       <b>{_raha(k['ehdotetut_ostot'])}</b>",
        f"Varaus:                {_raha(k['varaus'])}",
        f"Käteinen ostojen jälkeen: {_raha(k['kateinen_ostojen_jalkeen'])}",
    ]

    if a.get("osuudet_prosentteina"):
        jako = " · ".join(f"{nimi} {osuus:.0f} %"
                          for nimi, osuus in a["osuudet_prosentteina"].items())
        rivit += ["", f"Allokaatio: {e(jako)}"]
    if a.get("peruste"):
        rivit.append(f"<i>{e(a['peruste'])}</i>")
    if m.get("riskitaso") and m["riskitaso"] != "normaali":
        rivit.append(f"<i>Markkinariski: {e(m['riskitaso'])}</i>")
    if not a.get("ostot_sallittu", True):
        rivit.append("<b>Ei ostosuosituksia tänään.</b>")

    return "\n".join(rivit)


def _suositus_lohko(s: dict) -> str:
    """Yksi suositus raportissa."""
    kuvake = KUVAKKEET.get(s["toiminto"], "•")
    rivit = [f"{kuvake} <b>{e(s['toiminto'])}</b> — <b>{e(s.get('nimi') or s['symboli'])}</b>"]

    if s["toiminto"] == "BUY" and s.get("ehdotettu_summa"):
        rivit.append(f"Ehdotettu summa: <b>{_raha(s['ehdotettu_summa'], s.get('valuutta'))}</b>")
        if s.get("korvaava"):
            rivit.append("<i>Korvaava osto – rahoitetaan myynnistä, ei kuukausibudjetista.</i>")
    if s["toiminto"] == "REDUCE" and s.get("myyntiosuus_prosentti"):
        rivit.append(f"Myy: <b>{s['myyntiosuus_prosentti']} %</b> positiosta")

    mittarit = []
    if s.get("luottamus_prosentti") is not None:
        mittarit.append(f"Luottamus {s['luottamus_prosentti']} %")
    if s.get("ai_pisteet") is not None:
        mittarit.append(f"AI Score {s['ai_pisteet']}/100")
    if s.get("riski"):
        mittarit.append(e(s["riski"]))
    if mittarit:
        rivit.append(" | ".join(mittarit))

    tiedot = []
    if s.get("osuus_prosentti"):
        tiedot.append(f"osuus {s['osuus_prosentti']:.1f} %")
    if s.get("tuotto_prosentti") is not None:
        tiedot.append(f"tuotto {s['tuotto_prosentti']:+.1f} %")
    if s.get("volatiliteetti_prosentti") is not None:
        tiedot.append(f"vol {s['volatiliteetti_prosentti']:.1f} %")
    if tiedot:
        rivit.append("<i>" + e(" · ".join(tiedot)) + "</i>")

    if s.get("stop_loss_ehdotus") or s.get("take_profit_ehdotus"):
        rivit.append(
            f"SL {_raha(s.get('stop_loss_ehdotus'), 'USD')} · "
            f"TP {_raha(s.get('take_profit_ehdotus'), 'USD')}"
        )

    if s.get("perustelut"):
        rivit.append("Perustelu:")
        for p in s["perustelut"][:3]:
            rivit.append(f"• {e(p)}")

    if not s.get("tekninen_saatavilla", True):
        rivit.append("<i>Ei hintahistoriaa – arvio perustuu position tunnuslukuihin.</i>")

    return "\n".join(rivit)


def _luokkaosio(otsikko: str, suositukset: list) -> str:
    if not suositukset:
        return ""
    osat = [f"═══════════\n<b>{e(otsikko)}</b>", ""]
    osat.append("\n\n".join(_suositus_lohko(s) for s in suositukset))
    return "\n".join(osat)


def _watchlist_osio(mahdollisuudet: list) -> str:
    if not mahdollisuudet:
        return ""
    rivit = ["═══════════", "<b>WATCHLIST</b>", ""]
    for i, m in enumerate(mahdollisuudet[:5], 1):
        rivit.append(f"{i}. <b>{e(m.get('nimi') or m['symboli'])}</b>")
        osat = []
        if m.get("nousuvara_prosentti") is not None:
            osat.append(f"nousuvara {_pros(m['nousuvara_prosentti'])}")
        if m.get("volatiliteetti_prosentti") is not None:
            osat.append(f"riski {m['volatiliteetti_prosentti']:.1f} % vol")
        if m.get("luottamus_prosentti") is not None:
            osat.append(f"luottamus {m['luottamus_prosentti']} %")
        if osat:
            rivit.append("   " + e(" · ".join(osat)))
    return "\n".join(rivit)


def _alatunniste(data: dict) -> str:
    rivit = ["═══════════"]
    ibkr = data.get("salkku", {}).get("lahteet", {}).get("ibkr", {})
    if ibkr.get("on_mock"):
        rivit.append("⚠️ <i>IBKR: esimerkkidata – osake- ja ETF-luvut eivät ole todellisia.</i>")
    rivit.append("<i>Automaattinen analyysi, ei sijoitusneuvontaa.</i>")
    rivit.append("<i>Järjestelmä ei tee toimeksiantoja – päätökset teet sinä.</i>")
    return "\n".join(rivit)


# ─── Koko raportti ────────────────────────────────────────────


def muotoile_paivaraportti(data: dict) -> str:
    """
    Rakentaa päiväraportin. `data` on salkku_suositusmoottori-tulos,
    johon on lisätty avain `watchlist`.
    """
    salkku = data.get("salkku", {})
    sentimentti = data.get("sentimentti", {})
    suositukset = data.get("suositukset", [])

    score = _score_osio(data)
    lohkot = [(_otsikko(salkku, sentimentti) + ("\n\n" + score if score else ""))]
    for osio in (_markkinaosio(data), _allokaatio_osio(data),
                 _sync_osio(data), _budjettiosio(data)):
        if osio:
            lohkot.append(osio)
    budjetti = _budjettiosio(data)

    # Toimenpiteet ensin: BUY, SELL, REDUCE ennen HOLDia.
    jarjestys = {"BUY": 0, "SELL": 1, "REDUCE": 2, "HOLD": 3}
    for luokka, otsikko in LUOKKAOTSIKOT:
        joukko = [s for s in suositukset if s.get("luokka") == luokka]
        joukko.sort(key=lambda s: (jarjestys.get(s["toiminto"], 9),
                                   -(s.get("luottamus_prosentti") or 0)))
        osio = _luokkaosio(otsikko, joukko)
        if osio:
            lohkot.append(osio)

    wl = _watchlist_osio(data.get("watchlist", []))
    if wl:
        lohkot.append(wl)

    alatunniste = _alatunniste(data)

    # Pituudenhallinta: pudotetaan ensin watchlist, sitten HOLD-kohteet.
    viesti = "\n\n".join(lohkot + [alatunniste])
    if len(viesti) <= RAJA - VARAUS:
        return viesti

    if wl and wl in lohkot:
        lohkot.remove(wl)
        viesti = "\n\n".join(lohkot + ["<i>(watchlist jätetty pois pituuden vuoksi)</i>", alatunniste])
        if len(viesti) <= RAJA - VARAUS:
            return viesti

    # Karsi HOLD-suositukset: ne eivät vaadi toimenpiteitä.
    toimenpiteet = [s for s in suositukset if s["toiminto"] != "HOLD"]
    hold_maara = len(suositukset) - len(toimenpiteet)
    lohkot = [(_otsikko(salkku, sentimentti) + ("\n\n" + score if score else ""))]
    for osio in (_markkinaosio(data), _allokaatio_osio(data), _budjettiosio(data)):
        if osio:
            lohkot.append(osio)
    for luokka, otsikko in LUOKKAOTSIKOT:
        joukko = [s for s in toimenpiteet if s.get("luokka") == luokka]
        joukko.sort(key=lambda s: (jarjestys.get(s["toiminto"], 9),
                                   -(s.get("luottamus_prosentti") or 0)))
        osio = _luokkaosio(otsikko, joukko)
        if osio:
            lohkot.append(osio)
    if hold_maara:
        lohkot.append(f"<i>({hold_maara} HOLD-kohdetta jätetty pois pituuden vuoksi)</i>")

    viesti = "\n\n".join(lohkot + [alatunniste])
    if len(viesti) <= RAJA:
        return viesti

    # Viimeinen keino: kova katkaisu rivin kohdalta.
    katkaistu = viesti[: RAJA - VARAUS].rsplit("\n", 1)[0]
    return katkaistu + "\n\n<i>… raportti katkaistu pituuden vuoksi.</i>"


def muotoile_virheraportti(virhe: str) -> str:
    return (
        "⚠️ <b>Päivittäinen analyysi epäonnistui</b>\n"
        f"<i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>\n\n"
        f"<code>{html.escape(str(virhe)[:400])}</code>\n\n"
        "Tänään ei lähetetä suosituksia. Tarkista lokit."
    )
