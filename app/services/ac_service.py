import math
from fastapi import HTTPException
from app.database import db
from app.constants import (
    TABLA_CONDUIT_IMC_40, 
    TABLA_TIERRA_250_122, 
    FACTORES_TEMP_AC_90C,
    FACTORES_AGRUPAMIENTO
)

def calcular_circuito_ac(inversor_modelo: str, cantidad_inversores: int, distancia: float, tipo_canalizacion: str, clima):
    """
    Motor de Ingeniería AC (Lado Inversor -> Interconexión).
    
    Inputs:
    - inversor_modelo: SKU del inversor.
    - cantidad_inversores: Cantidad calculada por potencia.
    - distancia: Metros totales de trayectoria.
    - tipo_canalizacion: 'tubería' o 'charola'.
    - clima: Objeto con datos de temperatura (NASA/Override).
    """
    
    # 1. OBTENER DATOS TÉCNICOS
    inversor_data = db.get_inversor(inversor_modelo)
    if not inversor_data:
        raise ValueError(f"Inversor {inversor_modelo} no encontrado en DB.")

    Imax_CA = float(inversor_data['Imax_CA'])
    Vff = float(inversor_data['Vff']) # Voltaje Fase-Fase (ej. 480V)
    
    # 2. SELECCIÓN DE PROTECCIONES (ITM)
    # Regla NEC: Corriente continua * 1.25
    Idiseno_unitario = Imax_CA * 1.25
    
    # Lista comercial de ITMs (Amperes)
    itms_comerciales = [15, 20, 30, 40, 50, 60, 70, 80, 90, 100, 125, 150, 175, 200, 225, 250, 300, 350, 400]
    
    # Seleccionamos el ITM inmediato superior
    itm_seleccionado = next((x for x in itms_comerciales if x >= Idiseno_unitario), None)
    
    if not itm_seleccionado:
        # Si excede 400A, es un proyecto industrial mayor, lanzamos alerta o error
        raise HTTPException(400, f"La corriente requerida ({Idiseno_unitario}A) excede los ITMs comerciales estándar (Máx 400A).")

    # 3. SELECCIÓN DE TIERRA FÍSICA (Tabla 250-122)
    # Buscamos la llave en el diccionario que sea mayor o igual al ITM
    # TABLA_TIERRA_250_122 debe ser {Amp_Proteccion: "Calibre_AWG"}
    capacidad_tierra = next((k for k in sorted(TABLA_TIERRA_250_122.keys()) if k >= itm_seleccionado), 1200)
    calibre_tierra = TABLA_TIERRA_250_122[capacidad_tierra]

    # 4. SELECCIÓN DE CONDUCTOR DE POTENCIA (Ciclo Iterativo Inteligente)
    calibre_seleccionado = None
    caida_final = 0.0
    
    # Filtramos solo cables aptos para AC (Generalmente de 4 AWG hacia arriba para media tensión)
    # Nota: db.cables_ac.index debe devolver strings como "4 AWG", "1/0 AWG", etc.
    calibres_candidatos = [c for c in db.cables_ac.index if c not in ["14 AWG", "12 AWG", "10 AWG", "8 AWG", "6 AWG"]]
    
    # Temperatura para factores de corrección
    temp_sitio = clima.temperatura_maxima_promedio
    
    for calibre in calibres_candidatos:
        datos_cable = db.cables_ac.loc[calibre]
        ampacidad_base = float(datos_cable['Ampacidad_90C'])
        
        # A. Factor de Corrección por Temperatura
        # Buscamos el rango en la tabla (ej. si temp es 32, busca el rango 31-35)
        # FACTORES_TEMP_AC_90C Keys: Limite Superior del rango (ej. 30, 35, 40...)
        rango_temp = next((k for k in sorted(FACTORES_TEMP_AC_90C.keys()) if k >= temp_sitio), None)
        ft = FACTORES_TEMP_AC_90C.get(rango_temp, 0.41) # 0.41 si hace un calor extremo (>60C)
        
        # B. Factor de Agrupamiento (Solo afecta severamente a Tubería)
        fa = 1.0
        if tipo_canalizacion == "tubería":
            # Asumimos 3 fases + 1 neutro por inversor = 4 conductores activos
            # Si van varios inversores en la misma tubería, esto cambiaría, 
            # pero por estándar asumimos 1 tubería por inversor o agrupamiento controlado.
            # Usamos valor conservador para 4-6 conductores
            fa = FACTORES_AGRUPAMIENTO.get(6, 0.8) 
            
        # Ampacidad Real del Cable en esas condiciones
        Icorregida = ampacidad_base * ft * fa
        
        # VALIDACIÓN 1: ¿El cable aguanta la corriente protegida?
        # El cable debe soportar la corriente del ITM (o Idiseno según criterio estricto NEC)
        if Icorregida < itm_seleccionado:
            continue # Cable muy delgado, siguiente...

        # VALIDACIÓN 2: Caída de Tensión
        # Formula Trifásica: % = (sqrt(3) * Z * L * I) / Vff
        # Z debe venir en Ohm/km
        z_ohm_km = float(datos_cable['Impedancia_Acero']) 
        z_ohm_m = z_ohm_km / 1000
        
        # Usamos Imax real del inversor para caída de tensión (no la del ITM)
        v_drop = 1.732 * z_ohm_m * distancia * Imax_CA
        porcentaje_drop = (v_drop / Vff) * 100
        
        if porcentaje_drop < 3.0: # Cumple norma (3%)
            calibre_seleccionado = calibre
            caida_final = porcentaje_drop
            break # ¡Encontramos el óptimo!
    
    if not calibre_seleccionado:
        # Fallback manual o error si ni el 250 kcmil aguanta (raro en baja tensión)
        return {
            "cable_seleccionado": None,
            "error": "Distancia excesiva para baja tensión. Requiere media tensión."
        }

    # 5. CÁLCULO DE CANALIZACIÓN (La parte robusta que pediste)
    materiales_canalizacion = []
    
    # Datos físicos
    diam_fase = float(db.cables_ac.loc[calibre_seleccionado]['DiametroExt_mm'])
    
    # Diámetro tierra: Si no está en CSV AC, buscamos en DC o estimamos
    try:
        diam_tierra = float(db.cables_ac.loc[calibre_tierra]['DiametroExt_mm'])
    except:
        # Fallback seguro: aprox 70% del diametro de fase si no hay dato
        diam_tierra = diam_fase * 0.7 

    if tipo_canalizacion == "tubería":
        # --- CÁLCULO TUBERÍA (Método de Áreas - NOM) ---
        # 3 Fases + 1 Neutro + 1 Tierra por Inversor
        num_cables_potencia = 4
        num_cables_tierra = 1
        
        area_fase = math.pi * (diam_fase/2)**2
        area_tierra = math.pi * (diam_tierra/2)**2
        
        # Área total de ocupación (mm2)
        area_ocupada_unitaria = (num_cables_potencia * area_fase) + (num_cables_tierra * area_tierra)
        
        # Buscamos diámetro de tubería que permita ese relleno al 40%
        # TABLA_CONDUIT_IMC_40: {Area_Disponible_mm2: "Diámetro_Pulgadas"}
        # Ordenamos las llaves para buscar la primera que quepa
        tuberia_optima = next((v for k, v in sorted(TABLA_CONDUIT_IMC_40.items()) if k >= area_ocupada_unitaria), '4"')
        
        materiales_canalizacion.append({
            "item": "Tubo Conduit Pared Gruesa (IMC)",
            "especificacion": tuberia_optima,
            "cantidad_total": distancia * cantidad_inversores, # Metros totales (1 tubo por inv)
            "unidad": "m",
            "nota": f"1 Tubería de {tuberia_optima} por cada inversor"
        })

    elif tipo_canalizacion == "charola":
        # --- CÁLCULO CHAROLA (Método de Ancho - Finsolar) ---
        # Asumimos que TODOS los inversores van a la misma charola principal (Trébol)
        
        # Grupo Trébol = (3 Fases + 1 Neutro + 1 Tierra) agrupados
        ancho_grupo = (3 * diam_fase) + (1 * diam_fase) + (1 * diam_tierra)
        
        # Ancho total de cables
        ancho_cables = cantidad_inversores * ancho_grupo
        
        # Espaciamiento obligatorio (un diámetro entre grupos para ventilación)
        ancho_espacios = (cantidad_inversores - 1) * (diam_fase)
        if ancho_espacios < 0: ancho_espacios = 0
        
        ancho_total_requerido_mm = ancho_cables + ancho_espacios
        
        # Seleccionar ancho comercial (100mm a 600mm)
        anchos_comerciales = [100, 150, 200, 300, 400, 500, 600]
        ancho_charola = next((x for x in anchos_comerciales if x >= ancho_total_requerido_mm), 600)
        
        materiales_canalizacion.append({
            "item": "Charola tipo Malla",
            "especificacion": f"{ancho_charola} mm",
            "cantidad_total": distancia, # Una sola charola para todos
            "unidad": "m",
            "detalles": f"Ocupación: {ancho_total_requerido_mm:.1f}mm / {ancho_charola}mm"
        })

    # 6. RETORNO DE RESULTADOS
    return {
        "cable_seleccionado": calibre_seleccionado,
        "proteccion_requerida": itm_seleccionado, # Amperes
        "tierra_fisica": calibre_tierra,
        "caida_tension_pct": round(caida_final, 2),
        "canalizacion_sugerida": {
            "tipo": tipo_canalizacion,
            "materiales": materiales_canalizacion,
            "metros_totales": distancia if tipo_canalizacion == "charola" else distancia * cantidad_inversores
        }
    }