import numpy as np
import cv2

from utils import disegna_rettangolo, get_colore
import logging

def calcola_px_lux(image_input, image_output, point, offset, dim, cache, tipo_faro):
    x0 = int(point[0] + offset[0] - dim[0] / 2)
    x1 = int(point[0] + offset[0] + dim[0] / 2)
    y0 = int(point[1] + offset[1] - dim[1] / 2)
    y1 = int(point[1] + offset[1] + dim[1] / 2)

    disegna_rettangolo(image_output, (x0, y1), (x1, y0), 1, "green")

    zone = image_input[y0:y1, x0:x1]

    if len(zone) == 0:
        return 0

    g = cache['config']['cam_g']
    t = cache['config']['exposure_absolute']
    c = cache['config']['cam_c']
    a = 255 - c
    r = np.mean(zone)

    l = -(100000/t) * np.log(1 - (r**g / (a * 255**(g-1))) + c/a)

    logging.debug(f"l: {l} r:{r}")

    if cache['DEBUG']:
        msg = f"max {np.max(zone)}, mean {int(np.mean(zone))}"
        cv2.putText(image_output, msg, (5, 30), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)

    # Calibrazione luminosità: px_lux -> lux reali
    if tipo_faro == 'abbagliante':
        lux_m = cache['config'].get('lux_m_abb', 1.0)
        lux_q = cache['config'].get('lux_q_abb', 0.0)
    else:
        lux_m = cache['config'].get('lux_m', 1.0)
        lux_q = cache['config'].get('lux_q', 0.0)

    l = l * lux_m + lux_q
    return l
