import os
import json
import subprocess
from pathlib import Path

class ConfigManager:
    _instance = None
    _config_file = os.path.join(Path.home(), '.signally_config.json')
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Carga la configuración desde el archivo JSON"""
        if not os.path.exists(self._config_file):
            self.config = {
                'auto_start': False,
                'configuracion_inicial': False
            }
            self._save_config()
        else:
            try:
                with open(self._config_file, 'r') as f:
                    self.config = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.config = {
                    'auto_start': False,
                    'configuracion_inicial': False
                }
    
    def _save_config(self):
        """Guarda la configuración en el archivo JSON"""
        with open(self._config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get_auto_start(self):
        """Obtiene el estado del autoarranque"""
        return self.config.get('auto_start', False)
    
    def _run_command(self, command):
        """Ejecuta un comando y devuelve (éxito, salida)"""
        try:
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr or e.stdout
        except Exception as e:
            return False, str(e)

    def _setup_autostart(self, enable):
        """Configura o elimina el autoarranque en crontab"""
        home_dir = os.path.expanduser('~')
        script_path = os.path.join(home_dir, 'iniciar_signally.sh')
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(app_dir, 'logs')
        
        if enable:
            # Crear directorio de logs si no existe
            os.makedirs(log_dir, exist_ok=True)
            
            # Crear el script de inicio con supervisión
            script_content = f'''#!/bin/bash
# Script generado automáticamente por Signally con supervisión

# Configuración
APP_DIR="{app_dir}"
LOG_DIR="{log_dir}"
MAX_RESTARTS=5
INITIAL_DELAY=1  # segundos
MAX_DELAY=300    # 5 minutos
CURRENT_DELAY=$INITIAL_DELAY
RESTART_COUNT=0
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/app_$TIMESTAMP.log"

# Función para escribir en el log
log() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}}

# Función para limpiar procesos huérfanos
cleanup() {{
    log "Deteniendo la aplicación..."
    pkill -f "python3 -m flask run"
    exit 0
}}

# Capturar señales de terminación
trap cleanup SIGINT SIGTERM

# Iniciar la aplicación con supervisión
cd "$APP_DIR" || {{ log "Error: No se pudo cambiar al directorio $APP_DIR"; exit 1; }}

# Activar entorno virtual si existe
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

log "=== Iniciando aplicación con supervisión ==="
log "Directorio: $APP_DIR"
log "Logs: $LOG_FILE"

while true; do
    # Registrar inicio
    log "Iniciando la aplicación... (Intento $((RESTART_COUNT + 1)))"
    
    # Ejecutar la aplicación en segundo plano
    python3 -m flask run --host=0.0.0.0 --port=5000 >> "$LOG_FILE" 2>&1 &
    APP_PID=$!
    
    # Esperar a que la aplicación termine
    wait $APP_PID
    EXIT_CODE=$?
    
    # Registrar finalización
    log "La aplicación terminó con código $EXIT_CODE"
    
    # Verificar si es un cierre limpio
    if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 130 ] || [ $EXIT_CODE -eq 143 ]; then
        log "Cierre limpio detectado, terminando..."
        exit 0
    fi
    
    # Incrementar contador de reinicios
    RESTART_COUNT=$((RESTART_COUNT + 1))
    
    # Verificar límite de reinicios
    if [ $RESTART_COUNT -ge $MAX_RESTARTS ]; then
        log "Se alcanzó el límite de $MAX_RESTARTS reinicios. Terminando..."
        exit 1
    fi
    
    # Esperar con backoff exponencial
    log "Reiniciando en $CURRENT_DELAY segundos..."
    sleep $CURRENT_DELAY
    
    # Aumentar el retraso para el próximo reinicio (backoff exponencial)
    CURRENT_DELAY=$((CURRENT_DELAY * 2))
    if [ $CURRENT_DELAY -gt $MAX_DELAY ]; then
        CURRENT_DELAY=$MAX_DELAY
    fi
done
'''
            try:
                # Escribir el script
                with open(script_path, 'w') as f:
                    f.write(script_content)
                
                # Hacer el script ejecutable
                os.chmod(script_path, 0o755)
                
                # Obtener el crontab actual
                success, current_cron = self._run_command(['crontab', '-l'])
                current_cron = current_cron if success else ''
                
                # Verificar si ya existe la entrada
                if '@reboot' not in current_cron or 'iniciar_signally.sh' not in current_cron:
                    # Agregar la entrada al crontab
                    new_cron = f"{current_cron.rstrip()}\n@reboot {script_path}\n"
                    process = subprocess.Popen(
                        ['crontab', '-'],
                        stdin=subprocess.PIPE,
                        text=True
                    )
                    process.communicate(input=new_cron)
                    
                    if process.returncode == 0:
                        return True, "Autoarranque configurado correctamente"
                    return False, "Error al configurar crontab"
                return True, "Autoarranque ya estaba configurado"
                
            except Exception as e:
                return False, f"Error al configurar autoarranque: {str(e)}"
                
        else:
            # Eliminar la entrada de crontab
            try:
                success, current_cron = self._run_command(['crontab', '-l'])
                if success and 'iniciar_signally.sh' in current_cron:
                    # Filtrar la línea de autoarranque
                    new_cron = '\n'.join(
                        line for line in current_cron.split('\n')
                        if 'iniciar_signally.sh' not in line
                    )
                    process = subprocess.Popen(
                        ['crontab', '-'],
                        stdin=subprocess.PIPE,
                        text=True
                    )
                    process.communicate(input=new_cron)
                    
                    if process.returncode == 0:
                        return True, "Autoarranque deshabilitado correctamente"
                    return False, "Error al actualizar crontab"
                return True, "Autoarranque no estaba configurado"
                
            except Exception as e:
                return False, f"Error al deshabilitar autoarranque: {str(e)}"
    
    def set_auto_start(self, value):
        """Establece el estado del autoarranque"""
        value = bool(value)
        success, message = self._setup_autostart(value)
        
        if success:
            self.config['auto_start'] = value
            self._save_config()
            print(f"[SUCCESS] {message}")
        else:
            print(f"[ERROR] {message}")
        
        return success, message

# Instancia global para ser importada
config_manager = ConfigManager()
