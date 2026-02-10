import os
import time

import cv2
import logging
import numpy as np
from utils import disegna_rettangolo, get_colore

def apri_camera():
    for i in range(11):
        video = cv2.VideoCapture(i)
        if video.isOpened():
            return i, video

    return None, None


def set_camera(i, config):
    logging.info(f"set_camera /dev/video{i}")
    try:
        #os.system(f"v4l2-ctl --device /dev/video{i} --set-ctrl=exposure_auto={config['exposure_auto']}")
        os.system(f"v4l2-ctl --device /dev/video{i} --set-ctrl=brightness={config['brightness']}")
        os.system(f"v4l2-ctl --device /dev/video{i} --set-ctrl=contrast={config['contrast']}")
        os.system(f"v4l2-ctl --device /dev/video{i} --set-ctrl=saturation={config['saturation']}")
        os.system(f"v4l2-ctl --device /dev/video{i} --set-ctrl=exposure_absolute={config['exposure_absolute']}")
        os.system(f"v4l2-ctl --device /dev/video{i} --list-ctrls")
    except Exception as e:
        logging.error(f"error: {e}")

def autoexp(image_input,image_view,cache):
    cache['autoexp_ok'] = True

    try:
        r=np.max(image_input)
      #  logging.debug(f"cache-config: {cache['config']}")
        s235=np.sum(image_input>230)

        exp_old=cache['config']['exposure_absolute']
        if (r>240):
            cache['config']['exposure_absolute']=cache['config']['exposure_absolute']*0.9
            cache['autoexp_ok'] = False
        if r <235:
            cache['config']['exposure_absolute'] = cache['config']['exposure_absolute'] * 1.1
            cache['autoexp_ok'] = False
        if (r>=235)and(r<=240):
            if (r>237):
                 cache['config']['exposure_absolute']=cache['config']['exposure_absolute']*0.998
            if (r<=237):
                cache['config']['exposure_absolute'] = cache['config']['exposure_absolute'] * 1.002
        logging.debug(f"exp: {cache['config']['exposure_absolute']}")
        if cache['config']['exposure_absolute']<50:
            cache['config']['exposure_absolute']=50
        if cache['config']['exposure_absolute'] >10000:
            cache['config']['exposure_absolute'] = 10000

        if exp_old!=cache['config']['exposure_absolute']:
                os.system(f"v4l2-ctl --device /dev/video{cache['config']['indice_camera']} --set-ctrl=exposure_absolute={cache['config']['exposure_absolute']}")
                time.sleep(0.1)

        if cache['DEBUG']:
            msg = f"max:{r} mean:{int(np.mean(image_input))} exp:{int(cache['config']['exposure_absolute'])}"
            cv2.putText(image_view, msg, (5, 80),
                    cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)
    except Exception as e:
        logging.error(f"error: {e}")
    return image_view


def fixexp(cache,ctr):
    os.system(f"v4l2-ctl --device /dev/video{cache['config']['indice_camera']} --set-ctrl=exposure_absolute={ctr}")
    time.sleep(0.25)





