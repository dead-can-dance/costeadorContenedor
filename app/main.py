from fastapi import FastAPI, HTTPException, Query
from datetime import datetime
from app.models import ProyectoInput, DatosClimaticos, ProyectoOutput, ResumenCostos, ReporteGeneral
from app.services.dc_service import calcular_circuito_dc
from app.services.ac_service import calcular_circuito_ac
from app.services.costing_service import generar_reporte_costos
from app.services.weather_service import obtener_datos_nasa

app = FastAPI(title="Costeador Finsolar API", version="1.0")

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
        # --- NUEVO: Obtener Clima Automáticamente ---
        # 1. Parsear coordenadas (string "19.77, -103.97" -> lat, lon)
        try:
            lat_str, lon_str = proyecto.coordenadas.split(',')
            lat, lon = float(lat_str.strip()), float(lon_str.strip())
        except ValueError:
            raise ValueError("Formato de coordenadas inválido. Debe ser 'lat, lon' (ej: '19.43, -99.13')")

        # 2. Consultar Microservicio NASA
        datos_climaticos = await obtener_datos_nasa(lat, lon)
        
        # Agregamos una alerta informativa para saber que funcionó
        alertas.append({
            "codigo": "INFO-CLIMA",
            "mensaje": f"Clima obtenido de NASA: Tmin={datos_climaticos.temperatura_minima_historica}°C, TmaxAvg={datos_climaticos.temperatura_maxima_promedio}°C"
        })

        # --- Fin bloque clima ---

        # 3. Cálculo DC (Pasando datos climáticos)
        res_dc = calcular_circuito_dc(proyecto, datos_climaticos, alertas) # <--- OJO AQUÍ
        
        # 4. Cálculo AC (Pasando datos climáticos)
        res_ac = calcular_circuito_ac(proyecto, res_dc, datos_climaticos, alertas) # <--- OJO AQUÍ
        
        # 5. Costeo
        resultado_final = generar_reporte_costos(
            proyecto, 
            res_dc, 
            res_ac, 
            proyecto.decision_interconexion
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
        error_msg = traceback.format_exc()
        print(error_msg)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")