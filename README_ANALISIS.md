# Análisis del Proyecto Signage - Sistema de Gestión de Contenido Digital

## 📌 Visión General
Signage es un sistema completo para la gestión y transmisión de contenido multimedia en red local, diseñado para funcionar como un sistema de señalización digital. Permite la gestión de múltiples canales de transmisión con diferentes tipos de contenido, incluyendo imágenes, videos y streams en vivo.

## 🏗️ Arquitectura del Proyecto

### Estructura de Directorios
```
signage/
├── app/                           # Código fuente principal
│   ├── static/                   # Archivos estáticos (CSS, JS, imágenes)
│   ├── templates/                # Plantillas HTML
│   │   ├── base.html            # Plantilla base
│   │   ├── index.html           # Página principal
│   │   ├── conf.html            # Configuración del sistema
│   │   ├── gestion_canales.html # Gestión de canales
│   │   ├── gestion_contenido.html # Gestión de archivos multimedia
│   │   └── player.html          # Reproductor de transmisiones
│   ├── __init__.py             # Configuración de la aplicación Flask
│   ├── config_manager.py       # Gestor de configuración
│   ├── models.py              # Modelos de datos
│   └── routes.py              # Rutas y lógica de la aplicación
├── multimedia/                 # Archivos multimedia subidos
├── venv/                      # Entorno virtual de Python
├── requirements.txt           # Dependencias de Python
├── wsgi.py                   # Punto de entrada WSGI
├── install.py                # Script de instalación
└── actualizar_m3u.py         # Utilidad para actualizar listas M3U
```

## 🛠️ Tecnologías Principales

### Backend
- **Framework Web**: Flask (Python)
- **Procesamiento de Video**: FFmpeg
- **Formato de Transmisión**: HLS (HTTP Live Streaming)
- **Protocolo de Transmisión**: RTMP (para ingesta de streams)
- **Almacenamiento**: JSON para configuración y metadatos
- **Autenticación**: Basada en sesiones

### Frontend
- **HTML5/CSS3**: Estructura y estilos
- **JavaScript**: Interactividad y llamadas AJAX
- **Reproductor de Video**: Video.js
- **Bootstrap**: Framework CSS para diseño responsivo

## 🎯 Funcionalidades Principales

### 1. Gestión de Canales
- Crear, editar y eliminar canales de transmisión
- Configurar diferentes tipos de contenido (imágenes, videos, streams)
- Establecer rotación y repetición de contenido
- Vista previa en tiempo real de los canales

### 2. Gestión de Contenido Multimedia
- Subir y administrar archivos multimedia
- Soporte para múltiples formatos (imágenes, videos, audio)
- Vista previa de archivos subidos
- Eliminación segura de contenido

### 3. Transmisión en Vivo
- Transmisión de canales en tiempo real usando HLS
- Soporte para múltiples canales simultáneos
- Configuración de parámetros de transmisión
- Monitoreo del estado de las transmisiones

### 4. Reproductor Integrado
- Interfaz de usuario intuitiva
- Soporte para listas de reproducción M3U
- Control de reproducción (play/pause, volumen, pantalla completa)
- Visualización de múltiples canales en paralelo

### 5. Configuración del Sistema
- Configuración de inicio automático
- Gestión de rutas de almacenamiento
- Configuración de red para transmisión
- Registro de eventos

## 🔄 Flujo de Trabajo

1. **Configuración Inicial**
   - Instalar dependencias con `install.py`
   - Configurar rutas de almacenamiento
   - Establecer parámetros de red

2. **Gestión de Contenido**
   - Subir archivos multimedia a través de la interfaz web
   - Organizar el contenido en carpetas lógicas

3. **Configuración de Canales**
   - Crear canales con diferentes configuraciones
   - Asignar contenido a cada canal
   - Configurar parámetros de transmisión

4. **Transmisión**
   - Iniciar/Detener transmisiones
   - Monitorear el estado de las transmisiones
   - Verificar la calidad de la transmisión

5. **Visualización**
   - Acceder al reproductor web
   - Seleccionar canales para visualización
   - Controlar la reproducción

## 🚀 Despliegue

### Requisitos
- Python 3.8+
- FFmpeg
- Nginx (opcional para producción)
- Acceso a puertos 1935 (RTMP) y 5000 (HTTP)

### Instalación
```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/signage.git
cd signage

# Instalar dependencias y configurar el entorno
chmod +x install.py
sudo python3 install.py

# Activar entorno virtual
source venv/bin/activate

# Iniciar la aplicación
python wsgi.py
```

### Producción con Gunicorn
```bash
gunicorn --bind 0.0.0.0:5000 wsgi:application
```

## 📊 Estructura de Datos

### Modelo de Canal
```python
{
    "id": int,
    "nombre": str,
    "tipo_contenido": str,  # 'imagen', 'video', 'streaming'
    "rotacion": int,        # Grados de rotación (0, 90, 180, 270)
    "repeticion": str,      # 'bucle', 'una_vez', 'aleatorio'
    "contenidos": list,     # Lista de rutas a archivos multimedia
    "proceso_ffmpeg": int,  # PID del proceso de transmisión
    "en_transmision": bool, # Estado de la transmisión
    "fecha_creacion": str,  # Timestamp ISO
    "fecha_actualizacion": str  # Timestamp ISO
}
```

## 🔒 Seguridad
- Autenticación basada en sesiones
- Validación de tipos de archivo
- Sanitización de entradas
- Configuración segura por defecto

## 📈 Escalabilidad
- Arquitectura modular
- Soporte para múltiples canales simultáneos
- Gestión eficiente de recursos
- Fácil de extender con nuevas funcionalidades

## 🔄 Mantenimiento
- Registro de eventos
- Monitoreo de recursos
- Actualizaciones periódicas de seguridad
- Copias de seguridad de configuración

## 🤝 Contribución
Las contribuciones son bienvenidas. Por favor, lee nuestras guías de contribución antes de enviar un pull request.

## 📄 Licencia
Este proyecto está bajo la licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.
