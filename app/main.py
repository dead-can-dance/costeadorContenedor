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
        # 1. Cálculo DC
        res_dc = calcular_circuito_dc(proyecto, alertas)
        
        # 2. Cálculo AC
        res_ac = calcular_circuito_ac(proyecto, res_dc, alertas)
        
        # 3. Costeo y BOM
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
        # Errores de validación técnica (ej. cable no encontrado)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(error_msg) # Esto lo imprime en la consola de Docker
        # Esto te devolverá el error completo en el Swagger en lugar de solo "Internal Server Error"
        raise HTTPException(status_code=500, detail=f"Error interno detallado: {str(e)} | Trace: {error_msg}")
    