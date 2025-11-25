from fastapi import FastAPI

app = FastAPI(
    title="Motor de Cálculo Costeador - Finsolar",
    version="1.0"
)

@app.get("/")
def read_root():
    """
    Endpoint raíz para verificar que el API está en línea.
    """
    return {"mensaje": "Motor de Cálculo Costeador - ¡Listo para la Fase 2!"}

# Aquí es donde implementaremos el endpoint:
# POST /api/v1/costear-proyecto
