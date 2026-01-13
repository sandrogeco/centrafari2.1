import numpy as np
import cv2
import logging

from utils import get_colore, disegna_pallino
from funcs_misc import is_punto_ok


def trova_contorni_abbagliante(image_input, image_output, cache):
    AREA = image_input.shape[0] * image_input.shape[1]
    LEVEL = 0.97
    nclip = np.sum(image_input >= 255) / AREA

    image_tmp = image_input.copy()

    cv2.normalize(image_input, image_tmp, 0, 255, cv2.NORM_MINMAX)
    c = np.cumsum(np.histogram(image_tmp.reshape(AREA), bins=255)[0]) / AREA
    #l = np.where(c > LEVEL)[0][0]
    l=210
    image_tmp[image_tmp < l] = 0

    if cache["DEBUG"]:
        msg = f"clipping: {nclip}%, Max level: {np.max(image_input)}, aut level: {l}"
        cv2.putText(image_output, msg, (5, 20), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)

    # x = np.arange(imout1.shape[1])
    # y = np.arange(imout1.shape[0])
    # xx, yy = np.meshgrid(x, y)
    # imout1_float = imout1.astype(np.float32)
    # A = imout1_float.sum()
    #
    # x_cms = (np.int32)((xx * imout1_float).sum() / A)
    # y_cms = (np.int32)((yy * imout1_float).sum() / A)

    moments = cv2.moments(image_tmp, binaryImage=True)

    # Evita divisione per zero
    if moments['m00'] != 0:
        x_cms = int(moments['m10'] / moments['m00'])
        y_cms = int(moments['m01'] / moments['m00'])
    else:
        logging.error("punto abbagliante non trovato")
        return image_output, None, "punto non trovato"


    try:
        contours, _ = cv2.findContours(image_tmp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key=lambda d: cv2.contourArea(d))
        cv2.drawContours(image_output, [contour], -1, get_colore('blue'), 1, cv2.LINE_AA)
    except Exception as e:
        logging.error(f"trova_contorni_abbagliante e={e}")
    ptok = is_punto_ok((x_cms, y_cms), cache)
    if ptok:
        color ='green'
    else:
        color = 'red'

    disegna_pallino(image_output, (x_cms, y_cms), 6, color, -1)
    try:
        dx = (x_cms - cache['config']['width'] / 2) /cache['stato_comunicazione']['qin']
        dy = (y_cms - cache['config']['height'] / 2 + cache['stato_comunicazione']['inclinazione']) /cache['stato_comunicazione']['qin']
        yaw_deg = np.degrees(np.arctan2(dx, 25))  # rotazione orizzontale (destra/sinistra)
        pitch_deg = np.degrees(np.arctan2(dy, 25))
        roll_deg =0
    except:
        yaw_deg = 0
        roll_deg = 0
        pitch_deg = 0

    return image_output, (x_cms, y_cms), (yaw_deg,pitch_deg,0)
