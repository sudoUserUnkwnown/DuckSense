import asyncio
import time
import cv2
import numpy as np
import mss
import keyboard
import sys
import os
from buttplug.client import ButtplugClient, ButtplugClientWebsocketConnector, ButtplugClientDevice

def resolver_ruta(ruta_relativa):
    if hasattr(sys, '_MEIPASS'):
        # Cuando es .exe, busca en la carpeta temporal interna
        return os.path.join(sys._MEIPASS, ruta_relativa)
    # Cuando es script normal, busca en la carpeta actual
    return os.path.join(os.path.abspath("."), ruta_relativa)

# --- CONFIGURACIÓN DE COLORES (HSV) ---
# Estos rangos pueden necesitar ajuste dependiendo del brillo/pantalla
# Formato: [Lower Hue, Sat, Val], [Upper Hue, Sat, Val]
DUCK_COLORS = {
    "blanco":  (np.array([0, 0, 200]), np.array([180, 30, 255])),
    "gris":    (np.array([0, 0, 50]),  np.array([180, 50, 150])),
    "amarillo":(np.array([20, 100, 100]), np.array([30, 255, 255])),
    "naranja": (np.array([10, 100, 100]), np.array([20, 255, 255])),
    "rosa":    (np.array([140, 50, 50]), np.array([170, 255, 255])),
    "verde":   (np.array([40, 50, 50]),  np.array([80, 255, 255]))
}

class Player:
    def __init__(self, name, color_name, device):
        self.name = name
        self.color_name = color_name
        self.color_range = DUCK_COLORS.get(color_name)
        self.device = device
        self.intensity = 0.0  # 0.0 a 1.0

    async def update_vibration(self, change):
        # change puede ser positivo (perder) o negativo (ganar)
        new_intensity = self.intensity + change
        # Clamping entre 0.0 y 1.0
        self.intensity = max(0.0, min(1.0, new_intensity))
        
        if self.device:
            # Enviar comando de vibración a todos los motores del juguete
            try:
                await self.device.send_vibrate_cmd(self.intensity)
                print(f"[{self.name}] Intensidad: {int(self.intensity * 100)}%")
            except Exception as e:
                print(f"Error vibrando dispositivo {self.name}: {e}")

