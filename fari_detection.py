"""
Modulo unificato per il rilevamento di pattern luminosi dei fari.

Questo modulo gestisce il rilevamento (detection) e rendering di tutti i tipi di faro:
- Anabbagliante: pattern cut-off a 2 linee spezzate (15°/15°)
- Fendinebbia: pattern cut-off a 1 linea orizzontale
- Abbagliante: punto centrale luminoso (centro di massa)

Architettura:
- Funzioni detect_*() ritornano dizionari con risultati (no rendering)
- Funzione draw_results() gestisce il rendering unificato per tutti i tipi
"""

import cv2
import numpy as np
import logging
from typing import Tuple, Optional, List, Dict
from scipy.optimize import curve_fit
from funcs_misc import is_punto_ok


# ============================================================================
# HELPER FUNCTIONS - Preprocessing e modelli matematici
# ============================================================================

def preprocess(gray: np.ndarray,
               blur_ksize: int = 5,
               canny_lo: int = 40,
               canny_hi: int = 120) -> Tuple[np.ndarray, np.ndarray]:
    """
    Preprocessing dell'immagine: blur + threshold + edge detection.

    Args:
        gray: Immagine in scala di grigi
        blur_ksize: Dimensione kernel per GaussianBlur
        canny_lo: Soglia bassa per Canny
        canny_hi: Soglia alta per Canny

    Returns:
        Tuple con (edges, binary)
    """
    blur = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)
    _, binary = cv2.threshold(blur, 25, 255, cv2.THRESH_BINARY)

    # Rimuovi bordi per evitare rumore
    binary[0:5, :] = 0
    binary[-5:, :] = 0
    binary[:, 0:5] = 0
    binary[:, -5:] = 0

    edges = cv2.Canny(binary, canny_lo, canny_hi, apertureSize=3)

    return edges, binary


def extract_contour_points(edges: np.ndarray) -> Tuple[np.ndarray, list]:
    """
    Estrae i punti del contorno più grande dall'immagine degli edge.

    Args:
        edges: Immagine con edge detection

    Returns:
        Tuple con (punti_contorno, lista_contorni)

    Raises:
        ValueError: Se non vengono trovati contorni
    """
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise ValueError("No contours found")

    largest = max(contours, key=cv2.contourArea)
    pts = np.squeeze(largest)

    return pts.astype(float), contours


def two_lines_model(x: np.ndarray,
                    X0: float, Y0: float,
                    mo: float, mi: float) -> np.ndarray:
    """
    Modello a due linee spezzate per curve fitting.

    Args:
        x: Array di coordinate x
        X0: Coordinata x del punto di giunzione
        Y0: Coordinata y del punto di giunzione
        mo: Pendenza della linea sinistra (outer)
        mi: Pendenza della linea destra (inner)

    Returns:
        Array di coordinate y
    """
    if mi > mo:  # Vincolo: pendenza interna < esterna
        return np.full_like(x, 1e6)

    y = np.where(x <= X0,
                 Y0 + mo * (x - X0),
                 Y0 + mi * (x - X0))
    return y


def one_line_model(x: np.ndarray,
                   X0: float, Y0: float,
                   mo: float) -> np.ndarray:
    """
    Modello a una linea per curve fitting.

    Args:
        x: Array di coordinate x
        X0: Coordinata x del punto di riferimento
        Y0: Coordinata y del punto di riferimento
        mo: Pendenza

    Returns:
        Array di coordinate y
    """
    return mo * (x - X0) + Y0


def calculate_angles(X0: float, Y0: float, mo: float, cache: dict) -> Tuple[float, float, float]:
    """
    Calcola angoli yaw, pitch, roll dal punto rilevato.

    Args:
        X0: Coordinata x del punto
        Y0: Coordinata y del punto
        mo: Pendenza linea
        cache: Dizionario con config e stato comunicazione

    Returns:
        Tuple (yaw_deg, pitch_deg, roll_deg)
    """
    try:
        dx = (X0 - cache['config']['width'] / 2) / cache['stato_comunicazione']['qin']
        dy = (Y0 - cache['config']['height'] / 2 + cache['stato_comunicazione']['inclinazione']) / cache['stato_comunicazione']['qin']
        yaw_deg = np.degrees(np.arctan2(dx, 25))
        pitch_deg = np.degrees(np.arctan2(dy, 25))
        roll_deg = np.degrees(np.arctan(mo))
    except:
        yaw_deg = 0
        pitch_deg = 0
        roll_deg = 0

    return yaw_deg, pitch_deg, roll_deg


# ============================================================================
# DETECTION FUNCTIONS - Rilevamento senza rendering
# ============================================================================

