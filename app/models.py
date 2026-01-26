from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from enum import Enum

# --- ENUMS (Opciones fijas) ---

class TipoAnclaje(str, Enum):
    COPLANAR = "coplanar"
    TILT = "fix tilt"
    GROUND = "groundmount"
    CARPORT = "carport"

class TipoCanalizacion(str, Enum):
    TUBERIA = "tubería"
    CHAROLA = "charola"

# --- MODELOS DE ENTRADA (INPUTS) ---
class DatosClimaticos(BaseModel):
    temperatura_minima_historica: float = Field(..., description="Mínima histórica para corrección de Voc (NASA)")
    temperatura_maxima_promedio: float = Field(..., description="Máxima promedio para ampacidad (NASA)")
    temperatura_promedio_anual: Optional[float] = Field(None, description="Promedio anual")
    ubicacion_validada: str

class CalibracionClimatica(BaseModel):
    usar_override: bool = False
    datos_manuales: Optional[Dict[str, float]] = None
    # Ejemplo datos_manuales: {"temp_min": 5.0, "temp_max": 35.0}

class SeleccionComponentes(BaseModel):
    modelo_panel: str = Field(..., description="SKU del panel (ej. CS7N-680TB-AG)")
    modelo_inversor: str = Field(..., description="SKU del inversor (ej. Solis-75K-5G-US)")
    tipo_anclaje: TipoAnclaje = Field(..., description="Tipo de estructura para costeo")
    # Nota: modelo_cable_ac se eliminó (se calcula automático)
    # modelo_cable_dc se puede dejar opcional o manejar interno

class ParametrosDiseño(BaseModel):
    paneles_por_serie_sugerido: int = Field(..., description="Cantidad de paneles por string deseada (ej. 15)")
    distancia_dc_promedio: float = Field(..., description="Longitud promedio de los strings hacia el inversor (metros)")
    distancia_ac_total: float = Field(..., description="Distancia del inversor al punto de interconexión (metros)")
    tipo_canalizacion: TipoCanalizacion = Field(..., description="Preferencia de canalización (Tubería/Charola)")

class ProyectoInput(BaseModel):
    nombre_proyecto: str
    potencia_req_kw: float = Field(..., gt=0, description="Potencia Objetivo del Proyecto en kW (Dato Principal)")
    coordenadas: str = Field(..., description="Latitud, Longitud (ej. 21.115, -101.927)")
    seleccion_componentes: SeleccionComponentes
    parametros_diseno: ParametrosDiseño
    decision_interconexion: Dict[str, Any] = Field(default_factory=dict, description="Datos extra (tablero, trafo, etc.)")
    calibracion_climatica: Optional[CalibracionClimatica] = None

# --- MODELOS DE SALIDA (OUTPUTS) ---

class ResumenProyecto(BaseModel):
    potencia_solicitada_kw: float
    potencia_instalada_kw: float
    cantidad_modulos: int
    cantidad_inversores: int
    cantidad_series: int

class Alerta(BaseModel):
    codigo: str
    mensaje: str
    nivel: Literal["info", "warning", "error"]

class ResultadoIngenieriaDC(BaseModel):
    cable_seleccionado: str
    proteccion_requerida: str
    tierra_fisica: str
    caida_tension_pct: float
    total_metros_cable: float
    detalles_series: Dict[str, Any]

class ResultadoIngenieriaAC(BaseModel):
    cable_seleccionado: str
    proteccion_requerida: float
    caida_tension_pct: float
    canalizacion_sugerida: Dict[str, Any]

class DesgloseCostos(BaseModel):
    modulos: Dict[str, Any]
    inversores: Dict[str, Any]
    estructura: Dict[str, Any]
    bos_trayectorias: Dict[str, Any]
    mano_obra: Dict[str, Any]
    costos_fijos_operativos: Dict[str, Any]

class ResumenFinanciero(BaseModel):
    costo_directo_total: float
    precio_venta_sugerido: float
    indicador_usd_watt: float

class ProyectoOutput(BaseModel):
    resumen_proyecto: ResumenProyecto
    ingenieria: Dict[str, Any]  # Contiene dc: ResultadoIngenieriaDC, ac: ResultadoIngenieriaAC
    costos: Dict[str, Any]      # Contiene desglose_costos y resumen_financiero
    alertas: List[Alerta]