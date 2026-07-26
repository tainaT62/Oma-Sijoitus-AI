"""
Lokitusjärjestelmä - kaikki virheet ja tapahtumat kirjataan tiedostoon ja konsoliin.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logger(name: str = "sijoitusassistentti") -> logging.Logger:
    """
    Luo ja konfiguroi lokitusjärjestelmä.
    Kirjaa viestit sekä konsoliin että lokitiedostoon.
    """
    logger = logging.getLogger(name)

    # Älä lisää handlereja uudelleen, jos ne on jo asetettu
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Luo logs-hakemisto jos sitä ei ole
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Lokitiedoston muoto
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Konsoliloki (INFO-taso ja ylöspäin)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Tiedostoloki (DEBUG-taso ja ylöspäin, kierrätys 5MB, max 3 tiedostoa)
    log_file = os.path.join(log_dir, "app.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Erillinen virheloki kriittisille virheille
    error_log_file = os.path.join(log_dir, "errors.log")
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    return logger


# Oletusloggeri
logger = setup_logger()
