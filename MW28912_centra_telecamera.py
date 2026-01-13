import sys
import tkinter as tk
from sqlite3 import enable_callback_tracebacks

import PIL
from PIL import ImageTk
import time
import threading
from functools import partial
import json
import os
import subprocess
import atexit
import signal
from datetime import datetime
import logging
import cv2

from utils import uccidi_processo
from camera import set_camera, apri_camera,autoexp,fixexp


def show_frame( cache, lmain):
    image_input = cv2.imread("/mnt/temp/frame.jpg")
    if image_input is None:
        lmain.after(10, lambda: show_frame(cache, lmain))
        return
   # image_input = image_input[-cache['config']['height']:, :]
    fixexp(cache,5000)
    #cache['autoexp_ok']=False

    if cache["crop_center"]:
        cv2.circle(image_input, cache["crop_center"], 5, (255, 0, 0), 2)
    # if cache["crop_w"] and cache["crop_h"]:
    #     crop_center = cache["crop_center"]
    #     crop_w = cache['crop_w']
    #     crop_h = cache['crop_h']
    #     start_y = max(int(crop_center[1] - crop_h / 2), 0)
    #     end_y = int(start_y + crop_h)
    #     start_x = max(int(crop_center[0] - crop_w / 2), 0)
    #     end_x = int(start_x + crop_w)
    #
    #     cv2.rectangle(image_input, (start_x, start_y), (end_x, end_y), (255, 0, 0), 2)

        # Segnala che la procedura e' terminata
        cache["OK"] = True
    logging.info("xxxx"+str(cache["crop_w"]))
    if not cache["crop_center"]:
        cv2.putText(image_input, "Clicca sul punto che dovra' essere", (5, 30), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 1)
        cv2.putText(image_input, "al centro del frame", (5, 60), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 1)
    # elif not cache["crop_w"] or not cache["crop_h"]:
    #     cv2.putText(image_input, "Clicca sul punto che definisce il", (5, 30), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 1)
    #     cv2.putText(image_input, "margine inferiore sx del frame", (5, 60), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 1)
    if cache["OK"]:
         cv2.putText(image_input, "Clicca di nuovo per terminare", (5, 30), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 1)
         cv2.putText(image_input, "la procedura", (5, 60), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 1)

    img = PIL.Image.fromarray(image_input)
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
            logging.FileHandler(f"/tmp/MW28912_centra_telecamerapy_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"),
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

    logging.info(f"Avvio MW28912_centra_telecamera.py {sys.argv}")

  #  uccidi_processo("usb_video_capture_cm4")

    tipo_faro = sys.argv[1].lower()

    # Carica la configurazione
    percorso_script = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(percorso_script, f"config_{tipo_faro}.json"), "r") as f:
        config = json.load(f)

    try:
        del config["crop_center"]
    except:
        pass
    # try:
    #     del config["crop_w"]
    # except:
    #     pass
    # try:
    #     del config["crop_h"]
    # except:
    #     pass

    # indice_camera, video = apri_camera()
    # if video is None:
    #     logging.error("Nessuna telecamera trovata! Uscita")
    #     sys.exit(1)
    # video.release()
    indice_camera=0
    set_camera(indice_camera, config)

    # Avvia la cattura delle immagini
    # time.sleep(1)
    # process_video_capture = subprocess.Popen(
    #     f"/home/pi/Applications/usb_video_capture_cm4 -c 10000000 -d /dev/video{indice_camera} &>/tmp/usb_video_capture_cm4.log",
    #     shell=True,
    #     preexec_fn=os.setsid,
    #     stdin=subprocess.DEVNULL,
    #     stdout=subprocess.DEVNULL,
    #     stderr=subprocess.DEVNULL,
    # )
    # atexit.register(partial(cleanup, process_video_capture))
    # logging.debug("Cattura avviata")
    #
    # def _sig_handler(signum, frame):
    #     cleanup(process_video_capture)
    #     sys.exit(0)
    #
    # for s in (signal.SIGINT, signal.SIGTERM):
    #     signal.signal(s, _sig_handler)

    cache = {
        "crop_center": None,
        "crop_w": None,
        "crop_h": None,
        "OK": False,
        "config":config
    }
    cache['config']['indice_camera'] = 0
    # Imposta la finestra
    def callback_click(event):
        logging.info(f"callback_click {event.x}, {event.y}")

        with open(os.path.join(percorso_script, f"config_{tipo_faro}.json"), "r") as f:
            config = json.load(f)

        if not cache["crop_center"]:
            config["crop_center"] = (event.x, event.y)
            cache["crop_center"] = config["crop_center"]
        # elif not cache["crop_w"] or not cache["crop_h"]:
        #     config["crop_w"] = 2 * abs(event.x - cache["crop_center"][0])
        #     config["crop_h"] = 2 * abs(event.y - cache["crop_center"][1])
        #     cache["crop_w"] = config["crop_w"]
        #     cache["crop_h"] = config["crop_h"]

        if cache["OK"]:
            sys.exit(0)

        with open(os.path.join(percorso_script, f"config_{tipo_faro}.json"), "w") as f:
            json.dump(config, f, indent=4)
        with open(os.path.join(percorso_script, f"config_fendinebbia.json"), "r") as f:
            config = json.load(f)
        config["crop_center"] = (event.x, event.y)
        with open(os.path.join(percorso_script, f"config_fendinebbia.json"), "w") as f:
            json.dump(config, f, indent=4)#agg

    root = tk.Tk()
    root.overrideredirect(True)
    root.geometry(f"{config['width']}x{config['height']}+{config['window_shift_x']}+{config['window_shift_y']}")
    root.resizable(False, False)
    lmain = tk.Label(root)
    lmain.bind("<Button-1>", callback_click)
    lmain.pack()

    show_frame( cache, lmain)
    root.mainloop()
