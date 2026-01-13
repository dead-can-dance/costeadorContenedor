# app/services/weather_service.py
import httpx
from fastapi import HTTPException
from app.models import DatosClimaticos

NASA_API_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"

async def obtener_datos_nasa(lat: float, lon: float) -> DatosClimaticos:
    """
    Consulta la API de la NASA POWER para obtener temperaturas de diseño.
    """
    params = {
        "parameters": "T2M_MAX,T2M_MIN", # Pedimos Máximas y Mínimas
        "community": "RE",               # Renewable Energy
        "longitude": lon,
        "latitude": lat,
        "format": "JSON"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(NASA_API_URL, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Error conectando con NASA: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=response.status_code, detail="NASA API Error")

    try:
        # La NASA devuelve promedios mensuales (JAN a DEC) y un anual (ANN).
        # Extraemos los datos del diccionario de propiedades
        properties = data['properties']['parameter']
        
        # Lógica de Ingeniería:
        # 1. Para Voc Max (Riesgo quemar inversor): Buscamos el mes MÁS FRÍO del año.
        # No usamos el promedio anual, sino el "peor caso" de mes frío.
        temps_min_mensuales = properties['T2M_MIN'].values()
        temp_min_absoluta = min(t for t in temps_min_mensuales if isinstance(t, (int, float)))

        # 2. Para Cables (Riesgo incendio): Buscamos el mes MÁS CALIENTE.
        # Usamos el promedio de las máximas del mes más caluroso.
        temps_max_mensuales = properties['T2M_MAX'].values()
        temp_max_pico = max(t for t in temps_max_mensuales if isinstance(t, (int, float)))

        # 3. Factor de Seguridad (Opcional según tu criterio de ingeniería)
        # Algunos ingenieros restan 2-3°C extra a la mínima por olas de frío atípicas.
        temp_min_diseno = temp_min_absoluta - 2.0 

        return DatosClimaticos(
            temperatura_minima_historica=round(temp_min_diseno, 2),
            temperatura_maxima_promedio=round(temp_max_pico, 2),
            ubicacion_validada=f"Lat: {lat}, Lon: {lon}"
        )

    except KeyError:
        raise HTTPException(status_code=500, detail="Estructura de datos NASA inesperada")
