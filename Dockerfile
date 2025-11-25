# Usa una imagen de Python 3.11 ligera
FROM python:3.11-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia el archivo de requerimientos primero
COPY requirements.txt .

# Instala las librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto de tu código de la API
COPY ./app /app

# Expone el puerto en el que correrá el API
EXPOSE 8000

# Comando para iniciar el API (usando FastAPI/Uvicorn, como recomendamos)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
