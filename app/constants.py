# Tablas digitalizadas de la NOM-001-SEDE-VIGENTE

# Tabla 690-7: Factores de corrección de tensión DC
TABLA_690_7 = {
    20: 1.02, 15: 1.04, 10: 1.06, 5: 1.08, 0: 1.10,
    -5: 1.12, -10: 1.14, -15: 1.18, -20: 1.20
}

# Tabla 310-15(b)(2)(a): Factores de temp AC (Vinikob 90C)
FACTORES_TEMP_AC_90C = {
    25: 1.04, 30: 1.00, 35: 0.96, 40: 0.91,
    45: 0.87, 50: 0.82, 55: 0.76, 60: 0.71
}

# Tabla 310-15(b)(3)(a): Agrupamiento en Tubería
FACTORES_AGRUPAMIENTO = {
    6: 0.80, 9: 0.70, 20: 0.50, 30: 0.45, 40: 0.40, 999: 0.35
}

# Tabla 250-122: Puesta a Tierra
TABLA_TIERRA_250_122 = {
    15: "14 AWG", 20: "12 AWG", 60: "10 AWG", 100: "8 AWG",
    200: "6 AWG", 300: "4 AWG", 400: "2 AWG", 500: "2 AWG"
}

# Tabla IMC 40% Llenado (mm2)
# En app/constants.py

TABLA_CONDUIT_IMC_40 = {
    89: '1/2 pulgadas', 
    151: '3/4 pulgadas', 
    248: '1 pulgada', 
    425: '1 1/4 pulgadas',
    573: '1 1/2 pulgadas', 
    937: '2 pulgadas', 
    1323: '2 1/2 pulgadas', 
    2046: '3 pulgadas',
    3490: '4 pulgadas'
}

# Tabla: Costo Fijo Operativo por Potencia (Economía de Escala)
# Formato: (Potencia_kW, Costo_Fijo_USD)
TABLA_COSTOS_FIJOS_POTENCIA = [
    (20, 1400.00),
    (40, 2300.00),
    (60, 3200.00),
    (80, 4100.00),
    (100, 5000.00)
]

# Costo de Estructura por Watt (Según tipo de anclaje)
COSTOS_ESTRUCTURA_USD_PER_WATT = {
    "coplanar": 0.03,      
    "fix tilt": 0.05,
    "groundmount": 0.08,
    "carport": 0.12
}

# Costos Base Mano de Obra
MO_INSTALACION_PANEL_USD = 15.00
MO_INSTALACION_INVERSOR_USD = 250.00
COSTO_METRO_LINEAL_DC = 3.50  # USD/m (Cable + Tubería/Charola)
COSTO_METRO_LINEAL_AC = 15.00 # USD/m