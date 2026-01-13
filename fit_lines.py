"""
Modulo per il fitting di linee sui contorni dei fari.

Questo modulo implementa l'algoritmo di rilevamento e fitting delle linee
sui pattern luminosi dei fari (anabbagliante, abbagliante, fendinebbia).
"""

import cv2
import numpy as np
import logging
from typing import Tuple
from scipy.optimize import curve_fit
from funcs_misc import is_punto_ok, draw_polyline_aa
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


def two_lines(x: np.ndarray,
              X0: float, Y0: float,
              mo: float, mi: float) -> np.ndarray:
    """
    Modello a due linee spezzate per curve_fit.

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


def one_lines(x: np.ndarray,
              X0: float, Y0: float,
              mo: float) -> np.ndarray:
    """
    Modello a una sola linea per curve_fit (fendinebbia).

    Args:
        x: Array di coordinate x
        X0: Coordinata x del punto di riferimento
        Y0: Coordinata y del punto di riferimento
        mo: Pendenza della linea

    Returns:
        Array di coordinate y calcolate
    """
    return mo * (x - X0) + Y0


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
    Esegue il fitting delle linee sul pattern del faro.

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
        flat: True per fendinebbia (1 linea), False per anabbagliante (2 linee)

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

        # Determina bounds orizzontali
        if flat:
            x_min = np.min(pts[:, 0])
            x_max = np.max(pts[:, 0])
        else:
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

        logging.debug(f"cachex0:{cache['X0']}")
        logging.debug(f"left_bound:{left_bound}")
        logging.debug(f"right_bound:{right_bound}")
        logging.debug(f"x_max:{x_max}")

        # Filtra punti nella regione di interesse
        mask = (pts[:, 0] >= left_bound) & (pts[:, 0] <= right_bound)
        pts_mask = pts[mask]

        # Separa punti sopra e sotto y_h (usa solo quelli sopra)
        top_pts = pts_mask[pts_mask[:, 1] <= y_h]
        bot_pts = pts_mask[pts_mask[:, 1] > y_h]

        if debug:
            cv2.imshow('Contour split', image_output)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        # Usa solo punti superiori per il fitting
        pts = top_pts
        x_data = pts[:, 0]
        y_data = pts[:, 1]

        # ============================
        # FITTING: 1 o 2 linee
        # ============================

        if flat:
            # Fendinebbia: fitting con 1 linea
            p0 = [np.mean(x_data), np.max(y_data) - 1, -0.01]
            bounds = (
                [np.min(x_data), 0.0, -np.inf],
                [np.max(x_data), np.max(y_data), np.inf]
            )

            try:
                popt, _ = curve_fit(
                    one_lines, x_data, y_data,
                    p0=p0, bounds=bounds,
                    ftol=ftol, xtol=xtol, maxfev=maxfev
                )
                X0, Y0, mo = popt
                X0 = int((np.max(x_data) + np.min(x_data)) / 2)
                mi = 0
            except Exception as e:
                cv2.putText(image_output, str(e), (5, 100),
                           cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, (0, 255, 0), 1)

        else:
            # Anabbagliante: fitting con 2 linee spezzate
            p0 = [np.mean(x_data), np.max(y_data) - 1, -0.01, -1.0]
            bounds = (
                [np.min(x_data), 0.0, -0.5, -np.inf],
                [np.max(x_data), np.max(y_data), 0, 0]
            )

            try:
                popt, _ = curve_fit(
                    two_lines, x_data, y_data,
                    p0=p0, bounds=bounds,
                    ftol=ftol, xtol=xtol, maxfev=maxfev
                )
                X0, Y0, mo, mi = popt
            except Exception as e:
                cv2.putText(image_output, str(e), (5, 100),
                           cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, (0, 255, 0), 1)

        # ============================
        # DISEGNO RISULTATI
        # ============================

        h, w = image_input.shape
        xs = np.array([0, X0, w])
        ys = two_lines(xs, X0, Y0, mo, mi)

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

        # ============================
        # CALCOLO ANGOLI
        # ============================

        cache['X0'] = X0
        cache['Y0'] = Y0

        try:
            dx = (X0 - cache['config']['width'] / 2) / cache['stato_comunicazione']['qin']
            dy = (Y0 - cache['config']['height'] / 2 + cache['stato_comunicazione']['inclinazione']) / cache['stato_comunicazione']['qin']
            yaw_deg = np.degrees(np.arctan2(dx, 25))      # Rotazione orizzontale
            pitch_deg = np.degrees(np.arctan2(dy, 25))    # Rotazione verticale
            roll_deg = np.degrees(np.arctan(mo))          # Inclinazione linea
        except:
            yaw_deg = 0
            roll_deg = 0
            pitch_deg = 0

    except Exception as e:
        # In caso di errore, ritorna valori di default
        X0 = 0
        Y0 = 0
        mo = 0
        yaw_deg = 0
        roll_deg = 0
        pitch_deg = 0

    return image_output, (X0, Y0), (yaw_deg, pitch_deg, roll_deg)
