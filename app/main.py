from fastapi import FastAPI, HTTPException, Query
from datetime import datetime
from app.models import ProyectoInput, DatosClimaticos, ProyectoOutput, ResumenCostos, ReporteGeneral
from app.services.dc_service import calcular_circuito_dc
from app.services.ac_service import calcular_circuito_ac
from app.services.costing_service import generar_reporte_costos
from app.services.weather_service import obtener_datos_nasa

app = FastAPI(title="Costeador Finsolar API", version="1.1")

# --- NUEVO ENDPOINT ---
@app.get("/api/v1/clima", response_model=DatosClimaticos)
async def consultar_clima(
    lat: float = Query(..., description="Latitud decimal (ej. 19.43)"),
    lon: float = Query(..., description="Longitud decimal (ej. -99.13)")
):
    """
    Obtiene temperaturas críticas (Min histórica y Max promedio) 
    directamente de NASA POWER para dimensionamiento fotovoltaico.
    """
    return await obtener_datos_nasa(lat, lon)

@app.post("/api/v1/costear-proyecto", response_model=ProyectoOutput)
async def costear_proyecto(proyecto: ProyectoInput):
    alertas = []
    
    try:
        # 1. Parsear coordenadas
        try:
            lat_str, lon_str = proyecto.coordenadas.split(',')
            lat, lon = float(lat_str.strip()), float(lon_str.strip())
        except ValueError:
            raise ValueError("Formato de coordenadas inválido. Use 'lat, lon'")

        datos_climaticos = None

        # 2. Lógica Híbrida: Calibración vs NASA
        usar_manual = False
        if proyecto.calibracion_climatica and proyecto.calibracion_climatica.usar_override:
            usar_manual = True
            manual = proyecto.calibracion_climatica.datos_manuales
            
            # Verificamos que vengan los datos críticos
            if manual.temp_min_media_mensual is not None and manual.temp_max_media_mensual is not None:
                alertas.append({
                    "codigo": "CLIMA-MANUAL",
                    "mensaje": f"Usando datos manuales de: {proyecto.calibracion_climatica.fuente_datos}"
                })
                
                # Mapeo de variables Conagua -> Variables de Diseño del Sistema
                datos_climaticos = DatosClimaticos(
                    # Para Voc usamos la mínima media reportada (4.3°C según tu ejemplo)
                    # Nota: Podrías aplicar un margen de seguridad aquí si quisieras (ej. -2°C)
                    temperatura_minima_historica=manual.temp_min_media_mensual,
                    
                    # Para Ampacidad usamos la máxima media reportada (27.8°C)
                    temperatura_maxima_promedio=manual.temp_max_media_mensual,
                    
                    temperatura_promedio_anual=manual.temp_promedio_anual,
                    ubicacion_validada=f"Manual Override ({lat}, {lon})"
                )
            else:
                alertas.append({
                    "codigo": "WARN-MANUAL-INCOMPLETO",
                    "mensaje": "Se activó override pero faltan datos. Usando NASA como respaldo."
                })
                usar_manual = False

        # Si no se usó manual (o faltaban datos), vamos a la NASA
        if not usar_manual:
            datos_climaticos = await obtener_datos_nasa(lat, lon)
            alertas.append({
                "codigo": "INFO-CLIMA-NASA",
                "mensaje": f"Datos NASA: Tmin={datos_climaticos.temperatura_minima_historica}, Tmax={datos_climaticos.temperatura_maxima_promedio}"
            })

        # 3. Cálculo DC
        res_dc = calcular_circuito_dc(proyecto, datos_climaticos, alertas)
        
        # 4. Cálculo AC
        res_ac = calcular_circuito_ac(proyecto, res_dc, datos_climaticos, alertas)
        
        # 5. Costeo
        resultado_final = generar_reporte_costos(
            proyecto, res_dc, res_ac, proyecto.decision_interconexion
        )

        return ProyectoOutput(
            reporte_general=ReporteGeneral(
                nombre_proyecto=proyecto.nombre_proyecto,
                estatus="Cálculo Exitoso",
                fecha_calculo=datetime.now().isoformat()
            ),
            resumen_costos=resultado_final["Costos"],
            BOM_detallada=resultado_final["BOM"],
            alertas_ingenieria=alertas
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")