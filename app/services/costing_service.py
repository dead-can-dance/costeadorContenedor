from app.database import db
from app.models import ItemBOM, ResumenCostos

def buscar_precio(sku, tipo_item=""):
    """
    Busca el precio inteligentemente dependiendo del tipo de item.
    Orden de búsqueda:
    1. Base de datos específica (Paneles/Inversores)
    2. Catálogo general de materiales (BOS)
    """
    precio = 0.0
    encontrado = False

    # 1. Estrategia por Tipo de Componente
    if tipo_item == "Panel Solar" and sku in db.paneles.index:
        # Asegúrate de agregar la columna 'Costo' a paneles.csv
        try:
            precio = float(db.paneles.loc[sku]['Costo'])
            encontrado = True
        except KeyError:
            print(f"⚠️ El panel {sku} existe, pero no tiene columna 'Costo' en el CSV.")

    elif tipo_item == "Inversor" and sku in db.inversores.index:
        # Asegúrate de agregar la columna 'Costo' a inversores.csv
        try:
            precio = float(db.inversores.loc[sku]['Costo'])
            encontrado = True
        except KeyError:
             print(f"⚠️ El inversor {sku} existe, pero no tiene columna 'Costo' en el CSV.")

    # 2. Estrategia Fallback (Buscar en Materiales Generales)
    if not encontrado:
        if sku in db.precios_materiales.index:
            precio = float(db.precios_materiales.loc[sku]['Costo_Unitario'])
            encontrado = True

    if not encontrado:
        print(f"ALERTA 🔴: Precio no encontrado para SKU: {sku} (Tipo: {tipo_item})")
        return 0.0
    
    return precio
def buscar_precio_mo(actividad):
    if actividad in db.precios_mo.index:
        return float(db.precios_mo.loc[actividad]['Costo_Unitario'])
    return 0.0

def buscar_costo_indirecto(concepto):
    if concepto in db.precios_indirectos.index:
        return float(db.precios_indirectos.loc[concepto]['Costo'])
    return 0.0

