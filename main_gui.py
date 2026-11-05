import sys
import os
import time
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6 import uic
import pyqtgraph as pg  

# rutas para encontrar los módulos
ruta_src = os.path.join(os.path.dirname(__file__), 'src')
sys.path.append(ruta_src)

# from uiroc.device import FtdInterface #  archivo faltante

# ---------------------------------------------------------
# Hilo de Conexión
# ---------------------------------------------------------
class HiloConexion(QThread):
    mensaje_estado = pyqtSignal(str) 

    def __init__(self, usar_emulacion):
        super().__init__()
        self.usar_emulacion = usar_emulacion

    def run(self):
        modo = "Emulación" if self.usar_emulacion else "Físico"
        self.mensaje_estado.emit(f"Buscando placa Temporoc (Modo {modo})...")
        
        try:
            # código real de hardware:
            # self.placa = FtdInterface(emulate=self.usar_emulacion)
            # numero_serie = self.placa.connect(b"TP2_")
            
            time.sleep(2) # Simulación temporal
            self.mensaje_estado.emit(f"¡Conexión Exitosa en modo {modo}!")
        except Exception as e:
            self.mensaje_estado.emit(f"Error: {str(e)}")

# ---------------------------------------------------------
# Interfaz Gráfica (Ventana)
# ---------------------------------------------------------
def resource_path(relative_path):
    """ Obtiene la ruta absoluta a los recursos, funciona para desarrollo y para PyInstaller """
    try:
        # PyInstaller crea una carpeta temporal y guarda el path en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Cargar el diseño con pestañas desde Qt Designer
        # Reemplaza uic.loadUi("interfaz.ui", self) por:
        uic.loadUi(resource_path("interfaz.ui"), self)

        # --- Pestaña 1: Conexión y Logs ---
        self.boton_conectar.clicked.connect(self.iniciar_conexion)
        self.consola_texto.append("--- Sistema Inicializado ---")

        # --- Pestaña 2: Configuración ---
        self.boton_enviar.clicked.connect(self.enviar_parametros)

        # --- Pestaña 3: Visualización ---
        # el lienzo de pyqtgraph
        self.lienzo_grafica.setTitle("Espectro del Detector", color="w", size="14pt")
        self.lienzo_grafica.setLabel("left", "Amplitud / Cuentas")
        self.lienzo_grafica.setLabel("bottom", "Tiempo / Canales")
        self.lienzo_grafica.showGrid(x=True, y=True)
        #  línea vacía de color verde (g) que luego actualizaremos
        self.grafica_linea = self.lienzo_grafica.plot([0], [0], pen=pg.mkPen(color='g', width=2))

    def iniciar_conexion(self):
        self.boton_conectar.setEnabled(False) 
        usar_emulacion = self.check_emulacion.isChecked()

        self.hilo = HiloConexion(usar_emulacion)
        self.hilo.mensaje_estado.connect(self.actualizar_estado)
        self.hilo.start()

    def actualizar_estado(self, mensaje):
        # Actualiza la etiqueta rápida
        self.etiqueta_estado.setText(f"Estado: {mensaje}")
        # Agrega el mensaje al registro permanente de la consola
        self.consola_texto.append(f"> {mensaje}")
        
        if "Exitosa" in mensaje or "Error" in mensaje:
            self.boton_conectar.setEnabled(True)

    def enviar_parametros(self):
        # Leemos los valores que el usuario puso en las cajas numéricas
        voltaje = self.spin_voltaje.value()
        tiempo = self.spin_tiempo.value()
        
        # el comando al ASIC o al Slow Control en el futuro:
        # self.placa.write_words(add=..., word=..., length=...)
        
        # Registramos la acción en la consola para confirmar
        self.consola_texto.append(f"-> Comando Enviado: Voltaje={voltaje}, Tiempo={tiempo}")

    def actualizar_grafica(self, nuevos_datos_x, nuevos_datos_y):
        # Esta función la llamaremos después, cuando estemos leyendo la placa,
        # para inyectarle los números reales a la gráfica
        self.grafica_linea.setData(nuevos_datos_x, nuevos_datos_y)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())
