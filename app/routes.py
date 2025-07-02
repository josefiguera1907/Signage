from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session, send_from_directory, Response
from werkzeug.utils import secure_filename
import os
import subprocess
import time
import json
import hashlib
import threading
import signal
from datetime import datetime
from .models import Canal
from .config_manager import config_manager



# Variable global para almacenar el hash de la lista M3U
m3u_hash = None

def obtener_archivos_multimedia():
    """Obtiene la lista de archivos multimedia subidos."""
    upload_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'multimedia')
    archivos = []
    
    try:
        for filename in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, filename)
            if os.path.isfile(filepath):
                _, ext = os.path.splitext(filename)
                archivos.append({
                    'name': filename,
                    'type': ext[1:].lower() if ext else '',
                    'size': os.path.getsize(filepath)
                })
    except FileNotFoundError:
        pass
        
    return archivos

# Crear un Blueprint para las rutas principales
main_bp = Blueprint('main', __name__)

@main_bp.context_processor
def inject_now():
    """Inyecta la fecha actual en todas las plantillas."""
    return {'now': datetime.utcnow()}

@main_bp.route('/')
def index():
    """Ruta principal de la aplicación."""
    return render_template('index.html')

@main_bp.route('/configuracion')
def configuracion():
    """Página de configuración de la aplicación."""
    auto_start = config_manager.get_auto_start()
    return render_template('conf.html', auto_start=auto_start)

@main_bp.route('/api/config/auto_start', methods=['GET', 'POST'])
def handle_auto_start():
    """Maneja las solicitudes de configuración de autoarranque."""
    if request.method == 'POST':
        try:
            data = request.get_json()
            config_manager.set_auto_start(data.get('enabled', False))
            return jsonify({'success': True, 'message': 'Configuración guardada correctamente'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
    else:
        # GET request
        return jsonify({'auto_start': config_manager.get_auto_start()})

@main_bp.route('/player')
def player():
    """Reproductor de transmisiones HLS."""
    # Cargar solo los canales que estén en transmisión
    canales = [canal for canal in Canal.cargar_todos() if getattr(canal, 'en_transmision', False)]
    # Obtener la URL base del servidor RTMP desde la configuración o usar localhost por defecto
    rtmp_server = current_app.config.get('RTMP_SERVER', 'http://localhost:1936')
    return render_template('player.html',
                         canales=canales,
                         rtmp_server=rtmp_server.rstrip('/'))  # Asegurarse de que no haya barra al final

# Configuración de la subida de archivos
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'multimedia')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'mkv', 'mp3', 'wav'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main_bp.route('/gestion-contenido', methods=['GET', 'POST'])
def gestion_contenido():
    """Ruta para la gestión de contenido multimedia."""
    if request.method == 'POST':
        # Verificar si el post tiene la parte del archivo
        if 'mediaFile' not in request.files:
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(request.url)
        
        file = request.files['mediaFile']
        titulo = request.form.get('titulo', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        etiquetas = [tag.strip() for tag in request.form.get('etiquetas', '').split(',') if tag.strip()]
        
        # Validar que se haya proporcionado un título
        if not titulo:
            flash('El título es obligatorio', 'error')
            return redirect(request.url)
        
        # Si el usuario no selecciona un archivo, el navegador puede
        # enviar una parte vacía sin nombre de archivo
        if file.filename == '':
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            # Generar un nombre de archivo seguro y único
            filename = secure_filename(file.filename)
            base, ext = os.path.splitext(filename)
            counter = 1
            
            # Verificar si el archivo ya existe y generar un nuevo nombre si es necesario
            while os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
                filename = f"{base}_{counter}{ext}"
                counter += 1
            
            # Asegurarse de que el directorio multimedia exista
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            
            try:
                # Guardar el archivo
                file.save(filepath)
                
                # Aquí podrías guardar la información en una base de datos
                # con los campos del formulario (título, descripción, etc.)
                # Por ahora, solo mostramos un mensaje de éxito
                
                mensaje = f'Archivo "{filename}" subido correctamente.'
                if descripcion:
                    mensaje += f' Descripción: {descripcion}'
                if etiquetas:
                    mensaje += f' Etiquetas: {", ".join(etiquetas)}'
                
                flash(mensaje, 'success')
                return redirect(url_for('main.gestion_contenido'))
                
            except Exception as e:
                flash(f'Error al guardar el archivo: {str(e)}', 'error')
        else:
            flash('Tipo de archivo no permitido. Formatos aceptados: ' + ', '.join(ALLOWED_EXTENSIONS), 'error')
    
    # Obtener lista de archivos en la carpeta multimedia
    try:
        files = []
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath):
                files.append({
                    'name': filename,
                    'size': os.path.getsize(filepath),
                    'type': filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                })
    except FileNotFoundError:
        files = []
    
    return render_template('gestion_contenido.html', files=files)

@main_bp.route('/canales')
@main_bp.route('/canales/editar/<int:canal_id>', methods=['GET'])
def gestion_canales(canal_id=None):
    """Muestra la lista de canales y el formulario para crear/editar."""
    canales = Canal.cargar_todos()
    archivos = obtener_archivos_multimedia()
    canal_editar = Canal.obtener_por_id(canal_id) if canal_id else None
    
    # Obtener mensaje de error de la sesión si existe
    error_message = session.pop('error_message', None)
    if error_message:
        flash(error_message, 'error')
    
    return render_template('gestion_canales.html', 
                         canales=canales, 
                         archivos=archivos, 
                         canal_editar=canal_editar,
                         tipos_contenido=Canal.TIPOS_CONTENIDO)

@main_bp.route('/canales/guardar', methods=['POST'])
def guardar_canal():
    """Guarda un canal nuevo o actualizado."""
    print("=== Datos del formulario recibidos ===")
    print(f"Form data: {request.form}")
    print(f"Contenidos: {request.form.getlist('contenidos')}")
    
    canal_id = request.form.get('canal_id')
    nombre = request.form.get('nombre')
    tipo_contenido = request.form.get('tipo_contenido')
    rotacion = request.form.get('rotacion', 0)
    repeticion = request.form.get('repeticion', 'bucle')
    contenidos = request.form.getlist('contenidos')
    
    print(f"Valor de repetición recibido: {repeticion}")
    print(f"Todos los datos del formulario: {request.form}")
    
    print(f"Nombre: {nombre}")
    print(f"Tipo contenido: {tipo_contenido}")
    print(f"Contenidos seleccionados: {contenidos}")
    
    # Validación básica
    if not nombre or not tipo_contenido:
        error_msg = 'Por favor complete todos los campos requeridos. '
        error_msg += f'Nombre: {"Sí" if nombre else "No"}, Tipo: {"Sí" if tipo_contenido else "No"}'
        flash(error_msg, 'error')
        return redirect(request.referrer)
    
    # Crear o actualizar el canal
    if canal_id and canal_id.isdigit():
        canal = Canal.obtener_por_id(int(canal_id))
        if not canal:
            flash('No se encontró el canal a actualizar', 'error')
            return redirect(url_for('main.gestion_canales'))
        
        canal.nombre = nombre
        canal.tipo_contenido = tipo_contenido
        canal.rotacion = int(rotacion)
        canal.repeticion = repeticion
        canal.contenidos = contenidos
        canal.fecha_actualizacion = datetime.now().isoformat()
    else:
        canal = Canal(
            nombre=nombre,
            tipo_contenido=tipo_contenido,
            rotacion=int(rotacion),
            repeticion=repeticion,
            contenidos=contenidos
        )
    
    # Guardar el canal
    try:
        Canal.guardar(canal)
        mensaje = 'Canal actualizado correctamente' if canal_id else 'Canal creado correctamente'
        flash(mensaje, 'success')
    except Exception as e:
        flash(f'Error al guardar el canal: {str(e)}', 'error')
    
    return redirect(url_for('main.gestion_canales'))

@main_bp.route('/canales/eliminar/<int:canal_id>', methods=['POST'])
def eliminar_canal(canal_id):
    """Elimina un canal existente."""
    try:
        # Buscar el canal por ID
        canales = Canal.cargar_todos()
        canal_encontrado = next((c for c in canales if c.id == canal_id), None)
        
        if not canal_encontrado:
            return jsonify({
                'success': False,
                'message': 'El canal no existe'
            }), 404
            
        # Verificar si el canal está en transmisión
        if getattr(canal_encontrado, 'en_transmision', False):
            return jsonify({
                'success': False,
                'message': 'No se puede eliminar el canal mientras está en transmisión. Detenga la transmisión primero.'
            }), 400
            
        # Si no está en transmisión, proceder con la eliminación
        Canal.eliminar_por_id(canal_id)
        return jsonify({
            'success': True,
            'message': 'Canal eliminado correctamente'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al eliminar el canal: {str(e)}'
        }), 500

# Ruta para la vista previa de un canal
@main_bp.route('/canales/vista-previa/<int:canal_id>')
def vista_previa_canal(canal_id):
    """Muestra una vista previa del canal."""
    canal = Canal.obtener_por_id(canal_id)
    if not canal:
        flash('El canal solicitado no existe', 'error')
        return redirect(url_for('main.gestion_canales'))
    
    # Obtener información detallada de los archivos del canal
    archivos = []
    upload_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'multimedia')
    
    for nombre_archivo in canal.contenidos:
        filepath = os.path.join(upload_folder, nombre_archivo)
        if os.path.exists(filepath):
            _, ext = os.path.splitext(nombre_archivo)
            archivos.append({
                'nombre': nombre_archivo,
                'tipo': ext[1:].lower() if ext else '',
                'ruta': f'/multimedia/{nombre_archivo}'
            })
    
    return render_template('vista_previa_canal.html', canal=canal, archivos=archivos)

