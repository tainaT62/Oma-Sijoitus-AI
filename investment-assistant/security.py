"""
Sovelluksen tietoturvakerros: kirjautuminen, istunnon suojaus ja CSRF.

Suunnitteluperiaate: FAIL CLOSED.
Kaikki reitit vaativat kirjautumisen, ellei niitä ole erikseen merkitty
julkisiksi. Uusi reitti on siis automaattisesti suojattu – suojauksen
unohtaminen ei ole mahdollista.

Sovellus on yhden käyttäjän henkilökohtainen työkalu, joten käytössä on
yksi salasana. Salasanaa ei tallenneta selkotekstinä missään: ympäristössä
on vain werkzeug-tiiviste.
"""

import hmac
import secrets
import time
from functools import wraps

from flask import (
    jsonify, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash

from config import config
from utils.logger import logger


# Reitit, jotka toimivat ilman kirjautumista. Pidä lista minimissään.
JULKISET_ENDPOINTIT = {
    "kirjaudu",      # kirjautumissivu ja -lomake
    "static",        # tyylitiedostot
}

# Istuntoavaimet
ISTUNTO_KIRJAUTUNUT = "kirjautunut"
ISTUNTO_CSRF = "csrf_token"

# Tilaa muuttavat metodit, jotka vaativat CSRF-tarkistuksen.
MUUTTAVAT_METODIT = {"POST", "PUT", "PATCH", "DELETE"}


# ─── Kirjautumisyritysten rajoitus ────────────────────────────
# Prosessikohtainen muistinvarainen laskuri. Riittää yhden workerin
# ajossa (ks. gunicorn.conf.py); usealla workerilla raja on
# worker-kohtainen.
_yritykset: dict = {}


def _asiakkaan_tunniste() -> str:
    """Palauttaa pyytäjän IP:n rajoitusta varten."""
    # Huom: sovellus ei luota X-Forwarded-For-otsakkeeseen, koska sitä voi
    # väärentää. Kun käänteisproxy otetaan käyttöön (Phase 3C), tämä on
    # päivitettävä käyttämään ProxyFixiä.
    return request.remote_addr or "tuntematon"


def onko_lukittu() -> int:
    """Palauttaa jäljellä olevat lukitussekunnit, tai 0 jos ei lukittu."""
    tiedot = _yritykset.get(_asiakkaan_tunniste())
    if not tiedot:
        return 0
    lukittu_asti = tiedot.get("lukittu_asti", 0)
    jaljella = int(lukittu_asti - time.time())
    return jaljella if jaljella > 0 else 0


def kirjaa_epaonnistuminen() -> None:
    tunniste = _asiakkaan_tunniste()
    tiedot = _yritykset.setdefault(tunniste, {"maara": 0, "lukittu_asti": 0})
    tiedot["maara"] += 1
    if tiedot["maara"] >= config.LOGIN_MAX_ATTEMPTS:
        tiedot["lukittu_asti"] = time.time() + config.LOGIN_LOCKOUT_MINUTES * 60
        tiedot["maara"] = 0
        logger.warning(
            f"Kirjautuminen lukittu {config.LOGIN_LOCKOUT_MINUTES} min "
            f"(liikaa yrityksiä): {tunniste}"
        )


def _nollaa_yritykset() -> None:
    _yritykset.pop(_asiakkaan_tunniste(), None)


# ─── Salasanan tarkistus ──────────────────────────────────────


def tarkista_salasana(salasana: str) -> bool:
    """
    Vertaa salasanaa tallennettuun tiivisteeseen.
    check_password_hash on vakioaikainen, joten se ei vuoda tietoa
    ajoituksen kautta.
    """
    if not config.APP_PASSWORD_HASH or not salasana:
        return False
    try:
        return check_password_hash(config.APP_PASSWORD_HASH, salasana)
    except Exception as e:
        logger.error(f"Salasanan tarkistus epäonnistui: {e}")
        return False


def kirjaa_sisaan() -> None:
    """
    Merkitsee istunnon kirjautuneeksi.
    Istunto tyhjennetään ensin, jotta istunnon kiinnitys (session
    fixation) ei ole mahdollista.
    """
    session.clear()
    session[ISTUNTO_KIRJAUTUNUT] = True
    session[ISTUNTO_CSRF] = secrets.token_urlsafe(32)
    session.permanent = True


def kirjaa_ulos() -> None:
    session.clear()


def on_kirjautunut() -> bool:
    return session.get(ISTUNTO_KIRJAUTUNUT) is True


# ─── CSRF ─────────────────────────────────────────────────────


def hae_csrf_token() -> str:
    """Palauttaa istunnon CSRF-tokenin ja luo sen tarvittaessa."""
    token = session.get(ISTUNTO_CSRF)
    if not token:
        token = secrets.token_urlsafe(32)
        session[ISTUNTO_CSRF] = token
    return token


def _csrf_kelpaa() -> bool:
    """
    Tarkistaa CSRF-tokenin otsakkeesta tai lomakekentästä.
    SameSite=Lax estää jo suurimman osan hyökkäyksistä; tämä on
    toinen suojakerros.
    """
    odotettu = session.get(ISTUNTO_CSRF)
    if not odotettu:
        return False
    saatu = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    return bool(saatu) and hmac.compare_digest(str(odotettu), str(saatu))


# ─── Vastaukset ───────────────────────────────────────────────


def _haluaa_jsonia() -> bool:
    """
    Päättelee, odottaako kutsuja JSONia vai HTML-sivua.
    API-kutsut saavat 401 + JSON, selain ohjataan kirjautumissivulle.
    """
    if request.path.startswith("/api/"):
        return True
    if request.accept_mimetypes.best == "application/json":
        return True
    return not request.accept_mimetypes.accept_html


def _ei_oikeutta(viesti: str, koodi: int):
    """Palauttaa oikeanmuotoisen vastauksen pyynnön tyypin mukaan."""
    if _haluaa_jsonia():
        return jsonify({"ok": False, "virhe": viesti}), koodi
    return redirect(url_for("kirjaudu", seuraava=request.path))


# ─── Suojaus ──────────────────────────────────────────────────


def rekisteroi_suojaus(app) -> None:
    """
    Kytkee koko sovelluksen suojauksen.

    before_request ajetaan JOKAISELLE pyynnölle, myös reiteille jotka
    lisätään myöhemmin – siksi suojaus on oletuksena päällä.
    """

    @app.before_request
    def _vaadi_kirjautuminen():
        # Tuntematon reitti -> anna Flaskin palauttaa 404 normaalisti.
        if request.endpoint is None:
            return None

        if request.endpoint in JULKISET_ENDPOINTIT:
            return None

        if not on_kirjautunut():
            return _ei_oikeutta("Kirjautuminen vaaditaan", 401)

        # Kirjautunut: tarkista CSRF tilaa muuttavista pyynnöistä.
        if request.method in MUUTTAVAT_METODIT and not _csrf_kelpaa():
            logger.warning(
                f"CSRF-tarkistus epäonnistui: {request.method} {request.path}"
            )
            return jsonify({"ok": False, "virhe": "CSRF-token puuttuu tai virheellinen"}), 403

        return None

    @app.after_request
    def _turvaotsakkeet(vastaus):
        # Perusotsakkeet. Nämä eivät korvaa TLS:ää (Phase 3C).
        vastaus.headers.setdefault("X-Content-Type-Options", "nosniff")
        vastaus.headers.setdefault("X-Frame-Options", "DENY")
        vastaus.headers.setdefault("Referrer-Policy", "no-referrer")
        vastaus.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        # Selain ei saa välimuistittaa salkkudataa.
        if request.path.startswith("/api/"):
            vastaus.headers.setdefault("Cache-Control", "no-store")
        return vastaus


def kirjautuminen_vaaditaan(f):
    """
    Yksittäisen reitin suojaus. Kokonaissuojaus hoidetaan
    rekisteroi_suojaus():lla; tämä on saatavilla poikkeustapauksia varten.
    """
    @wraps(f)
    def kaare(*args, **kwargs):
        if not on_kirjautunut():
            return _ei_oikeutta("Kirjautuminen vaaditaan", 401)
        return f(*args, **kwargs)
    return kaare
