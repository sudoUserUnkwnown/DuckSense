import cv2
import numpy as np

# Crear una imagen negra de 60x60
img = np.zeros((60, 80, 3), dtype=np.uint8)

# Escribir "+1" en blanco (simulando la forma genérica)
# Usamos una fuente gruesa para que se parezca a la del juego
font = cv2.FONT_HERSHEY_SIMPLEX
cv2.putText(img, "+1", (10, 45), font, 1.8, (255, 255, 255), 3, cv2.LINE_AA)

# Guardar
cv2.imwrite("template.png", img)
print("Archivo template.png creado. Reemplázalo con un recorte real del juego si la detección falla.")