# Ruta para servir archivos multimedia
@main_bp.route('/uploads/<path:filename>')
def servir_archivo(filename):
    """Sirve archivos multimedia desde la carpeta de uploads."""
    return send_from_directory(UPLOAD_FOLDER, filename)

@main_bp.route('/eliminar-archivo', methods=['POST'])
def eliminar_archivo():
    """Elimina un archivo del servidor."""
    try:
        filename = request.form.get('filename')
        if not filename:
            flash('Nombre de archivo no proporcionado', 'error')
            return redirect(url_for('main.gestion_contenido'))
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        # Verificar que el archivo existe y está dentro del directorio permitido
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            flash('El archivo no existe', 'error')
            return redirect(url_for('main.gestion_contenido'))
            
        # Verificar que el archivo está dentro del directorio permitido (seguridad)
        if not os.path.realpath(filepath).startswith(os.path.realpath(UPLOAD_FOLDER)):
            flash('Acceso denegado', 'error')
            return redirect(url_for('main.gestion_contenido'))
            
        # Eliminar el archivo
        os.remove(filepath)
        
        flash('Archivo eliminado correctamente', 'success')
        return redirect(url_for('main.gestion_contenido'))
        
    except Exception as e:
        flash(f'Error al eliminar el archivo: {str(e)}', 'error')
        return redirect(url_for('main.gestion_contenido'))

