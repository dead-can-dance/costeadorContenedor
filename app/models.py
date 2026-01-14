from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum

# Definir las opciones válidas
class TipoCanalizacion(str, Enum):
    TUBERIA = "tubería"
    CHAROLA = "charola"

# --- Modelos de Calibración (NUEVO) ---
class DatosManuales(BaseModel):
    temp_max_media_mensual: Optional[float] = Field(None, description="Valor más alto de la media mensual (Conagua)")
    temp_min_media_mensual: Optional[float] = Field(None, description="Valor más bajo de la media mensual (Conagua)")
    temp_promedio_anual: Optional[float] = Field(None, description="Promedio anual de temperatura media")

class CalibracionClimatica(BaseModel):
    usar_override: bool = False
    fuente_datos: str = "Manual/Conagua"
    datos_manuales: DatosManuales

# --- Modelos de Entrada (Request) ---

# --- Modelos Existentes (Actualizados) ---

class DatosClimaticos(BaseModel):
    temperatura_minima_historica: float = Field(..., description="Usada para corrección de Voc")
    temperatura_maxima_promedio: float = Field(..., description="Usada para ampacidad")
    temperatura_promedio_anual: Optional[float] = Field(None, description="Dato informativo anual") # NUEVO CAMPO
    ubicacion_validada: str

class SeleccionComponentes(BaseModel):
    modelo_panel: str
    modelo_inversor: str
    modelo_cable_dc: str = "8 AWG" # Default o a elegir
    modelo_cable_ac: str = "1/0 AWG" # Default o a elegir

class SegmentoCanalizacion(BaseModel):
    tipo: Literal["tubería", "charola"]
    longitud: float
    ubicacion: Optional[Literal["Subterránea", "Expuesta"]] = None # Solo para AC tubería

class DisenoDC(BaseModel):
    paneles_por_serie: int
    numero_de_series: int
    segmentos: List[SegmentoCanalizacion]

class DisenoAC(BaseModel):
    numero_de_inversores: int
    segmentos: List[SegmentoCanalizacion]
    metodo_agrupacion_charola: Optional[Literal["Lineal", "Trébol"]] = "Trébol"

class DecisionInterconexion(BaseModel):
    punto_conexion_elegido: Literal[
        "Tablero Principal", 
        "Transformador MT", 
        "Acometida (Cable)", 
        "Tablero Secundario/Adecuaciones"
    ]

class ProyectoInput(BaseModel):
    nombre_proyecto: str
    coordenadas: str 
    seleccion_componentes: "SeleccionComponentes" # Usando ForwardRef o string si no está definido antes
    diseno_dc: "DisenoDC"
    diseno_ac: "DisenoAC"
    decision_interconexion: "DecisionInterconexion"
    # NUEVO CAMPO OPCIONAL
    calibracion_climatica: Optional[CalibracionClimatica] = None

# --- Modelos de Salida (Response) ---

class ItemBOM(BaseModel):
    item: str
    especificacion: str
    cantidad: float
    unidad: str

class ResumenCostos(BaseModel):
    Costo_Materiales: float
    Costo_Mano_Obra: float
    Costo_Directo_Total: float
    Contingencia: float
    Comision: float
    Utilidad: float
    CAPEX_Final: float

class ReporteGeneral(BaseModel):
    nombre_proyecto: str
    estatus: str
    fecha_calculo: str

class ProyectoOutput(BaseModel):
    reporte_general: ReporteGeneral
    resumen_costos: ResumenCostos
    BOM_detallada: List[ItemBOM]
    alertas_ingenieria: List[dict] = []

