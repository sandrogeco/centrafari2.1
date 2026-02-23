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
    Controllo PID esposizione automatica (moltiplicativo).
    Lavora sull'errore normalizzato (error/setpoint) per stabilità.
    autoexp_ok = True quando errore entro tolleranza per N frame consecutivi.
    Se CAMERA=False: non invia comandi, autoexp_ok=True dopo 5s.
    """
    if not cache.get('CAMERA', True):
        if cache.pop('reset_autoexp', False):
            cache['autoexp_pid'] = None
            cache['autoexp_ok'] = False
            cache['autoexp_fake_t0'] = None
        if cache.get('autoexp_fake_t0') is None:
            cache['autoexp_fake_t0'] = time.monotonic()
        cache['autoexp_ok'] = (time.monotonic() - cache['autoexp_fake_t0']) >= 5.0
        return image_view

    # Reset PID se richiesto
    if cache.pop('reset_autoexp', False):
        cache['autoexp_pid'] = None
        cache['autoexp_ok'] = False
        cache['autoexp_fake_t0'] = None
        exp_start = cache['config'].get('autoexp_exp_start', 200)
        cache['config']['exposure_absolute'] = exp_start
        os.system(f"v4l2-ctl --device /dev/video0 "
                  f"--set-ctrl=exposure_absolute={int(exp_start)}")

    config = cache['config']
    pid = cache.get('autoexp_pid')

    # Inizializza stato PID al primo frame
    if pid is None:
        pid = {
            'integral': 0.0,
            'prev_error': 0.0,
            'stable_since': None,
        }
        cache['autoexp_pid'] = pid

    # Parametri PID da config
    Kp = config.get('autoexp_Kp', 2.0)
    Ki = config.get('autoexp_Ki', 0.2)
    Kd = config.get('autoexp_Kd', 0.5)
    setpoint = config.get('autoexp_setpoint', 237)
    stable_tol = config.get('autoexp_stable_tol', 5)
    stable_time = config.get('autoexp_stable_time', 1.0)
    exp_min = config.get('autoexp_exp_min', 50)
    exp_max = config.get('autoexp_exp_max', 10000)
    integral_max = config.get('autoexp_integral_max', 2.0)

    try:
        r = np.max(image_input)
        exp_old = config['exposure_absolute']
        deadband = config.get('autoexp_deadband', 2)

        if abs(setpoint - r) <= deadband:
            # Banda morta: freeze esposizione e PID
            exp_new = exp_old
        else:
            # Errore normalizzato
            error = (setpoint - r) / setpoint

            # PID su errore normalizzato
            pid['integral'] += error
            pid['integral'] = np.clip(pid['integral'], -integral_max, integral_max)
            derivative = error - pid['prev_error']
            pid['prev_error'] = error

            correction = Kp * error + Ki * pid['integral'] + Kd * derivative

            # Limita correzione massima per frame (es. ±20%)
            max_corr = config.get('autoexp_max_corr', 0.2)
            correction = np.clip(correction, -max_corr, max_corr)

            # Applica correzione moltiplicativa
            exp_new = exp_old * (1.0 + correction)
            exp_new = np.clip(exp_new, exp_min, exp_max)
            config['exposure_absolute'] = float(exp_new)

            os.system(f"v4l2-ctl --device /dev/video0 "
                      f"--set-ctrl=exposure_absolute={int(exp_new)}")
            time.sleep(0.1)

        # Stabilità: max pixel entro tolleranza per stable_time secondi
        if abs(r - setpoint) <= stable_tol:
            if pid['stable_since'] is None:
                pid['stable_since'] = time.monotonic()
        else:
            pid['stable_since'] = None

        stable_elapsed = time.monotonic() - pid['stable_since'] if pid['stable_since'] else 0
        cache['autoexp_ok'] = stable_elapsed >= stable_time

        # Salva info debug per disegno su image_output
        ok_str = "OK" if cache['autoexp_ok'] else "..."
        px_lux = cache.get('px_lux', 0)
        cache['autoexp_debug_msg'] = f"max:{r} mean:{int(np.mean(image_input))} exp:{int(exp_new)} px_lux:{px_lux:.1f} [{ok_str}]"

    except Exception as e:
        logging.error(f"autoexp PID error: {e}")
        cache['autoexp_ok'] = False

    return image_view


def fixexp(cache,ctr):
    os.system(f"v4l2-ctl --device /dev/video{cache['config']['indice_camera']} --set-ctrl=exposure_absolute={ctr}")
    time.sleep(0.25)





