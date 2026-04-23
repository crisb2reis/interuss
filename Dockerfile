FROM python:3.11-slim

# Evita pychache e buffers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala dependências do sistema necessárias para PostGIS (GDAL, GEOS, PROJ)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Configura caminhos para GDAL (comum em distros Debian/Slim)
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]
