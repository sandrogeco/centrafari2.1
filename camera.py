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

def autoexp_legacy(image_input,image_view,cache):
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


def autoexp(image_input, image_view, cache):
    """
    Controllo PID esposizione automatica.
    Setpoint: max pixel = autoexp_setpoint (default 237).
    autoexp_ok = True quando errore stabile per N frame consecutivi.
    """
    config = cache['config']
    pid = cache.get('autoexp_pid')

    # Inizializza stato PID al primo frame
    if pid is None:
        pid = {
            'integral': 0.0,
            'prev_error': 0.0,
            'stable_count': 0,
        }
        cache['autoexp_pid'] = pid

    # Parametri PID da config
    Kp = config.get('autoexp_Kp', 0.5)
    Ki = config.get('autoexp_Ki', 0.05)
    Kd = config.get('autoexp_Kd', 0.1)
    setpoint = config.get('autoexp_setpoint', 237)
    stable_tol = config.get('autoexp_stable_tol', 3)
    stable_frames = config.get('autoexp_stable_frames', 5)
    exp_min = config.get('autoexp_exp_min', 50)
    exp_max = config.get('autoexp_exp_max', 10000)
    integral_max = config.get('autoexp_integral_max', 500)

    try:
        r = np.max(image_input)
        error = setpoint - r

        # PID
        pid['integral'] += error
        # Anti-windup
        pid['integral'] = np.clip(pid['integral'], -integral_max, integral_max)
        derivative = error - pid['prev_error']
        pid['prev_error'] = error

        output = Kp * error + Ki * pid['integral'] + Kd * derivative

        # Applica correzione all'esposizione
        exp_old = config['exposure_absolute']
        exp_new = exp_old + output
        exp_new = np.clip(exp_new, exp_min, exp_max)
        config['exposure_absolute'] = float(exp_new)

        # Stabilità: errore entro tolleranza per N frame consecutivi
        if abs(error) <= stable_tol:
            pid['stable_count'] += 1
        else:
            pid['stable_count'] = 0

        cache['autoexp_ok'] = pid['stable_count'] >= stable_frames

        # Applica esposizione se cambiata
        if int(exp_new) != int(exp_old):
            os.system(f"v4l2-ctl --device /dev/video{config['indice_camera']} "
                      f"--set-ctrl=exposure_absolute={int(exp_new)}")
            time.sleep(0.1)

        logging.debug(f"PID exp: {int(exp_new)} err:{error:.0f} P:{Kp*error:.1f} "
                     f"I:{Ki*pid['integral']:.1f} D:{Kd*derivative:.1f} "
                     f"stable:{pid['stable_count']}/{stable_frames}")

        if cache['DEBUG']:
            ok_str = "OK" if cache['autoexp_ok'] else "..."
            msg = f"max:{r} mean:{int(np.mean(image_input))} exp:{int(exp_new)} [{ok_str}]"
            cv2.putText(image_view, msg, (5, 80),
                    cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)

    except Exception as e:
        logging.error(f"autoexp PID error: {e}")
        cache['autoexp_ok'] = True

    return image_view


def fixexp(cache,ctr):
    os.system(f"v4l2-ctl --device /dev/video{cache['config']['indice_camera']} --set-ctrl=exposure_absolute={ctr}")
    time.sleep(0.25)





