#!/usr/bin/env python3
"""
Script para actualizar el hash M3U automáticamente.
"""
import os
import sys
from app import create_app
from app.models import Canal

# Configurar la aplicación Flask
app = create_app()

with app.app_context():
    try:
        # Importar las funciones necesarias
        from app.routes import get_m3u_hash, m3u_hash
        
        # Actualizar el hash M3U
        from app.routes import m3u_hash as m3u_module
        new_hash = get_m3u_hash()
        if new_hash != m3u_hash:
            m3u_module.m3u_hash = new_hash
            print(f"Hash M3U actualizado: {new_hash}")
        else:
            print("El hash M3U ya está actualizado")
        sys.exit(0)
    except Exception as e:
        print(f"Error al actualizar el hash M3U: {str(e)}")
        sys.exit(1)
