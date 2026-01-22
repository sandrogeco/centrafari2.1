import numpy as np
import cv2
import logging

from utils import get_colore_bgr, get_colore, angolo_vettori, find_y_by_x, \
    angolo_esterno_vettori, differenza_vettori, disegna_pallino, disegna_linea, disegna_linea_inf, disegna_linea_angolo


def rileva_contorno(image, cache):
    if 'lut' not in cache:
        def pullapart(v):
            vs = 250
            v = v - 2 * np.sign(v - vs) * (np.abs(v - vs) ** 0.6)
            v = np.clip(v, 0, 255).astype(np.uint8)
            return v

        cache['lut'] = np.array([pullapart(d) for d in range(256)], dtype=np.uint8)

    image1 = cv2.LUT(image, cache['lut'])

    # Sembra che THRESH_OTSU funzioni abbastanza meglio di THRESH_BINARY, cioe' il contorno che viene
    # fuori e' meno influenzato dalla haze nell'immagine e piu' vicino al bordo vero
    _, binary_image = cv2.threshold(image1, 0, 255, cv2.THRESH_OTSU)

    edges = cv2.Canny(binary_image, 50, 300)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        logging.debug("   contours vuoto")
        return None, '[rileva_contorno_1], contours vuoto'

    contour = max(contours, key=lambda d: cv2.arcLength(d, False))
    contour = contour[contour[:, 0, 0].argsort()]
    return contour, None


def rileva_punto_angoloso(image_input, image_output, cache):
    WIDTH_PIXEL = image_input.shape[1]
    AREA = image_input.shape[0] * image_input.shape[1]

    # Rileva contorno
    contour, err = rileva_contorno(image_input, cache)
    if contour is None or err is not None:
        return image_input, None, '[rileva_punto_angoloso] contour is None'

    if cache['DEBUG']:

        cv2.drawContours(image_output, [contour], -1, get_colore_bgr('red'), 1)
        msg = f"clipping: {np.sum(image_input >= 255) / AREA}%, Max level: {np.max(image_input)}"
        cv2.putText(image_output, msg, (5, 20), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)

    # Analisi contorno
    delta = 20
    punti = []
    angoli = []

    OFFSET_Y = 5

    for p in range(delta, 100 - delta, 1):
        p_prec = p - delta
        p_succ = p + delta

        x_prec = int(0.01 * p_prec * WIDTH_PIXEL)
        x = int(0.01 * p * WIDTH_PIXEL)
        x_succ = int(0.01 * p_succ * WIDTH_PIXEL)

        y_prec = find_y_by_x(contour, x_prec)
        y = find_y_by_x(contour, x)
        y_succ = find_y_by_x(contour, x_succ)
        if y_prec is None or y is None or y_succ is None:
            continue

        v_prec = (x_prec, y_prec + OFFSET_Y)
        v = (x, y + OFFSET_Y)
        v_succ = (x_succ, y_succ + OFFSET_Y)

        angolo = -angolo_esterno_vettori(differenza_vettori(v_prec, v), differenza_vettori(v_succ, v))
        angoli.append(angolo)

        range_angoli = cache.get('range_angoli', [10, 20])
        if range_angoli[0] < angolo < range_angoli[1]:
            punti.append(v)
            if cache['DEBUG']:
                cv2.putText(image_output, f"{int(angolo)}", (v[0], v[1] + 30 + int(20 * np.sin(60 * v[0] * 180 / np.pi))), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)
        else:
            if cache['DEBUG']:
                disegna_pallino(image_output, v, 2, 'red', -1)
                cv2.putText(image_output, f"{int(angolo)}", (v[0], v[1] + 30 + int(20 * np.sin(60 * v[0] * 180 / np.pi))), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('red'), 1)

    cache['range_angoli'] = [int(np.max(angoli)) - 4, int(np.max(angoli)) + 1]

    # Rimuovo i punti che sono troppo vicini alle estremita' del contour
    min_contour_x = np.min(contour[:, 0, 0])
    max_contour_x = np.max(contour[:, 0, 0])
    range_contour_x = max_contour_x - min_contour_x

    punti = [p for p in punti if min_contour_x + (0.05 * range_contour_x) < p[0] < max_contour_x - (0.05 * range_contour_x)]

    if len(punti) == 0:
        return image_output, None, '[rileva_punto_angoloso] nessun punto trovato'

    for punto in punti:
        disegna_pallino(image_output, punto, 2, 'green', -1)
    disegna_pallino(image_output, punti[0], 2, 'blue', -1)
    disegna_pallino(image_output, punti[-1], 2, 'blue', -1)

    punto_finale = tuple(np.median(punti, axis=0).astype(np.int32))
    try:
        disegna_linea_inf(image_output, (punti[0],punto_finale),1,'red')
        disegna_linea_inf(image_output, (punti[-1], punto_finale), 1, 'red')
    except:
        pass

    disegna_linea_angolo(image_output,(int(cache['config']['width'] / 2),
                                        int(cache['config']['height'] / 2)+cache['stato_comunicazione'].get('incl', 0)
                                        -cache['stato_comunicazione'].get('TOH', 50)),15,1,'green')

    disegna_linea_angolo(image_output, (int(cache['config']['width'] / 2),
                                         int(cache['config']['height'] / 2) +cache['stato_comunicazione'].get('incl', 0)
                                         + cache['stato_comunicazione'].get('TOH',50)), 15,1, 'green')

    disegna_linea_angolo(image_output,(int(cache['config']['width'] / 2),
                                        int(cache['config']['height'] / 2)+cache['stato_comunicazione'].get('incl', 0)
                                        -cache['stato_comunicazione'].get('TOH', 50)),180,1,'green')
    disegna_linea_angolo(image_output, (int(cache['config']['width'] / 2),
                                         int(cache['config']['height'] / 2) +cache['stato_comunicazione'].get('incl', 0)
                                         + cache['stato_comunicazione'].get('TOH',50)), 180,1, 'green')
    if 'numero_medie_punto' in cache['config']:
        cache['lista_ultimi_punti'] = cache.get('lista_ultimi_punti', []) + [punto_finale]
        cache['lista_ultimi_punti'] = cache['lista_ultimi_punti'][-cache['config']['numero_medie_punto']:]
        punto_finale = tuple(np.median(cache['lista_ultimi_punti'], axis=0).astype(np.int32))

    disegna_pallino(image_output, punto_finale, 10, 'green', -1)

    return image_output, punto_finale, None

