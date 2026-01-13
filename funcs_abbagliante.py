"""
Modulo per il rilevamento del centro massimo del faro abbagliante.

Questo modulo implementa l'algoritmo di rilevamento del punto centrale
del pattern luminoso del faro abbagliante tramite calcolo del centro di massa.
"""

import numpy as np
import cv2
import logging
from typing import Tuple, Optional
from utils import get_colore, disegna_pallino
from funcs_misc import is_punto_ok


def trova_contorni_abbagliante(image_input: np.ndarray,
                                image_output: np.ndarray,
                                cache: dict) -> Tuple[np.ndarray, Optional[Tuple[int, int]], Tuple[float, float, float]]:
    """
    Rileva il centro del pattern luminoso del faro abbagliante tramite centro di massa.

    Il faro abbagliante ha un pattern sostanzialmente circolare/ellittico
    concentrato. L'algoritmo normalizza l'immagine, applica una soglia per
    isolare il picco luminoso, e calcola il centro di massa (centroid) della
    regione risultante.

    Args:
        image_input: Immagine di input in scala di grigi
        image_output: Immagine su cui disegnare i risultati
        cache: Dizionario con cache e configurazione

    Returns:
        Tuple con (image_output, punto_centrale, angoli_yaw_pitch_roll)
        punto_centrale può essere None se non trovato
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

    # Mostra info debug se richiesto
    if cache["DEBUG"]:
        msg = f"clipping: {nclip}%, Max level: {np.max(image_input)}, threshold: {threshold_level}"
        cv2.putText(image_output, msg, (5, 20),
                   cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)

    # ============================
    # CALCOLO CENTRO DI MASSA
    # ============================

    moments = cv2.moments(image_tmp, binaryImage=True)

    # Evita divisione per zero
    if moments['m00'] == 0:
        logging.error("punto abbagliante non trovato - m00=0")
        return image_output, None, (0, 0, 0)

    x_cms = int(moments['m10'] / moments['m00'])
    y_cms = int(moments['m01'] / moments['m00'])

    # ============================
    # DISEGNO CONTORNI
    # ============================

    try:
        contours, _ = cv2.findContours(image_tmp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key=cv2.contourArea)
        cv2.drawContours(image_output, [contour], -1, get_colore('blue'), 1, cv2.LINE_AA)
    except Exception as e:
        logging.error(f"trova_contorni_abbagliante - errore drawContours: {e}")

    # ============================
    # DISEGNO PUNTO CENTRALE
    # ============================

    # Verifica se il punto è nel range valido
    ptok = is_punto_ok((x_cms, y_cms), cache)
    color = 'green' if ptok else 'red'
    disegna_pallino(image_output, (x_cms, y_cms), 6, color, -1)

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

    return image_output, (x_cms, y_cms), (yaw_deg, pitch_deg, roll_deg)