@main_bp.route('/canales/transmitir/<int:canal_id>', methods=['GET', 'POST'])
def transmitir_canal(canal_id):
    """Inicia o detiene la transmisión de un canal."""
    import os
    import signal
    import subprocess
    import time
    from datetime import datetime
    from flask import redirect, url_for, flash, request, current_app, jsonify
    from .models import Canal
    
    def responder(request, data):
        """Función auxiliar para manejar la respuesta HTTP."""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify(data)
        else:
            if data.get('success', False):
                flash(data['message'], 'success')
            else:
                flash(data['message'], 'error')
            return redirect(url_for('main.gestion_canales'))
    
    global m3u_hash  # Declaración global para el hash M3U
    
    def get_child_pids(pid):
        """Obtiene todos los PIDs de los procesos hijos de un proceso dado."""
        try:
            # Usar ps para obtener todos los procesos hijos recursivamente
            result = subprocess.run(
                ['pstree', '-p', str(pid)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Extraer todos los PIDs del árbol de procesos
                import re
                pids = re.findall(r'\((\d+)\)', result.stdout)
                # Convertir a enteros, eliminar duplicados y el PID principal
                pids = list(set(int(p) for p in pids if p.isdigit()))
                if pid in pids:
                    pids.remove(pid)
                return pids
        except Exception as e:
            print(f"Error al obtener procesos hijos: {e}")
        return []
    
    def verificar_servidor_rtmp(rtmp_server, rtmp_port=1935, timeout=5):
        """Verifica si el servidor RTMP está disponible."""
        import socket
        try:
            # Extraer el host si la URL incluye protocolo
            host = rtmp_server.replace('rtmp://', '').replace('http://', '').replace('https://', '').split(':')[0].split('/')[0]
            
            print(f"[DEBUG] Intentando conectar a RTMP {host}:{rtmp_port}...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((host, rtmp_port))
            s.close()
            print("[DEBUG] Conexión RTMP exitosa")
            return True
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            print(f"[ERROR] No se pudo conectar al servidor RTMP {rtmp_server}:{rtmp_port}: {e}")
            return False
    
    def verificar_dependencias():
        """Verifica que todas las dependencias necesarias estén instaladas."""
        try:
            # Verificar si pstree está disponible
            try:
                subprocess.run(['which', 'pstree'], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE, 
                             check=True)
                print("[DEBUG] pstree encontrado en el sistema")
                return True
            except subprocess.CalledProcessError:
                print("[WARNING] pstree no encontrado, algunas características estarán limitadas")
                return False
        except Exception as e:
            print(f"[ERROR] Error al verificar dependencias: {e}")
            return False
    
    def obtener_procesos_hijos(pid):
        """Obtiene los PIDs de los procesos hijos usando diferentes métodos."""
        # Método 1: Usando pstree si está disponible
        try:
            result = subprocess.run(
                ['pstree', '-p', str(pid)],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                import re
                pids = re.findall(r'\((\d+)\)', result.stdout)
                pids = list(set(int(p) for p in pids if p.isdigit()))
                if pid in pids:
                    pids.remove(pid)
                return pids
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
            
        # Método 2: Usando ps -o pid= --ppid
        try:
            result = subprocess.run(
                ['ps', '-o', 'pid=', '--ppid', str(pid)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                pids = [int(p.strip()) for p in result.stdout.split() if p.strip().isdigit()]
                # Obtener también los hijos de los hijos de forma recursiva
                all_pids = pids.copy()
                for child_pid in pids:
                    all_pids.extend(obtener_procesos_hijos(child_pid))
                return list(set(all_pids))
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
            
        return []
    
    def stop_ffmpeg_process(pid, canal_id):
        """Detiene un proceso FFmpeg y sus hijos de manera segura."""
        if not pid:
            print("[DEBUG] PID no proporcionado, no hay nada que detener")
            return False
            
        try:
            print(f"[DEBUG] === Iniciando detención del proceso FFmpeg (PID: {pid}) para el canal {canal_id} ===")
            
            # 1. Obtener todos los PIDs del árbol de procesos
            all_pids = [pid] + obtener_procesos_hijos(pid)
            print(f"[DEBUG] Procesos a detener: {all_pids}")
            
            # 2. Enviar SIGTERM a todos los procesos
            for current_pid in all_pids:
                try:
                    print(f"[DEBUG] Enviando SIGTERM al proceso {current_pid}")
                    os.kill(current_pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError) as e:
                    print(f"[DEBUG] No se pudo enviar SIGTERM a {current_pid}: {e}")
            
            # 3. Esperar un poco a que los procesos terminen
            time.sleep(2)
            
            # 4. Verificar qué procesos siguen activos
            remaining_pids = []
            for current_pid in all_pids:
                try:
                    os.kill(current_pid, 0)  # Solo verifica si el proceso existe
                    remaining_pids.append(current_pid)
                except (ProcessLookupError, PermissionError):
                    pass
            
            # 5. Si aún quedan procesos, intentar con SIGKILL
            if remaining_pids:
                print(f"[DEBUG] Procesos que no respondieron a SIGTERM: {remaining_pids}")
                for current_pid in remaining_pids:
                    try:
                        print(f"[DEBUG] Enviando SIGKILL al proceso {current_pid}")
                        os.kill(current_pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError) as e:
                        print(f"[DEBUG] No se pudo enviar SIGKILL a {current_pid}: {e}")
                
                # Esperar un poco más
                time.sleep(1)
            
            # 6. Limpiar procesos zombie
            print("[DEBUG] Limpiando procesos zombie...")
            try:
                while True:
                    try:
                        # waitpid con WNOHANG para no bloquear
                        pid_done, status = os.waitpid(-1, os.WNOHANG)
                        if pid_done == 0:  # No hay más procesos hijos
                            break
                        print(f"[DEBUG] Proceso hijo {pid_done} terminado con estado {status}")
                    except ChildProcessError:
                        print("[DEBUG] No hay más procesos hijos para esperar")
                        break
                    except Exception as e:
                        print(f"[ERROR] Error al esperar procesos hijos: {e}")
                        break
            except Exception as e:
                print(f"[ERROR] Error en la limpieza de procesos zombie: {e}")
            
            # 7. Verificación final
            try:
                os.kill(pid, 0)  # Solo verifica si el proceso existe
                print(f"[WARNING] El proceso {pid} sigue activo después de intentar detenerlo")
                
                # Limpieza de emergencia
                print("[EMERGENCIA] Intentando limpieza de emergencia con pkill...")
                try:
                    # Intentar matar cualquier proceso relacionado con FFmpeg
                    subprocess.run(['pkill', '-9', '-f', f'ffmpeg.*canal_{canal_id}'], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
                    print(f"[EMERGENCIA] Se ejecutó pkill para limpiar procesos del canal {canal_id}")
                    
                    # Verificar nuevamente
                    os.kill(pid, 0)
                    print("[ERROR] No se pudo detener el proceso incluso después de pkill")
                    return False
                    
                except ProcessLookupError:
                    print("[EMERGENCIA] Proceso detenido exitosamente con pkill")
                    return True
                except Exception as e:
                    print(f"[EMERGENCIA] Error en la limpieza de emergencia: {e}")
                    return False
                    
            except ProcessLookupError:
                print(f"[DEBUG] Proceso {pid} detenido exitosamente")
                return True
                
        except Exception as e:
            print(f"[ERROR] Error inesperado al detener el proceso FFmpeg: {e}")
            # Intentar limpieza de emergencia
            try:
                subprocess.run(['pkill', '-9', '-f', f'ffmpeg.*canal_{canal_id}'], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
                print("[EMERGENCIA] Se ejecutó pkill para limpieza de emergencia")
            except Exception as e:
                print(f"[EMERGENCIA] Error al ejecutar pkill: {e}")
                
            return False
    
    # Obtener el canal
    canal = Canal.obtener_por_id(canal_id)
    if not canal:
        error_msg = 'Canal no encontrado'
        if request.is_json:
            return jsonify({'success': False, 'message': error_msg}), 404
        flash(error_msg, 'error')
        return redirect(url_for('main.gestion_canales'))
    
    # Si ya está en transmisión, detenerla
    if canal.en_transmision and canal.proceso_ffmpeg:
        try:
            # Obtener información del proceso guardada
            proceso_info = canal.proceso_ffmpeg
            if not isinstance(proceso_info, dict) or 'pid' not in proceso_info:
                print("Información del proceso no válida")
                canal.en_transmision = False
                canal.proceso_ffmpeg = None
                Canal.guardar(canal)
                return responder(request, {
                    'success': False,
                    'message': 'Error: Información del proceso de transmisión no válida',
                    'canal_id': canal_id,
                    'en_transmision': False
                })
            
            pid = proceso_info['pid']
            print(f"Deteniendo proceso FFmpeg con PID: {pid}")
            
            # Detener el proceso FFmpeg y sus hijos
            if stop_ffmpeg_process(pid, canal_id):
                # Actualizar el estado del canal
                canal.en_transmision = False
                canal.proceso_ffmpeg = None
                canal.ultima_transmision = datetime.now()
                Canal.guardar(canal)
                
                # Actualizar la lista M3U
                actualizar_m3u()
                
                print(f"Transmisión detenida para el canal {canal.nombre}")
                return responder(request, {
                    'success': True,
                    'message': 'Transmisión detenida correctamente',
                    'canal_id': canal_id,
                    'en_transmision': False
                })
            else:
                return responder(request, {
                    'success': False,
                    'message': 'Error al detener la transmisión',
                    'canal_id': canal_id,
                    'en_transmision': True
                })
                
        except Exception as e:
            error_msg = f'Error al detener la transmisión: {str(e)}'
            print(error_msg)
            return responder(request, {
                'success': False,
                'message': error_msg,
                'canal_id': canal_id,
                'en_transmision': canal.en_transmision
            })
    
    # Si no está en transmisión, iniciarla
    else:
        try:
            # Verificar si hay contenidos en el canal
            if not canal.contenidos:
                error_msg = 'El canal no tiene contenido para transmitir.'
                print(error_msg)
                return responder(request, {
                    'success': False,
                    'message': error_msg,
                    'canal_id': canal_id,
                    'en_transmision': False
                })
                
            # Verificar que el servidor RTMP esté disponible
            rtmp_server = current_app.config.get('RTMP_SERVER', 'localhost')
            rtmp_port = 1935
            
            print(f"[DEBUG] Verificando servidor RTMP en {rtmp_server}:{rtmp_port}...")
            if not verificar_servidor_rtmp(rtmp_server, rtmp_port):
                error_msg = f'No se pudo conectar al servidor RTMP en {rtmp_server}:{rtmp_port}.'
                print(f"[ERROR] {error_msg}")
                print("[DEBUG] Verifica que el servidor RTMP esté en ejecución y accesible desde esta máquina.")
                print("[DEBUG] Intenta ejecutar manualmente: ffmpeg -re -i input.mp4 -c:v libx264 -preset veryfast -f flv rtmp://{rtmp_server}/live/prueba")
                
                return responder(request, {
                    'success': False,
                    'message': error_msg,
                    'canal_id': canal_id,
                    'en_transmision': False
                })
                
            # Crear directorio de listas de reproducción si no existe
            playlist_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'playlists')
            os.makedirs(playlist_dir, exist_ok=True)
            
            # Crear archivo de lista de reproducción
            playlist_file = os.path.join(playlist_dir, f'playlist_{canal.id}.txt')
            with open(playlist_file, 'w', encoding='utf-8') as f:
                for contenido in canal.contenidos:
                    ruta_contenido = os.path.join(current_app.config['UPLOAD_FOLDER'], contenido)
                    if os.path.isfile(ruta_contenido):
                        # Asegurar que la ruta esté correctamente escapada
                        ruta_escapada = ruta_contenido.replace("'", "'\\''")
                        f.write(f"file '{ruta_escapada}'\n")
                
                # Añadir una línea en blanco al final del archivo
                f.write("\n")
            
            # Verificar si hay archivos en la lista de reproducción
            if os.path.getsize(playlist_file) == 0:
                error_msg = 'No se encontraron archivos válidos para reproducir.'
                print(error_msg)
                return responder(request, {
                    'success': False,
                    'message': error_msg,
                    'canal_id': canal_id,
                    'en_transmision': False
                })
            
            # Configurar la URL de transmisión RTMP
            nombre_stream = canal.nombre.replace(' ', '_').lower()
            rtmp_port = 1935  # Puerto RTMP estándar
            rtmp_server = current_app.config.get('RTMP_SERVER', 'localhost')
            
            # Limpiar la URL para asegurar que no tenga protocolo ni barras al final
            rtmp_server = rtmp_server.replace('rtmp://', '').replace('http://', '').replace('https://', '').rstrip('/')
            
            # Construir la URL RTMP correctamente formada
            rtmp_url = f'rtmp://{rtmp_server}:{rtmp_port}/live/{nombre_stream}'
            
            print(f"Iniciando transmisión en: {rtmp_url}")
            print(f"Asegúrate de que el servidor RTMP en {rtmp_server} esté en ejecución y accesible")
            
            # Configurar filtros de video (incluyendo rotación)
            filter_complex = []
            
            # Unir todos los filtros con comas
            vf = ','.join(filter_complex) if filter_complex else ''
            
            # Construir comando FFmpeg con parámetros optimizados
            ffmpeg_cmd = ['ffmpeg']
            
            # Opciones de entrada
            ffmpeg_cmd.extend([
                '-re',  # Leer entrada a velocidad nativa
                '-stream_loop', '-1' if canal.repeticion == 'bucle' else '0',  # Bucle infinito si está habilitado
                '-f', 'concat',  # Usar concatenación
                '-safe', '0',  # Permitir rutas absolutas en la lista
                '-i', playlist_file  # Archivo de lista de reproducción
            ])
            
            # Configuración de video
            video_filters = []
            
            # Aplicar rotación según la configuración del canal
            if hasattr(canal, 'rotacion') and canal.rotacion is not None:
                if canal.rotacion == 90:
                    video_filters.append('transpose=1')  # 90° horario
                elif canal.rotacion == 180:
                    video_filters.append('transpose=2,transpose=2')  # 180°
                elif canal.rotacion == 270:
                    video_filters.append('transpose=2')  # 90° antihorario
            
            # Añadir filtros de video si existen
            if video_filters:
                ffmpeg_cmd.extend(['-vf', ','.join(video_filters)])
            
            # Configuración de codificación optimizada
            ffmpeg_cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'veryfast',  # Balance entre velocidad y calidad
                '-tune', 'zerolatency',  # Optimización para streaming en tiempo real
                '-b:v', '3000k',  # Bitrate de video
                '-maxrate', '3000k',  # Bitrate máximo
                '-bufsize', '6000k',  # Tamaño del buffer (2x el bitrate)
                '-g', '60',  # Keyframe cada 2 segundos (a 30fps)
                '-keyint_min', '60',  # Mínimo de frames entre keyframes
                '-sc_threshold', '0',  # Deshabilitar detección de escenas
                '-pix_fmt', 'yuv420p',  # Formato de píxel compatible
                '-c:a', 'aac',  # Códec de audio
                '-b:a', '128k',  # Bitrate de audio
                '-ar', '44100',  # Frecuencia de muestreo de audio
                '-ac', '2',  # Audio estéreo
                '-f', 'flv',  # Formato de salida
                rtmp_url
            ])
            
            # Mostrar el comando completo para depuración
            print("Comando FFmpeg:", ' '.join(ffmpeg_cmd))
            
            # Crear directorio de logs si no existe
            log_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            # Archivos de log para stdout y stderr
            log_file = os.path.join(log_dir, f'ffmpeg_{canal_id}.log')
            error_file = os.path.join(log_dir, f'ffmpeg_{canal_id}_error.log')
            
            # Iniciar el proceso FFmpeg con manejo adecuado de procesos
            proceso = None
            pgid = None
            
            try:
                # Abrir archivos de log
                f_log = open(log_file, 'a')
                f_err = open(error_file, 'a')
                
                try:
                    # Configuración para el proceso
                    process_args = {
                        'stdin': subprocess.DEVNULL,  # No necesitamos stdin
                        'stdout': f_log,
                        'stderr': f_err,
                        'start_new_session': True,
                        'close_fds': True,  # Cerrar todos los descriptores de archivo heredados
                        'bufsize': 0,  # Sin buffer
                    }
                    
                    # Iniciar el proceso FFmpeg
                    try:
                        # Primero intentamos con preexec_fn si está disponible
                        try:
                            process_args['preexec_fn'] = os.setsid
                            proceso = subprocess.Popen(ffmpeg_cmd, **process_args)
                            print("Proceso FFmpeg iniciado con nuevo grupo de sesión")
                        except Exception as e:
                            print(f"No se pudo crear nuevo grupo de sesión: {e}")
                            print("Intentando sin preexec_fn...")
                            if 'preexec_fn' in process_args:
                                del process_args['preexec_fn']
                            proceso = subprocess.Popen(ffmpeg_cmd, **process_args)
                            print("Proceso FFmpeg iniciado sin nuevo grupo de sesión")
                        
                        # Pequeña pausa para permitir que FFmpeg inicie
                        time.sleep(1)
                        
                        # Verificar si el proceso sigue activo
                        if proceso.poll() is not None:
                            # Leer el error si hay alguno
                            f_err.flush()
                            with open(error_file, 'r') as f:
                                error_output = f.read()
                            raise Exception(f"El proceso FFmpeg terminó inesperadamente con código {proceso.returncode}. Error: {error_output[-1000:]}")
                            
                        # Obtener el ID del grupo de procesos si es posible
                        try:
                            pgid = os.getpgid(proceso.pid)
                            print(f"Proceso FFmpeg iniciado con PID: {proceso.pid}, PGID: {pgid}")
                        except Exception as e:
                            print(f"No se pudo obtener el PGID del proceso: {e}")
                            pgid = None
                        
                        # Guardar información del proceso
                        canal.proceso_ffmpeg = {
                            'pid': proceso.pid,
                            'pgid': pgid,  # Puede ser None si no se pudo obtener
                            'inicio': datetime.now().isoformat(),
                            'comando': ' '.join(ffmpeg_cmd)
                        }
                            
                    except Exception as e:
                        error_msg = f'Error al iniciar FFmpeg: {str(e)}'
                        print(error_msg)
                        if proceso and proceso.poll() is None:
                            try:
                                proceso.terminate()
                                proceso.wait(timeout=5)
                            except:
                                pass
                        raise Exception(error_msg)
                        
                finally:
                    # Cerrar archivos de log
                    f_log.flush()
                    f_err.flush()
                    f_log.close()
                    f_err.close()
                    
            except Exception as e:
                error_msg = f'Error al configurar el proceso FFmpeg: {str(e)}'
                print(error_msg)
                raise Exception(error_msg)
                
            except Exception as e:
                error_msg = f'Error al iniciar FFmpeg: {str(e)}'
                print(error_msg)
                raise Exception(error_msg)
            

            canal.en_transmision = True
            canal.ultima_transmision = datetime.now()
            Canal.guardar(canal)
            
            # Actualizar la lista M3U
            actualizar_m3u()
            
            print(f"Transmisión iniciada para el canal {canal.nombre} (PID: {proceso.pid})")
            
            return responder(request, {
                'success': True,
                'message': 'Transmisión iniciada correctamente',
                'canal_id': canal_id,
                'en_transmision': True,
                'rtmp_url': rtmp_url,
                'hls_url': f'http://{rtmp_server}:8000/hls/{nombre_stream}.m3u8',
                'dash_url': f'http://{rtmp_server}:8000/dash/{nombre_stream}.mpd'
            })
            
        except Exception as e:
            error_msg = f'Error al iniciar la transmisión: {str(e)}'
            print(error_msg)
            
            # Asegurarse de que el estado del canal sea consistente
            try:
                canal.en_transmision = False
                canal.proceso_ffmpeg = None
                Canal.guardar(canal)
            except:
                pass
            
            return responder(request, {
                'success': False,
                'message': error_msg,
                'canal_id': canal_id,
                'en_transmision': False
            })
    # Función auxiliar para responder a las peticiones
    def responder(request, data):
        if request.is_json:
            return jsonify(data)
        
        if data.get('success', False):
            flash(data['message'], 'success')
        else:
            flash(data['message'], 'error')
        
        return redirect(url_for('main.gestion_canales'))
    
    # Función para obtener PIDs de procesos hijos
    def get_child_pids(pid):
        """Obtiene todos los PIDs de los procesos hijos de un proceso dado."""
        try:
            # Usar ps para obtener todos los procesos hijos recursivamente
            result = subprocess.run(
                ['pstree', '-p', str(pid)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Extraer todos los PIDs del árbol de procesos
                import re
                pids = re.findall(r'\((\d+)\)', result.stdout)
                # Convertir a enteros, eliminar duplicados y el PID principal
                pids = list(set(int(p) for p in pids if p.isdigit()))
                if pid in pids:
                    pids.remove(pid)
                return pids
        except Exception as e:
            print(f"Error al obtener procesos hijos: {e}")
        return []
    
    # Función para detener un proceso y sus hijos
    def stop_ffmpeg_process(pid, canal_id):
        """Detiene un proceso FFmpeg y su grupo de procesos de manera segura."""
        try:
            # Obtener el grupo de procesos
            try:
                pgid = os.getpgid(pid)
                print(f"Deteniendo grupo de procesos {pgid} (proceso principal: {pid})")
                
                # Enviar señal SIGTERM a todo el grupo
                os.killpg(pgid, signal.SIGTERM)
                
                # Esperar un tiempo razonable para que los procesos terminen
                time.sleep(1)
                
                # Verificar si algún proceso del grupo sigue en ejecución
                try:
                    os.killpg(pgid, 0)  # Verifica si el grupo aún existe
                    print(f"Algunos procesos del grupo {pgid} no terminaron, forzando terminación...")
                    os.killpg(pgid, signal.SIGKILL)
                    time.sleep(0.5)
                except (OSError, ProcessLookupError):
                    pass
                    
            except (OSError, ProcessLookupError) as e:
                print(f"Error al detener el grupo de procesos: {e}")
                # Intentar detener solo el proceso principal si falla el grupo
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.5)
                    try:
                        os.kill(pid, 0)
                        os.kill(pid, signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        pass
                except (OSError, ProcessLookupError) as e:
                    print(f"Error al detener el proceso {pid}: {e}")
                    return False
            
            # Actualizar el estado del canal
            try:
                canal = Canal.obtener_por_id(canal_id)
                if canal:
                    canal.en_transmision = False
                    canal.proceso_ffmpeg = None
                    canal.ultima_transmision = datetime.now()
                    Canal.guardar(canal)
                    
                    # Actualizar la lista M3U
                    actualizar_m3u()
                    
                    print(f"Transmisión detenida para el canal {canal.nombre}")
                
                return True
                
            except Exception as e:
                print(f"Error al actualizar el estado del canal: {e}")
                return False
                
        except Exception as e:
            print(f"Error inesperado al detener el proceso: {e}")
            return False
            
    # Si no está en transmisión, iniciarla
    try:
        # Verificar si el archivo de origen existe
        if not os.path.isfile(canal.archivo_origen):
            error_msg = f'El archivo de origen no existe: {canal.archivo_origen}'
            print(error_msg)
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': error_msg,
                    'canal_id': canal_id,
                    'en_transmision': False
                }), 400
            
            flash(error_msg, 'error')
            return redirect(url_for('main.gestion_canales'))
        
        # Configurar la URL de transmisión RTMP
        nombre_stream = f"{canal.id}_{canal.nombre.replace(' ', '_').lower()}"
        rtmp_port = 1935  # Puerto RTMP estándar
        rtmp_server = current_app.config.get('RTMP_SERVER', 'localhost')
        
        # Limpiar la URL para asegurar que no tenga protocolo ni barras al final
        rtmp_server = rtmp_server.replace('rtmp://', '').replace('http://', '').replace('https://', '').rstrip('/')
        
        # Construir la URL RTMP correctamente formada
        rtmp_url = f'rtmp://{rtmp_server}:{rtmp_port}/live/{nombre_stream}'
        
        print(f"Iniciando transmisión en: {rtmp_url}")
        print(f"Asegúrate de que el servidor RTMP en {rtmp_server} esté en ejecución y accesible")
        
        # Construir el comando base de FFmpeg
        ffmpeg_cmd = [
            'ffmpeg',
            '-loglevel', 'debug',  # Habilitar logs detallados
            '-re',  # Leer entrada a velocidad nativa
            '-i', canal.archivo_origen  # Archivo de entrada
        ]
        
        # Configurar filtros de video (incluyendo rotación)
        vf_filters = []
        
        # Aplicar rotación según la configuración del canal
        if hasattr(canal, 'rotacion') and canal.rotacion is not None:
            if canal.rotacion == 90:
                vf_filters.append('transpose=1')  # 90° horario
            elif canal.rotacion == 180:
                vf_filters.append('transpose=2,transpose=2')  # 180° (volteado vertical y horizontal)
            elif canal.rotacion == 270:
                vf_filters.append('transpose=2')  # 90° antihorario
        
        # Añadir filtros de video si existen
        if vf_filters:
            ffmpeg_cmd.extend(['-vf', ','.join(vf_filters)])
            print(f"Aplicando filtros de video: {','.join(vf_filters)}")
        else:
            print("No se aplicaron filtros de video")
        
        # Añadir parámetros de codificación
        ffmpeg_cmd.extend([
            '-c:v', 'libx264',  # Códec de video
            '-preset', 'veryfast',  # Velocidad de codificación
            '-tune', 'zerolatency',  # Optimización para streaming
            '-c:a', 'aac',  # Códec de audio
            '-ar', '44100',  # Frecuencia de muestreo de audio
            '-b:a', '128k',  # Tasa de bits de audio
            '-f', 'flv',  # Formato de salida
            rtmp_url  # URL de destino RTMP
        ])
        
        try:
            # Iniciar el proceso FFmpeg
            proceso = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # Guardar información del proceso
            canal.proceso_ffmpeg = {
                'pid': proceso.pid,
                'inicio': datetime.now().isoformat(),
                'comando': ' '.join(ffmpeg_cmd)
            }
            canal.en_transmision = True
            canal.ultima_transmision = datetime.now()
            Canal.guardar(canal)
            
            # Actualizar la lista M3U
            actualizar_m3u()
            
            print(f"Transmisión iniciada para el canal {canal.nombre} (PID: {proceso.pid})")
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': 'Transmisión iniciada correctamente',
                    'canal_id': canal_id,
                    'en_transmision': True,
                    'rtmp_url': rtmp_url,
                    'hls_url': f'http://{rtmp_server}:8000/hls/{nombre_stream}.m3u8',
                    'dash_url': f'http://{rtmp_server}:8000/dash/{nombre_stream}.mpd'
                })
            
            flash('Transmisión iniciada correctamente', 'success')
            return redirect(url_for('main.gestion_canales'))
            
        except Exception as e:
            error_msg = f'Error al iniciar FFmpeg: {str(e)}'
            print(error_msg)
            
            canal.en_transmision = False
            canal.proceso_ffmpeg = None
            Canal.guardar(canal)
            
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': error_msg,
                    'canal_id': canal_id,
                    'en_transmision': False
                }), 500
            
            flash(error_msg, 'error')
            return redirect(url_for('main.gestion_canales'))
            
    except Exception as e:
        error_msg = f'Error al iniciar la transmisión: {str(e)}'
        print(error_msg)
        
        if request.is_json:
            return jsonify({
                'success': False,
                'message': error_msg,
                'canal_id': canal_id,
                'en_transmision': canal.en_transmision
            }), 500
        
        flash(error_msg, 'error')
        return redirect(url_for('main.gestion_canals'))
    
    # Si no está en transmisión, iniciarla
    print("El canal no está en transmisión. Preparando para iniciar...")
    try:
        # Verificar si hay un proceso FFmpeg activo
        if canal.proceso_ffmpeg and isinstance(canal.proceso_ffmpeg, dict) and 'pid' in canal.proceso_ffmpeg:
            print("Advertencia: Se encontró un proceso FFmpeg activo pero el canal no estaba marcado como en transmisión")
            # Limpiar el proceso FFmpeg
            canal.proceso_ffmpeg = None
            Canal.guardar(canal)
        
        # Verificar que el canal tenga contenido
        if not canal.contenidos:
            flash('El canal no tiene contenido para transmitir', 'error')
            return redirect(url_for('main.gestion_canales'))
        
        # Crear directorio de playlists si no existe
        playlists_dir = os.path.join(current_app.root_path, 'playlists')
        try:
            os.makedirs(playlists_dir, exist_ok=True)
            print(f"Directorio de playlists creado/verificado en: {playlists_dir}")
        except Exception as e:
            error_msg = f'Error al crear directorio de playlists: {str(e)}'
            print(error_msg)
            flash(error_msg, 'error')
            return redirect(url_for('main.gestion_canales'))
            
        # Crear archivo de playlist
        playlist_path = os.path.join(playlists_dir, f'playlist_{canal.id}.txt')
        print(f"\n=== Creando playlist en: {playlist_path} ===")
        print(f"Contenidos del canal a incluir: {canal.contenidos}")
        
        try:
            with open(playlist_path, 'w') as f:
                for nombre_archivo in canal.contenidos:
                    # Construir la ruta completa al archivo
                    ruta_archivo = os.path.join(UPLOAD_FOLDER, nombre_archivo)
                    
                    # Verificar que el archivo existe y es legible
                    if not os.path.exists(ruta_archivo):
                        error_msg = f'Error: No se encontró el archivo {ruta_archivo} en {os.path.abspath(UPLOAD_FOLDER)}. Archivos disponibles: {os.listdir(UPLOAD_FOLDER) if os.path.exists(UPLOAD_FOLDER) else "Directorio no existe"}'
                        print(error_msg)
                        flash(error_msg, 'error')
                        return redirect(url_for('main.gestion_canales'))
                    elif not os.path.isfile(ruta_archivo):
                        error_msg = f'Error: {ruta_archivo} no es un archivo válido'
                        print(error_msg)
                        flash(error_msg, 'error')
                        return redirect(url_for('main.gestion_canales'))
                    elif not os.access(ruta_archivo, os.R_OK):
                        error_msg = f'Error: No se tienen permisos de lectura para {ruta_archivo}. Permisos: {oct(os.stat(ruta_archivo).st_mode)[-3:]}'
                        print(error_msg)
                        flash(error_msg, 'error')
                        return redirect(url_for('main.gestion_canales'))
                    
                    # Escribir la ruta en formato compatible con FFmpeg
                    ruta_escapada = ruta_archivo.replace("'", "'\\''")  # Escapar comillas simples
                    f.write(f"file '{ruta_escapada}'\n")
                    print(f"Archivo agregado a la playlist: {ruta_archivo}")
            
            print(f"Playlist creada exitosamente en {playlist_path}")
            
        except Exception as e:
            error_msg = f'Error al crear el archivo de playlist: {str(e)}'
            print(error_msg)
            flash(error_msg, 'error')
            return redirect(url_for('main.gestion_canales'))
        
        # Configurar la URL de transmisión RTMP
        nombre_stream = f"{canal.id}_{canal.nombre.replace(' ', '_').lower()}"
        rtmp_port = 1935  # Puerto RTMP estándar (cambiado de 1936 a 1935)
        # Obtener la dirección IP del servidor RTMP desde la configuración o usar localhost por defecto
        rtmp_server = current_app.config.get('RTMP_SERVER', 'localhost')
        
        # Limpiar la URL para asegurar que no tenga protocolo ni barras al final
        rtmp_server = rtmp_server.replace('rtmp://', '').replace('http://', '').replace('https://', '').rstrip('/')
        
        # Asegurarse de que el nombre del stream sea seguro para URL
        nombre_stream = f"{canal.id}_{canal.nombre}".replace(' ', '_').lower()
        
        # Construir la URL RTMP correctamente formada
        rtmp_url = f'rtmp://{rtmp_server}:{rtmp_port}/stream/{nombre_stream}'
        
        print(f"Iniciando transmisión en: {rtmp_url}")
        print(f"Asegúrate de que el servidor RTMP en {rtmp_server} esté en ejecución y accesible")
        
        # Verificar si el servidor RTMP está accesible
        def verificar_conexion_rtmp(host, port, timeout=5):
            import socket
            try:
                socket.setdefaulttimeout(timeout)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((host, port))
                s.close()
                return True
            except (socket.error, socket.timeout) as e:
                print(f"Error de conexión con {host}:{port} - {str(e)}")
                return False
        
        if not verificar_conexion_rtmp(rtmp_server, rtmp_port):
            error_msg = f"No se puede conectar al servidor RTMP en {rtmp_server}:{rtmp_port}. " \
                       f"Verifica que el servidor esté en ejecución y que el firewall permita conexiones en ese puerto."
            print(error_msg)
            flash(error_msg, 'error')
            return redirect(url_for('main.gestion_canales'))
        
        # Configurar archivos de log
        logs_dir = os.path.join(current_app.root_path, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(logs_dir, f'ffmpeg_{canal.id}_{timestamp}.log')
        err_file = os.path.join(logs_dir, f'ffmpeg_{canal.id}_{timestamp}.err')
        
        # Función para obtener procesos hijos de un proceso
        def get_child_pids(pid):
            """Obtiene todos los PIDs de los procesos hijos de un proceso dado."""
            try:
                # Usar pstree para obtener todos los procesos hijos recursivamente
                result = subprocess.run(
                    ['pstree', '-p', str(pid)],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    # Extraer todos los PIDs del árbol de procesos
                    import re
                    pids = re.findall(r'\((\d+)\)', result.stdout)
                    # Convertir a enteros, eliminar duplicados y el PID principal
                    pids = list(set(int(p) for p in pids if p.isdigit()))
                    if pid in pids:
                        pids.remove(pid)
                    return pids
                return []
            except Exception as e:
                print(f"Error al obtener procesos hijos: {e}")
                return []
                
        # Continuar con la lógica de transmisión
        print(f"Configuración de logs en {log_file} y {err_file}")
        
        # Verificar si hay un proceso FFmpeg previo que necesite ser detenido
        if canal.proceso_ffmpeg and isinstance(canal.proceso_ffmpeg, dict) and 'pid' in canal.proceso_ffmpeg:
            pid = canal.proceso_ffmpeg['pid']
            pgid = canal.proceso_ffmpeg.get('pgid')
            print(f"Deteniendo proceso FFmpeg previo con PID: {pid}, PGID: {pgid}")
            
            try:
                # Si tenemos el PGID, usarlo para terminar todo el grupo de procesos
                if pgid:
                    print(f"Enviando SIGTERM al grupo de procesos {pgid}")
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                        time.sleep(2)  # Esperar a que los procesos terminen
                        
                        # Verificar si el proceso principal aún está corriendo
                        try:
                            os.kill(pid, 0)  # Solo verifica si el proceso existe
                            print(f"El proceso {pid} no respondió a SIGTERM, forzando con SIGKILL")
                            os.killpg(pgid, signal.SIGKILL)
                        except ProcessLookupError:
                            print(f"El proceso {pid} ha terminado correctamente")
                    except ProcessLookupError as e:
                        print(f"Error al enviar señal al grupo {pgid}: {e}")
                
                # Método de respaldo si no tenemos PGID o si falla el método anterior
                try:
                    # Obtener y terminar procesos hijos
                    child_pids = get_child_pids(pid)
                    for child_pid in child_pids:
                        try:
                            os.kill(child_pid, signal.SIGTERM)
                            print(f"Señal SIGTERM enviada al proceso hijo {child_pid}")
                        except (ProcessLookupError, PermissionError) as e:
                            print(f"No se pudo enviar SIGTERM al proceso hijo {child_pid}: {e}")
                    
                    time.sleep(1)  # Esperar a que los procesos hijos terminen
                    
                    # Intentar terminar el proceso principal
                    try:
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(1)  # Esperar a que el proceso termine
                        
                        # Verificar si el proceso sigue activo
                        try:
                            os.kill(pid, 0)
                            print(f"Forzando terminación del proceso {pid} con SIGKILL")
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                            
                    except ProcessLookupError:
                        print(f"El proceso {pid} ya no existe")
                    
                    try:
                        # Limpiar el proceso FFmpeg
                        canal.proceso_ffmpeg = None
                        canal.en_transmision = False
                    except Exception as e:
                        print(f"Error al limpiar el proceso FFmpeg: {e}")
                    
                except Exception as e:
                    print(f"Error al detener los procesos hijos: {e}")
                    
            except Exception as e:
                print(f"Error al detener el proceso FFmpeg: {e}")
            
            # Construir el comando FFmpeg base
            cmd = [
                'ffmpeg',
                '-loglevel', 'debug',
                '-re',
                '-stream_loop', '-1' if canal.repeticion == 'bucle' else '0',
                '-f', 'concat',
                '-safe', '0',
                '-i', playlist_path
            ]
            
            # Configurar filtros de video (incluyendo rotación)
            vf_filters = []
            
            # Aplicar rotación según la configuración del canal
            if hasattr(canal, 'rotacion') and canal.rotacion is not None:
                if canal.rotacion == 90:
                    vf_filters.append('transpose=1')  # 90° horario
                elif canal.rotacion == 180:
                    vf_filters.append('transpose=2,transpose=2')  # 180° (volteado vertical y horizontal)
                elif canal.rotacion == 270:
                    vf_filters.append('transpose=2')  # 90° antihorario
            
            # Añadir filtros de video si existen
            if vf_filters:
                cmd.extend(['-vf', ','.join(vf_filters)])
                print(f"Aplicando filtros de video: {','.join(vf_filters)}")
            else:
                print("No se aplicaron filtros de video")
            
            # Añadir parámetros de codificación
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-tune', 'zerolatency',
                '-profile:v', 'high',
                '-level', '4.2',
                '-x264opts', 'keyint=60:min-keyint=30:no-scenecut',
                '-b:v', '2500k',
                '-maxrate', '3000k',
                '-bufsize', '5000k',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-ar', '44100',
                '-ac', '2',
                '-f', 'flv',
                '-flvflags', 'no_duration_filesize',
                rtmp_url
            ])
            
            print(f"Iniciando transmisión con comando: {' '.join(cmd)}")
            
            try:
                # Iniciar el proceso FFmpeg
                with open(log_file, 'w') as log_f, open(err_file, 'w') as err_f:
                    process = subprocess.Popen(
                        cmd,
                        stdout=log_f,
                        stderr=err_f
                    )
                    
                    # Configurar manejo de señales simple sin verificación de hilo
                    def handle_signal(signum, frame):
                        if process.poll() is None:  # Si el proceso aún está corriendo
                            try:
                                # Intentar terminar el proceso de manera ordenada
                                process.terminate()
                                try:
                                    process.wait(timeout=5)  # Esperar hasta 5 segundos
                                except subprocess.TimeoutExpired:
                                    # Si no responde, forzar terminación
                                    process.kill()
                            except Exception as e:
                                print(f"Error al manejar la señal {signum}: {e}")
                    
                    # Registrar manejador de señales de forma segura
                    try:
                        signal.signal(signal.SIGTERM, handle_signal)
                        signal.signal(signal.SIGINT, handle_signal)
                    except (ValueError, AttributeError) as e:
                        print(f"No se pudo configurar el manejador de señales: {e}")
                    
                    # Guardar información del proceso
                    proceso_info = {
                        'pid': process.pid,
                        'start_time': datetime.now().isoformat(),
                        'rtmp_url': rtmp_url,
                        'log_file': log_file,
                        'err_file': err_file
                    }
                    
                    # Solo intentar obtener el PGID en sistemas que lo soporten
                    try:
                        if hasattr(os, 'getpgid'):
                            proceso_info['pgid'] = os.getpgid(process.pid)
                    except Exception as e:
                        print(f"No se pudo obtener el PGID: {e}")
                    
                    canal.proceso_ffmpeg = proceso_info
                    canal.en_transmision = True
                    Canal.guardar(canal)
                    
                    # Iniciar un hilo para monitorear el proceso
                    def monitor_process(proc, pid, log_path):
                        proc.wait()
                        print(f"Proceso FFmpeg {pid} terminado con código {proc.returncode}")
                        # Leer los logs para depuración
                        try:
                            with open(log_path, 'r') as f:
                                logs = f.read()
                                print(f"Últimas líneas del log ({pid}): {logs[-500:]}")
                        except Exception as e:
                            print(f"No se pudo leer el log del proceso {pid}: {e}")
                    
                    import threading
                    monitor_thread = threading.Thread(
                        target=monitor_process,
                        args=(process, process.pid, err_file),
                        daemon=True
                    )
                    monitor_thread.start()
                    
                    print(f"Transmisión iniciada con PID {process.pid} (PGID: {os.getpgid(process.pid) if hasattr(os, 'getpgid') else 'N/A'})")
                    flash('Transmisión iniciada correctamente', 'success')
            
            except Exception as e:
                error_msg = f'Error al iniciar la transmisión: {str(e)}'
                print(error_msg)
                flash(error_msg, 'error')
                canal.en_transmision = False
                canal.proceso_ffmpeg = None
                Canal.guardar(canal)
                return redirect(url_for('main.gestion_canales'))
         
        return redirect(url_for('main.gestion_canales'))
        
    except Exception as e:
        error_msg = f'Error en la transmisión: {str(e)}'
        print(error_msg)
        flash(error_msg, 'error')
        return redirect(url_for('main.gestion_canales'))
        try:
            os.makedirs(playlists_dir, exist_ok=True)
            print(f"Directorio de playlists creado/verificado en: {playlists_dir}")
            print(f"Permisos del directorio: {oct(os.stat(playlists_dir).st_mode)[-3:]}")
        except Exception as e:
            error_msg = f'Error al crear directorio de playlists: {str(e)}'
            print(error_msg)
            return jsonify({
                'success': False,
                'message': error_msg,
                'action': 'error'
            }), 500
        
        # Crear archivo de playlist
        playlist_path = os.path.join(playlists_dir, f'playlist_{canal.id}.txt')
        print(f"\n=== Creando playlist en: {playlist_path} ===")
        print(f"Contenidos del canal a incluir: {canal.contenidos}")
        
        try:
            with open(playlist_path, 'w') as f:
                if not canal.contenidos:
                    error_msg = 'El canal no tiene contenido para transmitir.'
                    print(error_msg)
                    session['error_message'] = error_msg
                    return redirect(url_for('main.gestion_canales'))
                    
                print(f"Contenidos del canal: {canal.contenidos}")
                
                for nombre_archivo in canal.contenidos:
                    try:
                        # Construir la ruta completa al archivo
                        ruta_archivo = os.path.join(UPLOAD_FOLDER, nombre_archivo)
                        print(f"\nVerificando archivo: {ruta_archivo}")
                        print(f"¿Existe el archivo? {'Sí' if os.path.exists(ruta_archivo) else 'No'}")
                        if os.path.exists(ruta_archivo):
                            print(f"Permisos del archivo: {oct(os.stat(ruta_archivo).st_mode)[-3:]}")
                            print(f"Tamaño del archivo: {os.path.getsize(ruta_archivo)} bytes")
                            
                        # Verificar que el archivo existe y es legible
                        if not os.path.exists(ruta_archivo):
                            error_msg = f'Error: No se encontró el archivo {ruta_archivo} en {os.path.abspath(UPLOAD_FOLDER)}. Archivos disponibles: {os.listdir(UPLOAD_FOLDER) if os.path.exists(UPLOAD_FOLDER) else "Directorio no existe"}'
                        elif not os.path.isfile(ruta_archivo):
                            error_msg = f'Error: {ruta_archivo} no es un archivo válido'
                        elif not os.access(ruta_archivo, os.R_OK):
                            error_msg = f'Error: No se tienen permisos de lectura para {ruta_archivo}. Permisos: {oct(os.stat(ruta_archivo).st_mode)[-3:]}'
                        else:
                            error_msg = None
                        
                        if error_msg:
                            print(error_msg)
                            session['error_message'] = error_msg
                            return redirect(url_for('main.gestion_canales'))
                            
                        # Escribir la ruta en formato compatible con FFmpeg
                        ruta_escapada = ruta_archivo.replace("'", "'\\''")  # Escapar comillas simples
                        f.write(f"file '{ruta_escapada}'\n")
                        print(f"Archivo agregado a la playlist: {ruta_archivo}")
                            
                    except Exception as e:
                        error_msg = f'Error al verificar el archivo {nombre_archivo}: {str(e)}'
                        print(error_msg)
                        session['error_message'] = error_msg
                        return redirect(url_for('main.gestion_canales'))
                        
            print(f"Playlist creada exitosamente en {playlist_path}")
            
        except Exception as e:
            error_msg = f'Error al crear el archivo de playlist: {str(e)}'
            print(error_msg)
            session['error_message'] = error_msg
            return redirect(url_for('main.gestion_canales'))
        
        # Construir comando FFmpeg con puerto único basado en el ID del canal
        nombre_stream = f"{canal.id}_{canal.nombre.replace(' ', '_').lower()}"
        # Usar un puerto base (1935 por defecto) + el ID del canal para asegurar unicidad
        # Todos los canales usan el mismo puerto pero con diferentes nombres de stream
        rtmp_port = 1936  # Puerto fijo para todos los canales
        rtmp_url = f'rtmp://localhost:{rtmp_port}/stream/{nombre_stream}'
        print(f"Iniciando transmisión en: {rtmp_url}")
        
        # Verificar que el archivo de playlist existe y tiene contenido
        if not os.path.exists(playlist_path):
            error_msg = f'Error: No se pudo crear el archivo de playlist en {playlist_path}'
            print(error_msg)
            flash(error_msg, 'error')
            return redirect(url_for('main.gestion_canales'))
        
        # Leer el contenido del archivo de playlist para depuración
        try:
            with open(playlist_path, 'r') as f:
                playlist_content = f.read()
                print(f"Contenido de la playlist:\n{playlist_content}")
                if not playlist_content.strip():
                    error_msg = 'Error: La lista de reproducción está vacía'
                    print(error_msg)
                    flash(error_msg, 'error')
                    return redirect(url_for('main.gestion_canales'))
        except Exception as e:
            error_msg = f'Error al leer el archivo de playlist: {str(e)}'
            print(error_msg)
            flash(error_msg, 'error')
            return redirect(url_for('main.gestion_canales'))
            
        # Verificar que el directorio multimedia existe y es accesible
        if not os.path.exists(UPLOAD_FOLDER):
            error_msg = f'Error: El directorio de multimedia no existe: {UPLOAD_FOLDER}'
            print(error_msg)
            flash(error_msg, 'error')
            return redirect(url_for('main.gestion_canales'))
            
        if not os.access(UPLOAD_FOLDER, os.R_OK):
            error_msg = f'Error: No se tienen permisos de lectura en el directorio de multimedia: {UPLOAD_FOLDER}'
            print(error_msg)
            flash(error_msg, 'error')
            return redirect(url_for('main.gestion_canales'))
        
        # Configuración básica de FFmpeg para RTMP
        try:
            # Verificar si FFmpeg está instalado
            print("Verificando instalación de FFmpeg...")
            result = subprocess.run(
                ['which', 'ffmpeg'], 
                capture_output=True, 
                text=True
            )
            print(f"Resultado de 'which ffmpeg': {result.stdout.strip()}")
            
            # Verificar la versión de FFmpeg
            version_result = subprocess.run(
                ['ffmpeg', '-version'], 
                capture_output=True, 
                text=True
            )
            # Obtener la primera línea de la salida de forma segura
            version_line = version_result.stdout.splitlines()[0] if version_result.stdout else 'No disponible'
            print(f"Versión de FFmpeg: {version_line}")
            
            if version_result.returncode != 0:
                raise subprocess.CalledProcessError(
                    version_result.returncode, 
                    'ffmpeg -version',
                    version_result.stderr
                )
                
            ffmpeg_available = True
            print("FFmpeg está correctamente instalado y accesible")
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            ffmpeg_available = False
            error_msg = 'Error: FFmpeg no está instalado o no está en el PATH del sistema.'
            print(error_msg)
            if hasattr(e, 'stderr') and e.stderr:
                print(f"Error de FFmpeg: {e.stderr}")
            flash(error_msg, 'error')
            return redirect(url_for('main.gestion_canales'))
        
        # Configurar archivos de log con identificadores únicos
        logs_dir = os.path.join(current_app.root_path, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(logs_dir, f'ffmpeg_{canal.id}_{timestamp}.log')
        err_file = os.path.join(logs_dir, f'ffmpeg_{canal.id}_{timestamp}.err')
        
        # Verificar permisos de escritura en el directorio de logs
        try:
            with open(os.path.join(logs_dir, 'test_permissions'), 'w') as f:
                f.write('test')
            os.remove(os.path.join(logs_dir, 'test_permissions'))
        except Exception as e:
            error_msg = f'Error de permisos en el directorio de logs: {str(e)}'
            print(error_msg)
            flash(error_msg, 'error')
            return redirect(url_for('main.gestion_canales'))
        
        # Construir comando FFmpeg con más opciones de depuración
        # Usar un identificador único para cada instancia de FFmpeg
        stream_id = f"{canal.id}_{timestamp}"
        
        # Construir el filtro de rotación si es necesario
        vf_filters = []
        if canal.rotacion == 90:
            vf_filters.append('transpose=1')  # 90° horario
        elif canal.rotacion == 180:
            vf_filters.append('transpose=2,transpose=2')  # 180° (volteado vertical y horizontal)
        elif canal.rotacion == 270:
            vf_filters.append('transpose=2')  # 90° antihorario
            
        cmd = [
            'ffmpeg',
            '-nostdin',  # Evitar problemas con la entrada estándar
            '-loglevel', 'debug',  # Nivel de log más detallado
            '-re',  # Leer entrada a velocidad nativa
            '-stream_loop', '-1' if canal.repeticion == 'bucle' else '0',
            '-thread_queue_size', '512',  # Aumentar el tamaño de la cola de hilos
            '-f', 'concat',
            '-safe', '0',
            '-protocol_whitelist', 'file,pipe',
            '-i', playlist_path
        ]
        
        # Añadir filtros de video si existen
        if vf_filters:
            cmd.extend(['-vf', ','.join(vf_filters)])
            
        # Añadir parámetros de codificación de video
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-pix_fmt', 'yuv420p',
            # Audio (asegurarse de que el audio esté presente)
            '-c:a', 'aac',
            '-ar', '44100',
            '-b:a', '128k',
            '-ac', '2',
            # Opciones de salida
            '-f', 'flv',
            '-flush_packets', '1',
            '-rtmp_buffer', '100',
            '-rtmp_live', 'live',
            rtmp_url
        ])
        
        # Imprimir el comando completo para depuración
        print("Comando FFmpeg:", ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd))
        
        # Imprimir información de depuración en los logs
        debug_info = [
            "=== INFORMACIÓN DE DEPURACIÓN ===",
            f"Directorio de trabajo actual: {os.getcwd()}",
            f"Ruta completa del archivo de playlist: {os.path.abspath(playlist_path)}",
            f"Contenido de la carpeta multimedia: {os.listdir(UPLOAD_FOLDER) if os.path.exists(UPLOAD_FOLDER) else 'No existe'}",
            "Contenido del archivo de playlist:",
        ]
        
        # Leer el contenido del archivo de playlist
        try:
            with open(playlist_path, 'r') as f:
                playlist_content = f.read()
                debug_info.append(playlist_content)
        except Exception as e:
            debug_info.append(f"Error al leer el archivo de playlist: {str(e)}")
        
        debug_info.extend([
            "================================",
            f"RTMP URL: {rtmp_url}",
            "================================"
        ])
        
        # Escribir la información de depuración en un archivo de log
        try:
            debug_log_path = os.path.join(current_app.root_path, 'debug.log')
            with open(debug_log_path, 'w') as f:
                f.write('\n'.join(debug_info))
        except Exception as e:
            print(f"No se pudo escribir el archivo de log de depuración: {str(e)}")
        
        # Imprimir solo información esencial en la consola
        print("=== INFORMACIÓN ESENCIAL ===")
        print(f"Iniciando transmisión para el canal: {canal.nombre}")
        print(f"RTMP: {rtmp_url}")
        print("===========================")
        
        # Configurar redirección de salida
        with open(log_file, 'w') as log, open(err_file, 'w') as err:
            log.write(f"Comando: {' '.join(cmd)}\n\n")
            log.write(f"Directorio de trabajo: {os.getcwd()}\n")
            log.write(f"Playlist path: {playlist_path}\n")
            log.write(f"Contenido de la playlist:\n{playlist_content}\n\n")
            log.flush()
            
            try:
                # Iniciar el proceso FFmpeg con más información de depuración
                print(f"Iniciando proceso FFmpeg con PID: {os.getpid()}")
                print(f"Archivo de log: {log_file}")
                print(f"Archivo de error: {err_file}")
                
                try:
                    # Imprimir el comando exacto que se va a ejecutar
                    print(f"Ejecutando comando: {' '.join(cmd)}")
                    
                    # Ejecutar FFmpeg con un timeout para detectar fallos tempranos
                    try:
                        # Primero probamos con un comando simple de FFmpeg para ver si funciona
                        test_cmd = ['ffmpeg', '-version']
                        test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=5)
                        print(f"Prueba de FFmpeg exitosa. Salida: {test_result.stdout[:100]}...")
                    except Exception as test_e:
                        print(f"Error en prueba de FFmpeg: {str(test_e)}")
                        if hasattr(test_e, 'stderr') and test_e.stderr:
                            print(f"Salida de error: {test_e.stderr}")
                    
                    # Crear el directorio de logs si no existe
                    os.makedirs(logs_dir, exist_ok=True)
                    
                    # Abrir los archivos de log en modo append para no perder información
                    with open(log_file, 'a') as log_f, open(err_file, 'a') as err_f:
                        log_f.write(f"\n\n=== Iniciando transmisión a las {datetime.now().isoformat()} ===\n")
                        log_f.write(f"Comando: {' '.join(cmd)}\n")
                        log_f.flush()
                        
                        # Ejecutar FFmpeg con Popen
                        proceso = subprocess.Popen(
                            cmd,
                            stdout=log_f,
                            stderr=err_f,
                            start_new_session=True,
                            text=True,
                            bufsize=1,
                            universal_newlines=True
                        )
                        
                        # Esperar un momento para ver si el proceso falla inmediatamente
                        import time
                        time.sleep(2)
                        
                        # Verificar si el proceso sigue en ejecución
                        if proceso.poll() is not None:
                            # El proceso terminó prematuramente
                            error_msg = f'Error al iniciar FFmpeg. Código de salida: {proceso.returncode}'
                            # Leer el contenido del archivo de error para más detalles
                            try:
                                with open(err_file, 'r') as f:
                                    error_details = f.read()
                                    error_msg += f'\nDetalles del error:\n{error_details}'
                            except Exception as e:
                                error_msg += f'\nNo se pudo leer el archivo de error: {str(e)}'
                            
                            print(error_msg)
                            flash(error_msg, 'error')
                            return redirect(url_for('main.gestion_canales'))
                        
                        # Almacenar información detallada del proceso
                        proceso_info = {
                            'pid': proceso.pid,
                            'rtmp_port': rtmp_port,
                            'rtmp_url': rtmp_url,
                            'start_time': datetime.now().isoformat(),
                            'log_file': log_file,
                            'err_file': err_file
                        }
                        
                        # Actualizar el estado del canal
                        canal.en_transmision = True
                        canal.proceso_ffmpeg = proceso_info  # Guardar toda la información del proceso
                        
                        try:
                            # Guardar el canal y actualizar el hash M3U
                            if Canal.guardar(canal):
                                m3u_hash = get_m3u_hash()
                                print(f"Estado del canal actualizado. Nuevo hash M3U: {m3u_hash}")
                            else:
                                print("Advertencia: No se pudo guardar el estado del canal")
                        except Exception as e:
                            print(f"Error al guardar el estado del canal: {str(e)}")
                        
                        print(f"Transmisión iniciada correctamente para el canal {canal.nombre} (PID: {proceso.pid})")
                        print(f"RTMP URL: {rtmp_url}")
                        print(f"Puerto RTMP: {rtmp_port}")
                        print(f"Archivos de log: {log_file}, {err_file}")
                        
                        flash('Transmisión iniciada correctamente', 'success')
                        return redirect(url_for('main.gestion_canales'))
                        
                except Exception as e:
                    error_msg = f"Error al iniciar FFmpeg: {str(e)}"
                    print(error_msg)
                    if hasattr(e, 'stderr') and e.stderr:
                        print(f"Salida de error: {e.stderr}")
                    log.write(f"ERROR: {error_msg}\n")
                    flash(f"Error al iniciar FFmpeg: {str(e)}", 'error')
                    return redirect(url_for('main.gestion_canales'))
                
                # Pequeña pausa para verificar si el proceso sigue vivo
                import time
                time.sleep(2)  # Esperar un poco más para asegurarnos
                
                # Verificar si el proceso sigue en ejecución
                if proceso.poll() is not None:
                    # El proceso ya terminó, leer el error
                    error_output = ""
                    try:
                        with open(err_file, 'r') as err_f:
                            error_output = err_f.read()
                    except Exception as e:
                        error_output = f"No se pudo leer el archivo de error: {str(e)}"
                    
                    # Registrar el error en el log
                    with open(log_file, 'a') as log_f:
                        log_f.write(f"FFmpeg terminó con código {proceso.returncode}. Error: {error_output}\n")
                    
                    # Mostrar un mensaje de error más detallado
                    error_msg = f'Error al iniciar FFmpeg. Código de salida: {proceso.returncode}'
                    print(error_msg)
                    print(f"Salida de error: {error_output}")
                    
                    # Intentar obtener más información sobre el error
                    if "No such file or directory" in error_output:
                        error_msg += "\nError: No se encontró un archivo o directorio. Verifica las rutas de los archivos multimedia."
                    elif "Permission denied" in error_output:
                        error_msg += "\nError: Permiso denegado. Verifica los permisos de los archivos y directorios."
                    elif "Invalid data found" in error_output:
                        error_msg += "\nError: Datos inválidos en el archivo de entrada. Verifica el formato de los archivos multimedia."
                    
                    flash(error_msg, 'error')
                    return redirect(url_for('main.gestion_canales'))
                
                # Este bloque de código es redundante y ya se manejó anteriormente
                # No es necesario actualizar el estado del canal nuevamente
                print("Advertencia: Se intentó actualizar el estado del canal dos veces")
                return redirect(url_for('main.gestion_canales'))
                
            except Exception as e:
                error_msg = f"Error al iniciar el proceso: {str(e)}"
                print(error_msg)
                log.write(f"{error_msg}\n")
                log.flush()
                flash(error_msg, 'error')
                return redirect(url_for('main.gestion_canales'))
            
            # Función para limpieza cuando el proceso termine
            def cleanup(pid):
                try:
                    canal_cleanup = Canal.obtener_por_id(canal_id)
                    if canal_cleanup and canal_cleanup.proceso_ffmpeg == pid:
                        canal_cleanup.en_transmision = False
                        canal_cleanup.proceso_ffmpeg = None
                        Canal.guardar(canal_cleanup)
                except Exception as e:
                    print(f"Error en limpieza: {e}")
            
            # Usar un hilo para esperar el proceso sin bloquear
            try:
                import threading
                thread = threading.Thread(
                    target=lambda p, pid: (p.wait(), cleanup(pid)),
                    args=(proceso, proceso.pid)
                )
                thread.daemon = True  # El hilo no evitará que el programa termine
                thread.start()
                
                # Actualizar el hash M3U cuando se inicia una transmisión
                m3u_hash = get_m3u_hash()
                
                flash('Transmisión iniciada correctamente', 'success')
                return redirect(url_for('main.gestion_canales'))
                
            except Exception as e:
                import traceback
                error_msg = f'Error al iniciar el hilo de limpieza: {str(e)}\n\n{traceback.format_exc()}'
                print(error_msg)
                
                # Intentar escribir en el archivo de log si es posible
                try:
                    logs_dir = os.path.join(current_app.root_path, 'logs')
                    os.makedirs(logs_dir, exist_ok=True)
                    with open(os.path.join(logs_dir, 'error.log'), 'a') as f:
                        f.write(f"[{datetime.now().isoformat()}] {error_msg}\n\n")
                except Exception as log_error:
                    print(f"Error al escribir en el log: {str(log_error)}")
                
                flash('Error al iniciar la transmisión. Por favor, inténtalo de nuevo.', 'error')
                return redirect(url_for('main.gestion_canales'))
            
            # Si llegamos aquí, la transmisión se inició correctamente
            return redirect(url_for('main.gestion_canales'))
            
            flash('Error al gestionar la transmisión. Por favor, verifica los logs para más detalles.', 'error')
            return redirect(url_for('main.gestion_canales'))

