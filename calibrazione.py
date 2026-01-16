"""
Modulo per la calibrazione della telecamera.
Gestisce diversi step di calibrazione in modo modulare.
"""

import cv2
import json
import os
import logging
from utils import get_colore


class CalibrationManager:
    """
    Gestisce il processo di calibrazione multi-step.

    Step disponibili:
    - Step 0: Inizializzazione (copia default.json -> config.json)
    - Step 1: Centra telecamera (crop_center)
    - Step 2+: Futuri step (da aggiungere)
    """

    def __init__(self, config_path, cache):
        """
        Inizializza il gestore di calibrazione.

        Args:
            config_path: Path alla directory contenente i file di configurazione
            cache: Dizionario cache condiviso con MW28912
        """
        self.config_path = config_path
        self.default_file = os.path.join(config_path, "default.json")
        self.config_file = os.path.join(config_path, "config.json")
        self.cache = cache

        # Stato calibrazione
        self.current_step = 0
        self.step_data = {}
        self.calibration_active = False

        # Area pulsante "TERMINA CALIBRAZIONE" (x, y, w, h)
        self.exit_button_rect = None

    def start_calibration(self):
        """
        Avvia la procedura di calibrazione.
        Carica default.json in cache e inizializza lo step 1.
        """
        logging.info("Avvio calibrazione: caricamento default.json in cache")

        # Carica default.json in cache (invece di copiare file)
        init_config = self.cache.get('init_config')
        if init_config:
            init_config("default.json")
            logging.info("Configurazione default caricata in cache")
        else:
            logging.warning("init_config non disponibile in cache")

        # Inizializza step 1: centra telecamera
        self.current_step = 1
        self.calibration_active = True
        self.step_data = {
            'crop_center': self.cache['config'].get('crop_center'),  # Prendi da default
            'ok': False
        }

        logging.info(f"Calibrazione avviata: step {self.current_step}")

    def stop_calibration(self):
        """Termina la calibrazione, salva config.json e ricarica."""
        logging.info("Calibrazione terminata")

        # Salva cache['config'] su config.json
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.cache['config'], f, indent=4)
            logging.info("Configurazione salvata in config.json")
        except Exception as e:
            logging.error(f"Errore nel salvare config.json: {e}")

        # Ricarica config.json in cache
        init_config = self.cache.get('init_config')
        if init_config:
            init_config("config.json")
            logging.info("Configurazione ricaricata da config.json")

        self.calibration_active = False
        self.current_step = 0
        self.step_data = {}

        # Rimuovi "calibrazione" da tipo_faro per uscire dalla modalità
        if 'tipo_faro' in self.cache['stato_comunicazione']:
            if self.cache['stato_comunicazione']['tipo_faro'] == 'calibrazione':
                # Ripristina a anabbagliante (default)
                self.cache['stato_comunicazione']['tipo_faro'] = 'anabbagliante'
                logging.info("tipo_faro ripristinato a 'anabbagliante'")

    def process_frame(self, image_output, cache):
        """
        Elabora un frame durante la calibrazione.

        Args:
            image_output: Immagine su cui disegnare
            cache: Cache con configurazione

        Returns:
            Immagine con overlay di calibrazione
        """
        if not self.calibration_active:
            return image_output

        if self.current_step == 1:
            return self._process_step1_centra_telecamera(image_output, cache)

        # Step futuri qui
        # elif self.current_step == 2:
        #     return self._process_step2_xxx(image_output, cache)

        return image_output

    def _process_step1_centra_telecamera(self, image_output, cache):
        """
        Step 1: Centra telecamera (crop_center).

        Args:
            image_output: Immagine su cui disegnare
            cache: Cache con configurazione

        Returns:
            Immagine con overlay
        """
        # Disegna cerchio blu sul crop_center se già impostato
        crop_center = self.step_data.get('crop_center')
        if crop_center:
            cv2.circle(image_output, crop_center, 5, (255, 0, 0), 2)
            cv2.circle(image_output, crop_center, 10, (255, 0, 0), 1)

        # Istruzioni
        if not crop_center:
            cv2.putText(image_output, "CALIBRAZIONE: Clicca sul punto che", (5, 30),
                       cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, get_colore('cyan'), 1)
            cv2.putText(image_output, "dovra' essere al centro del frame", (5, 60),
                       cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, get_colore('cyan'), 1)
        elif self.step_data.get('ok'):
            cv2.putText(image_output, "CALIBRAZIONE: Clicca di nuovo per", (5, 30),
                       cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, get_colore('green'), 1)
            cv2.putText(image_output, "confermare e terminare", (5, 60),
                       cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, get_colore('green'), 1)

        # Pulsante "TERMINA CALIBRAZIONE" in basso a destra
        width = cache['config'].get('width', 630)
        height = cache['config'].get('height', 320)

        btn_w = 200
        btn_h = 40
        btn_x = width - btn_w - 10
        btn_y = height - btn_h - 10

        # Salva area pulsante per rilevamento click
        self.exit_button_rect = (btn_x, btn_y, btn_w, btn_h)

        # Disegna rettangolo pulsante (rosso)
        cv2.rectangle(image_output, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h),
                     get_colore('red'), -1)
        cv2.rectangle(image_output, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h),
                     get_colore('white'), 2)

        # Testo "TERMINA" centrato nel pulsante
        text = "TERMINA"
        font_scale = 1.0
        thickness = 2
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
        text_x = btn_x + (btn_w - text_size[0]) // 2
        text_y = btn_y + (btn_h + text_size[1]) // 2

        cv2.putText(image_output, text, (text_x, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale, get_colore('white'), thickness)

        return image_output

    def handle_click(self, x, y, cache):
        """
        Gestisce il click del mouse durante la calibrazione.

        Args:
            x: Coordinata X del click
            y: Coordinata Y del click
            cache: Cache con configurazione

        Returns:
            True se la calibrazione è terminata, False altrimenti
        """
        if not self.calibration_active:
            return False

        if self.current_step == 1:
            return self._handle_click_step1(x, y, cache)

        # Step futuri qui
        # elif self.current_step == 2:
        #     return self._handle_click_step2(x, y, cache)

        return False

    def _handle_click_step1(self, x, y, cache):
        """
        Gestisce il click per lo step 1: centra telecamera.

        Args:
            x: Coordinata X del click
            y: Coordinata Y del click
            cache: Cache con configurazione

        Returns:
            True se lo step è completato, False altrimenti
        """
        logging.info(f"Step 1 - Click ricevuto: ({x}, {y})")

        # Verifica se il click è sul pulsante TERMINA
        if self.exit_button_rect:
            btn_x, btn_y, btn_w, btn_h = self.exit_button_rect
            if btn_x <= x <= btn_x + btn_w and btn_y <= y <= btn_y + btn_h:
                logging.info("Click sul pulsante TERMINA: esco dalla calibrazione")
                self.stop_calibration()
                return True

        # Primo click: imposta crop_center
        if not self.step_data.get('crop_center'):
            self.step_data['crop_center'] = (x, y)
            self.step_data['ok'] = True

            # Aggiorna cache['config'] (non salvare su file ancora)
            self.cache['config']['crop_center'] = [x, y]

            logging.info(f"crop_center impostato a ({x}, {y}) in cache")
            return False

        # Secondo click: conferma e termina
        elif self.step_data.get('ok'):
            logging.info("Calibrazione Step 1 completata")
            self.stop_calibration()
            return True

        return False

    def get_status(self):
        """
        Restituisce lo stato attuale della calibrazione.

        Returns:
            Dict con stato calibrazione
        """
        return {
            'active': self.calibration_active,
            'step': self.current_step,
            'data': self.step_data
        }
