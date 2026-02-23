"""
Modulo per la calibrazione della telecamera.
Gestisce diversi step di calibrazione in modo modulare.

Step di calibrazione:
    1    - Calibrazione buio
    20   - Accendi anabbagliante incl 0, premi punto
    21   - Attesa autoexp OK
    22   - Click su punto centrale (salva crop_center)
    30   - Accendi abbagliante incl 0, premi punto
    31   - Attesa autoexp OK (salva px_lux_bright_abb)
    40   - Porta anabbagliante a incl -4%, premi punto
    41   - Attesa autoexp OK (calcola y_calib_m, lux_m/q, lux_m_abb/q_abb)
    100  - Calibrazione terminata
"""

import cv2
import json
import os
import logging
from utils import get_colore
import fari_detection


STRINGS_IT = {
    'title': 'Calibrazione',

    # Nomi gruppi (lista a sinistra)
    'step1_name':   '1. Calibrazione buio',
    'step2_name':   '2. Centraggio',
    'step3_name':   '3. Lum. abbagliante',
    'step4_name':   '4. Inclinazione',
    'step100_name': 'Calibrazione terminata',

    # Istruzioni per substep
    'step1_instruction':   'Spegnere faro e premere un punto qualsiasi',
    'step20_instruction':  'Accendere anabbagliante a inclinazione 0 e premere un punto qualsiasi',
    'step21_instruction':  'Attendere autoexp OK...',
    'step22_instruction':  'Cliccare sul punto centrale',
    'step30_instruction':  'Accendere abbagliante a inclinazione 0 e premere un punto qualsiasi',
    'step31_instruction':  'Attendere autoexp OK...',
    'step40_instruction':  'Portare anabbagliante a inclinazione -4% e premere un punto qualsiasi',
    'step41_instruction':  'Attendere autoexp OK...',
    'step100_instruction': 'Calibrazione terminata',

    'btn_terminate': 'TERMINA',
}

STRINGS = STRINGS_IT


