import cv2

from utils import disegna_pallino, disegna_croce


def preprocess(image_orig, cache):
    config = cache['config']

    if 'crop_w' not in config or 'crop_h' not in config:
        return image_orig, image_orig.copy()

    height, width = image_orig.shape[:2]
    crop_center = config.get('crop_center', [width/2, height/2])
    crop_w = config['crop_w']
    crop_h = config['crop_h']

    # Calcola regione di crop centrata su crop_center
    start_y = max(int(crop_center[1] - crop_h/2), 0)
    end_y = min(int(crop_center[1] + crop_h/2), height)
    start_x = max(int(crop_center[0] - crop_w/2), 0)
    end_x = min(int(crop_center[0] + crop_w/2), width)

    # Crop effettivo
    image_input = image_orig[start_y:end_y, start_x:end_x].copy()
    image_view = cv2.convertScaleAbs(image_input, alpha=1.0, beta=20)

    return image_input, image_view


def is_punto_ok(point, cache):
    """
    Verifica se il punto è dentro la croce di riferimento e fornisce indicazioni direzionali.

    Args:
        point: Tuple (x, y) con coordinate del punto
        cache: Dizionario con config e stato_comunicazione

    Returns:
        Dict con:
        - 'ok': bool - True se punto dentro la croce
        - 'left': int - 0=ok, 1=poco fuori sx (entro 2×TOH), 2=molto fuori sx
        - 'right': int - 0=ok, 1=poco fuori dx (entro 2×TOH), 2=molto fuori dx
        - 'up': int - 0=ok, 1=poco fuori su (entro 2×TOV), 2=molto fuori su
        - 'down': int - 0=ok, 1=poco fuori giù (entro 2×TOV), 2=molto fuori giù
        - 'status': str - 'ok', 'warning' (poco fuori), 'error' (molto fuori)
    """
    stato_comunicazione = cache['stato_comunicazione']
    config = cache["config"]
    width = config["width"]
    height = config["height"]

    # Prendi TOV e TOH: prima da comunicazione, poi da config
    # Comunicazione ha priorità per permettere aggiustamenti real-time
    toh = int(stato_comunicazione.get('TOH', config.get('TOH', 50)))
    tov = int(stato_comunicazione.get('TOV', config.get('TOV', 50)))
    inclinazione = int(stato_comunicazione.get('incl', 0))

    # Centro della croce
    center_x = width / 2
    center_y = height / 2 + inclinazione

    # Distanze dal centro
    dx = point[0] - center_x
    dy = point[1] - center_y

    # Verifica se dentro la croce
    is_inside = abs(dx) <= toh and abs(dy) <= tov

    # Calcola indicazioni direzionali con 3 livelli
    # 3 = ok (centro), 2 = fuori, 1 = molto fuori, 0 = direzione opposta

    # Orizzontale (left/right)
    if dx < -toh:
        # Punto a sinistra → spostare faro a DESTRA
        if dx < -2*toh:
            right = 1  # Molto fuori
        else:
            right = 2  # Fuori
        left = 0
    elif dx > toh:
        # Punto a destra → spostare faro a SINISTRA
        if dx > 2*toh:
            left = 1  # Molto fuori
        else:
            left = 2  # Fuori
        right = 0
    else:
        # Dentro orizzontalmente
        left = 3
        right = 3

    # Verticale (up/down)
    if dy < -tov:
        # Punto in alto → spostare faro in BASSO (GIÙ)
        if dy < -2*tov:
            down = 1  # Molto fuori
        else:
            down = 2  # Fuori
        up = 0
    elif dy > tov:
        # Punto in basso → spostare faro in ALTO (SU)
        if dy > 2*tov:
            up = 1  # Molto fuori
        else:
            up = 2  # Fuori
        down = 0
    else:
        # Dentro verticalmente
        up = 3
        down = 3

    # Determina status generale (ignora 0 che è direzione opposta)
    levels = [v for v in [left, right, up, down] if v > 0]
    min_level = min(levels) if levels else 3
    if min_level == 3:
        status = 'ok'
    elif min_level == 2:
        status = 'warning'
    else:
        status = 'error'

    return {
        'ok': is_inside,
        'left': left,
        'right': right,
        'up': up,
        'down': down,
        'status': status
    }


def visualizza_croce_riferimento(frame, x, y, width, heigth):
    disegna_croce(frame, (x - width / 2, y - heigth / 2), 1000, 1, 'green')
    disegna_croce(frame, (x + width / 2, y + heigth / 2), 1000, 1, 'green')

def point_in_rect(pt, rect):
    x, y = pt
    rx, ry, rw, rh = rect
    return (rx <= x <= rx + rw) and (ry <= y <= ry + rh)

import cv2
import numpy as np

