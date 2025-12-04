from fastapi import FastAPI, HTTPException
from datetime import datetime
from app.models import ProyectoInput, ProyectoOutput, ItemBOM, ResumenCostos, ReporteGeneral
from app.services.dc_service import calcular_circuito_dc
# from app.services.ac_service import calcular_circuito_ac (Pendiente implementar)
# from app.services.costing_service import generar_reporte_costos (Pendiente implementar)

app = FastAPI(title="Costeador Finsolar API", version="1.0")

@app.post("/api/v1/costear-proyecto", response_model=ProyectoOutput)
async def costear_proyecto(proyecto: ProyectoInput):
    alertas = []
    bom = []
    
    try:
        # 1. Cálculo DC
        res_dc = calcular_circuito_dc(proyecto, alertas)
        
        # Agregar resultados DC al BOM (Ejemplo simplificado)
        bom.append(ItemBOM(
            item="Cable DC PV", 
            especificacion=res_dc['calibre'], 
            cantidad=100, # Calcular real
            unidad="m"
        ))
        for mat in res_dc['canalizacion']:
            bom.append(ItemBOM(**mat))

        # 2. Cálculo AC (Pendiente - Usar lógica similar a DC)
        # res_ac = calcular_circuito_ac(proyecto, alertas)
        
        # 3. Costeo (Pendiente)
        # costos = generar_reporte_costos(bom, proyecto.decision_interconexion)
        
        # Mock de respuesta mientras terminamos AC y Costeo
        costos_mock = ResumenCostos(
            Costo_Materiales=0, Costo_Mano_Obra=0, Costo_Directo_Total=0,
            Contingencia=0, Comision=0, Utilidad=0, CAPEX_Final=0
        )

        return ProyectoOutput(
            reporte_general=ReporteGeneral(
                nombre_proyecto=proyecto.nombre_proyecto,
                estatus="Parcial (Solo DC implementado)",
                fecha_calculo=datetime.now().isoformat()
            ),
            resumen_costos=costos_mock,
            BOM_detallada=bom,
            alertas_ingenieria=alertas
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