class DuckHaptics:
    def __init__(self):
        self.client = ButtplugClient("DuckGame Haptics")
        self.players = []
        self.sct = mss.mss()
        self.running = True

        path_imagen = resolver_ruta('template.png')
        self.template = cv2.imread(path_imagen, 0)

        if self.template is None:
            # Tip: Imprime la ruta para ver dónde está buscando si falla
            print(f"Error: No se pudo cargar {path_imagen}") 
            self.w, self.h = 0, 0
        else:
            self.w, self.h = self.template.shape[::-1]
        
        # Cache para el template normalizado
        self.template_mean = 0
        self.template_std = 0
        if self.template is not None:
            self.template_mean = np.mean(self.template)
            self.template_std = np.std(self.template)
            if self.template_std == 0:
                self.template_std = 1

    async def connect_intiface(self):
        print("Conectando a Intiface Central...")
        connector = ButtplugClientWebsocketConnector("ws://127.0.0.1:12345")
        try:
            await self.client.connect(connector)
            print("¡Conectado a Intiface!")
        except Exception as e:
            print(f"Error conectando a Intiface: {e}")
            return False
        
        print("Escaneando dispositivos...")
        await self.client.start_scanning()
        await asyncio.sleep(2) # Esperar a que encuentre cosas
        await self.client.stop_scanning()
        
        if not self.client.devices:
            print("No se encontraron juguetes. Asegúrate de que estén conectados en Intiface.")
            return False
        return True

    async def setup_players(self):
        try:
            num_players = int(input("¿Cuántos jugadores (con juguetes) van a jugar? "))
        except:
            num_players = 1

        available_devices = list(self.client.devices.values())

        for i in range(num_players):
            print(f"\n--- Configurando Jugador {i+1} ---")
            print("Colores disponibles: " + ", ".join(DUCK_COLORS.keys()))
            color = input("Elige el color del pato: ").lower()
            while color not in DUCK_COLORS:
                print("Color no válido.")
                color = input("Elige el color del pato: ").lower()

            print("Dispositivos disponibles:")
            for idx, dev in enumerate(available_devices):
                print(f"{idx}: {dev.name}")
            
            try:
                dev_idx = int(input("Selecciona el ID del juguete para este jugador: "))
                device = available_devices[dev_idx]
            except:
                print("Selección inválida, asignando el primero.")
                device = available_devices[0]

            self.players.append(Player(f"P{i+1}", color, device))
            print(f"Jugador {i+1} listo: {color} -> {device.name}")

    def detect_winner_color(self, frame):
        if self.template is None:
            return None

        # Convertir a escala de grises para template matching
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Template Matching con correlación normalizada
        res = cv2.matchTemplate(gray_frame, self.template, cv2.TM_CCOEFF_NORMED)
        
        # Threshold adaptativo: mejor detección
        threshold = 0.75
        loc = np.where(res >= threshold)
        
        if len(loc[0]) == 0:
            return None
        
        # Obtener el match con mejor puntuación
        best_score_idx = np.argmax(res[loc])
        x, y = loc[1][best_score_idx], loc[0][best_score_idx]
        
        # Extraer ROI y buscar color
        roi_bgr = frame[y:y+self.h, x:x+self.w]
        roi_hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        
        max_pixels = 0
        best_color = None
        min_color_pixels = self.w * self.h * 0.05  # 5% del área
        
        # Buscar color predominante de forma eficiente
        for color_name, (lower, upper) in DUCK_COLORS.items():
            mask = cv2.inRange(roi_hsv, lower, upper)
            count = cv2.countNonZero(mask)
            
            if count > max_pixels:
                max_pixels = count
                best_color = color_name
        
        # Retornar color si es significativo
        return best_color if max_pixels > min_color_pixels else None

    async def game_loop(self):
        print("\n--- INICIANDO MONITOR DE DUCK GAME ---")
        print("Presiona 'q' en la consola para salir.")
        
        monitor = self.sct.monitors[1] # Monitor principal
        
        cooldown = False
        cooldown_timer = 0
        
        while self.running:
            if keyboard.is_pressed('q'):
                self.running = False
                break

            # Captura de pantalla
            screenshot = np.array(self.sct.grab(monitor))
            # Eliminar canal alpha para OpenCV
            frame = screenshot[:, :, :3]

            # Solo procesamos si no estamos en cooldown (para no detectar el mismo +1 60 veces)
            if not cooldown:
                winner_color = self.detect_winner_color(frame)
                
                if winner_color:
                    print(f"¡Detectado +1 de color {winner_color}!")
                    
                    # Lógica de juego
                    for player in self.players:
                        if player.color_name == winner_color:
                            # GANÓ: Baja intensidad
                            await player.update_vibration(-0.2) # Baja un 20%
                        else:
                            # PERDIÓ (Ganó otro): Sube intensidad
                            await player.update_vibration(0.1) # Sube un 10%
                    
                    cooldown = True
                    cooldown_timer = time.time()
            else:
                # Esperar 3 segundos antes de volver a escanear para dar tiempo a que desaparezca el +1
                if time.time() - cooldown_timer > 3:
                    cooldown = False

            # Pequeña pausa para no quemar CPU
            await asyncio.sleep(0.5)

        # Apagar todo al salir
        print("Apagando juguetes...")
        for p in self.players:
            try:
                await p.device.send_stop_device_cmd()
            except:
                pass

if __name__ == "__main__":
    game = DuckHaptics()
    loop = asyncio.get_event_loop()
    
    # Ejecución
    if loop.run_until_complete(game.connect_intiface()):
        loop.run_until_complete(game.setup_players())
        loop.run_until_complete(game.game_loop())
    
    print("Programa finalizado.")