class CalibrationManager:
    """
    Gestisce il processo di calibrazione multi-step.
    """

    STEP_SEQUENCE = [1, 20, 21, 22, 30, 31, 40, 41]

    # Mappa substep -> numero gruppo UI
    STEP_GROUP = {
        1: 1,
        20: 2, 21: 2, 22: 2,
        30: 3, 31: 3,
        40: 4, 41: 4,
        100: 100
    }

    # Ultimo substep di ogni gruppo (per determinare spunta completato)
    GROUP_LAST = {1: 1, 2: 22, 3: 31, 4: 41, 100: 100}

    def __init__(self, config_path, cache):
        self.config_path = config_path
        self.default_file = os.path.join(config_path, "default.json")
        self.config_file = os.path.join(config_path, "config.json")
        self.cache = cache

        self.current_step = 0
        self.step_data = {}
        self.calibration_active = False
        self.steps_completed = set()
        self.exit_button_rect = None

    def start_calibration(self):
        logging.info("Avvio calibrazione: caricamento default.json in cache")

        init_config = self.cache.get('init_config')
        if init_config:
            init_config("default.json")
        else:
            logging.warning("init_config non disponibile in cache")

        self.steps_completed = set()
        self.calibration_active = True
        self.current_step = 1
        self.step_data = {'state': 0}

        logging.info(f"Calibrazione avviata: step {self.current_step}")

    def stop_calibration(self):
        logging.info("Calibrazione terminata")

        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.cache['config'], f, indent=4)
            logging.info("Configurazione salvata in config.json")
        except Exception as e:
            logging.error(f"Errore nel salvare config.json: {e}")

        init_config = self.cache.get('init_config')
        if init_config:
            init_config("config.json")

        self.calibration_active = False
        self.current_step = 0
        self.step_data = {}
        self.steps_completed = set()

    def _advance_to_next_step(self):
        self.steps_completed.add(self.current_step)
        logging.info(f"Step {self.current_step} completato")

        try:
            idx = self.STEP_SEQUENCE.index(self.current_step)
            if idx + 1 < len(self.STEP_SEQUENCE):
                self.current_step = self.STEP_SEQUENCE[idx + 1]
                self.step_data = {'state': 0}
                logging.info(f"Avanzamento a step {self.current_step}")
            else:
                self.current_step = 100
                logging.info("Tutti gli step completati, mostro schermata finale")
        except ValueError:
            self.current_step = 100

    def process_frame(self, image_output, cache):
        if not self.calibration_active:
            return image_output

        self._draw_calibration_ui(image_output, cache)

        if self.current_step == 21:
            self._process_step21(image_output, cache)
        elif self.current_step == 31:
            self._process_step31(image_output, cache)
        elif self.current_step == 41:
            self._process_step41(image_output, cache)

        self._draw_terminate_button(image_output, cache)
        return image_output

    def _draw_calibration_ui(self, image_output, cache):
        height = cache['config'].get('height', 320)

        color_title = get_colore('cyan')
        color_active = get_colore('yellow')
        color_completed = get_colore('green')
        color_pending = get_colore('white')
        color_instruction = get_colore('cyan')

        cv2.putText(image_output, STRINGS['title'], (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_title, 2)

        group_names = [
            (1,   STRINGS['step1_name']),
            (2,   STRINGS['step2_name']),
            (3,   STRINGS['step3_name']),
            (4,   STRINGS['step4_name']),
            (100, STRINGS['step100_name']),
        ]

        current_group = self.STEP_GROUP.get(self.current_step, 0)

        y_pos = 55
        for group_num, group_name in group_names:
            last_substep = self.GROUP_LAST[group_num]
            is_completed = last_substep in self.steps_completed
            is_active = (group_num == current_group)

            if is_completed:
                color = color_completed
                cv2.line(image_output, (10, y_pos - 5), (15, y_pos), color, 2)
                cv2.line(image_output, (15, y_pos), (25, y_pos - 12), color, 2)
                text_x = 30
            elif is_active:
                color = color_active
                cv2.circle(image_output, (15, y_pos - 5), 5, color, -1)
                text_x = 30
            else:
                color = color_pending
                cv2.circle(image_output, (15, y_pos - 5), 5, color, 1)
                text_x = 30

            cv2.putText(image_output, group_name, (text_x, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            y_pos += 25

        instr_key = f'step{self.current_step}_instruction'
        instruction_text = STRINGS.get(instr_key, '')
        if instruction_text:
            cv2.putText(image_output, instruction_text, (10, height - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_instruction, 1)

    def _draw_terminate_button(self, image_output, cache):
        width = cache['config'].get('width', 630)
        height = cache['config'].get('height', 320)

        btn_w = 120
        btn_h = 35
        btn_x = width - btn_w - 10
        btn_y = height - btn_h - 10

        self.exit_button_rect = (btn_x, btn_y, btn_w, btn_h)

        cv2.rectangle(image_output, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h),
                     get_colore('red'), -1)
        cv2.rectangle(image_output, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h),
                     get_colore('white'), 2)

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
    # =========================================================================

    def _handle_click_step1(self, x, y, cache):
        logging.info(f"Step 1 (buio) - Click: ({x}, {y})")
        px_lux_dark = cache.get('calib_px_lux_dark', 0)
        self.cache['config']['px_lux_dark'] = px_lux_dark
        logging.info(f"Step 1: px_lux_dark = {px_lux_dark:.3f}")
        self._advance_to_next_step()
        return False

    # =========================================================================
    # STEP 2.0: ACCENDI ANABBAGLIANTE INCL 0
    # =========================================================================

    def _handle_click_step20(self, x, y, cache):
        logging.info(f"Step 20 - Click ricevuto")
        self._advance_to_next_step()
        return False

    # =========================================================================
    # STEP 2.1: ATTENDI AUTOEXP OK
    # =========================================================================

    def _process_step21(self, image_output, cache):
        if cache.get('autoexp_ok', False):
            self._advance_to_next_step()

    # =========================================================================
    # STEP 2.2: CLICK SUL PUNTO CENTRALE
    # =========================================================================

    def _handle_click_step22(self, x, y, cache):
        logging.info(f"Step 22 (centraggio) - Click: ({x}, {y})")
        self.cache['config']['crop_center'] = [x, y]

        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.cache['config'], f, indent=4)
            logging.info(f"crop_center salvato: ({x}, {y})")
        except Exception as e:
            logging.error(f"Errore nel salvare config.json: {e}")

        init_config = self.cache.get('init_config')
        if init_config:
            init_config("config.json")

        self._advance_to_next_step()
        return False

    # =========================================================================
    # STEP 3.0: ACCENDI ABBAGLIANTE INCL 0
    # =========================================================================

    def _handle_click_step30(self, x, y, cache):
        logging.info(f"Step 30 - Click ricevuto")
        self._advance_to_next_step()
        return False

    # =========================================================================
    # STEP 3.1: ATTENDI AUTOEXP OK, SALVA px_lux_bright_abb
    # =========================================================================

    def _process_step31(self, image_output, cache):
        if cache.get('autoexp_ok', False):
            px_lux_bright_abb = cache.get('calib_px_lux_bright_abb', 0)
            self.cache['config']['px_lux_bright_abb'] = px_lux_bright_abb
            logging.info(f"Step 31: px_lux_bright_abb = {px_lux_bright_abb:.3f}")
            self._advance_to_next_step()

    # =========================================================================
    # STEP 4.0: PORTA ANABBAGLIANTE A INCL -4%
    # =========================================================================

    def _handle_click_step40(self, x, y, cache):
        logging.info(f"Step 40 - Click ricevuto")
        self._advance_to_next_step()
        return False

    # =========================================================================
    # STEP 4.1: ATTENDI AUTOEXP OK, CALCOLA TUTTO
    # =========================================================================

    def _process_step41(self, image_output, cache):
        if cache.get('autoexp_ok', False):
            self._complete_calibration(cache)

    def _complete_calibration(self, cache):
        # --- y_calib_m ---
        punto = cache.get('calibration_point')
        if punto is None:
            logging.error("Step 41: punto non rilevato, impossibile calcolare y_calib_m")
            return

        height = cache['config'].get('height', 480)
        center_y = height / 2
        calib_m = (punto[1] - center_y) / -4.0

        if abs(calib_m) < 0.1:
            logging.error("Step 41: pendenza troppo piccola, riprova")
            return

        self.cache['config']['y_calib_m'] = calib_m
        logging.info(f"Step 41: y_calib_m={calib_m:.3f} px/%")

        px_lux_dark = self.cache['config'].get('px_lux_dark', 0)
        luxnom = float(cache.get('stato_comunicazione', {}).get('luxnom', 0))

        # --- lux_m, lux_q per anabbagliante ---
        px_lux_bright = cache.get('calib_px_lux_bright', 0)
        self.cache['config']['px_lux_bright'] = px_lux_bright
        delta = px_lux_bright - px_lux_dark
        if abs(delta) > 0.01 and luxnom > 0:
            lux_m = luxnom / delta
            lux_q = -lux_m * px_lux_dark
            self.cache['config']['lux_m'] = lux_m
            self.cache['config']['lux_q'] = lux_q
            logging.info(f"lux anabb: lux_m={lux_m:.4f}, lux_q={lux_q:.4f} "
                        f"(dark={px_lux_dark:.3f}, bright={px_lux_bright:.3f})")
        else:
            logging.warning(f"Calibrazione lux anabb non possibile (delta={delta:.3f}, luxnom={luxnom:.1f})")

        # --- lux_m_abb, lux_q_abb per abbagliante ---
        px_lux_bright_abb = self.cache['config'].get('px_lux_bright_abb', 0)
        delta_abb = px_lux_bright_abb - px_lux_dark
        if abs(delta_abb) > 0.01 and luxnom > 0:
            lux_m_abb = luxnom / delta_abb
            lux_q_abb = -lux_m_abb * px_lux_dark
            self.cache['config']['lux_m_abb'] = lux_m_abb
            self.cache['config']['lux_q_abb'] = lux_q_abb
            logging.info(f"lux abb: lux_m_abb={lux_m_abb:.4f}, lux_q_abb={lux_q_abb:.4f} "
                        f"(bright_abb={px_lux_bright_abb:.3f})")
        else:
            logging.warning(f"Calibrazione lux abb non possibile (delta={delta_abb:.3f}, luxnom={luxnom:.1f})")

        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.cache['config'], f, indent=4)
            logging.info("Calibrazione salvata in config.json")
        except Exception as e:
            logging.error(f"Errore nel salvare config.json: {e}")

        init_config = self.cache.get('init_config')
        if init_config:
            init_config("config.json")

        self._advance_to_next_step()

    # =========================================================================
    # GESTIONE CLICK
    # =========================================================================

    def handle_click(self, x, y, cache):
        if not self.calibration_active:
            return False

        if self.exit_button_rect:
            btn_x, btn_y, btn_w, btn_h = self.exit_button_rect
            if btn_x <= x <= btn_x + btn_w and btn_y <= y <= btn_y + btn_h:
                logging.info("Click sul pulsante TERMINA")
                self.stop_calibration()
                return True

        if self.current_step == 1:
            return self._handle_click_step1(x, y, cache)
        elif self.current_step == 20:
            return self._handle_click_step20(x, y, cache)
        elif self.current_step == 22:
            return self._handle_click_step22(x, y, cache)
        elif self.current_step == 30:
            return self._handle_click_step30(x, y, cache)
        elif self.current_step == 40:
            return self._handle_click_step40(x, y, cache)

        return False

    def get_status(self):
        return {
            'active': self.calibration_active,
            'step': self.current_step,
            'steps_completed': list(self.steps_completed),
            'data': self.step_data
        }
