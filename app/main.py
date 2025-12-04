from fastapi import FastAPI, HTTPException
from datetime import datetime
from app.models import ProyectoInput, ProyectoOutput, ResumenCostos, ReporteGeneral
from app.services.dc_service import calcular_circuito_dc
from app.services.ac_service import calcular_circuito_ac
from app.services.costing_service import generar_reporte_costos

app = FastAPI(title="Costeador Finsolar API", version="1.0")

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
    