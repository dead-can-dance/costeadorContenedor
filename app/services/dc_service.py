import math
from app.database import db
from app.constants import TABLA_690_7, TABLA_TIERRA_250_122, TABLA_CONDUIT_IMC_40

def calcular_circuito_dc(proyecto_input, alertas):
    # 1. Obtener Datos
    panel = db.get_panel(proyecto_input.seleccion_componentes.modelo_panel)
    inversor = db.get_inversor(proyecto_input.seleccion_componentes.modelo_inversor)
    diseno = proyecto_input.diseno_dc
    
    # --- MOCK CLIMA (Falta integrar API real) ---
    # Por ahora usamos valores fijos o calculados simples
    LTemp = 10.0 # Ejemplo
    TempPromedio = 34.0
    
    # 2. Validar Arreglos
    # Implementar lógica Vmax/Vmin aquí...
    
    # 3. Selección de Conductor DC (Iterativo)
    Isc = panel['Isc']
    Imp = panel['Imp']
    Idiseno_a = Isc * 1.56
    
    # Seleccionar protección primero
    # Lista comercial simple de ejemplo
    itms_comerciales = [10, 15, 20, 25, 30, 32, 40, 50, 63] 
    itm_dc = next((x for x in itms_comerciales if x >= Idiseno_a), None)
    
    longitud_total = sum(s.longitud for s in diseno.segmentos)
    calibre_seleccionado = None
    
    # Iterar calibres (de menor a mayor ampacidad)
    # Nota: En el CSV deben estar ordenados o se ordenan aquí
    for calibre, datos_cable in db.cables_dc.iterrows():
        # Validación Ampacidad
        # Factor temp simple (puedes hacerlo complejo con la tabla)
        ft = 0.94 # Ejemplo 34C
        icorregida = datos_cable['Ampacidad_90C'] * ft
        
        if icorregida < itm_dc:
            continue # No cumple ampacidad vs protección
            
        # Validación Caída de Tensión
        v_nominal_serie = panel['Vmp'] * diseno.paneles_por_serie
        # Formula: % = (2 * R * L * I) / V
        # R viene en Ohm/km, longitud en m -> ajustar unidades
        r_ohm_m = datos_cable['Resistencia_DC'] / 1000 
        v_drop = 2 * r_ohm_m * longitud_total * Imp
        porcentaje_drop = (v_drop / v_nominal_serie) * 100
        
        if porcentaje_drop < 3.0:
            calibre_seleccionado = calibre
            alertas.append({
                "codigo": "DC-CALC-OK", 
                "mensaje": f"Calibre DC {calibre} seleccionado. Vdrop: {porcentaje_drop:.2f}%"
            })
            break
            
    if not calibre_seleccionado:
        raise ValueError("No se encontró calibre DC adecuado")

    # 4. Canalización (Lógica Tubería/Charola)
    materiales_canalizacion = []
    cable_tierra = TABLA_TIERRA_250_122.get(next(k for k in TABLA_TIERRA_250_122 if k >= itm_dc), "8 AWG")
    
    # Datos físicos para canalización
    diam_pv = db.cables_dc.loc[calibre_seleccionado]['DiametroExt_mm']
    # Asumimos diametro tierra similar al PV o buscamos en tabla si existe
    diam_tierra = diam_pv * 0.8 
    
    for segmento in diseno.segmentos:
        if segmento.tipo == "tubería":
            # Calculo de área (NOM)
            area_pv = (math.pi * (diam_pv/2)**2) * (diseno.numero_de_series * 2)
            area_tierra = (math.pi * (diam_tierra/2)**2)
            area_total = area_pv + area_tierra
            
            # Buscar tubería
            tuberia = next((k for k, v in TABLA_CONDUIT_IMC_40.items() if v >= area_total), '4"')
            materiales_canalizacion.append({
                "item": "Tubería Conduit IMC",
                "especificacion": tuberia,
                "cantidad": segmento.longitud,
                "unidad": "m"
            })
            
        elif segmento.tipo == "charola":
            # Calculo de ancho (Regla Finsolar)
            # Ancho cables + Ancho espacios
            ancho_cables = (diseno.numero_de_series * 2 * diam_pv) + diam_tierra
            ancho_espacios = (diseno.numero_de_series * 2 - 1) * diam_pv
            ancho_total_mm = ancho_cables + ancho_espacios
            
            # Redondear a comercial (ej. 100mm, 150mm, 200mm...)
            anchos_comerciales = [100, 150, 200, 300, 400, 500, 600]
            ancho_final = next((x for x in anchos_comerciales if x >= ancho_total_mm), 600)
            
            materiales_canalizacion.append({
                "item": "Charola tipo Malla",
                "especificacion": f"{ancho_final} mm",
                "cantidad": segmento.longitud,
                "unidad": "m"
            })

    return {
        "calibre": calibre_seleccionado,
        "itm": itm_dc,
        "tierra": cable_tierra,
        "canalizacion": materiales_canalizacion
    }