def generate_m3u():
    """Genera el contenido M3U de los streams activos"""
    try:
        canales = Canal.cargar_todos() or []
        m3u_content = "#EXTM3U\n"
        
        for canal in canales:
            # Asegurarse de que el canal sea un diccionario
            if not isinstance(canal, dict):
                canal = canal.__dict__ if hasattr(canal, '__dict__') else {}
            
            # Verificar si el canal está transmitiendo
            if canal.get('en_transmision') == True or canal.get('estado') == 'transmitiendo':
                # Obtener el ID y nombre del canal de manera segura
                canal_id = canal.get('id') or ''
                nombre = canal.get('nombre', 'Sin nombre')
                
                # Construir la URL del stream con el formato correcto: /hls/NOMBRE.m3u8
                host = request.host.split(':')[0]  # Remover el puerto si existe
                nombre_archivo = f"{nombre.lower().replace(' ', '_')}.m3u8"
                
                # Usar siempre HTTP para la URL del stream ya que Nginx manejará el SSL
                stream_url = f"http://{host}/hls/{nombre_archivo}"
                
                # Agregar la entrada al M3U
                m3u_content += f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{nombre}\" group-title=\"Signally\",{nombre}\n"
                m3u_content += f"{stream_url}\n"
        
        return m3u_content
    except Exception as e:
        import traceback
        print(f"Error al generar M3U: {str(e)}")
        print(traceback.format_exc())
        return "#EXTM3U\n# Error al generar la lista de reproducción"