def generar_reporte_costos(proyecto_input, res_dc, res_ac, decision_interconexion):
    BOM = []
    
    # ------------------------------------------------
    # 1. Generación de BOM (Cantidades)
    # ------------------------------------------------
    
    # 1.1 Paneles
    cant_paneles = proyecto_input.diseno_dc.paneles_por_serie * proyecto_input.diseno_dc.numero_de_series
    BOM.append(ItemBOM(
        item="Panel Solar",
        especificacion=proyecto_input.seleccion_componentes.modelo_panel,
        cantidad=cant_paneles,
        unidad="pza"
    ))
    
    # 1.2 Inversores
    BOM.append(ItemBOM(
        item="Inversor",
        especificacion=proyecto_input.seleccion_componentes.modelo_inversor,
        cantidad=proyecto_input.diseno_ac.numero_de_inversores,
        unidad="pza"
    ))
    
    # 1.3 Materiales DC
    long_dc = sum(s.longitud for s in proyecto_input.diseno_dc.segmentos)
    # Cable PV: (Longitud total * num_series * 2 polos)
    BOM.append(ItemBOM(item="Cable Fotovoltaico", especificacion=res_dc['calibre'], cantidad=long_dc * proyecto_input.diseno_dc.numero_de_series * 2, unidad="m"))
    # Tierra DC: (Longitud total * 1 hilo) - Se asume tierra corre por todo el trayecto
    BOM.append(ItemBOM(item="Cable Fotovoltaico (Tierra)", especificacion=res_dc['tierra'], cantidad=long_dc, unidad="m")) # Usamos cable PV para tierra en exterior o desnudo según práctica, aqui asumimos PV por simplicidad SKU
    # Protecciones DC
    BOM.append(ItemBOM(item="Interruptor Termomagnético", especificacion=f"{res_dc['itm']}A", cantidad=proyecto_input.diseno_dc.numero_de_series, unidad="pza")) # 1 por serie o por MPPT
    # Canalización DC
    for mat in res_dc['canalizacion']:
        BOM.append(ItemBOM(item=mat['item'], especificacion=mat['especificacion'], cantidad=mat['cantidad'], unidad=mat['unidad']))

    # 1.4 Materiales AC
    long_ac = sum(s.longitud for s in proyecto_input.diseno_ac.segmentos)
    num_inv = proyecto_input.diseno_ac.numero_de_inversores
    # Cable AC: (Longitud * num_inv * 4 hilos [3F+N])
    BOM.append(ItemBOM(item="Cable THW-LS", especificacion=res_ac['calibre'], cantidad=long_ac * num_inv * 4, unidad="m"))
    # Tierra AC
    BOM.append(ItemBOM(item="Cable THW-LS", especificacion=res_ac['tierra'], cantidad=long_ac * num_inv, unidad="m"))
    # Protecciones AC
    BOM.append(ItemBOM(item="Interruptor Termomagnético", especificacion=f"{res_ac['itm']}A", cantidad=num_inv, unidad="pza"))
    # Canalización AC
    for mat in res_ac['canalizacion']:
        BOM.append(ItemBOM(item=mat['item'], especificacion=mat['especificacion'], cantidad=mat['cantidad'], unidad=mat['unidad']))
        
    # 1.5 Interconexión
    punto_conexion = proyecto_input.decision_interconexion.punto_conexion_elegido
    # Mapeo del string del usuario al SKU del CSV
    sku_interconexion = punto_conexion # Asumimos que coinciden, si no, hacer un map
    BOM.append(ItemBOM(item="Paquete Interconexión", especificacion=sku_interconexion, cantidad=1, unidad="pza"))

    # ------------------------------------------------
    # 2. Cálculo de Costos
    # ------------------------------------------------
    
    costo_materiales = 0.0
    for item in BOM:
        # Construimos el SKU de búsqueda (A veces es directo la especificación, a veces item + espec)
        # En precios_materiales.csv tenemos SKUs como "8 AWG", "32A", "2 pulgadas"
        sku_busqueda = item.especificacion 
        costo_materiales += item.cantidad * buscar_precio(sku_busqueda, item.item)

    # Costo Mano de Obra (Simplificado según plantilla)
    costo_mo = 0.0
    costo_mo += cant_paneles * buscar_precio_mo("instalacion_panel")
    costo_mo += (long_dc + long_ac) * buscar_precio_mo("instalacion_canalizacion_metro")
    costo_mo += num_inv * buscar_precio_mo("instalacion_inversor")
    costo_mo += buscar_precio_mo("gestion_permisos")

    costo_directo = costo_materiales + costo_mo

    # 3. Indirectos y Márgenes (Desde configuracion_global o constantes)
    # Valores default si no carga el CSV
    porc_contingencia = 0.05 
    porc_utilidad = 0.20
    costo_ingenieria = 15000.00 # Fijo ejemplo
    
    # Intento de cargar de DB si existe
    try:
        porc_contingencia = float(db.config_global.loc['Contingencia_Porcentaje']['Valor'])
        porc_utilidad = float(db.config_global.loc['Margen_Utilidad_Porcentaje']['Valor'])
    except:
        pass

    contingencia = costo_directo * porc_contingencia
    subtotal_1 = costo_directo + costo_ingenieria + contingencia
    
    # Comision (ej. 3% del subtotal)
    comision = subtotal_1 * 0.03 
    subtotal_2 = subtotal_1 + comision
    
    utilidad = subtotal_2 * porc_utilidad
    capex_final = subtotal_2 + utilidad

    return {
        "BOM": BOM,
        "Costos": ResumenCostos(
            Costo_Materiales=round(costo_materiales, 2),
            Costo_Mano_Obra=round(costo_mo, 2),
            Costo_Directo_Total=round(costo_directo, 2),
            Contingencia=round(contingencia, 2),
            Comision=round(comision, 2),
            Utilidad=round(utilidad, 2),
            CAPEX_Final=round(capex_final, 2)
        )
    }