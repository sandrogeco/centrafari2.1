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
    sharpen_bandlimited,
    is_punto_ok
)
from funcs_anabbagliante import rileva_punto_angoloso, rileva_punto_angoloso1
from funcs_luminosita import calcola_px_lux
from camera import set_camera, apri_camera, autoexp
from comms import thread_comunicazione
from utils import uccidi_processo, get_colore, disegna_segmento
from calibrazione import CalibrationManager


def init_config(config_path, cache, percorso_script):
    """
    Carica configurazione da file JSON e aggiorna la cache.

    Args:
        config_path: Nome file config (es. "config.json" o "default.json")
        cache: Dizionario cache da aggiornare
        percorso_script: Path directory script
    """
    filepath = os.path.join(percorso_script, config_path)
    logging.info(f"Caricamento configurazione da {config_path}")

    with open(filepath, "r") as f:
        config = json.load(f)

    # Aggiorna cache
    cache["config"] = config
    cache["DEBUG"] = config.get("DEBUG") or False
    cache["CAMERA"] = config.get("CAMERA") or False
    cache["COMM"] = config.get("COMM") or False
    cache["AUTOEXP"] = config.get("AUTOEXP") or False

    # Aggiorna livello logging
    logging.getLogger().setLevel(
        logging.DEBUG if config.get("DEBUG", False) else logging.INFO
    )

    logging.info(f"Configurazione caricata da {config_path}")


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
    # 0. HOT RELOAD CONFIG
    # ====================
    config_file = os.path.join(cache['percorso_script'], 'config.json')
    try:
        mtime = os.path.getmtime(config_file)
        if mtime != cache.get('config_mtime', 0):
            cache['config_mtime'] = mtime
            init_config('config.json', cache, cache['percorso_script'])
            logging.info("Config ricaricata (file modificato)")
    except Exception as e:
        logging.error(f"Errore hot reload config: {e}")

    # ====================
    # 1. GESTIONE VISIBILITÀ FINESTRA
    # ====================
    root = lmain.master
    stato_comunicazione = cache.get('stato_comunicazione', {})
    should_show = stato_comunicazione.get('run', '1') == '1'
    prev_run = cache.get('prev_run', False)
    cache['prev_run'] = should_show

    # Transizione run 0→1: reset PID autoexp e riparti da esposizione iniziale
    if should_show and not prev_run:
        cache['autoexp_pid'] = None
        cache['config']['exposure_absolute'] = cache['config'].get('autoexp_exp_start', 200)
        logging.info("Run 0→1: reset autoexp PID")

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

    # Posizione: 0=dx, 1=sx, 2=fendinebbia
    pos = str(stato_comunicazione.get('pos', '0'))
    is_left_position = (pos == '1')
    is_fendinebbia_mode = (pos == '2')

    # Flip immagine se posizione sinistra
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
    # 4. ELABORAZIONE TIPO FARO / CALIBRAZIONE
    # ====================
    # pos=2 forza fendinebbia
    if is_fendinebbia_mode:
        tipo_faro = 'fendinebbia'
    else:
        tipo_faro = stato_comunicazione.get('tipo_faro', 'anabbagliante').strip()

    # Modalità calibrazione - avvia solo su transizione a 'calibrazione'
    prev_tipo_faro = cache.get('prev_tipo_faro', '')
    cache['prev_tipo_faro'] = tipo_faro

    if tipo_faro == 'calibrazione':
        # Transizione da altro tipo_faro -> calibrazione: ricrea e avvia
        if prev_tipo_faro != 'calibrazione':
            cache['calibration_manager'] = CalibrationManager(cache['percorso_script'], cache)
            cache['calibration_manager'].start_calibration()
        # Crea CalibrationManager on-demand se non esiste
        elif 'calibration_manager' not in cache:
            cache['calibration_manager'] = CalibrationManager(cache['percorso_script'], cache)
            cache['calibration_manager'].start_calibration()

        calibration_manager = cache['calibration_manager']

    if tipo_faro == 'calibrazione' and cache.get('calibration_manager') and cache['calibration_manager'].calibration_active:
        calibration_manager = cache['calibration_manager']

        # Step 1: salva media pixel intera immagine (riferimento buio)
        if calibration_manager.current_step == 1:
            import numpy as np
            cache['calib_px_lux_dark'] = 0.0

        # Step 3: esegui detection per mostrare punto e linee
        if calibration_manager.current_step == 3:
            results = fari_detection.detect_anabbagliante(
                image_input, cache, 5, 40, 120, 1e-8, 1e-8, 1000
            )
            image_output = fari_detection.draw_results(image_view, results, cache)
            point = results['punto']
            angles = results['angoli']
            # Salva punto per calibrazione (già su immagine preprocessata)
            cache['calibration_point'] = point
        else:
            # Step 1-2: nessuna detection
            image_output = image_view.copy()
            point = None
            angles = (0, 0, 0)
            results = {'punto': None, 'angoli': (0, 0, 0), 'linee': [], 'contorni': []}

        # Applica overlay di calibrazione
        image_output = calibration_manager.process_frame(image_output, cache)

    # Modalità detection normale
    else:
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
    lux_size = (config['lux_w'], config['lux_h'])

    # Abbagliante e fendinebbia: quadrato centrato sul punto (offset 0)
    if tipo_faro in ('abbagliante', 'fendinebbia'):
        sft_x = 0
        sft_y = 0
    else:
        sft_x = config['lux_sft_x'] * config['crop_w'] / 160
        sft_y = config['lux_sft_y'] * config['crop_h'] / 160

    if point:
        px_lux = calcola_px_lux(
            image_input, image_output, point,
            (sft_x, sft_y), lux_size, cache
        )
    else:
        center_point = (config['width'] / 2, config['height'] / 2)
        px_lux = calcola_px_lux(
            image_input, image_output, center_point,
            (sft_x, sft_y), lux_size, cache
        )

    cache['px_lux'] = px_lux

    # Salva px_lux per calibrazione step 3
    if (cache.get('calibration_manager') and
        cache['calibration_manager'].calibration_active and
        cache['calibration_manager'].current_step == 3 and point):
        cache['calib_px_lux_bright'] = px_lux

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
        inclinazione = int(stato_comunicazione.get('incl', 0))

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
        # Calcola indicatori direzionali
        ptok_result = is_punto_ok(point, cache)

        # Debug: verifica inclinazione e indicatori
        incl_value = cache['stato_comunicazione'].get('inclinazione', 'NOT_SET')
        toh_value = cache['stato_comunicazione'].get('TOH', 'NOT_SET')
        tov_value = cache['stato_comunicazione'].get('TOV', 'NOT_SET')
        logging.debug(f"Inclinazione: '{incl_value}' | TOH: '{toh_value}' | TOV: '{tov_value}'")
        logging.debug(f"Punto: {point} | Indicatori: L={ptok_result['left']} R={ptok_result['right']} U={ptok_result['up']} D={ptok_result['down']}")

        data = {
            'posiz_pattern_x': point[0],
            'posiz_pattern_y': point[1],
            'px_lux': px_lux,
            'yaw': angles[0],
            'pitch': angles[1],
            'roll': angles[2],
            'left': ptok_result['left'],
            'right': ptok_result['right'],
            'up': ptok_result['up'],
            'down': ptok_result['down']
        }
    else:
        data = {
            'posiz_pattern_x': 0,
            'posiz_pattern_y': 0,
            'px_lux': px_lux,
            'yaw': 0,
            'pitch': 0,
            'roll': 0,
            'left': 0,
            'right': 0,
            'up': 0,
            'down': 0
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

        # Autoexp debug
        autoexp_msg = cache.get('autoexp_debug_msg')
        if autoexp_msg:
            cv2.putText(image_output, autoexp_msg, (5, 80),
                    cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, get_colore('green'), 1)

    # Gestione rot (0=normale, 1=ruotato 180°)
    rot = int(stato_comunicazione.get('rot', 0))

    # Sposta finestra se rot cambia
    if 'root' in cache and rot != cache.get('last_rot', 0):
        root = cache['root']
        width = config['width']
        height = config['height']
        if rot == 1:
            # Posizione ruotata
            new_x = cache['screen_width'] - config['window_shift_x'] - width
            new_y = cache['screen_height'] - config['window_shift_y'] - height
        else:
            # Posizione normale
            new_x = config['window_shift_x']
            new_y = config['window_shift_y']
        root.geometry(f"{width}x{height}+{new_x}+{new_y}")
        cache['last_rot'] = rot
        logging.info(f"Finestra spostata per rot={rot}: ({new_x}, {new_y})")

    # Converti BGR (OpenCV) → RGB (PIL/tkinter) e visualizza immagine finale
    image_rgb = cv2.cvtColor(image_output, cv2.COLOR_BGR2RGB)
    img = PIL.Image.fromarray(image_rgb)

    # Flip 180° solo per visualizzazione se rot=1
    if rot == 1:
        img = img.transpose(PIL.Image.ROTATE_180)

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

    # Path directory script
    percorso_script = os.path.dirname(os.path.abspath(__file__))

    # Inizializza cache
    cache = {
        "DEBUG": False,
        "CAMERA": False,
        "COMM": False,
        "AUTOEXP": False,
        "config": {},
        "stato_comunicazione": {},
        "queue": Queue(),
        "percorso_script": percorso_script,
        "init_config": None  # Sarà impostato dopo
    }

    # Passa riferimento a init_config in cache (per calibrazione)
    cache["init_config"] = lambda config_path: init_config(config_path, cache, percorso_script)

    # Carica configurazione iniziale
    init_config("config.json", cache, percorso_script)

    #Avvia thread di comunicazione 
    if cache['COMM']:
        threading.Thread(
            target=partial(thread_comunicazione, cache['config']['port'], cache),
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

        # Callback per il click del mouse (modalità calibrazione e pulsante touch)
        def callback_click(event):
            """Gestisce il click del mouse/touch durante la calibrazione."""
            calibration_manager = cache.get('calibration_manager')
            if calibration_manager and calibration_manager.calibration_active:
                logging.info(f"Click ricevuto in calibrazione: ({event.x}, {event.y})")
                calibration_manager.handle_click(event.x, event.y, cache)
            else:
                logging.debug(f"Click ignorato (non in modalità calibrazione): ({event.x}, {event.y})")

        root = tk.Tk()
        root.overrideredirect(True)
        root.geometry(
            f"{cache['config']['width']}x{cache['config']['height']}+"
            f"{cache['config']['window_shift_x']}+{cache['config']['window_shift_y']}"
        )
        root.resizable(False, False)

        # Salva dimensioni schermo e root in cache per gestione rot
        cache['screen_width'] = root.winfo_screenwidth()
        cache['screen_height'] = root.winfo_screenheight()
        cache['root'] = root
        cache['last_rot'] = 0  # Traccia ultimo valore rot per rilevare cambiamenti

        lmain = tk.Label(root)
        lmain.bind("<Button-1>", callback_click)  # Bind click sinistro/touch
        lmain.pack()

        show_frame(cache, lmain)
        root.mainloop()
