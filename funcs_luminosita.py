import numpy as np
import cv2

from utils import disegna_rettangolo, get_colore
import logging

def calcola_px_lux(image_input, image_output, point, offset, dim, cache):
    x0 = int(point[0] + offset[0] - dim[0] / 2)
    x1 = int(point[0] + offset[0] + dim[0] / 2)
    y0 = int(point[1] + offset[1] - dim[1] / 2)
    y1 = int(point[1] + offset[1] + dim[1] / 2)

    disegna_rettangolo(image_output, (x0, y1), (x1, y0), 1, "green")


    zone = image_input[y0:y1, x0:x1]
    g=cache['config']['cam_g']
    t=cache['config']['exposure_absolute']
    c=cache['config']['cam_c']
    a=255-c
    r=np.mean(zone)

    l=-(100000/t)*np.log(1-(r**g/(a*255**(g-1)))+c/a)

    logging.debug(f"l: {l} r:{r}")

    if len(zone) == 0:
     return 0

    if cache['DEBUG']:
        msg = f"max {np.max(zone)}, mean {int(np.mean(zone))}"
        cv2.putText(image_output, msg, (5, 30), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)

    return l#np.mean(zone)
