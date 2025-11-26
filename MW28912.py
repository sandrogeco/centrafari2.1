import sys
import cv2
import tkinter as tk
import PIL
from PIL import ImageTk
import time
import threading
from queue import Queue
from functools import partial
import json
import os
import subprocess
import atexit
import signal
from datetime import datetime
import logging
import fit_lines
from funcs_misc import preprocess, visualizza_croce_riferimento,blur_and_sharpen,sharpen_dog,sharpen_bandlimited
from funcs_anabbagliante import rileva_punto_angoloso,rileva_punto_angoloso1
from funcs_abbagliante import trova_contorni_abbagliante
from funcs_luminosita import calcola_lux
from camera import set_camera, apri_camera, autoexp
from comms import thread_comunicazione
from utils import uccidi_processo, get_colore, disegna_segmento


def show_frame( cache, lmain):
    if cache['DEBUG']:
        t0 = time.monotonic()

    image_input = cv2.imread("/mnt/temp/frame.jpg")

    if image_input is None:
        lmain.after(10, lambda: show_frame( cache, lmain))
        return
    stato_comunicazione = cache['stato_comunicazione']

    image_input,image_view = preprocess(image_input, cache)
    if (cache['CAMERA'])and(cache['AUTOEXP']):
        image_view=autoexp(image_input, image_view,cache)
    else:
        cache['autoexp']=False

    if cache['pos']=='sx':
        image_input=cv2.flip(image_input,1)
        image_view = cv2.flip(image_view, 1)
    #image_output= cv2.cvtColor(image_input, cv2.COLOR_GRAY2BGR)
#    image_output = cv2.cvtColor(image_input.copy(), cv2.COLOR_GRAY2BGR)
    if stato_comunicazione.get('pattern',0)==0:
        image_input = cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)
        #image_view = cv2.cvtColor(image_view, cv2.COLOR_BGR2GRAY)
    if stato_comunicazione.get('pattern',0)==1:
        image_input = cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)
       # image_view = cv2.applyColorMap(image_view.copy(), cv2.COLOR_BGR2GRAY)
    if stato_comunicazione.get('pattern',0)==2:
        image_view = cv2.applyColorMap(255-image_view.copy(), cv2.COLORMAP_JET)
        image_input = cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)

    dim=image_view.shape


    logging.debug(f"[PT] {stato_comunicazione.get('pattern',0)}")

    if cache['tipo_faro'] == 'anabbagliante':
        image_output, point,angles =fit_lines.fit_lines(image_input,image_view,cache, 5, 40, 120, 1e-8, 1e-8, 1000)
    if cache['tipo_faro'] == 'fendinebbia':
        image_output, point,angles =fit_lines.fit_lines(image_input,image_view,cache, 5, 40, 120, 1e-8, 1e-8, 1000,False,True)
    elif cache['tipo_faro'] == 'abbagliante':
        image_output, point,angles = trova_contorni_abbagliante(image_input, image_view, cache)
    sft_x=cache['config']['lux_sft_x']*cache['config']['crop_w']/160
    sft_y = cache['config']['lux_sft_y'] * cache['config']['crop_h'] / 160
    lux = calcola_lux(image_input, image_output, point, (sft_x,sft_y),
                      (cache['config']['lux_w'], cache['config']['lux_h']), cache) if point \
        else calcola_lux(image_input, image_output, (cache['config']['width']/2,cache['config']['height']/2), (sft_x, sft_y),
                (cache['config']['lux_w'], cache['config']['lux_h']), cache)

    if cache['pos']=='sx':
        point=(cache['config']['width']-point[0],point[1])
        image_output = cv2.flip(image_output, 1)
    logging.debug("pos "+cache['pos'])


    if stato_comunicazione.get('croce', 0) == 1:
        if cache['tipo_faro'] == 'fendinebbia':

            disegna_segmento(image_output, (0,
                             int(cache['config']['height'] / 2) + stato_comunicazione.get('inclinazione', 0)-stato_comunicazione.get('TOV', 50)),
                             (int(cache['config']['width']),
                             int(cache['config']['height'] / 2) + stato_comunicazione.get('inclinazione', 0)-stato_comunicazione.get('TOV', 50)),1,'green')
            disegna_segmento(image_output, (0,
                             int(cache['config']['height'] / 2) + stato_comunicazione.get('inclinazione', 0)+stato_comunicazione.get('TOV', 50)),
                             (int(cache['config']['width']),
                             int(cache['config']['height'] / 2) + stato_comunicazione.get('inclinazione', 0)+stato_comunicazione.get('TOV', 50)),1,'green')


        else:
            visualizza_croce_riferimento(
                image_output,
                int(cache['config']['width'] / 2),
                int(cache['config']['height'] / 2) + stato_comunicazione.get('inclinazione', 0),
                2 * stato_comunicazione.get('TOV', 50),
                2 * stato_comunicazione.get('TOH', 50)
            )

    if point:

        cache['queue'].put({ 'posiz_pattern_x': point[0], 'posiz_pattern_y': point[1], 'lux': lux ,'yaw':angles[0],'pitch':angles[1],'roll':angles[2]})
    else:
        cache['queue'].put({'posiz_pattern_x': 0, 'posiz_pattern_y': 0, 'lux': lux,'yaw':0,'pitch':0,'roll':0})

    if cache['DEBUG']:
        msg = f"Durata elaborazione: {int(1000 * (time.monotonic() - t0))} ms, fps = {int(1 / (t0 - cache.get('t0', 0)))}"
        logging.debug(msg)
        cv2.putText(image_output, msg, (5, 60), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)
        cache['t0'] = t0


    #image_output=blur_and_sharpen(image_output,1.5,0.5,True)
    #image_output=sharpen_dog(image_output,2,4,0.7)
    #image_output=sharpen_bandlimited(image_output,5,4,2)
    # c = 5
    # image_output=cv2.resize(image_output, (dim[1]*c,dim[0]*c), interpolation=cv2.INTER_NEAREST)


    # import numpy as np
    # kernel = np.array([[-1, -1, -1],
    #                    [-1, 9, -1],
    #                    [-1, -1, -1]], np.float32)
    # kernel = np.array([[0, -1, 0],
    #                    [-1, 5, -1],
    #                    [0, -1, 0]], np.float32)
    #
    #
    # image_output = cv2.filter2D(image_output, -1, kernel)
    # image_output = cv2.resize(image_output,(dim[1] , dim[0] ), interpolation=cv2.INTER_AREA)

    img = PIL.Image.fromarray(image_output)
    imgtk = ImageTk.PhotoImage(image=img)
    lmain.imgtk = imgtk
    lmain.configure(image=imgtk)
    lmain.after(5, lambda: show_frame(cache, lmain))