def curv_ch(image_output,contour):


    dx = np.gradient(contour[:, 0])
    dy = np.gradient(contour[:, 1])
    ddx = np.gradient(dx)
    ddy = np.gradient(dy)

    # Curvatura discreta
    curvature = (dx * ddy - dy * ddx) / (dx ** 2 + dy ** 2) ** 1.5

    # Trova cambi di segno nella curvatura
    sign_changes = np.where(np.diff(np.sign(curvature)))[0]

    for s in sign_changes:
        logging.debug(f"sign:{contour[s - 1]}")
        try:
            disegna_pallino(image_output, (contour[s-1][0],contour[s-1][1]), 2, 'red', -1)
        except:
            pass
    #print('x')



def rileva_punto_angoloso1(image_input, image_output, cache):
    WIDTH_PIXEL = image_input.shape[1]
    AREA = image_input.shape[0] * image_input.shape[1]

    # Rileva contorno
    contour, err = rileva_contorno(image_input, cache)
    if contour is None or err is not None:
        return image_input, None, '[rileva_punto_angoloso] contour is None'

    if cache['DEBUG']:
        image_tmp = image_input.copy()
        cv2.normalize(image_input, image_tmp, 0, 255, cv2.NORM_MINMAX)

        image_tmp[image_tmp < 150] = 0
        #image_tmp[image_tmp >= 100] = 255
        image_tmp = cv2.GaussianBlur(image_tmp, (11, 11), sigmaX=0.0)
        image_output=image_tmp

        contours, _ = cv2.findContours(image_tmp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour1 = max(contours, key=lambda d: cv2.contourArea(d))
      #  cv2.drawContours(image_output, [contour1], -1, get_colore('green'), 1)

        epsilon = 0.0005 * cv2.arcLength(contour1, True)
        approx = cv2.approxPolyDP(contour1, epsilon, closed=True)
        approx = approx.reshape(-1, 2)
        cv2.drawContours(image_output, [approx], -1, get_colore('blue'), 1)
        curv_ch(image_output,approx)
       # cv2.drawContours(image_output, [contour], -1, get_colore('red'), 1)
        msg = f"clipping: {np.sum(image_input >= 255) / AREA}%, Max level: {np.max(image_input)}"
        cv2.putText(image_output, msg, (5, 20), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)
        return image_output, None, None

    # Analisi contorno
    delta = 20
    punti = []
    angoli = []

    OFFSET_Y = 5
    yy=[]
    xx=[]

    for p in range(delta, 100 - delta, 1):

        x = int(0.01 * p * WIDTH_PIXEL)
        y = find_y_by_x(contour, x)


        yy.append(y)
        xx.append(x)

    dxx=np.diff(np.asarray(xx))
    dyy=-np.diff(np.asarray(yy))

    mm=dyy/dxx
    pp=np.where((0.2 < mm) & (mm < 1))[0]
    for px in pp:
        punti.append ((xx[px], yy[px]))


        #
        # angolo = 0#-angolo_esterno_vettori(differenza_vettori(v_prec, v), differenza_vettori(v_succ, v))
        # angoli.append(angolo)
        #
        # range_angoli = cache.get('range_angoli', [10, 20])
        # if range_angoli[0] < angolo < range_angoli[1]:
        #     punti.append(v)
        #     if cache['DEBUG']:
        #         cv2.putText(image_output, f"{int(angolo)}", (v[0], v[1] + 30 + int(20 * np.sin(60 * v[0] * 180 / np.pi))), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)
        # else:
        #     if cache['DEBUG']:
        #         disegna_pallino(image_output, v, 2, 'red', -1)
        #         cv2.putText(image_output, f"{int(angolo)}", (v[0], v[1] + 30 + int(20 * np.sin(60 * v[0] * 180 / np.pi))), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('red'), 1)

    #cache['range_angoli'] = [int(np.max(angoli)) - 4, int(np.max(angoli)) + 1]

    # Rimuovo i punti che sono troppo vicini alle estremita' del contour
    min_contour_x = np.min(contour[:, 0, 0])
    max_contour_x = np.max(contour[:, 0, 0])
    range_contour_x = max_contour_x - min_contour_x

    punti = [p for p in punti if min_contour_x + (0.05 * range_contour_x) < p[0] < max_contour_x - (0.05 * range_contour_x)]

    if len(punti) == 0:
        return image_output, None, '[rileva_punto_angoloso] nessun punto trovato'

    for punto in punti:
        disegna_pallino(image_output, punto, 2, 'green', -1)
    disegna_pallino(image_output, punti[0], 2, 'blue', -1)
    disegna_pallino(image_output, punti[-1], 2, 'blue', -1)

    punto_finale =tuple(np.median(punti[0:5], axis=0).astype(np.int32))
    try:
        disegna_linea_inf(image_output, (punti[0],punto_finale),1,'red')
        disegna_linea_inf(image_output, (punti[-1], punto_finale), 1, 'red')
    except:
        pass

    disegna_linea_angolo(image_output,(int(cache['config']['width'] / 2),
                                        int(cache['config']['height'] / 2)+cache['stato_comunicazione'].get('incl', 0)
                                        -cache['stato_comunicazione'].get('TOH', 50)),15,1,'green')

    disegna_linea_angolo(image_output, (int(cache['config']['width'] / 2),
                                         int(cache['config']['height'] / 2) +cache['stato_comunicazione'].get('incl', 0)
                                         + cache['stato_comunicazione'].get('TOH',50)), 15,1, 'green')

    disegna_linea_angolo(image_output,(int(cache['config']['width'] / 2),
                                        int(cache['config']['height'] / 2)+cache['stato_comunicazione'].get('incl', 0)
                                        -cache['stato_comunicazione'].get('TOH', 50)),180,1,'green')
    disegna_linea_angolo(image_output, (int(cache['config']['width'] / 2),
                                         int(cache['config']['height'] / 2) +cache['stato_comunicazione'].get('incl', 0)
                                         + cache['stato_comunicazione'].get('TOH',50)), 180,1, 'green')
    if 'numero_medie_punto' in cache['config']:
        cache['lista_ultimi_punti'] = cache.get('lista_ultimi_punti', []) + [punto_finale]
        cache['lista_ultimi_punti'] = cache['lista_ultimi_punti'][-cache['config']['numero_medie_punto']:]
        punto_finale = tuple(np.median(cache['lista_ultimi_punti'], axis=0).astype(np.int32))

    disegna_pallino(image_output, punto_finale, 10, 'green', -1)

    return image_output, punto_finale, None