def detect_anabbagliante(image_input: np.ndarray,
                         cache: dict,
                         blur_ksize: int = 5,
                         canny_lo: int = 40,
                         canny_hi: int = 120,
                         ftol: float = 1e-7,
                         xtol: float = 1e-7,
                         maxfev: int = 1000) -> Dict:
    """
    Rileva pattern cut-off anabbagliante (2 linee spezzate).

    Il faro anabbagliante ha un pattern caratteristico con due pendenze diverse
    (sinistra più ripida ~15°, destra più piatta ~15°).

    Args:
        image_input: Immagine in scala di grigi
        cache: Dizionario con cache e configurazione
        blur_ksize: Dimensione kernel blur
        canny_lo: Soglia bassa Canny
        canny_hi: Soglia alta Canny
        ftol: Tolleranza funzione curve_fit
        xtol: Tolleranza parametri curve_fit
        maxfev: Max iterazioni curve_fit

    Returns:
        Dict con 'tipo', 'punto', 'linee', 'contorni', 'punti_fitted', 'angoli', 'params'
    """
    edges, binary = preprocess(image_input, blur_ksize, canny_lo, canny_hi)

    try:
        pts, ctrs = extract_contour_points(edges)

        # Trova estremi contorno
        leftset_upper = pts[np.lexsort((pts[:, 1], pts[:, 0]))]
        rightest_upper = pts[np.lexsort((pts[:, 0], pts[:, 1]))]
        y_h = leftset_upper[0][1]
        x_min = leftset_upper[0][0]
        x_max = rightest_upper[0][0]

        # Inizializza cache se necessario
        if 'margin_auto' not in cache:
            cache['margin_auto'] = 0
            cache['s_err'] = np.inf
            cache['X0'] = 300
            cache['Y0'] = 0
            cache['r_bound'] = x_max

        # Reset cache se autoesposizione convergente
        if cache.get('autoexp_ok', False):
            cache['margin_auto'] = 0
            cache['s_err'] = np.inf
            cache['r_bound'] = x_max

        # Calcola bounds per fitting
        marginl = 10
        left_bound = x_min + marginl
        right_bound = np.minimum(x_max, cache['r_bound']) - marginl

        logging.debug(f"anabbagliante - X0:{cache['X0']}, bounds:[{left_bound}, {right_bound}]")

        # Filtra punti nella ROI
        mask = (pts[:, 0] >= left_bound) & (pts[:, 0] <= right_bound)
        top_pts = pts[mask][pts[mask][:, 1] <= y_h]
        x_data = top_pts[:, 0]
        y_data = top_pts[:, 1]

        # Fitting 2 linee spezzate
        p0 = [np.mean(x_data), np.max(y_data) - 1, -0.01, -1.0]
        bounds = (
            [np.min(x_data), 0.0, -0.5, -np.inf],
            [np.max(x_data), np.max(y_data), 0, 0]
        )

        popt, _ = curve_fit(two_lines_model, x_data, y_data, p0=p0, bounds=bounds,
                           ftol=ftol, xtol=xtol, maxfev=maxfev)
        X0, Y0, mo, mi = popt

        # Salva in cache e calcola angoli
        cache['X0'] = X0
        cache['Y0'] = Y0
        angles = calculate_angles(X0, Y0, mo, cache)

        # Calcola punti linee per rendering
        h, w = image_input.shape
        xs = np.array([0, X0, w])
        ys = two_lines_model(xs, X0, Y0, mo, mi)

        linee = [
            (int(round(xs[0])), int(round(ys[0])), int(round(xs[1])), int(round(ys[1]))),
            (int(round(xs[1])), int(round(ys[1])), int(round(xs[2])), int(round(ys[2])))
        ]

        return {
            'tipo': 'anabbagliante',
            'punto': (X0, Y0),
            'linee': linee,
            'contorni': ctrs,
            'punti_fitted': top_pts,
            'angoli': angles,
            'params': (X0, Y0, mo, mi)
        }

    except Exception as e:
        logging.error(f"Errore detect_anabbagliante: {e}")
        return {
            'tipo': 'anabbagliante',
            'punto': None,
            'linee': [],
            'contorni': [],
            'punti_fitted': np.array([]),
            'angoli': (0, 0, 0),
            'params': (0, 0, 0, 0)
        }


