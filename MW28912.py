"""
Applicazione per centratura e calibrazione fari MW28912.
Gestisce l'elaborazione immagini e l'interfaccia grafica per la centratura dei fari.
"""

# Standard library imports
import sys
import os
import json
import time
import logging
import signal
import subprocess
import atexit
import threading
from datetime import datetime
from functools import partial
from queue import Queue

# Third-party imports
import cv2
import tkinter as tk
import PIL
from PIL import ImageTk

# Local imports
import fari_detection
from funcs_misc import (
    preprocess,
    visualizza_croce_riferimento,
    blur_and_sharpen,
    sharpen_dog,
    sharpen_bandlimited
)
from funcs_anabbagliante import rileva_punto_angoloso, rileva_punto_angoloso1
from funcs_luminosita import calcola_lux
from camera import set_camera, apri_camera, autoexp
from comms import thread_comunicazione
from utils import uccidi_processo, get_colore, disegna_segmento


def show_frame(cache, lmain):
    """
    Elabora e visualizza un frame dell'immagine del faro.

    Ciclo principale di elaborazione che:
    1. Gestisce la visibilità della finestra
    2. Carica e preprocessa l'immagine
    3. Rileva il pattern del faro
    4. Calcola luminosità e posizione
    5. Visualizza croce di riferimento
    6. Aggiorna i dati in coda per la comunicazione

    Args:
        cache: Dizionario con configurazione e stato dell'applicazione
        lmain: Widget Label di tkinter per visualizzare l'immagine
    """
    # ====================
    # 1. GESTIONE VISIBILITÀ FINESTRA
    # ====================
    root = lmain.master
    stato_comunicazione = cache.get('stato_comunicazione', {})
    should_show = stato_comunicazione.get('run', '1') == '1'

    current_state = root.state()
    if should_show and current_state == 'withdrawn':
        root.deiconify()
        logging.info("Finestra mostrata")
    elif not should_show and current_state != 'withdrawn':
        root.withdraw()
        logging.info("Finestra nascosta")

    # Timer debug
    if cache['DEBUG']:
        t0 = time.monotonic()

    # ====================
    # 2. CARICAMENTO FRAME
    # ====================
    image_input = cv2.imread("/mnt/temp/frame.jpg")

    if image_input is None:
        lmain.after(10, lambda: show_frame(cache, lmain))
        return

    # ====================
    # 3. PREPROCESSING IMMAGINE
    # ====================
    # Preprocessing base e auto-esposizione
    image_input, image_view = preprocess(image_input, cache)
    if cache['AUTOEXP']:
        image_view = autoexp(image_input, image_view, cache)
    else:
        cache['autoexp_ok'] = True

    # Flip immagine se posizione sinistra
    is_left_position = cache.get('pos', 'dx') == 'sx'
    if is_left_position:
        image_input = cv2.flip(image_input, 1)
        image_view = cv2.flip(image_view, 1)

    # Conversione pattern (0,1 = grayscale, 2 = colormap JET)
    pattern = stato_comunicazione.get('pattern', '0')
    logging.debug(f"[PT] {pattern}")

    if pattern in ['0', '1']:
        image_input = cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)
    elif pattern == '2':
        image_view = cv2.applyColorMap(255 - image_view.copy(), cv2.COLORMAP_JET)
        image_input = cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)

    # ====================
    # 4. ELABORAZIONE TIPO FARO
    # ====================
    tipo_faro = stato_comunicazione.get('tipo_faro', 'anabbagliante').strip()

    # Esegui detection (solo calcolo, no disegno)
    if tipo_faro == 'anabbagliante':
        results = fari_detection.detect_anabbagliante(
            image_input, cache, 5, 40, 120, 1e-8, 1e-8, 1000
        )
    elif tipo_faro == 'fendinebbia':
        results = fari_detection.detect_fendinebbia(
            image_input, cache, 5, 40, 120, 1e-8, 1e-8, 1000
        )
    elif tipo_faro == 'abbagliante':
        results = fari_detection.detect_abbagliante(
            image_input, cache
        )
    else:
        logging.warning(f"Tipo faro sconosciuto: {tipo_faro}")
        results = {'punto': None, 'angoli': (0, 0, 0), 'linee': [], 'contorni': []}

    # Disegna i risultati
    image_output = fari_detection.draw_results(image_view, results, cache)

    # Estrai punto e angoli dai risultati
    point = results['punto']
    angles = results['angoli']

    # ====================
    # 5. CALCOLO LUMINOSITÀ
    # ====================
    config = cache['config']
    sft_x = config['lux_sft_x'] * config['crop_w'] / 160
    sft_y = config['lux_sft_y'] * config['crop_h'] / 160
    lux_size = (config['lux_w'], config['lux_h'])

    if point:
        lux = calcola_lux(
            image_input, image_output, point,
            (sft_x, sft_y), lux_size, cache
        )
    else:
        center_point = (config['width'] / 2, config['height'] / 2)
        lux = calcola_lux(
            image_input, image_output, center_point,
            (sft_x, sft_y), lux_size, cache
        )

    # ====================
    # 6. POST-PROCESSING
    # ====================
    # Flip finale se posizione sinistra
    if is_left_position:
        if point:
            point = (config['width'] - point[0], point[1])
        image_output = cv2.flip(image_output, 1)

    # Visualizza croce di riferimento
    if stato_comunicazione.get('croce', '0') == '1':
        center_x = int(config['width'] / 2)
        center_y = int(config['height'] / 2)
        inclinazione = int(stato_comunicazione.get('inclinazione', '0'))

        if tipo_faro == 'fendinebbia':
            # Linee orizzontali per fendinebbia
            tov = config.get('TOV', 50)
            y_top = center_y + inclinazione - tov
            y_bottom = center_y + inclinazione + tov

            disegna_segmento(
                image_output, (0, y_top),
                (config['width'], y_top), 1, 'green'
            )
            disegna_segmento(
                image_output, (0, y_bottom),
                (config['width'], y_bottom), 1, 'green'
            )
        else:
            # Croce standard per anabbagliante/abbagliante
            toh = int(stato_comunicazione.get('TOH', config.get('TOH', 50)))
            tov = int(stato_comunicazione.get('TOV', config.get('TOV', 50)))
            visualizza_croce_riferimento(
                image_output, center_x, center_y + inclinazione,
                2 * tov, 2 * toh
            )

    # ====================
    # 7. AGGIORNAMENTO DATI IN CODA
    # ====================
    if point:
        data = {
            'posiz_pattern_x': point[0],
            'posiz_pattern_y': point[1],
            'lux': lux,
            'yaw': angles[0],
            'pitch': angles[1],
            'roll': angles[2]
        }
    else:
        data = {
            'posiz_pattern_x': 0,
            'posiz_pattern_y': 0,
            'lux': lux,
            'yaw': 0,
            'pitch': 0,
            'roll': 0
        }

    cache['queue'].put(data)

    # ====================
    # 8. DEBUG E VISUALIZZAZIONE
    # ====================
    if cache['DEBUG']:
        elapsed_ms = int(1000 * (time.monotonic() - t0))
        fps = int(1 / (t0 - cache.get('t0', 0))) if cache.get('t0') else 0
        msg = f"Elaborazione: {elapsed_ms} ms, FPS: {fps}"
        logging.debug(msg)

        cv2.putText(
            image_output, msg, (5, 60),
            cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5,
            get_colore('green'), 1
        )
        cache['t0'] = t0

    # Converti BGR (OpenCV) → RGB (PIL/tkinter) e visualizza immagine finale
    image_rgb = cv2.cvtColor(image_output, cv2.COLOR_BGR2RGB)
    img = PIL.Image.fromarray(image_rgb)
    imgtk = ImageTk.PhotoImage(image=img)
    lmain.imgtk = imgtk
    lmain.configure(image=imgtk)

    # Richiama ricorsivamente dopo 5ms
    lmain.after(5, lambda: show_frame(cache, lmain))


