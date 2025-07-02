#!/bin/bash
# Script para actualizar el hash M3U

# Cambiar al directorio de la aplicación
cd "$(dirname "$0")"

# Activar el entorno virtual
source venv/bin/activate

# Ejecutar el script de Python
python3 actualizar_m3u.py

echo "M3U actualizado el $(date)"
