import asyncio
import time
import cv2
import numpy as np
import mss
import keyboard
import sys
import os
import math
from buttplug.client import ButtplugClient, ButtplugClientWebsocketConnector, ButtplugClientDevice

def resolve_path(relative_path):
    # When packaged (e.g., PyInstaller) resources are in a temporary folder via _MEIPASS
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    # Otherwise resolve relative to current working directory
    return os.path.join(os.path.abspath("."), relative_path)

# --- COLOR CONFIGURATION (HSV) ---
# These ranges may require tuning depending on brightness/screen
# Format: (Lower HSV), (Upper HSV)
DUCK_COLORS = {
    "white":  (np.array([0, 0, 200]), np.array([180, 30, 255])),
    "gray":   (np.array([0, 0, 50]),  np.array([180, 50, 150])),
    "yellow": (np.array([20, 100, 100]), np.array([30, 255, 255])),
    "orange": (np.array([10, 100, 100]), np.array([20, 255, 255])),
    "pink":   (np.array([140, 50, 50]), np.array([170, 255, 255])),
    "green":  (np.array([40, 50, 50]),  np.array([80, 255, 255]))
}

class Player:
    def __init__(self, name, color_name, device):
        self.name = name
        self.color_name = color_name
        self.color_range = DUCK_COLORS.get(color_name)
        self.device = device
        self.intensity = 0.0  # 0.0 to 1.0
        self.vib_task = None

    async def update_vibration(self, change):
        # change may be positive (lost) or negative (won)
        new_intensity = self.intensity + change
        # Clamp between 0.0 and 1.0
        self.intensity = max(0.0, min(1.0, new_intensity))
        print(f"[{self.name}] Intensity: {int(self.intensity * 100)}%")

    async def send_vibrate_level(self, level):
        if self.device:
            try:
                await self.device.send_vibrate_cmd(level)
            except Exception as e:
                print(f"Error vibrating device {self.name}: {e}")

    async def stop_device(self):
        if self.device:
            try:
                await self.device.send_stop_device_cmd()
            except:
                pass