def detect_fendinebbia(image_input: np.ndarray,
                       cache: dict,
                       blur_ksize: int = 5,
                       canny_lo: int = 40,
                       canny_hi: int = 120,
                       ftol: float = 1e-7,
                       xtol: float = 1e-7,
                       maxfev: int = 1000) -> Dict:
    """
    Rileva pattern cut-off fendinebbia (1 linea orizzontale).

    Il faro fendinebbia ha un pattern sostanzialmente piatto orizzontale.

    Args:
        image_input: Immagine in scala di grigi
        cache: Dizionario con cache e configurazione
        blur_ksize: Dimensione kernel blur
        canny_lo: Soglia bassa Canny
        canny_hi: Soglia alta Canny
        ftol: Tolleranza funzione curve_fit
        xtol: Tolleranza parametri curve_fit
        maxfev: Max iterazioni curve_fit

    Returns:
        Dict con 'tipo', 'punto', 'linee', 'contorni', 'punti_fitted', 'angoli', 'params'
    """
    edges, binary = preprocess(image_input, blur_ksize, canny_lo, canny_hi)

    try:
        pts, ctrs = extract_contour_points(edges)

        # Trova estremi contorno (usa tutto lo span orizzontale)
        leftset_upper = pts[np.lexsort((pts[:, 1], pts[:, 0]))]
        y_h = leftset_upper[0][1]
        x_min = np.min(pts[:, 0])
        x_max = np.max(pts[:, 0])

        # Inizializza cache se necessario
        if 'margin_auto' not in cache:
            cache['margin_auto'] = 0
            cache['s_err'] = np.inf
            cache['X0'] = 300
            cache['Y0'] = 0
            cache['r_bound'] = x_max

        # Reset cache se autoesposizione convergente
        if cache.get('autoexp_ok', False):
            cache['margin_auto'] = 0
            cache['s_err'] = np.inf
            cache['r_bound'] = x_max

        # Calcola bounds per fitting
        marginl = 10
        left_bound = x_min + marginl
        right_bound = np.minimum(x_max, cache['r_bound']) - marginl

        logging.debug(f"fendinebbia - X0:{cache['X0']}, bounds:[{left_bound}, {right_bound}]")

        # Filtra punti nella ROI
        mask = (pts[:, 0] >= left_bound) & (pts[:, 0] <= right_bound)
        top_pts = pts[mask][pts[mask][:, 1] <= y_h]
        x_data = top_pts[:, 0]
        y_data = top_pts[:, 1]

        # Fitting 1 linea
        p0 = [np.mean(x_data), np.max(y_data) - 1, -0.01]
        bounds = (
            [np.min(x_data), 0.0, -np.inf],
            [np.max(x_data), np.max(y_data), np.inf]
        )

        popt, _ = curve_fit(one_line_model, x_data, y_data, p0=p0, bounds=bounds,
                           ftol=ftol, xtol=xtol, maxfev=maxfev)
        X0, Y0, mo = popt
        X0 = int((np.max(x_data) + np.min(x_data)) / 2)  # Centro dello span
        mi = 0

        # Salva in cache e calcola angoli
        cache['X0'] = X0
        cache['Y0'] = Y0
        angles = calculate_angles(X0, Y0, mo, cache)

        # Calcola punti linea per rendering
        h, w = image_input.shape
        xs = np.array([0, X0, w])
        ys = two_lines_model(xs, X0, Y0, mo, mi)

        linee = [
            (int(round(xs[0])), int(round(ys[0])), int(round(xs[2])), int(round(ys[2])))
        ]

        return {
            'tipo': 'fendinebbia',
            'punto': (X0, Y0),
            'linee': linee,
            'contorni': ctrs,
            'punti_fitted': top_pts,
            'angoli': angles,
            'params': (X0, Y0, mo, 0)
        }

    except Exception as e:
        logging.error(f"Errore detect_fendinebbia: {e}")
        return {
            'tipo': 'fendinebbia',
            'punto': None,
            'linee': [],
            'contorni': [],
            'punti_fitted': np.array([]),
            'angoli': (0, 0, 0),
            'params': (0, 0, 0, 0)
        }


