import math
from app.database import db
from app.constants import (
    TABLA_CONDUIT_IMC_40, 
    TABLA_TIERRA_250_122, 
    FACTORES_TEMP_AC_90C,
    FACTORES_AGRUPAMIENTO
)
from fastapi import HTTPException

def calcular_circuito_ac(proyecto_input, resultados_dc, datos_climaticos, alertas):
    # 1. Obtener Datos
    inversor_data = db.get_inversor(proyecto_input.seleccion_componentes.modelo_inversor)
    diseno = proyecto_input.diseno_ac
    
    Imax_CA = float(inversor_data['Imax_CA'])
    Vff = float(inversor_data['Vff'])
    
    # 2. Selección de Protecciones AC (Primero Protecciones, luego cable)
    Idiseno = Imax_CA * 1.25
    
    # Lista comercial de ITMs (puedes moverla a constants.py si crece)
    itms_comerciales = [15, 20, 30, 40, 50, 60, 70, 80, 100, 125, 150, 175, 200, 225, 250, 400]
    itm_ac = next((x for x in itms_comerciales if x >= Idiseno), None)
    
    if not itm_ac:
        raise ValueError(f"La corriente requerida ({Idiseno}A) excede los ITMs comerciales disponibles.")

    # Selección de Tierra AC basada en el ITM (Tabla 250-122)
    # Buscamos la llave en el diccionario que sea mayor o igual al ITM
    capacidad_tierra = next((k for k in sorted(TABLA_TIERRA_250_122.keys()) if k >= itm_ac), 1200)
    calibre_tierra = TABLA_TIERRA_250_122[capacidad_tierra]

    # 3. Selección de Conductor AC (Ciclo Iterativo)
    calibre_seleccionado = None
    # Obtenemos lista de calibres AC disponibles en CSV (4 AWG, 2 AWG, etc.)
    # IMPORTANTE: Tu regla de negocio dice iniciar desde 4 AWG mínimo para AC
    calibres_candidatos = [c for c in db.cables_ac.index if c in ["4 AWG", "2 AWG", "1/0 AWG", "2/0 AWG", "3/0 AWG", "4/0 AWG"]]
    
    longitud_total = sum(s.longitud for s in diseno.segmentos)
    tipo_canalizacion_principal = diseno.segmentos[0].tipo # Asumimos homogeneidad para factores
    
    # Datos climáticos Mock (Idealmente vendrían del API de clima)
    TempPromedio = datos_climaticos.temperatura_maxima_promedio
    
    for calibre in calibres_candidatos:
        datos_cable = db.cables_ac.loc[calibre]
        ampacidad_base = datos_cable['Ampacidad_90C']
        
        # A. Factores de Corrección
        # Factor Temperatura (Vinikob 90C)
        # Buscamos el rango en la tabla (ej. 35 >= 34.0)
        rango_temp = next((k for k in sorted(FACTORES_TEMP_AC_90C.keys()) if k >= TempPromedio), None)
        if rango_temp is None:
             # Si hace más calor que el máximo de la tabla (>60C?), usamos un factor muy bajo por seguridad
             ft = 0.41
        else:
             ft = FACTORES_TEMP_AC_90C[rango_temp]
        
        # Factor Agrupamiento (Solo si es Tubería)
        fa = 1.0
        if tipo_canalizacion_principal == "tubería":
            # Asumimos 3 fases + 1 neutro = 4 conductores activos -> Fa aprox 0.8
            # Si quieres ser exacto: num_inversores * 3 fases
            fa = FACTORES_AGRUPAMIENTO[6] # Valor 0.80 para 4-6 conductores
            
        Icorregida = ampacidad_base * ft * fa
        
        # Validación 1: Ampacidad (Cable >= Protección)
        if Icorregida < itm_ac:
            continue

        # Validación 2: Caída de Tensión
        # Formula Trifásica: % = (sqrt(3) * Z * L * I) / Vff
        constante_fases = 1.732 # Raíz de 3
        z_ohm_km = datos_cable['Impedancia_Acero'] # Usamos columna 'Impedancia_Acero' del CSV
        z_ohm_m = z_ohm_km / 1000
        
        v_drop = constante_fases * z_ohm_m * longitud_total * Imax_CA
        porcentaje_drop = (v_drop / Vff) * 100
        
        if porcentaje_drop < 3.0:
            calibre_seleccionado = calibre
            alertas.append({
                "codigo": "AC-CALC-OK", 
                "mensaje": f"Calibre AC {calibre} seleccionado. Vdrop: {porcentaje_drop:.2f}%. ITM: {itm_ac}A"
            })
            break
    
    if not calibre_seleccionado:
        raise HTTPException(
        status_code=422, # Entidad no procesable
        detail={
            "error_code": "CABLE_INSUFICIENTE",
            "mensaje": "No se encontró un cable AC comercial que soporte la corriente requerida bajo estas condiciones (Temp/Agrupamiento).",
            "sugerencia": "Intente cambiar a 'Charola' o reduzca la potencia del inversor."
        }
    )
    # 4. Cálculo de Canalización AC
    materiales_canalizacion = []
    
    # Datos físicos del cable seleccionado
    diam_fase = db.cables_ac.loc[calibre_seleccionado]['DiametroExt_mm']
    # Buscamos diametro de tierra en la tabla DC (Viakon) o AC si existe, usaremos DC como referencia segura o cálculo aprox
    # Para ser robustos, si el calibre tierra está en cables_ac, lo usamos, si no estimamos.
    try:
        diam_tierra = db.cables_ac.loc[calibre_tierra]['DiametroExt_mm']
    except:
        diam_tierra = diam_fase * 0.7 # Estimación si no está en CSV
        
    num_inv = diseno.numero_de_inversores
    
    for segmento in diseno.segmentos:
        if segmento.tipo == "tubería":
            # Metodo ÁREA (NOM)
            # 3 Fases + 1 Neutro por inversor = 4
            num_cables_potencia = num_inv * 4
            num_cables_tierra = num_inv * 1 # Una tierra por inversor
            
            area_fase = math.pi * (diam_fase/2)**2
            area_tierra = math.pi * (diam_tierra/2)**2
            
            area_total_ocupada = (num_cables_potencia * area_fase) + (num_cables_tierra * area_tierra)
            
            # Buscar tubería en Tabla IMC 40%
            # Las llaves del dict son mm2, valores son pulgadas. Invertimos lógica o iteramos valores.
            # En constants.py: TABLA_CONDUIT_IMC_40 = {89: '1/2"', ...} (Llave es mm2)
            tuberia = next((v for k, v in TABLA_CONDUIT_IMC_40.items() if k >= area_total_ocupada), '4"')
            
            materiales_canalizacion.append({
                "item": "Tubo Conduit Pared Delgada", # SKU Genérico
                "especificacion": tuberia, # SKU Variable
                "cantidad": segmento.longitud,
                "unidad": "m"
            })
            
        elif segmento.tipo == "charola":
            # Método ANCHO (Finsolar)
            metodo = diseno.metodo_agrupacion_charola # "Lineal" o "Trébol"
            
            ancho_requerido = 0
            if metodo == "Lineal":
                total_conductores = (num_inv * 4) + (num_inv * 1)
                ancho_cables = (num_inv * 4 * diam_fase) + (num_inv * 1 * diam_tierra)
                ancho_espacios = (total_conductores - 1) * diam_fase
                ancho_requerido = ancho_cables + ancho_espacios
            else: # Trébol
                # Grupo = 3 fases + 1 neutro + 1 tierra
                ancho_grupo = (3 * diam_fase) + (1 * diam_fase) + (1 * diam_tierra)
                ancho_grupos = num_inv * ancho_grupo
                ancho_espacios = (num_inv - 1) * (2.15 * diam_fase)
                ancho_requerido = ancho_grupos + ancho_espacios
            
            # Seleccionar ancho comercial (mm)
            anchos_comerciales = [100, 150, 200, 300, 400, 500]
            ancho_final = next((x for x in anchos_comerciales if x >= ancho_requerido), 500)
            
            materiales_canalizacion.append({
                "item": "Charola tipo Malla",
                "especificacion": f"{ancho_final} mm",
                "cantidad": segmento.longitud,
                "unidad": "m"
            })

    return {
        "calibre": calibre_seleccionado,
        "itm": itm_ac,
        "tierra": calibre_tierra,
        "canalizacion": materiales_canalizacion
    }