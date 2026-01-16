"""
Modulo per la calibrazione della telecamera.
Gestisce diversi step di calibrazione in modo modulare.
"""

import cv2
import json
import os
import logging
import shutil
from utils import get_colore


class CalibrationManager:
    """
    Gestisce il processo di calibrazione multi-step.

    Step disponibili:
    - Step 0: Inizializzazione (copia default.json -> config.json)
    - Step 1: Centra telecamera (crop_center)
    - Step 2+: Futuri step (da aggiungere)
    """

    def __init__(self, config_path):
        """
        Inizializza il gestore di calibrazione.

        Args:
            config_path: Path alla directory contenente i file di configurazione
        """
        self.config_path = config_path
        self.default_file = os.path.join(config_path, "default.json")
        self.config_file = os.path.join(config_path, "config.json")

        # Stato calibrazione
        self.current_step = 0
        self.step_data = {}
        self.calibration_active = False

    def start_calibration(self):
        """
        Avvia la procedura di calibrazione.
        Copia default.json -> config.json e inizializza lo step 1.
        """
        logging.info("Avvio calibrazione: copia default.json -> config.json")

        # Copia default.json -> config.json
        if os.path.exists(self.default_file):
            shutil.copy(self.default_file, self.config_file)
            logging.info("Config ripristinato da default.json")
        else:
            logging.warning("default.json non trovato, uso config.json esistente")

        # Inizializza step 1: centra telecamera
        self.current_step = 1
        self.calibration_active = True
        self.step_data = {
            'crop_center': None,
            'ok': False
        }

        logging.info(f"Calibrazione avviata: step {self.current_step}")

    def stop_calibration(self):
        """Termina la calibrazione e salva i dati."""
        logging.info("Calibrazione terminata")
        self.calibration_active = False
        self.current_step = 0
        self.step_data = {}

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

        # Primo click: imposta crop_center
        if not self.step_data.get('crop_center'):
            self.step_data['crop_center'] = (x, y)
            self.step_data['ok'] = True

            # Salva in config.json
            self._save_crop_center(x, y)

            logging.info(f"crop_center impostato a ({x}, {y})")
            return False

        # Secondo click: conferma e termina
        elif self.step_data.get('ok'):
            logging.info("Calibrazione Step 1 completata")
            self.stop_calibration()
            return True

        return False

    def _save_crop_center(self, x, y):
        """
        Salva crop_center in config.json.

        Args:
            x: Coordinata X
            y: Coordinata Y
        """
        try:
            # Leggi config.json
            with open(self.config_file, 'r') as f:
                config = json.load(f)

            # Aggiorna crop_center
            config['crop_center'] = [x, y]

            # Salva config.json
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)

            logging.info(f"crop_center salvato in config.json: [{x}, {y}]")

        except Exception as e:
            logging.error(f"Errore nel salvare crop_center: {e}")

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
