#!/usr/bin/env python3
"""
WSGI entry point for the Flask application.
This file is used by Gunicorn and other WSGI servers to serve the application.
"""

import os
import sys
from pathlib import Path

# Asegurarse de que el directorio del proyecto esté en el PYTHONPATH
project_dir = str(Path(__file__).parent.absolute())
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Importar la aplicación Flask
from app import create_app

# Crear la instancia de la aplicación Flask
application = create_app()

if __name__ == "__main__":
    # Ejecutar la aplicación en modo desarrollo
    application.run(host='0.0.0.0', port=5000, debug=True)
