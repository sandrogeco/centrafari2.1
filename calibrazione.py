"""
Modulo per la calibrazione della telecamera.
Gestisce diversi step di calibrazione in modo modulare.

Step di calibrazione:
    1. Calibrazione buio - Acquisizione riferimento con faro spento
    2. Centraggio - Definizione punto centrale del frame
    3. Inclinazione - Calibrazione inclinazione fascio luminoso
"""

import cv2
import json
import os
import logging
from utils import get_colore
import fari_detection


# =============================================================================
# STRINGHE LOCALIZZABILI
# Dizionario per supporto multilingua. Chiave = codice stringa, valore = testo.
# Per aggiungere una lingua: creare nuovo dizionario (es. STRINGS_EN) e
# selezionarlo in base alla configurazione.
# =============================================================================

STRINGS_IT = {
    # Titolo sezione calibrazione
    'title': 'Calibrazione',

    # Nomi degli step (mostrati nella lista a sinistra)
    'step1_name': '1. Calibrazione buio',
    'step2_name': '2. Centraggio',
    'step3_name': '3. Inclinazione',

    # Istruzioni per ogni step (mostrate in basso)
    'step1_instruction': 'Spegnere faro',
    'step2_instruction': 'Accendere a inclinazione 0 e cliccare su punto centrale',
    'step3_instruction': 'Portare a inclinazione 4% e cliccare per confermare',

    # Pulsante termina
    'btn_terminate': 'TERMINA',
}

# Lingua attiva (per ora solo italiano, in futuro selezionabile)
STRINGS = STRINGS_IT