def cleanup(p):
    logging.info("cleanup...")
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler(f"/mnt/temp/MW28912py_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"),
            logging.StreamHandler()
        ]
    )

    def log_unhandled(exc_type, exc_value, exc_tb):
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
    sys.excepthook = log_unhandled

    def log_thread_exceptions(args):
        logging.error("Uncaught exception in thread %s", args.thread.name,
                      exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    threading.excepthook = log_thread_exceptions

    logging.info(f"Avvio MW28912.py {sys.argv}")

    percorso_script = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(percorso_script, f"config.json"), "r") as f:
        config = json.load(f)

    logging.getLogger().setLevel(logging.DEBUG if config.get("DEBUG", False) else logging.INFO)

    cache = {
        "DEBUG": config.get("DEBUG") or False,
        "CAMERA":config.get("CAMERA") or False,
        "COMM":config.get("COMM") or False,
        "AUTOEXP": config.get("AUTOEXP") or False,
        "config": config,
        "stato_comunicazione": {},
        "queue": Queue()
    }

    if cache['COMM']:
        threading.Thread(target=partial(thread_comunicazione, config['port'], cache), daemon=True, name="com_in").start()

if False:
    if cache['CAMERA']:
        indice_camera=0
        cache['config']['indice_camera']=indice_camera
        set_camera(indice_camera, cache['config'])
        time.sleep(1)

    root = tk.Tk()
    root.overrideredirect(True)
    root.geometry(f"{config['width']}x{config['height']}+{config['window_shift_x']}+{config['window_shift_y']}")
    root.resizable(False, False)
    lmain = tk.Label(root)
    lmain.pack()

    show_frame(cache, lmain)
    root.mainloop()