def blur_and_sharpen(img, sigma=1.5, strength=0.8, eight_neighbors=False):
    """
    Anti-alias 'morbido' via GaussianBlur + sharpen con filter2D.

    :param img: immagine BGR/GRAY (uint8 o float32/float64)
    :param sigma: intensità blur gaussiano (1.0–3.0 tipico)
    :param strength: forza sharpen (0.3–1.2; più alto = più nitido)
    :param eight_neighbors: False => kernel 'a croce' (4-neighbors), True => 8-neighbors
    :return: immagine filtrata, stesso dtype dell'input
    """
    # Lavoro in float [0,1] per stabilità
    src_dtype = img.dtype
    x = img.astype(np.float32)
    if x.max() > 1.5:  # probabilmente uint8
        x /= 255.0

    # 1) BLUR (anti-alias / smoothing)
    x_blur = cv2.GaussianBlur(x, (0, 0), sigmaX=sigma, sigmaY=sigma)

    # 2) SHARPEN con filter2D
    a = float(strength)

    if not eight_neighbors:
        # kernel 'a croce' (4-neighbors): [[0,-a,0],[-a,1+4a,-a],[0,-a,0]]
        k = np.array([[0, -a, 0],
                      [-a, 1 + 4 * a, -a],
                      [0, -a, 0]], dtype=np.float32)
    else:
        # kernel 8-neighbors: tutti intorno pesati -a, centro 1+8a (più aggressivo)
        k = np.full((3, 3), -a, np.float32)
        k[1, 1] = 1 + 8 * a

    x_sharp = cv2.filter2D(x_blur, ddepth=-1, kernel=k, borderType=cv2.BORDER_REPLICATE)

    # clamp e ritorno al dtype originale
    x_sharp = np.clip(x_sharp, 0.0, 1.0)
    if src_dtype == np.uint8:
        x_sharp = (x_sharp * 255.0 + 0.5).astype(np.uint8)
    else:
        x_sharp = x_sharp.astype(src_dtype)

    return x_sharp


def sharpen_dog(img, sigma_small=0.8, sigma_large=1.8, amount=1.0):
    # band = G(small) - G(large): medie frequenze (niente jaggies 1px)
    x = img.astype(np.float32)
    x=cv2.normalize(x, None, 0, 255, cv2.NORM_MINMAX)
    g1 = cv2.GaussianBlur(x, (0,0), sigma_small)
    g1=cv2.normalize(g1, None, 0, 255, cv2.NORM_MINMAX)

   # g2 = cv2.GaussianBlur(x, (0,0), sigma_large)
  #  band = g1 - g2
    out = (1-amount)*x + amount * g1
    out = cv2.normalize(out, None, 0, 255, cv2.NORM_MINMAX)
  #   if img.dtype == np.uint8:
  #       out = out.astype(np.float32)
  #       out = (out - out.min()) / (out.max() - out.min() + 1e-8)  # eviti div/0
  #       out = (out * 255.0).astype(np.uint8)
  #   else:
    out = out.astype(img.dtype)
    return out

# Esempi:
# out = sharpen_dog(image_output, sigma_small=0.9, sigma_large=2.0, amount=1.2)


def gaussian_kernel(size=5, sigma=1.2):
    ax = np.arange(-(size//2), size//2 + 1, dtype=np.float32)
    xx, yy = np.meshgrid(ax, ax)
    g = np.exp(-(xx**2 + yy**2) / (2*sigma**2))
    g /= g.sum()
    return g

def unsharp_kernel(size=5, sigma=1.2, alpha=0.6):
    g = gaussian_kernel(size, sigma)
    k = -(alpha) * g
    k[size//2, size//2] += (1.0 + alpha)   # (1+α)*δ - α*G
    return k.astype(np.float32)

def sharpen_bandlimited(img, size=5, sigma=1.2, alpha=0.6):
    src_dtype = img.dtype
    x = img.astype(np.float32)
    out = cv2.filter2D(x, ddepth=-1, kernel=unsharp_kernel(size, sigma, alpha),
                       borderType=cv2.BORDER_REPLICATE)
    if src_dtype == np.uint8:
        out = np.clip(out, 0, 255).astype(np.uint8)
    else:
        out = out.astype(src_dtype)
    return out


import cv2
import numpy as np

import cv2
import numpy as np
import math
import cv2
import numpy as np

def draw_polyline_aa(img, points, color=(255,255,255), thickness=2, closed=False):
    """
    Disegna una polilinea AA con giunzioni arrotondate e cappucci arrotondati.
    Simula un vero polilines antialiasato (migliore di cv2.polylines).

    :param img: immagine BGR o GRAY
    :param points: lista di (x, y)
    :param color: colore BGR
    :param thickness: spessore linea
    :param closed: se True chiude la polilinea
    """
    pts = np.asarray(points, dtype=np.int32)
    if len(pts) < 2:
        return img

    r = max(1, thickness // 2)
    n = len(pts)

    # disegna tutti i segmenti
    for i in range(n - 1):
        cv2.line(img, tuple(pts[i]), tuple(pts[i+1]), color, thickness, cv2.LINE_AA)
    if closed:
        cv2.line(img, tuple(pts[-1]), tuple(pts[0]), color, thickness, cv2.LINE_AA)

    # arrotonda giunzioni
    join_start = 0 if closed else 1
    join_end = n if closed else n - 1
    for i in range(join_start, join_end):
        cv2.circle(img, tuple(pts[i % n]), r, color, -1, cv2.LINE_AA)

    # cappucci alle estremità (solo se aperta)
    if not closed:
        cv2.circle(img, tuple(pts[0]), r, color, -1, cv2.LINE_AA)
        cv2.circle(img, tuple(pts[-1]), r, color, -1, cv2.LINE_AA)

    return img