def get_m3u_hash():
    """Calcula el hash del contenido M3U actual"""
    m3u_content = generate_m3u()
    return hashlib.md5(m3u_content.encode('utf-8')).hexdigest()

@main_bp.route('/api/check_m3u_update')
def check_m3u_update():
    """Verifica si hay cambios en la lista M3U"""
    global m3u_hash
    try:
        current_hash = get_m3u_hash()
        
        print(f"\n=== check_m3u_update ===")
        print(f"m3u_hash actual: {m3u_hash}")
        print(f"current_hash: {current_hash}")
        print(f"¿Necesita actualización?: {m3u_hash != current_hash}")
        
        # Si no hay hash guardado, actualizamos con el actual
        if m3u_hash is None:
            print("No había hash guardado, actualizando...")
            m3u_hash = current_hash
        
        needs_update = m3u_hash != current_hash
        
        # Si hay una diferencia, actualizamos el hash guardado
        if needs_update:
            print("Se detectó un cambio en la lista M3U")
            m3u_hash = current_hash
        
        response = {
            'success': True,
            'needs_update': needs_update,
            'current_hash': current_hash,
            'stored_hash': m3u_hash
        }
        
        print(f"Respuesta enviada: {response}")
        return jsonify(response)
        
    except Exception as e:
        print(f"Error en check_m3u_update: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'needs_update': True  # Por defecto, asumir que necesita actualización en caso de error
        })

@main_bp.route('/playlist.m3u')
def get_m3u_playlist():
    """Sirve la lista M3U actual"""
    m3u_content = generate_m3u()
    return Response(
        m3u_content,
        mimetype='audio/x-mpegurl',
        headers={
            'Content-Disposition': 'attachment; filename=signally_playlist.m3u',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    )

@main_bp.route('/actualizar_m3u', methods=['POST'])
def actualizar_m3u():
    """Actualiza el hash de la lista M3U cuando se hace clic en el botón"""
    global m3u_hash
    try:
        old_hash = m3u_hash
        m3u_hash = get_m3u_hash()
        print(f"\n=== actualizar_m3u ===")
        print(f"Hash anterior: {old_hash}")
        print(f"Nuevo hash: {m3u_hash}")
        
        response = {
            'success': True,
            'message': 'Lista M3U actualizada',
            'hash': m3u_hash,
            'old_hash': old_hash
        }
        print(f"Respuesta: {response}")
        return jsonify(response)
    except Exception as e:
        error_msg = f'Error al actualizar M3U: {str(e)}'
        print(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

# Puedes agregar más rutas aquí según sea necesario