class CalibrationManager:
    """
    Gestisce il processo di calibrazione multi-step.

    Step disponibili:
        - Step 1: Calibrazione buio (placeholder - da implementare)
        - Step 2: Centraggio telecamera (crop_center)
        - Step 3: Inclinazione (placeholder - da implementare)

    Attributi:
        config_path: Path alla directory dei file di configurazione
        cache: Dizionario cache condiviso con MW28912
        current_step: Step attualmente attivo (1-3)
        steps_completed: Set degli step completati
        calibration_active: True se calibrazione in corso
    """

    # Numero totale di step di calibrazione
    TOTAL_STEPS = 3

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

        # Set degli step completati (per mostrare spunta)
        self.steps_completed = set()

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

        # Reset stato
        self.steps_completed = set()
        self.calibration_active = True

        # Inizia da step 1 (calibrazione buio)
        self.current_step = 1
        self.step_data = {
            'state': 0,  # Stato iniziale per ogni step
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
        self.steps_completed = set()

    def _advance_to_next_step(self):
        """
        Avanza allo step successivo o termina se completati tutti.
        Marca lo step corrente come completato prima di avanzare.
        """
        # Marca step corrente come completato
        self.steps_completed.add(self.current_step)
        logging.info(f"Step {self.current_step} completato")

        # Avanza al prossimo step
        if self.current_step < self.TOTAL_STEPS:
            self.current_step += 1
            self.step_data = {'state': 0}  # Reset stato per nuovo step
            logging.info(f"Avanzamento a step {self.current_step}")
        else:
            # Tutti gli step completati
            logging.info("Tutti gli step completati, termino calibrazione")
            self.stop_calibration()

    def process_frame(self, image_output, cache):
        """
        Elabora un frame durante la calibrazione.
        Disegna l'interfaccia di calibrazione sull'immagine.

        Args:
            image_output: Immagine su cui disegnare
            cache: Cache con configurazione

        Returns:
            Immagine con overlay di calibrazione
        """
        if not self.calibration_active:
            return image_output

        # Disegna interfaccia comune (titolo, lista step, istruzioni)
        self._draw_calibration_ui(image_output, cache)

        # Elabora step specifico
        if self.current_step == 1:
            self._process_step1_buio(image_output, cache)
        elif self.current_step == 2:
            self._process_step2_centraggio(image_output, cache)
        elif self.current_step == 3:
            self._process_step3_inclinazione(image_output, cache)

        # Disegna pulsante TERMINA
        self._draw_terminate_button(image_output, cache)

        return image_output

    def _draw_calibration_ui(self, image_output, cache):
        """
        Disegna l'interfaccia comune di calibrazione:
        - Titolo "Calibrazione" in alto a sinistra
        - Lista step con spunte per quelli completati
        - Istruzione corrente in basso

        Args:
            image_output: Immagine su cui disegnare
            cache: Cache con configurazione
        """
        height = cache['config'].get('height', 320)

        # Colori
        color_title = get_colore('cyan')
        color_active = get_colore('yellow')
        color_completed = get_colore('green')
        color_pending = get_colore('white')
        color_instruction = get_colore('cyan')

        # --- TITOLO ---
        cv2.putText(image_output, STRINGS['title'], (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_title, 2)

        # --- LISTA STEP ---
        step_names = [
            STRINGS['step1_name'],
            STRINGS['step2_name'],
            STRINGS['step3_name'],
        ]

        y_pos = 55  # Posizione Y iniziale per lista step
        for i, step_name in enumerate(step_names):
            step_num = i + 1

            # Determina colore e simbolo in base allo stato
            if step_num in self.steps_completed:
                # Step completato: verde con spunta
                color = color_completed
                # Disegna spunta (checkmark) prima del testo
                check_x = 10
                check_y = y_pos
                # Spunta semplice con due linee
                cv2.line(image_output, (check_x, check_y - 5), (check_x + 5, check_y), color, 2)
                cv2.line(image_output, (check_x + 5, check_y), (check_x + 15, check_y - 12), color, 2)
                text_x = 30
            elif step_num == self.current_step:
                # Step attivo: giallo con indicatore
                color = color_active
                cv2.circle(image_output, (15, y_pos - 5), 5, color, -1)  # Pallino pieno
                text_x = 30
            else:
                # Step pending: bianco
                color = color_pending
                cv2.circle(image_output, (15, y_pos - 5), 5, color, 1)  # Pallino vuoto
                text_x = 30

            cv2.putText(image_output, step_name, (text_x, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            y_pos += 25

        # --- ISTRUZIONE CORRENTE (in basso) ---
        instructions = {
            1: STRINGS['step1_instruction'],
            2: STRINGS['step2_instruction'],
            3: STRINGS['step3_instruction'],
        }

        instruction_text = instructions.get(self.current_step, '')
        if instruction_text:
            # Posiziona istruzione in basso a sinistra
            cv2.putText(image_output, instruction_text, (10, height - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_instruction, 1)

    def _draw_terminate_button(self, image_output, cache):
        """
        Disegna il pulsante TERMINA in basso a destra.

        Args:
            image_output: Immagine su cui disegnare
            cache: Cache con configurazione
        """
        width = cache['config'].get('width', 630)
        height = cache['config'].get('height', 320)

        btn_w = 120
        btn_h = 35
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
        text = STRINGS['btn_terminate']
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
        text_x = btn_x + (btn_w - text_size[0]) // 2
        text_y = btn_y + (btn_h + text_size[1]) // 2

        cv2.putText(image_output, text, (text_x, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale, get_colore('white'), thickness)

    # =========================================================================
    # STEP 1: CALIBRAZIONE BUIO
    # Acquisizione riferimento con faro spento.
    # TODO: Implementare acquisizione e salvataggio riferimento buio.
    # =========================================================================

    def _process_step1_buio(self, image_output, cache):
        """
        Step 1: Calibrazione buio.
        Placeholder - da implementare.

        Args:
            image_output: Immagine su cui disegnare
            cache: Cache con configurazione
        """
        # TODO: Implementare logica calibrazione buio
        # Per ora questo step non fa nulla, attende solo un click per avanzare
        pass

    def _handle_click_step1(self, x, y, cache):
        """
        Gestisce il click per lo step 1: calibrazione buio.
        Placeholder - al click avanza allo step successivo.

        Args:
            x: Coordinata X del click
            y: Coordinata Y del click
            cache: Cache con configurazione

        Returns:
            True se lo step e' completato, False altrimenti
        """
        logging.info(f"Step 1 (buio) - Click ricevuto: ({x}, {y})")

        # TODO: Implementare logica acquisizione buio
        # Per ora: un click completa lo step
        self._advance_to_next_step()
        return False  # Calibrazione continua con step successivo

    # =========================================================================
    # STEP 2: CENTRAGGIO
    # Definizione del punto centrale del frame (crop_center).
    # L'utente clicca sul punto che dovra' essere al centro.
    # =========================================================================

    def _process_step2_centraggio(self, image_output, cache):
        """
        Step 2: Centraggio telecamera (crop_center).
        Non disegna mirino - solo l'UI comune gia' disegnata.

        Args:
            image_output: Immagine su cui disegnare
            cache: Cache con configurazione
        """
        # Nessun overlay aggiuntivo per questo step
        # Il mirino blu e' stato rimosso come richiesto
        pass

    def _handle_click_step2(self, x, y, cache):
        """
        Gestisce il click per lo step 2: centraggio.

        Args:
            x: Coordinata X del click
            y: Coordinata Y del click
            cache: Cache con configurazione

        Returns:
            True se lo step e' completato, False altrimenti
        """
        logging.info(f"Step 2 (centraggio) - Click ricevuto: ({x}, {y})")

        # Salva coordinate crop_center in cache e config
        self.cache['config']['crop_center'] = [x, y]

        # Salva config.json immediatamente
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.cache['config'], f, indent=4)
            logging.info(f"crop_center salvato: ({x}, {y})")
        except Exception as e:
            logging.error(f"Errore nel salvare config.json: {e}")

        # Ricarica config.json in cache
        init_config = self.cache.get('init_config')
        if init_config:
            init_config("config.json")
            logging.info("Configurazione ricaricata")

        # Avanza allo step successivo
        self._advance_to_next_step()
        return False  # Calibrazione continua

    # =========================================================================
    # STEP 3: INCLINAZIONE
    # Calibrazione dell'inclinazione del fascio luminoso.
    # TODO: Implementare calibrazione inclinazione a 4%.
    # =========================================================================

    def _process_step3_inclinazione(self, image_output, cache):
        """
        Step 3: Inclinazione.
        Placeholder - da implementare.

        Args:
            image_output: Immagine su cui disegnare
            cache: Cache con configurazione
        """
        # TODO: Implementare logica calibrazione inclinazione
        pass

    def _handle_click_step3(self, x, y, cache):
        """
        Gestisce il click per lo step 3: inclinazione.
        Rileva punto automaticamente e calcola coefficiente pixel/inclinazione.

        Args:
            x: Coordinata X del click
            y: Coordinata Y del click
            cache: Cache con configurazione

        Returns:
            True se la calibrazione e' terminata, False altrimenti
        """
        logging.info(f"Step 3 (inclinazione) - Click ricevuto")

        # Usa il punto già rilevato da MW28912.py (su immagine preprocessata)
        punto = cache.get('calibration_point')
        if punto is None:
            logging.error("Step 3: punto non rilevato, riprova")
            return False

        # Calcola coefficiente calibrazione: pixel = m * incl% + center
        # Riferimento = centro immagine (height/2)
        # Punto a 4%: pixel=punto.y
        # m = (punto.y - center) / 4
        width = cache['config'].get('width', 640)
        height = cache['config'].get('height', 480)
        center_x = width / 2
        center_y = height / 2

        # m = pendenza (pixel per 1% di inclinazione)
        calib_m = (punto[1] - center_y) / 4.0

        if abs(calib_m) < 0.1:
            logging.error("Step 3: pendenza troppo piccola, riprova")
            return False

        logging.info(f"Step 3: punto=({punto[0]:.1f}, {punto[1]:.1f}), "
                    f"centro=({center_x:.1f}, {center_y:.1f}), "
                    f"calib_m={calib_m:.3f} px/%")

        # Salva in config (solo m, q=center è implicito)
        self.cache['config']['y_calib_m'] = calib_m

        # Salva config.json
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.cache['config'], f, indent=4)
            logging.info(f"Calibrazione salvata: m={calib_m:.3f} px/%")
        except Exception as e:
            logging.error(f"Errore nel salvare config.json: {e}")

        # Ricarica config
        init_config = self.cache.get('init_config')
        if init_config:
            init_config("config.json")

        self._advance_to_next_step()
        return not self.calibration_active

    # =========================================================================
    # GESTIONE CLICK
    # =========================================================================

    def handle_click(self, x, y, cache):
        """
        Gestisce il click del mouse durante la calibrazione.
        Smista il click allo step corrente o al pulsante TERMINA.

        Args:
            x: Coordinata X del click
            y: Coordinata Y del click
            cache: Cache con configurazione

        Returns:
            True se la calibrazione e' terminata, False altrimenti
        """
        if not self.calibration_active:
            return False

        # Controlla click su pulsante TERMINA (priorita' massima)
        if self.exit_button_rect:
            btn_x, btn_y, btn_w, btn_h = self.exit_button_rect
            if btn_x <= x <= btn_x + btn_w and btn_y <= y <= btn_y + btn_h:
                logging.info("Click sul pulsante TERMINA: esco dalla calibrazione")
                self.stop_calibration()
                return True

        # Smista click allo step corrente
        if self.current_step == 1:
            return self._handle_click_step1(x, y, cache)
        elif self.current_step == 2:
            return self._handle_click_step2(x, y, cache)
        elif self.current_step == 3:
            return self._handle_click_step3(x, y, cache)

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
            'steps_completed': list(self.steps_completed),
            'data': self.step_data
        }
