"""
Modulo per il rilevamento del centro massimo del faro abbagliante.

Questo modulo implementa l'algoritmo di rilevamento del punto centrale
del pattern luminoso del faro abbagliante tramite calcolo del centro di massa.

Separazione tra detection e rendering:
- La funzione trova_contorni_abbagliante() ritorna solo i dati rilevati
- La funzione draw_detection_results() di fit_lines.py gestisce il rendering
"""

import numpy as np
import cv2
import logging
from typing import Tuple, Optional
from utils import get_colore


def trova_contorni_abbagliante(image_input: np.ndarray,
                                cache: dict) -> dict:
    """
    Rileva il centro del pattern luminoso del faro abbagliante tramite centro di massa.

    Il faro abbagliante ha un pattern sostanzialmente circolare/ellittico
    concentrato. L'algoritmo normalizza l'immagine, applica una soglia per
    isolare il picco luminoso, e calcola il centro di massa (centroid) della
    regione risultante.

    Args:
        image_input: Immagine di input in scala di grigi
        cache: Dizionario con cache e configurazione

    Returns:
        Dizionario con:
        - 'tipo': 'abbagliante'
        - 'punto': (x_cms, y_cms) o None
        - 'linee': [] - abbagliante non ha linee
        - 'contorni': lista di contorni da cv2.findContours
        - 'punti_fitted': [] - abbagliante non ha punti fitted
        - 'angoli': (yaw, pitch, roll)
        - 'debug_info': dict con info debug (clipping, threshold, etc.)
    """
    AREA = image_input.shape[0] * image_input.shape[1]
    LEVEL = 0.97  # Percentile per soglia automatica (non usato, hardcoded a 210)

    # Calcola percentuale pixel saturati
    nclip = np.sum(image_input >= 255) / AREA

    # ============================
    # PREPROCESSING
    # ============================

    image_tmp = image_input.copy()
    cv2.normalize(image_input, image_tmp, 0, 255, cv2.NORM_MINMAX)

    # Soglia fissa per isolare il picco luminoso
    threshold_level = 210
    image_tmp[image_tmp < threshold_level] = 0

    # ============================
    # CALCOLO CENTRO DI MASSA
    # ============================

    moments = cv2.moments(image_tmp, binaryImage=True)

    # Evita divisione per zero
    if moments['m00'] == 0:
        logging.error("punto abbagliante non trovato - m00=0")
        return {
            'tipo': 'abbagliante',
            'punto': None,
            'linee': [],
            'contorni': [],
            'punti_fitted': [],
            'angoli': (0, 0, 0),
            'debug_info': {
                'clipping': nclip,
                'max_level': np.max(image_input),
                'threshold': threshold_level
            }
        }

    x_cms = int(moments['m10'] / moments['m00'])
    y_cms = int(moments['m01'] / moments['m00'])

    # ============================
    # ESTRAZIONE CONTORNI
    # ============================

    contorni = []
    try:
        contours, _ = cv2.findContours(image_tmp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            contorni = contours
    except Exception as e:
        logging.error(f"trova_contorni_abbagliante - errore findContours: {e}")

    # ============================
    # CALCOLO ANGOLI
    # ============================

    try:
        dx = (x_cms - cache['config']['width'] / 2) / cache['stato_comunicazione']['qin']
        dy = (y_cms - cache['config']['height'] / 2 + cache['stato_comunicazione']['inclinazione']) / cache['stato_comunicazione']['qin']
        yaw_deg = np.degrees(np.arctan2(dx, 25))      # Rotazione orizzontale (destra/sinistra)
        pitch_deg = np.degrees(np.arctan2(dy, 25))    # Rotazione verticale (alto/basso)
        roll_deg = 0                                   # Abbagliante non ha roll
    except:
        yaw_deg = 0
        pitch_deg = 0
        roll_deg = 0

    return {
        'tipo': 'abbagliante',
        'punto': (x_cms, y_cms),
        'linee': [],
        'contorni': contorni,
        'punti_fitted': [],
        'angoli': (yaw_deg, pitch_deg, roll_deg),
        'debug_info': {
            'clipping': nclip,
            'max_level': np.max(image_input),
            'threshold': threshold_level
        }
    }