def cleanup(p):
    """
    Pulisce i processi all'uscita.

    Args:
        p: Processo da terminare
    """
    logging.info("cleanup...")
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


if __name__ == "__main__":
    # Configurazione logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler(
                f"/mnt/temp/MW28912py_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
            ),
            logging.StreamHandler()
        ]
    )

    def log_unhandled(exc_type, exc_value, exc_tb):
        """Logga eccezioni non gestite."""
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = log_unhandled

    def log_thread_exceptions(args):
        """Logga eccezioni nei thread."""
        logging.error(
            "Uncaught exception in thread %s", args.thread.name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
        )

    threading.excepthook = log_thread_exceptions

    logging.info(f"Avvio MW28912.py {sys.argv}")

    # Carica configurazione
    percorso_script = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(percorso_script, "config.json"), "r") as f:
        config = json.load(f)

    logging.getLogger().setLevel(
        logging.DEBUG if config.get("DEBUG", False) else logging.INFO
    )

    # Inizializza cache
    cache = {
        "DEBUG": config.get("DEBUG") or False,
        "CAMERA": config.get("CAMERA") or False,
        "COMM": config.get("COMM") or False,
        "AUTOEXP": config.get("AUTOEXP") or False,
        "config": config,
        "stato_comunicazione": {},
        "queue": Queue()
    }

    #Avvia thread di comunicazione 
    if cache['COMM']:
        threading.Thread(
            target=partial(thread_comunicazione, config['port'], cache),
            daemon=True,
            name="com_in"
        ).start()

    # Inizializza e avvia GUI
    if True:
        if cache['CAMERA']:
            indice_camera = 0
            cache['config']['indice_camera'] = indice_camera
            set_camera(indice_camera, cache['config'])
            time.sleep(1)

        root = tk.Tk()
        root.overrideredirect(True)
        root.geometry(
            f"{config['width']}x{config['height']}+"
            f"{config['window_shift_x']}+{config['window_shift_y']}"
        )
        root.resizable(False, False)
        lmain = tk.Label(root)
        lmain.pack()

        show_frame(cache, lmain)
        root.mainloop()
