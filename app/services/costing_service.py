# app/services/costing_service.py
from app.constants import (
    TABLA_COSTOS_FIJOS_POTENCIA, 
    COSTOS_ESTRUCTURA_USD_PER_WATT,
    MO_INSTALACION_PANEL_USD,
    MO_INSTALACION_INVERSOR_USD,
    COSTO_METRO_LINEAL_DC,
    COSTO_METRO_LINEAL_AC
)

def interpolar_costo_fijo(potencia_proyecto_kw):
    """Calcula el costo fijo operativo basado en la tabla de potencia."""
    tabla = sorted(TABLA_COSTOS_FIJOS_POTENCIA, key=lambda x: x[0])
    
    if potencia_proyecto_kw <= tabla[0][0]: return tabla[0][1]
    if potencia_proyecto_kw >= tabla[-1][0]:
        factor = tabla[-1][1] / tabla[-1][0]
        return potencia_proyecto_kw * factor

    for i in range(len(tabla) - 1):
        p_inf, c_inf = tabla[i]
        p_sup, c_sup = tabla[i+1]
        if p_inf <= potencia_proyecto_kw <= p_sup:
            ratio = (potencia_proyecto_kw - p_inf) / (p_sup - p_inf)
            return c_inf + ratio * (c_sup - c_inf)
    return tabla[-1][1]

def generar_reporte_costos(proyecto_input, datos_calculados):
    """
    Genera el BOM financiero basado en la ingeniería automática.
    """
    # 1. Recuperar Cantidades Calculadas
    num_paneles = datos_calculados['resumen_proyecto']['modulos']
    num_inversores = datos_calculados['resumen_proyecto']['inversores']
    potencia_kw = datos_calculados['resumen_proyecto']['potencia_instalada']
    potencia_watts = potencia_kw * 1000
    
    # 2. Precios Unitarios (En producción vendrían de DB)
    precio_panel = 180.00   # Mock
    precio_inversor = 2500.00 # Mock
    
    # 3. Cálculos por Partida
    
    # A. Materiales Mayores
    total_paneles = num_paneles * precio_panel
    total_inversores = num_inversores * precio_inversor
    
    # B. Estructura
    tipo_anclaje = proyecto_input.seleccion_componentes.tipo_anclaje
    # Si el enum llega como objeto, lo convertimos a string, si es string lo usamos directo
    if hasattr(tipo_anclaje, 'value'):
        tipo_anclaje = tipo_anclaje.value
        
    factor_estructura = COSTOS_ESTRUCTURA_USD_PER_WATT.get(tipo_anclaje, 0.05)
    total_estructura = potencia_watts * factor_estructura
    
    # C. Trayectorias (BOS)
    mts_dc = datos_calculados['ingenieria']['dc']['total_metros_cable']
    # En AC, tomamos los metros de canalización sugerida
    mts_ac = datos_calculados['ingenieria']['ac']['canalizacion_sugerida']['metros_totales']
    
    total_bos_dc = mts_dc * COSTO_METRO_LINEAL_DC
    total_bos_ac = mts_ac * COSTO_METRO_LINEAL_AC
    
    # D. Mano de Obra
    mo_total = (num_paneles * MO_INSTALACION_PANEL_USD) + \
               (num_inversores * MO_INSTALACION_INVERSOR_USD) + \
               ((mts_dc + mts_ac) * 2.50) # MO tendido cable aprox
               
    # E. Costos Fijos (Escala)
    costo_fijo = interpolar_costo_fijo(potencia_kw)
    
    # 4. Totales
    costo_directo = total_paneles + total_inversores + total_estructura + total_bos_dc + total_bos_ac + mo_total
    precio_venta = costo_directo + costo_fijo
    usd_watt = precio_venta / potencia_watts if potencia_watts > 0 else 0

    return {
        "desglose_costos": {
            "1_modulos": {"cantidad": num_paneles, "total": total_paneles},
            "2_inversores": {"cantidad": num_inversores, "total": total_inversores},
            "3_estructura": {"tipo": tipo_anclaje, "total": total_estructura},
            "4_bos": {"dc": total_bos_dc, "ac": total_bos_ac},
            "5_mano_obra": {"total": mo_total},
            "6_operativos": {"total": costo_fijo}
        },
        "resumen_financiero": {
            "costo_directo_total": costo_directo,
            "precio_venta_sugerido": precio_venta,
            "indicador_usd_watt": usd_watt
        }
    }