def detect_abbagliante(image_input: np.ndarray,
                       cache: dict) -> Dict:
    """
    Rileva punto centrale abbagliante tramite centro di massa.

    Il faro abbagliante ha un pattern circolare/ellittico concentrato.
    Algoritmo: normalizza, applica soglia, calcola centro di massa.

    Args:
        image_input: Immagine in scala di grigi
        cache: Dizionario con cache e configurazione

    Returns:
        Dict con 'tipo', 'punto', 'linee', 'contorni', 'punti_fitted', 'angoli', 'debug_info'
    """
    AREA = image_input.shape[0] * image_input.shape[1]
    nclip = np.sum(image_input >= 255) / AREA

    # Preprocessing
    image_tmp = image_input.copy()
    cv2.normalize(image_input, image_tmp, 0, 255, cv2.NORM_MINMAX)

    threshold_level = 210
    image_tmp[image_tmp < threshold_level] = 0

    # Calcolo centro di massa
    moments = cv2.moments(image_tmp, binaryImage=True)

    if moments['m00'] == 0:
        logging.error("detect_abbagliante: punto non trovato (m00=0)")
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

    # Estrai contorni
    contorni = []
    try:
        contours, _ = cv2.findContours(image_tmp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            contorni = contours
    except Exception as e:
        logging.error(f"detect_abbagliante: errore findContours: {e}")

    # Calcola angoli
    try:
        dx = (x_cms - cache['config']['width'] / 2) / cache['stato_comunicazione']['qin']
        dy = (y_cms - cache['config']['height'] / 2 + cache['stato_comunicazione']['inclinazione']) / cache['stato_comunicazione']['qin']
        yaw_deg = np.degrees(np.arctan2(dx, 25))
        pitch_deg = np.degrees(np.arctan2(dy, 25))
        roll_deg = 0
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


# ============================================================================
# RENDERING FUNCTION - Disegno unificato per tutti i tipi
# ============================================================================

def draw_results(image_output: np.ndarray,
                 results: Dict,
                 cache: dict) -> np.ndarray:
    """
    Disegna i risultati del rilevamento sull'immagine.

    Funzione unificata per tutti i tipi di faro (anabbagliante, fendinebbia, abbagliante).
    Gestisce automaticamente 3 livelli di colore in base a is_punto_ok():
    - Verde: punto dentro la croce (ok)
    - Giallo: punto poco fuori (entro 2×TOH/TOV - warning)
    - Rosso: punto molto fuori (oltre 2×TOH/TOV - error)

    Args:
        image_output: Immagine su cui disegnare
        results: Dizionario risultati da detect_*()
        cache: Dizionario con cache e configurazione

    Returns:
        Immagine con risultati disegnati
    """
    # Determina colore PRIMA in base a is_punto_ok con 3 livelli
    punto = results.get('punto')
    if punto is not None:
        ptok_result = is_punto_ok(punto, cache)
        status = ptok_result['status']

        if status == 'ok':
            color = (0, 255, 0)      # Verde - dentro la croce
        elif status == 'warning':
            color = (0, 255, 255)    # Giallo - poco fuori (entro 2×TOH/TOV)
        else:  # status == 'error'
            color = (0, 0, 255)      # Rosso - molto fuori (oltre 2×TOH/TOV)
    else:
        color = (128, 128, 128)      # Grigio se nessun punto rilevato

    # Disegna contorni (sempre rossi)
    if results.get('contorni'):
        try:
            largest = max(results['contorni'], key=cv2.contourArea)
            cv2.drawContours(image_output, [largest], -1, (0, 0, 255), 1, lineType=cv2.LINE_AA)
        except:
            pass

    # Disegna linee (usano il colore del punto: verde o rosso)
    for linea in results.get('linee', []):
        if len(linea) == 4:
            x1, y1, x2, y2 = linea
            cv2.line(image_output, (x1, y1), (x2, y2), color, 1, lineType=cv2.LINE_AA)

    # Disegna punto centrale (con colore già determinato)
    if punto is not None:
        # Pallino ben visibile per tutti i tipi
        radius = 8 if results.get('tipo') == 'abbagliante' else 6
        cv2.circle(image_output, (int(round(punto[0])), int(round(punto[1]))),
                  radius, color, -1, lineType=cv2.LINE_AA)

        # Disegna punti fitted (solo per anabbagliante/fendinebbia)
        punti_fitted = results.get('punti_fitted', np.array([]))
        if len(punti_fitted) > 0:
            # Cancella punti originali
            for p in punti_fitted:
                image_output[int(p[1]), int(p[0])] = 0

            # Ridisegna punti colorati
            [cv2.circle(image_output, (int(p[0]), int(p[1])), 1, color, 1, lineType=cv2.LINE_AA)
             for p in punti_fitted]

    return image_output


# ============================================================================
# BACKWARD COMPATIBILITY - Wrapper per codice legacy
# ============================================================================

def fit_lines(image_input: np.ndarray,
              image_output: np.ndarray,
              cache: dict,
              blur_ksize: int = 5,
              canny_lo: int = 40,
              canny_hi: int = 120,
              ftol: float = 1e-7,
              xtol: float = 1e-7,
              maxfev: int = 1000,
              debug: bool = False,
              flat: bool = False) -> Tuple[np.ndarray, Optional[Tuple[float, float]], Tuple[float, float, float]]:
    """
    Wrapper per backward compatibility con codice legacy.

    Args:
        flat: True per fendinebbia, False per anabbagliante

    Returns:
        Tuple (image_output, punto, angoli)
    """
    if flat:
        results = detect_fendinebbia(image_input, cache, blur_ksize, canny_lo, canny_hi,
                                     ftol, xtol, maxfev)
    else:
        results = detect_anabbagliante(image_input, cache, blur_ksize, canny_lo, canny_hi,
                                       ftol, xtol, maxfev)

    image_output = draw_results(image_output, results, cache)

    return image_output, results['punto'], results['angoli']
