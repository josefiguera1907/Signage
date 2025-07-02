# Signage - Sistema de Gestión de Contenido Digital

Sistema de gestión de contenido digital para transmisión de video en red local.

## 📋 Requisitos del Sistema

- **Sistema Operativo**: Debian/Ubuntu (recomendado) o cualquier distribución Linux
- **Python**: 3.8 o superior
- **FFmpeg**: Para procesamiento de video
- **Nginx**: Opcional para producción
- **Git**: Para clonar el repositorio

## 🚀 Instalación Rápida

1. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/tu-usuario/signage.git
   cd signage
   ```

2. **Ejecutar el instalador** (requiere sudo para dependencias del sistema):
   ```bash
   # Hacer ejecutable el script de instalación
   chmod +x install.py
   
   # Ejecutar con privilegios de superusuario
   sudo python3 install.py
   ```

3. **Activar el entorno virtual**:
   ```bash
   # Linux/Mac
   source venv/bin/activate
   
   # Windows
   .\venv\Scripts\activate
   ```

## 💻 Uso

### Modo Desarrollo
```bash
python wsgi.py
```

### Modo Producción con Gunicorn
```bash
gunicorn --bind 0.0.0.0:5000 wsgi:application
```

### 📍 Acceso a la aplicación
Abre tu navegador y visita:
- **Desarrollo**: http://localhost:5000
- **Red local**: http://[TU_IP_LOCAL]:5000

## 🗂️ Estructura del Proyecto

```
signage/
├── app/                    # Código fuente principal
│   ├── static/             # Archivos estáticos (CSS, JS, imágenes)
│   ├── templates/          # Plantillas HTML
│   ├── __init__.py         # Configuración de la aplicación
│   ├── routes.py           # Rutas y lógica de la aplicación
│   ├── models.py           # Modelos de datos
│   └── config_manager.py   # Gestor de configuración
├── multimedia/             # Archivos multimedia subidos
├── venv/                   # Entorno virtual de Python
├── requirements.txt        # Dependencias de Python
├── wsgi.py                # Punto de entrada WSGI
└── install.py             # Script de instalación
```

## ⚙️ Configuración

La aplicación se puede configurar editando:
- `app/__init__.py` - Configuración básica de Flask
- `app/config_manager.py` - Configuración de la aplicación

## 🔄 Actualización

Para actualizar a la última versión:
```bash
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
```

## 📝 Licencia

Este proyecto está bajo la licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor, lee nuestras [guías de contribución](CONTRIBUTING.md) antes de enviar un pull request.
