import pandas as pd
import os

# Ruta base de los datos
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.load_data()
        return cls._instance

    def load_data(self):
        # Cargar CSVs en DataFrames
        # Asegúrate de que los nombres de archivo coincidan con los de tu carpeta data/
        try:
            self.paneles = pd.read_csv(os.path.join(DATA_DIR, 'paneles.csv')).set_index('Modelo')
            self.inversores = pd.read_csv(os.path.join(DATA_DIR, 'inversores.csv')).set_index('Modelo')
            self.cables_dc = pd.read_csv(os.path.join(DATA_DIR, 'cables_dc.csv')).set_index('Calibre')
            self.cables_ac = pd.read_csv(os.path.join(DATA_DIR, 'cables_ac.csv')).set_index('Calibre')
            # ... dentro de load_data ...
            self.precios_materiales = pd.read_csv(os.path.join(DATA_DIR, 'precios_materiales.csv')).set_index('SKU')
            self.precios_mo = pd.read_csv(os.path.join(DATA_DIR, 'precios_mano_de_obra.csv')).set_index('Actividad')
            self.precios_indirectos = pd.read_csv(os.path.join(DATA_DIR, 'precios_indirectos.csv')).set_index('Concepto')
            
            # Si usas config global:
            #self.config_global = pd.read_csv(os.path.join(DATA_DIR, 'configuracion_global.csv')).set_index('Clave')
            
            
                        # Cargar precios (Fase 1.D)
            
            self.precios_materiales = pd.read_csv(os.path.join(DATA_DIR, 'precios_materiales.csv')).set_index('SKU')
            # ... cargar el resto de tablas de costos aquí ...
            print("Bases de datos cargadas correctamente.")
        except Exception as e:
            print(f"Error cargando bases de datos: {e}")
            # Para desarrollo, podemos crear DataFrames vacíos o mocks si fallan los archivos
            self.paneles = pd.DataFrame() 
        
        try:
            # Cargar CSVs
            self.paneles = pd.read_csv(os.path.join(DATA_DIR, 'paneles.csv')) # Quitamos set_index temporalmente para ver todo
            
            # --- AGREGA ESTAS 3 LÍNEAS DE DIAGNÓSTICO ---
            print("--- DIAGNÓSTICO DE PANELES ---")
            print("Columnas detectadas:", self.paneles.columns.tolist())
            print(self.paneles.head(2))
            print("--------------------------------")
            # ---------------------------------------------

            # Ahora sí aplicamos el índice
            self.paneles = self.paneles.set_index('Modelo')
            
            self.inversores = pd.read_csv(os.path.join(DATA_DIR, 'inversores.csv')).set_index('Modelo')
        finally:
            print("Carga de paneles y inversores completada.")
    def get_panel(self, modelo):
        return self.paneles.loc[modelo]

    def get_inversor(self, modelo):
        return self.inversores.loc[modelo]
        
    # Helpers para obtener listas de calibres ordenados
    def get_lista_calibres_dc(self):
        return self.cables_dc.index.tolist() # ["12 AWG", "10 AWG"...]

db = Database() # Instancia global