class DuckHaptics:
    def __init__(self):
        self.client = ButtplugClient("DuckGame Haptics")
        self.players = []
        self.sct = mss.mss()
        self.running = True

        path_imagen = resolve_path('templates/template.png')
        self.template = cv2.imread(path_imagen, 0)

        if self.template is None:
            # Tip: Imprime la ruta para ver dónde está buscando si falla
            print(f"Error: No se pudo cargar {path_imagen}") 
            self.w, self.h = 0, 0
        else:
            self.w, self.h = self.template.shape[::-1]
        
        # Cache for normalized template
        self.template_mean = 0
        self.template_std = 0
        if self.template is not None:
            self.template_mean = np.mean(self.template)
            self.template_std = np.std(self.template)
            if self.template_std == 0:
                self.template_std = 1

        # Load optional intermission template to detect intermissions/screens
        inter_path = resolve_path('templates/intermission.png')
        self.intermission_template = None
        if os.path.exists(inter_path):
            self.intermission_template = cv2.imread(inter_path, 0)

        # Runtime settings
        self.monitor = None
        self.intensity_multiplier = 1.0
        self.vibration_freq = 40.0   # Hz for sine wave
        self.vibration_rate = 40.0   # updates per second
        self.lang = 'en'
        self.MSG = {}
        self.vibration_tasks = []

    async def connect_intiface(self):
        print(self.MSG.get('connecting', "Connecting to Intiface Central..."))
        connector = ButtplugClientWebsocketConnector("ws://127.0.0.1:12345")
        try:
            await self.client.connect(connector)
            print(self.MSG.get('connected', "Connected to Intiface!"))
        except Exception as e:
            print(f"Error connecting to Intiface: {e}")
            return False
        
        print(self.MSG.get('scanning', "Scanning for devices..."))
        await self.client.start_scanning()
        await asyncio.sleep(2)
        await self.client.stop_scanning()
        
        if not self.client.devices:
            print(self.MSG.get('no_devices', "No devices found. Make sure they are connected in Intiface."))
            return False
        return True

    def set_language(self):
        # Choose language using indices so text differences can't break selection
        print("Select language / Selecciona idioma:")
        print("0: English")
        print("1: Español")
        try:
            choice = int(input("Choice (0/1): "))
        except:
            choice = 0
        self.lang = 'es' if choice == 1 else 'en'

        self.MSG = {
            'en': {
                'connecting': "Connecting to Intiface Central...",
                'connected': "Connected to Intiface!",
                'scanning': "Scanning for devices...",
                'no_devices': "No devices found. Make sure they are connected in Intiface.",
                'how_many_players': "How many players (with toys) will play? ",
                'colors_available': "Available colors:",
                'choose_color_idx': "Choose the color index for the duck: ",
                'invalid_color': "Invalid color selection.",
                'devices_available': "Available devices:",
                'choose_device_idx': "Select the device ID for this player: ",
                'invalid_selection_assign_first': "Invalid selection, assigning the first one.",
                'starting_monitor': "--- STARTING DUCK GAME MONITOR ---",
                'press_q_exit': "Press 'q' in the console to exit.",
                'detected_plus_one': "Detected +1 of color {color}!",
                'shutting_down': "Shutting down devices...",
                'no_template': "Error: Could not load template",
                'intermission_detected': "Intermission detected — resetting vibrations."
            },
            'es': {
                'connecting': "Conectando a Intiface Central...",
                'connected': "¡Conectado a Intiface!",
                'scanning': "Escaneando dispositivos...",
                'no_devices': "No se encontraron juguetes. Asegúrate de que estén conectados en Intiface.",
                'how_many_players': "¿Cuántos jugadores (con juguetes) van a jugar? ",
                'colors_available': "Colores disponibles:",
                'choose_color_idx': "Elige el índice del color del pato: ",
                'invalid_color': "Color no válido.",
                'devices_available': "Dispositivos disponibles:",
                'choose_device_idx': "Selecciona el ID del juguete para este jugador: ",
                'invalid_selection_assign_first': "Selección inválida, asignando el primero.",
                'starting_monitor': "--- INICIANDO MONITOR DE DUCK GAME ---",
                'press_q_exit': "Presiona 'q' en la consola para salir.",
                'detected_plus_one': "¡Detectado +1 de color {color}!",
                'shutting_down': "Apagando juguetes...",
                'no_template': "Error: No se pudo cargar el template",
                'intermission_detected': "Intermission detectado — reiniciando vibraciones."
            }
        }
        self.MSG = self.MSG[self.lang]

    def configure_settings(self):
        # Monitor selection (index-based to avoid language issues)
        print("Available monitors:")
        for idx, mon in enumerate(self.sct.monitors):
            print(f"{idx}: {mon}")
        try:
            mon_idx = int(input("Select monitor index (default 1): "))
            self.monitor = self.sct.monitors[mon_idx]
        except:
            print("Invalid monitor selection, using main monitor (1).")
            self.monitor = self.sct.monitors[1]

        # Intensity multiplier
        try:
            v = float(input("Set global intensity multiplier (0.0 to 1.0, default 1.0): "))
            if 0.0 <= v <= 1.0:
                self.intensity_multiplier = v
            else:
                print("Invalid multiplier, using 1.0")
        except:
            self.intensity_multiplier = 1.0

    async def setup_players(self):
        try:
            num_players = int(input(self.MSG.get('how_many_players', "How many players (with toys) will play? ")))
        except:
            num_players = 1

        available_devices = list(self.client.devices.values())
        colors = list(DUCK_COLORS.keys())

        for i in range(num_players):
            print(f"\n--- Configuring Player {i+1} ---")
            print(self.MSG.get('colors_available', "Available colors:"))
            for idx, cname in enumerate(colors):
                print(f"{idx}: {cname}")

            try:
                color_idx = int(input(self.MSG.get('choose_color_idx', "Choose the color index for the duck: ")))
                if color_idx < 0 or color_idx >= len(colors):
                    raise ValueError()
                color = colors[color_idx]
            except:
                print(self.MSG.get('invalid_color', "Invalid color selection."))
                color = colors[0]

            print(self.MSG.get('devices_available', "Available devices:"))
            for idx, dev in enumerate(available_devices):
                print(f"{idx}: {dev.name}")
            
            try:
                dev_idx = int(input(self.MSG.get('choose_device_idx', "Select the device ID for this player: ")))
                device = available_devices[dev_idx]
            except:
                print(self.MSG.get('invalid_selection_assign_first', "Invalid selection, assigning the first one."))
                device = available_devices[0]

            player = Player(f"P{i+1}", color, device)
            self.players.append(player)
            print(f"Player {i+1} ready: {color} -> {device.name}")

        # Start the per-player vibration tasks
        self.start_vibration_tasks()

    def detect_winner_color(self, frame):
        if self.template is None:
            return None

        # Convert to grayscale for template matching
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Template Matching with normalized correlation
        res = cv2.matchTemplate(gray_frame, self.template, cv2.TM_CCOEFF_NORMED)
        
        threshold = 0.75
        loc = np.where(res >= threshold)
        
        if len(loc[0]) == 0:
            return None
        
        best_score_idx = np.argmax(res[loc])
        x, y = loc[1][best_score_idx], loc[0][best_score_idx]
        
        roi_bgr = frame[y:y+self.h, x:x+self.w]
        roi_hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        
        max_pixels = 0
        best_color = None
        min_color_pixels = self.w * self.h * 0.05  # 5% of area
        
        for color_name, (lower, upper) in DUCK_COLORS.items():
            mask = cv2.inRange(roi_hsv, lower, upper)
            count = cv2.countNonZero(mask)
            
            if count > max_pixels:
                max_pixels = count
                best_color = color_name
        
        return best_color if max_pixels > min_color_pixels else None

    def is_intermission(self, frame):
        if self.intermission_template is None:
            return False
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray_frame, self.intermission_template, cv2.TM_CCOEFF_NORMED)
        return np.max(res) >= 0.8

    def start_vibration_tasks(self):
        for p in self.players:
            t = asyncio.create_task(self._vibration_loop(p))
            self.vibration_tasks.append(t)

    async def _vibration_loop(self, player):
        period = 1.0 / self.vibration_rate
        freq = self.vibration_freq
        start_time = time.time()
        last_sent_zero = False
        while self.running:
            intensity = player.intensity * self.intensity_multiplier
            if intensity > 0 and player.device:
                t = time.time() - start_time
                sine = (math.sin(2 * math.pi * freq * t) + 1.0) / 2.0  # 0..1
                level = float(sine * intensity)
                try:
                    await player.device.send_vibrate_cmd(level)
                except Exception as e:
                    print(f"Error sending vibrate level to {player.name}: {e}")
                last_sent_zero = False
            else:
                if player.device and not last_sent_zero:
                    try:
                        await player.device.send_stop_device_cmd()
                    except:
                        pass
                    last_sent_zero = True
            await asyncio.sleep(period)

    async def game_loop(self):
        print(self.MSG.get('starting_monitor', "--- STARTING DUCK GAME MONITOR ---"))
        print(self.MSG.get('press_q_exit', "Press 'q' in the console to exit."))
        
        monitor = self.monitor if self.monitor is not None else self.sct.monitors[1]
        
        cooldown = False
        cooldown_timer = 0
        
        while self.running:
            if keyboard.is_pressed('q'):
                self.running = False
                break

            screenshot = np.array(self.sct.grab(monitor))
            frame = screenshot[:, :, :3]

            # Intermission detection: if intermission screen appears, reset all vibrations
            if self.is_intermission(frame):
                print(self.MSG.get('intermission_detected', "Intermission detected — resetting vibrations."))
                for p in self.players:
                    p.intensity = 0.0
                    try:
                        await p.stop_device()
                    except:
                        pass
                # small pause to avoid flapping
                await asyncio.sleep(0.5)
                continue

            if not cooldown:
                winner_color = self.detect_winner_color(frame)
                
                if winner_color:
                    print(self.MSG.get('detected_plus_one', "Detected +1 of color {color}!").format(color=winner_color))
                    
                    for player in self.players:
                        if player.color_name == winner_color:
                            # WON: reduce intensity
                            await player.update_vibration(-0.2)
                        else:
                            # LOST: increase intensity
                            await player.update_vibration(0.1)
                    
                    cooldown = True
                    cooldown_timer = time.time()
            else:
                if time.time() - cooldown_timer > 3:
                    cooldown = False

            await asyncio.sleep(0.5)

        # Shutdown: cancel vibration tasks and stop devices
        print(self.MSG.get('shutting_down', "Shutting down devices..."))
        for t in self.vibration_tasks:
            t.cancel()
        for p in self.players:
            try:
                await p.stop_device()
            except:
                pass

if __name__ == "__main__":
    game = DuckHaptics()
    # Ask language first so prompts are shown in the selected language
    game.set_language()

    loop = asyncio.get_event_loop()
    # Connect to Intiface and configure settings
    if loop.run_until_complete(game.connect_intiface()):
        game.configure_settings()
        loop.run_until_complete(game.setup_players())
        loop.run_until_complete(game.game_loop())

    print("Program finished.")
