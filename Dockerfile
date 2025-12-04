# Dockerfile CORREGIDO
FROM python:3.11-slim

# Establecemos una carpeta raíz genérica
WORKDIR /code

# Copiamos requirements e instalamos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos TODO el proyecto (incluida la carpeta 'app') al contenedor
COPY . .

# Exponemos el puerto
EXPOSE 8000

# Ejecutamos uvicorn apuntando a la carpeta app como módulo
# Nota el cambio: "app.main:app" le dice a Python que busque dentro del paquete 'app'
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

