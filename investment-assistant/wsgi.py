"""
WSGI-sisääntulopiste tuotantokäyttöön.

Käynnistys:
    gunicorn --config gunicorn.conf.py wsgi:sovellus

Flaskin oma kehityspalvelin (app.py:n __main__-lohko) on tarkoitettu
VAIN paikalliseen kehitykseen – sitä ei käytetä tuotannossa.
"""

from config import config

# Werkzeugin debuggeri sallii mielivaltaisen koodin ajon selaimesta.
# Tuotantoajossa se ei saa olla päällä missään olosuhteissa, joten
# tarkistus tehdään ennen sovelluksen tuontia.
if config.DEBUG:
    raise RuntimeError(
        "\n\nKÄYNNISTYS KESKEYTETTY: FLASK_DEBUG=true tuotantoajossa.\n"
        "  Werkzeugin debuggeri mahdollistaa koodin ajon etänä.\n"
        "  Aseta FLASK_DEBUG=false.\n"
    )

from app import app as sovellus

# Gunicorn etsii oletuksena nimeä `application`.
application = sovellus

__all__ = ["sovellus", "application"]
