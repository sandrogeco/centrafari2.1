"""
Modulo per il fitting di linee sui contorni dei fari.

Questo modulo implementa gli algoritmi di rilevamento e fitting delle linee
sui pattern luminosi dei fari anabbaglianti e fendinebbia.
"""

import cv2
import numpy as np
import logging
from typing import Tuple
from scipy.optimize import curve_fit
from funcs_misc import is_punto_ok
from utils import disegna_pallino


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
        Tuple con (edges, binary) - edges da Canny e immagine binarizzata
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
    Modello a due linee spezzate per anabbagliante.

    Args:
        x: Array di coordinate x
        X0: Coordinata x del punto di giunzione
        Y0: Coordinata y del punto di giunzione
        mo: Pendenza della linea sinistra (outer)
        mi: Pendenza della linea destra (inner)

    Returns:
        Array di coordinate y calcolate
    """
    # Vincolo: pendenza interna deve essere minore della esterna
    if mi > mo:
        return np.full_like(x, 1e6)

    y = np.where(x <= X0,
                 Y0 + mo * (x - X0),
                 Y0 + mi * (x - X0))

    return y


def one_line_model(x: np.ndarray,
                   X0: float, Y0: float,
                   mo: float) -> np.ndarray:
    """
    Modello a una sola linea per fendinebbia.

    Args:
        x: Array di coordinate x
        X0: Coordinata x del punto di riferimento
        Y0: Coordinata y del punto di riferimento
        mo: Pendenza della linea

    Returns:
        Array di coordinate y calcolate
    """
    return mo * (x - X0) + Y0


def calculate_angles(X0: float, Y0: float, mo: float, cache: dict) -> Tuple[float, float, float]:
    """
    Calcola gli angoli yaw, pitch e roll dal punto rilevato.

    Args:
        X0: Coordinata x del punto centrale
        Y0: Coordinata y del punto centrale
        mo: Pendenza della linea
        cache: Dizionario con configurazione e stato comunicazione

    Returns:
        Tuple con (yaw_deg, pitch_deg, roll_deg)
    """
    try:
        dx = (X0 - cache['config']['width'] / 2) / cache['stato_comunicazione']['qin']
        dy = (Y0 - cache['config']['height'] / 2 + cache['stato_comunicazione']['inclinazione']) / cache['stato_comunicazione']['qin']
        yaw_deg = np.degrees(np.arctan2(dx, 25))      # Rotazione orizzontale
        pitch_deg = np.degrees(np.arctan2(dy, 25))    # Rotazione verticale
        roll_deg = np.degrees(np.arctan(mo))          # Inclinazione linea
    except:
        yaw_deg = 0
        pitch_deg = 0
        roll_deg = 0

    return yaw_deg, pitch_deg, roll_deg


def fit_lines_anabbagliante(image_input: np.ndarray,
                             image_output: np.ndarray,
                             cache: dict,
                             blur_ksize: int = 5,
                             canny_lo: int = 40,
                             canny_hi: int = 120,
                             ftol: float = 1e-7,
                             xtol: float = 1e-7,
                             maxfev: int = 1000,
                             debug: bool = False) -> Tuple[np.ndarray, Tuple[float, float], Tuple[float, float, float]]:
    """
    Esegue il fitting a DUE linee spezzate per faro anabbagliante.

    Rileva il pattern cut-off caratteristico del faro anabbagliante (15°/15° o simile)
    che presenta due pendenze diverse (sinistra più ripida, destra più piatta).

    Args:
        image_input: Immagine di input in scala di grigi
        image_output: Immagine su cui disegnare i risultati
        cache: Dizionario con cache e configurazione
        blur_ksize: Dimensione kernel per blur
        canny_lo: Soglia bassa Canny
        canny_hi: Soglia alta Canny
        ftol: Tolleranza funzione per curve_fit
        xtol: Tolleranza parametri per curve_fit
        maxfev: Numero massimo iterazioni per curve_fit
        debug: Flag per visualizzazione debug

    Returns:
        Tuple con (image_output, punto_centrale, angoli_yaw_pitch_roll)
    """
    # Preprocessing: edge detection
    edges, binary = preprocess(image_input, blur_ksize, canny_lo, canny_hi)

    try:
        # Estrai punti del contorno
        pts, ctrs = extract_contour_points(edges)

        # Disegna il contorno più grande
        if ctrs:
            largest = max(ctrs, key=cv2.contourArea)
            cv2.drawContours(image_output, [largest], -1, (0, 0, 255), 1, lineType=cv2.LINE_AA)

        # Trova estremi del contorno
        leftset_upper = pts[np.lexsort((pts[:, 1], pts[:, 0]))]
        rightest_upper = pts[np.lexsort((pts[:, 0], pts[:, 1]))]
        y_h = leftset_upper[0][1]
        x_min = leftset_upper[0][0]
        x_max = rightest_upper[0][0]

        # Inizializza cache se necessario
        try:
            marginl = cache['margin_auto']
        except:
            marginl = 0
            cache['margin_auto'] = 0
            cache['s_err'] = np.inf
            cache['X0'] = 300
            cache['Y0'] = 0
            cache['r_bound'] = x_max

        # Reset cache se autoesposizione è convergente
        if cache['autoexp_ok']:
            cache['margin_auto'] = 0
            cache['s_err'] = np.inf
            cache['r_bound'] = x_max

        # Calcola bounds per il fitting
        marginl = 10
        left_bound = x_min + marginl
        right_bound = np.minimum(x_max, cache['r_bound']) - marginl

        logging.debug(f"anabbagliante - cachex0:{cache['X0']}, left:{left_bound}, right:{right_bound}")

        # Filtra punti nella regione di interesse
        mask = (pts[:, 0] >= left_bound) & (pts[:, 0] <= right_bound)
        pts_mask = pts[mask]

        # Usa solo punti superiori per il fitting
        top_pts = pts_mask[pts_mask[:, 1] <= y_h]
        x_data = top_pts[:, 0]
        y_data = top_pts[:, 1]

        # ============================
        # FITTING: 2 linee spezzate
        # ============================

        p0 = [np.mean(x_data), np.max(y_data) - 1, -0.01, -1.0]
        bounds = (
            [np.min(x_data), 0.0, -0.5, -np.inf],
            [np.max(x_data), np.max(y_data), 0, 0]
        )

        try:
            popt, _ = curve_fit(
                two_lines_model, x_data, y_data,
                p0=p0, bounds=bounds,
                ftol=ftol, xtol=xtol, maxfev=maxfev
            )
            X0, Y0, mo, mi = popt
        except Exception as e:
            cv2.putText(image_output, str(e), (5, 100),
                       cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, (0, 255, 0), 1)
            X0, Y0, mo, mi = 0, 0, 0, 0

        # ============================
        # DISEGNO RISULTATI
        # ============================

        h, w = image_input.shape
        xs = np.array([0, X0, w])
        ys = two_lines_model(xs, X0, Y0, mo, mi)

        # Disegna le due linee fitted
        cv2.line(image_output,
                (int(round(xs[0])), int(round(ys[0]))),
                (int(round(xs[1])), int(round(ys[1]))),
                (0, 255, 255), 1, lineType=cv2.LINE_AA)
        cv2.line(image_output,
                (int(round(xs[1])), int(round(ys[1]))),
                (int(round(xs[2])), int(round(ys[2]))),
                (0, 255, 255), 1, lineType=cv2.LINE_AA)

        # Disegna punto centrale (verde se OK, rosso se fuori range)
        ptok = is_punto_ok((X0, Y0), cache)
        color = (0, 255, 0) if ptok else (255, 0, 0)
        cv2.circle(image_output, (int(round(X0)), int(round(Y0))), 2, color, 2, -1)

        # Disegna i punti del contorno
        for p in top_pts:
            image_output[int(p[1]), int(p[0])] = 0

        [cv2.circle(image_output, (int(p[0]), int(p[1])), 1, color, 1, lineType=cv2.LINE_AA)
         for p in top_pts]

        # Salva in cache e calcola angoli
        cache['X0'] = X0
        cache['Y0'] = Y0
        yaw_deg, pitch_deg, roll_deg = calculate_angles(X0, Y0, mo, cache)

    except Exception as e:
        # In caso di errore, ritorna valori di default
        X0, Y0 = 0, 0
        yaw_deg, pitch_deg, roll_deg = 0, 0, 0

    return image_output, (X0, Y0), (yaw_deg, pitch_deg, roll_deg)


def fit_lines_fendinebbia(image_input: np.ndarray,
                           image_output: np.ndarray,
                           cache: dict,
                           blur_ksize: int = 5,
                           canny_lo: int = 40,
                           canny_hi: int = 120,
                           ftol: float = 1e-7,
                           xtol: float = 1e-7,
                           maxfev: int = 1000,
                           debug: bool = False) -> Tuple[np.ndarray, Tuple[float, float], Tuple[float, float, float]]:
    """
    Esegue il fitting a UNA sola linea per faro fendinebbia.

    Rileva il pattern cut-off caratteristico del fendinebbia che presenta
    una linea orizzontale sostanzialmente piatta.

    Args:
        image_input: Immagine di input in scala di grigi
        image_output: Immagine su cui disegnare i risultati
        cache: Dizionario con cache e configurazione
        blur_ksize: Dimensione kernel per blur
        canny_lo: Soglia bassa Canny
        canny_hi: Soglia alta Canny
        ftol: Tolleranza funzione per curve_fit
        xtol: Tolleranza parametri per curve_fit
        maxfev: Numero massimo iterazioni per curve_fit
        debug: Flag per visualizzazione debug

    Returns:
        Tuple con (image_output, punto_centrale, angoli_yaw_pitch_roll)
    """
    # Preprocessing: edge detection
    edges, binary = preprocess(image_input, blur_ksize, canny_lo, canny_hi)

    try:
        # Estrai punti del contorno
        pts, ctrs = extract_contour_points(edges)

        # Disegna il contorno più grande
        if ctrs:
            largest = max(ctrs, key=cv2.contourArea)
            cv2.drawContours(image_output, [largest], -1, (0, 0, 255), 1, lineType=cv2.LINE_AA)

        # Trova estremi del contorno (per fendinebbia usa tutto lo span orizzontale)
        leftset_upper = pts[np.lexsort((pts[:, 1], pts[:, 0]))]
        y_h = leftset_upper[0][1]
        x_min = np.min(pts[:, 0])
        x_max = np.max(pts[:, 0])

        # Inizializza cache se necessario
        try:
            marginl = cache['margin_auto']
        except:
            marginl = 0
            cache['margin_auto'] = 0
            cache['s_err'] = np.inf
            cache['X0'] = 300
            cache['Y0'] = 0
            cache['r_bound'] = x_max

        # Reset cache se autoesposizione è convergente
        if cache['autoexp_ok']:
            cache['margin_auto'] = 0
            cache['s_err'] = np.inf
            cache['r_bound'] = x_max

        # Calcola bounds per il fitting
        marginl = 10
        left_bound = x_min + marginl
        right_bound = np.minimum(x_max, cache['r_bound']) - marginl

        logging.debug(f"fendinebbia - cachex0:{cache['X0']}, left:{left_bound}, right:{right_bound}")

        # Filtra punti nella regione di interesse
        mask = (pts[:, 0] >= left_bound) & (pts[:, 0] <= right_bound)
        pts_mask = pts[mask]

        # Usa solo punti superiori per il fitting
        top_pts = pts_mask[pts_mask[:, 1] <= y_h]
        x_data = top_pts[:, 0]
        y_data = top_pts[:, 1]

        # ============================
        # FITTING: 1 linea
        # ============================

        p0 = [np.mean(x_data), np.max(y_data) - 1, -0.01]
        bounds = (
            [np.min(x_data), 0.0, -np.inf],
            [np.max(x_data), np.max(y_data), np.inf]
        )

        try:
            popt, _ = curve_fit(
                one_line_model, x_data, y_data,
                p0=p0, bounds=bounds,
                ftol=ftol, xtol=xtol, maxfev=maxfev
            )
            X0, Y0, mo = popt
            # Per fendinebbia, X0 è il centro dello span
            X0 = int((np.max(x_data) + np.min(x_data)) / 2)
            mi = 0
        except Exception as e:
            cv2.putText(image_output, str(e), (5, 100),
                       cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, (0, 255, 0), 1)
            X0, Y0, mo, mi = 0, 0, 0, 0

        # ============================
        # DISEGNO RISULTATI
        # ============================

        h, w = image_input.shape
        xs = np.array([0, X0, w])
        ys = two_lines_model(xs, X0, Y0, mo, mi)

        # Disegna la linea fitted
        cv2.line(image_output,
                (int(round(xs[0])), int(round(ys[0]))),
                (int(round(xs[1])), int(round(ys[1]))),
                (0, 255, 255), 1, lineType=cv2.LINE_AA)
        cv2.line(image_output,
                (int(round(xs[1])), int(round(ys[1]))),
                (int(round(xs[2])), int(round(ys[2]))),
                (0, 255, 255), 1, lineType=cv2.LINE_AA)

        # Disegna punto centrale (verde se OK, rosso se fuori range)
        ptok = is_punto_ok((X0, Y0), cache)
        color = (0, 255, 0) if ptok else (255, 0, 0)
        cv2.circle(image_output, (int(round(X0)), int(round(Y0))), 2, color, 2, -1)

        # Disegna i punti del contorno
        for p in top_pts:
            image_output[int(p[1]), int(p[0])] = 0

        [cv2.circle(image_output, (int(p[0]), int(p[1])), 1, color, 1, lineType=cv2.LINE_AA)
         for p in top_pts]

        # Salva in cache e calcola angoli
        cache['X0'] = X0
        cache['Y0'] = Y0
        yaw_deg, pitch_deg, roll_deg = calculate_angles(X0, Y0, mo, cache)

    except Exception as e:
        # In caso di errore, ritorna valori di default
        X0, Y0 = 0, 0
        yaw_deg, pitch_deg, roll_deg = 0, 0, 0

    return image_output, (X0, Y0), (yaw_deg, pitch_deg, roll_deg)


# Mantieni fit_lines per backward compatibility
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
              flat: bool = False) -> Tuple[np.ndarray, Tuple[float, float], Tuple[float, float, float]]:
    """
    Wrapper per compatibilità. Usa fit_lines_anabbagliante o fit_lines_fendinebbia.

    Args:
        flat: True per fendinebbia, False per anabbagliante

    Returns:
        Tuple con (image_output, punto_centrale, angoli_yaw_pitch_roll)
    """
    if flat:
        return fit_lines_fendinebbia(image_input, image_output, cache,
                                      blur_ksize, canny_lo, canny_hi,
                                      ftol, xtol, maxfev, debug)
    else:
        return fit_lines_anabbagliante(image_input, image_output, cache,
                                        blur_ksize, canny_lo, canny_hi,
                                        ftol, xtol, maxfev, debug)
