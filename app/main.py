from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import math

# Importamos los modelos y servicios actualizados
from app.models import ProyectoInput, ProyectoOutput, Alerta
from app.database import db
from app.services.dc_service import calcular_circuito_dc
from app.services.ac_service import calcular_circuito_ac
from app.services.costing_service import generar_reporte_costos
from app.services.weather_service import obtener_datos_nasa

app = FastAPI(
    title="Costeador Finsolar 2.0",
    description="API de Ingeniería y Costos Fotovoltaicos (Power-Driven Design)",
    version="2.0.0"
)

# Configuración CORS (Importante para conectar con Frontend/Odoo después)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción cambiar por el dominio real
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "online", "system": "Costeador Finsolar 2.0"}

@app.post("/api/v1/costear-proyecto", response_model=ProyectoOutput)
async def costear_proyecto(proyecto: ProyectoInput):
    """
    Endpoint Maestro:
    1. Recibe Potencia Objetivo (kW).
    2. Dimensiona equipos (Paneles e Inversores).
    3. Ejecuta Ingeniería DC y AC automática.
    4. Calcula Costos Financieros por Economía de Escala.
    """
    alertas = []
    
    try:
        # --- PASO 0: RECUPERAR DATOS TÉCNICOS DE LA DB ---
        panel_db = db.get_panel(proyecto.seleccion_componentes.modelo_panel)
        if not panel_db:
            raise HTTPException(status_code=404, detail=f"Panel {proyecto.seleccion_componentes.modelo_panel} no encontrado")
            
        inversor_db = db.get_inversor(proyecto.seleccion_componentes.modelo_inversor)
        if not inversor_db:
            raise HTTPException(status_code=404, detail=f"Inversor {proyecto.seleccion_componentes.modelo_inversor} no encontrado")
        
        # Convertimos valores a float para cálculos
        potencia_panel_w = float(panel_db['Pmax'])
        potencia_inversor_ac_w = float(inversor_db['PotenciaSalidaAC'])
        
        # --- PASO 1: DIMENSIONAMIENTO AUTOMÁTICO (Lógica del Excel) ---
        
        # A. Cantidad de Paneles
        potencia_req_watts = proyecto.potencia_req_kw * 1000
        # Fórmula: Potencia Total / Potencia Panel (Redondeo hacia arriba)
        num_modulos_teorico = potencia_req_watts / potencia_panel_w
        num_modulos_calculado = math.ceil(num_modulos_teorico)
        
        # B. Ajuste por Strings (Series)
        # Ajustamos el número total para que sea múltiplo del tamaño de serie sugerido
        paneles_x_serie = proyecto.parametros_diseno.paneles_por_serie_sugerido
        num_series = math.ceil(num_modulos_calculado / paneles_x_serie)
        
        # Recálculo final exacto
        num_modulos_final = num_series * paneles_x_serie
        potencia_instalada_kw = (num_modulos_final * potencia_panel_w) / 1000
        
        if num_modulos_final != num_modulos_calculado:
            alertas.append(Alerta(
                codigo="AJUSTE-SERIES",
                mensaje=f"Se ajustaron los módulos de {num_modulos_calculado} a {num_modulos_final} para completar {num_series} series de {paneles_x_serie}.",
                nivel="info"
            ))

        # C. Cantidad de Inversores
        # Fórmula: Potencia Requerida / Potencia Inversor
        num_inversores_teorico = potencia_req_watts / potencia_inversor_ac_w
        num_inversores = math.ceil(num_inversores_teorico)
        
        # Validación de Ratio DC/AC
        potencia_ac_total_w = num_inversores * potencia_inversor_ac_w
        ratio_dc_ac = (potencia_instalada_kw * 1000) / potencia_ac_total_w
        
        if ratio_dc_ac > 1.3:
            alertas.append(Alerta(
                codigo="RATIO-ALTO",
                mensaje=f"El Ratio DC/AC es alto ({ratio_dc_ac:.2f}). Considera agregar otro inversor.",
                nivel="warning"
            ))

        # --- PASO 2: OBTENCIÓN DE DATOS CLIMÁTICOS ---
        datos_climaticos = obtener_datos_nasa(
            lat=proyecto.coordenadas.split(',')[0].strip(),
            lon=proyecto.coordenadas.split(',')[1].strip(),
            override=proyecto.calibracion_climatica
        )

        # --- PASO 3: INGENIERÍA DC (Simulación) ---
        # Preparamos el objeto de diseño "virtual" con los datos calculados
        diseno_dc_simulado = {
            "paneles_por_serie": paneles_x_serie,
            "numero_de_series": num_series,
            "longitud_promedio": proyecto.parametros_diseno.distancia_dc_promedio,
            "canalizacion": proyecto.parametros_diseno.tipo_canalizacion
        }
        
        resultado_dc = calcular_circuito_dc(
            componentes=proyecto.seleccion_componentes,
            diseno=diseno_dc_simulado,
            clima=datos_climaticos
        )

        # --- PASO 4: INGENIERÍA AC (Selección Automática) ---
        # El servicio ahora busca el cable óptimo, ya no se lo pedimos al usuario
        resultado_ac = calcular_circuito_ac(
            inversor_modelo=proyecto.seleccion_componentes.modelo_inversor,
            cantidad_inversores=num_inversores,
            distancia=proyecto.parametros_diseno.distancia_ac_total,
            tipo_canalizacion=proyecto.parametros_diseno.tipo_canalizacion,
            clima=datos_climaticos
        )
        
        if not resultado_ac.get('cable_seleccionado'):
            alertas.append(Alerta(
                codigo="ERR-CABLE-AC",
                mensaje="No se encontró un cable AC comercial que cumpla con la caída de tensión < 3%. Revisa la distancia.",
                nivel="error"
            ))

        # --- PASO 5: CÁLCULO DE COSTOS (Modelo Financiero) ---
        # Empaquetamos todo lo calculado para enviarlo al cotizador
        datos_para_costeo = {
            "resumen_proyecto": {
                "potencia_instalada": potencia_instalada_kw,
                "modulos": num_modulos_final,
                "inversores": num_inversores
            },
            "ingenieria": {
                "dc": resultado_dc,
                "ac": resultado_ac
            }
        }
        
        reporte_costos = generar_reporte_costos(proyecto, datos_para_costeo)

        # --- PASO 6: RESPUESTA FINAL ---
        return ProyectoOutput(
            resumen_proyecto={
                "potencia_solicitada_kw": proyecto.potencia_req_kw,
                "potencia_instalada_kw": potencia_instalada_kw,
                "cantidad_modulos": num_modulos_final,
                "cantidad_inversores": num_inversores,
                "cantidad_series": num_series
            },
            ingenieria={
                "dc": resultado_dc,
                "ac": resultado_ac
            },
            costos=reporte_costos,
            alertas=alertas
        )

    except Exception as e:
        # Captura cualquier error inesperado para no tumbar el servidor
        print(f"Error crítico en costeo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno de cálculo: {str(e)}")