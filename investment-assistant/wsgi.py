"""
WSGI-sisääntulopiste tuotantokäyttöön.

Käynnistys:
    gunicorn --config gunicorn.conf.py wsgi:sovellus

Flaskin oma kehityspalvelin (app.py:n __main__-lohko) on tarkoitettu
VAIN paikalliseen kehitykseen – sitä ei käytetä tuotannossa.
"""

from app import app as sovellus

# Gunicorn etsii oletuksena nimeä `application`.
application = sovellus

__all__ = ["sovellus", "application"]
