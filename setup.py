#!/usr/bin/env python3
"""
Script de configuración para Signage

Este script prepara el entorno necesario para ejecutar la aplicación Signage.
"""

import os
import sys
import subprocess
import shutil
import venv
import platform
import socket
import time
import datetime

def run_command(cmd, cwd=None, sudo=False):
    """
    Ejecuta un comando en la terminal.
    
    Args:
        cmd: Puede ser un string con el comando o una lista de argumentos
        cwd: Directorio de trabajo
        sudo: Si es True, ejecuta el comando con sudo
    """
    # Convertir a lista si es necesario
    if isinstance(cmd, str):
        cmd = cmd.split()
    
    # Añadir sudo si es necesario
    if sudo:
        cmd = ['sudo'] + cmd
    
    try:
        print(f"Ejecutando: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, 
            check=True, 
            cwd=cwd, 
            text=True, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.stdout:
            print(result.stdout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar el comando: {' '.join(cmd)}")
        if e.stdout:
            print(f"Salida:\n{e.stdout}")
        if e.stderr:
            print(f"Error:\n{e.stderr}")
        return None

def install_system_dependencies():
    """Instala las dependencias del sistema"""
    print("\n=== Instalando dependencias del sistema ===")
    
    # Actualizar lista de paquetes
    run_command("apt-get update", sudo=True)
    
    # Instalar paquetes necesarios
    packages = [
        "python3-pip",
        "python3-venv",
        "ffmpeg",
        "nginx",
        "git"
    ]
    
    for pkg in packages:
        run_command(f"apt-get install -y {pkg}", sudo=True)

def setup_python_environment():
    """Configura el entorno virtual de Python"""
    print("\n=== Configurando entorno virtual de Python ===")
    
    # Crear entorno virtual si no existe
    venv_dir = "venv"
    if not os.path.exists(venv_dir):
        print(f"Creando entorno virtual en {venv_dir}")
        venv.create(venv_dir, with_pip=True)
    
    # Activar entorno virtual e instalar dependencias
    if platform.system() == "Windows":
        pip_path = os.path.join(venv_dir, "Scripts", "pip")
    else:
        pip_path = os.path.join(venv_dir, "bin", "pip")
    
    print("Instalando dependencias de Python...")
    run_command(f"{pip_path} install --upgrade pip")
    run_command(f"{pip_path} install -r requirements.txt")

def setup_directories():
    """Crea los directorios necesarios"""
    print("\n=== Creando estructura de directorios ===")
    
    directories = [
        "multimedia",
        "app/static/uploads",
        "app/logs",
        "/var/www/html/stream/hls"  # Directorio para archivos HLS
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"Directorio creado: {directory}")
        except Exception as e:
            print(f"Advertencia: No se pudo crear el directorio {directory}: {e}")
            print("Es posible que necesites ejecutar con sudo para crear directorios del sistema")

def set_permissions():
    """Establece los permisos necesarios"""
    print("\n=== Estableciendo permisos ===")
    
    # Permisos para archivos de la aplicación
    files = ["wsgi.py", "actualizar_m3u.py"]
    for f in files:
        if os.path.exists(f):
            os.chmod(f, 0o755)
    
    # Permisos para directorios del sistema
    system_dirs = [
        "/var/www/html/stream",
        "/var/www/html/stream/hls"
    ]
    
    for directory in system_dirs:
        try:
            # Establecer propietario y grupo
            run_command(['chown', '-R', 'www-data:www-data', directory], sudo=True)
            # Establecer permisos
            run_command(['chmod', '-R', '755', directory], sudo=True)
            print(f"Permisos establecidos para: {directory}")
        except Exception as e:
            print(f"Advertencia: No se pudieron establecer permisos para {directory}: {e}")
    
    # Asegurar que el directorio de multimedia tenga permisos correctos
    multimedia_dir = os.path.abspath("multimedia")
    try:
        run_command(['chown', '-R', 'www-data:www-data', multimedia_dir], sudo=True)
        run_command(['chmod', '-R', '755', multimedia_dir], sudo=True)
        print(f"Permisos establecidos para: {multimedia_dir}")
    except Exception as e:
        print(f"Advertencia: No se pudieron establecer permisos para {multimedia_dir}: {e}")
    
    # Mensaje de finalización
    print("=== Configuración de permisos completada ===")

def main():
    """Función principal"""
    print("=== Configuración de Signage ===")
    
    # Verificar si se está ejecutando como root
    if os.geteuid() != 0:
        print("\n¡Atención! Este script requiere privilegios de superusuario.")
        print("Algunos pasos de la instalación podrían fallar.")
        print("Se recomienda ejecutar con: sudo python3 setup.py")
        print("\n¿Desea continuar de todos modos? (s/n): ", end="")
        if input().lower() != 's':
            print("Instalación cancelada.")
            sys.exit(1)
    
    # Actualizar lista de paquetes
    print("\nActualizando lista de paquetes...")
    run_command(['apt-get', 'update'], sudo=True)
    
    # Instalar dependencias del sistema
    print("\nInstalando dependencias del sistema...")
    dependencies = [
        'build-essential',
        'libpcre3',
        'libpcre3-dev',
        'libssl-dev',
        'zlib1g',
        'zlib1g-dev',
        'unzip',
        'ffmpeg',
        'libavcodec-dev',
        'libavformat-dev',
        'libswscale-dev',
        'libavutil-dev',
        'libx264-dev',
        'libx265-dev',
        'libfdk-aac-dev',
        'libmp3lame-dev',
        'libvpx-dev',
        'libopus-dev',
        'libass-dev',
        'libtheora-dev',
        'libvorbis-dev',
        'libxcb1-dev',
        'libxcb-shm0-dev',
        'libxcb-xfixes0-dev',
        'pkg-config',
        'yasm',
        'git',
        'wget',
        'curl',
        'python3-pip',
        'python3-venv',
        'nginx',
        'supervisor'
    ]
    
    # Instalar dependencias en lotes para evitar errores
    batch_size = 10
    for i in range(0, len(dependencies), batch_size):
        batch = dependencies[i:i + batch_size]
        run_command(['apt-get', 'install', '-y', '--no-install-recommends'] + batch, sudo=True)
    
    # Configurar entorno Python
    setup_python_environment()
    
    # Crear directorios necesarios
    setup_directories()
    
    # Establecer permisos
    set_permissions()
    
    # Instalar FileBrowser
    install_filebrowser()
    
    # Configurar Nginx con soporte RTMP
    print("\n=== Configurando Nginx con soporte RTMP ===")
    
    # Instalar dependencias de Nginx y RTMP
    run_command(['apt-get', 'install', '-y', 'nginx', 'libnginx-mod-rtmp'], sudo=True)
    
    # Configuración RTMP y HTTP unificada en un solo archivo
    
    # Crear directorios necesarios
    stream_dir = '/var/www/html/stream'
    hls_dir = os.path.join(stream_dir, 'hls')
    
    run_command(['mkdir', '-p', hls_dir], sudo=True)
    run_command(['chown', '-R', 'www-data:www-data', stream_dir], sudo=True)
    run_command(['chmod', '-R', '755', stream_dir], sudo=True)
    
    # Hacer una copia de seguridad del archivo de configuración actual si existe
    if os.path.exists('/etc/nginx/nginx.conf'):
        backup_time = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'/etc/nginx/nginx.conf.backup_{backup_time}'
        run_command(['cp', '/etc/nginx/nginx.conf', backup_file], sudo=True)
        print(f"✓ Copia de seguridad creada en {backup_file}")
    
    # Crear configuración principal de Nginx limpia
    main_nginx_conf = """# Configuración principal de Nginx
user www-data;
worker_processes auto;
pid /run/nginx.pid;

# Cargar módulo RTMP dinámicamente
load_module /usr/lib/nginx/modules/ngx_rtmp_module.so;

events {
    worker_connections 1024;
    multi_accept on;
}

# Configuración RTMP
rtmp {
    server {
        listen 1935;
        chunk_size 4000;
        
        application live {
            live on;
            record off;
            
            # HLS Configuration
            hls on;
            hls_path /var/www/html/stream/hls;
            hls_fragment 3s;
            hls_playlist_length 60s;
            hls_continuous on;
            hls_cleanup on;
            hls_nested off;
            
            hls_fragment_naming sequential;
            hls_fragment_slicing aligned;
            
            # Match the stream key in your FFmpeg command
            hls_variant _low BANDWIDTH=4000000;

            # Allow all connections
            allow publish all;
            allow play all;
            
            # Disable access logs for RTMP
            access_log off;
        }
    }
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    tcp_nopush    on;
    tcp_nodelay   on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    server_tokens off;
    client_max_body_size 200M;
    
    # Configuración del servidor
    server {
        listen       80 default_server;
        server_name  _;
        
        # Configuración para HLS
        location /hls {
            # Disable cache
            add_header 'Cache-Control' 'no-cache';
            
            # CORS setup
            add_header 'Access-Control-Allow-Origin' '*' always;
            add_header 'Access-Control-Expose-Headers' 'Content-Length';
            
            # Allow CORS preflight requests
            if ($request_method = 'OPTIONS') {
                add_header 'Access-Control-Allow-Origin' '*';
                add_header 'Access-Control-Max-Age' 1728000;
                add_header 'Content-Type' 'text/plain charset=UTF-8';
                add_header 'Content-Length' 0;
                return 204;
            }
            
            types {
                application/vnd.apple.mpegurl m3u8;
                video/mp2t ts;
            }
            
            root /var/www/html/stream;
            add_header Cache-Control no-cache;
        }
        
        # Configuración para WebSocket
        location /ws {
            proxy_pass http://127.0.0.1:5000/ws;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            
            # WebSocket specific settings
            proxy_connect_timeout 7d;
            proxy_send_timeout 7d;
            proxy_read_timeout 7d;
        }
        
        # Configuración para la aplicación
        location / {
            proxy_pass http://127.0.0.1:5000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            
            # Timeout settings
            proxy_connect_timeout 300s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
        }
    }
}
"""
    
    # Guardar la configuración principal de Nginx
    with open('/etc/nginx/nginx.conf', 'w') as f:
        f.write(main_nginx_conf)
    
    # Asegurar que los permisos sean correctos
    run_command(['chmod', '644', '/etc/nginx/nginx.conf'], sudo=True)
    run_command(['chown', 'root:root', '/etc/nginx/nginx.conf'], sudo=True)
    
    # Verificar configuración
    print("Verificando configuración de Nginx...")
    
    # Verificar si el módulo RTMP está instalado
    rtmp_installed = run_command(['dpkg', '-l', 'libnginx-mod-rtmp'], sudo=True)
    if "no packages found" in rtmp_installed.lower():
        print("✗ El módulo RTMP no está instalado")
        print("Instalando módulo RTMP...")
        run_command(['apt-get', 'update'], sudo=True)
        run_command(['apt-get', 'install', '-y', 'libnginx-mod-rtmp'], sudo=True)
    else:
        print("✓ Módulo RTMP ya está instalado")
    
    # Verificar si el módulo se cargó correctamente
    nginx_v = run_command(['nginx', '-V'], sudo=True)
    if "with-http_ssl_module" not in nginx_v:
        print("✗ Módulo SSL no encontrado, instalando...")
        run_command(['apt-get', 'install', '-y', 'nginx-extras'], sudo=True)
    
    # Verificar la configuración
    test_result = run_command(['nginx', '-t'], sudo=True)
    if test_result and "test is successful" in test_result:
        print("✓ Configuración de Nginx verificada correctamente")
        # Reiniciar Nginx
        run_command(['systemctl', 'restart', 'nginx'], sudo=True)
        print("✓ Nginx reiniciado con la nueva configuración")
    else:
        print("✗ Error en la configuración de Nginx.")
        print("=== Detalles del error ===")
        print(test_result or "No se pudo obtener el error. Verifica los logs manualmente.")
        print("=========================")
        print("Puedes revisar los logs con: sudo tail -f /var/log/nginx/error.log")
        print("Configuración actual cargada:")
        print(result or "No se pudo cargar la configuración")
        sys.exit(1)
    
    # Configuración finalizada
    print("\n=== Configuración completada ===")
    print("Nginx ha sido configurado con soporte RTMP.")
    print("Puedes iniciar una transmisión con:")
    print("ffmpeg -re -i tu_video.mp4 -c:v libx264 -preset veryfast -f flv rtmp://tu_servidor/live/tu_stream")
    print("Y verla en: http://tu_servidor/hls/tu_stream.m3u8")
    
    # Obtener la IP del servidor
    try:
        ip = get_local_ip()
        if ip:
            print(f"\nTu dirección IP local es: {ip}")
            print(f"URL de transmisión: rtmp://{ip}/live/tu_stream")
            print(f"URL de reproducción: http://{ip}/hls/tu_stream.m3u8")
    except Exception as e:
        print(f"No se pudo obtener la dirección IP: {e}")

    # Configuración del servidor web
    nginx_web_config = """
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
    
    location /hls {
        types {
            application/vnd.apple.mpegurl m3u8;
            video/mp2t ts;
        }
        root /var/www/html/stream;
        add_header Cache-Control no-cache;
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Expose-Headers' 'Content-Length';
    }
    
    location /ws {
        proxy_pass http://127.0.0.1:5000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
"""
    
    # Guardar configuración del servidor web
    with open('/etc/nginx/sites-available/default', 'w') as f:
        f.write(nginx_web_config)
    
    # Crear enlace simbólico si no existe
    if not os.path.exists('/etc/nginx/sites-enabled/default'):
        run_command(['ln', '-s', '/etc/nginx/sites-available/default', '/etc/nginx/sites-enabled/'], sudo=True)
    
    # Verificar configuración de Nginx
    result = run_command(['nginx', '-t'], sudo=True)
    if result is not None and "test is successful" in result:
        print("✓ Configuración de Nginx verificada correctamente")
        # Reiniciar Nginx
        run_command(['systemctl', 'restart', 'nginx'], sudo=True)
        print("✓ Nginx reiniciado con la nueva configuración")
    else:
        print("✗ Error en la configuración de Nginx. Verifica los logs.")
        sys.exit(1)
    
    # Configuración de Nginx RTMP
    with open('/etc/nginx/nginx.conf', 'w') as f:
        f.write(nginx_conf)
    
    # Crear directorio para logs de Nginx si no existe
    run_command(['mkdir', '-p', '/var/log/nginx/'], sudo=True)
    run_command(['touch', '/var/log/nginx/access.log', '/var/log/nginx/error.log'], sudo=True)
    run_command(['chown', '-R', 'www-data:www-data', '/var/log/nginx/'], sudo=True)
    
    # Configurar Nginx para iniciar automáticamente
    print("Configurando Nginx para inicio automático...")
    
    # Crear archivo de servicio systemd para Nginx
    nginx_service = """[Unit]
Description=The NGINX HTTP and reverse proxy server with RTMP module
After=syslog.target network-online.target remote-fs.target nss-lookup.target
Wants=network-online.target

[Service]
Type=forking
PIDFile=/run/nginx.pid
ExecStartPre=/usr/sbin/nginx -t
ExecStart=/usr/sbin/nginx
ExecReload=/usr/sbin/nginx -s reload
ExecStop=/bin/kill -s QUIT $MAINPID
PrivateTmp=true
TimeoutStopSec=5
KillMode=mixed

[Install]
WantedBy=multi-user.target
"""
    
    # Guardar configuración del servicio
    with open('/etc/systemd/system/nginx.service', 'w') as f:
        f.write(nginx_service)
    
    # Recargar systemd y habilitar Nginx
    run_command(['systemctl', 'daemon-reload'], sudo=True)
    run_command(['systemctl', 'enable', 'nginx'], sudo=True)
    
    # Iniciar Nginx
    print("Iniciando Nginx...")
    run_command(['systemctl', 'start', 'nginx'], sudo=True)
    
    # Verificar estado de Nginx
    run_command(['systemctl', 'status', 'nginx', '--no-pager'], sudo=True)
    
    # Configurar cron job para el gestor de videos
    print("\nConfigurando cron job para el gestor de videos...")
    log_file = os.path.join(os.path.expanduser('~'), 'video_stream.log')
    cron_command = f"* * * * * /usr/bin/python3 /usr/local/bin/video_stream_manager.py >> {log_file} 2>&1"
    cron_job = f"(crontab -l 2>/dev/null | grep -v 'video_stream_manager.py'; echo '{cron_command}') | crontab -"
    print(f"Comando cron: {cron_command}")
    
    try:
        subprocess.run(cron_job, shell=True, check=True)
        print("Cron job configurado correctamente.")
    except subprocess.CalledProcessError as e:
        print(f"Error al configurar el cron job: {e}")
    
    # Copiar el script de gestión de videos si no existe
    current_dir = os.path.dirname(os.path.abspath(__file__))
    video_manager_src = os.path.join(current_dir, 'video_stream_manager.py')
    video_manager_dst = '/usr/local/bin/video_stream_manager.py'
    
    try:
        # Copiar el archivo a /usr/local/bin/
        run_command(['cp', video_manager_src, video_manager_dst], sudo=True)
        # Hacer el script ejecutable
        run_command(['chmod', '755', video_manager_dst], sudo=True)
        print(f"Script de gestión de videos copiado a {video_manager_dst}")
    except Exception as e:
        print(f"Error al copiar el script de gestión de videos: {e}")
    
    # Configurar firewall (si está habilitado)
    try:
        print("\nConfigurando el firewall...")
        run_command(['ufw', 'allow', '80/tcp'], sudo=True)
        run_command(['ufw', 'allow', '443/tcp'], sudo=True)
        run_command(['ufw', 'allow', '1935/tcp'], sudo=True)
        run_command(['ufw', 'allow', '1935/udp'], sudo=True)
        run_command(['ufw', 'reload'], sudo=True)
        print("Reglas de firewall configuradas correctamente.")
    except Exception as e:
        print(f"Advertencia: No se pudo configurar el firewall: {e}")
    
    # Obtener la IP local
    local_ip = get_local_ip()
    
    # Mensaje de finalización
    print("\n" + "="*80)
    print("¡Configuración completada exitosamente!")
    print("="*80)
    print("\n¡Nginx con el módulo RTMP se ha instalado y configurado correctamente!")
    print("\n=== Configuración de Servicios ===")
    print(f"Servidor RTMP:     rtmp://{local_ip}:1935/live")
    print(f"Reproductor HLS:   http://{local_ip}/hls/")
    print(f"Reproductor DASH:  http://{local_ip}/dash/")
    print(f"Interfaz Web:      http://{local_ip}")
    
    print("\n=== Comandos útiles ===")
    print("Reiniciar Nginx:    sudo systemctl restart nginx")
    print("Ver logs de Nginx:  sudo journalctl -u nginx -f")
    print("Ver estado Nginx:   sudo systemctl status nginx")
    
    print("\n=== Notas importantes ===")
    print("1. Asegúrate de que los puertos 80, 443 y 1935 estén abiertos en tu firewall")
    print("2. Para transmisiones estables, se recomienda una conexión de red cableada")
    print("3. Los streams estarán disponibles en /hls/STREAM_NAME.m3u8 y /dash/STREAM_NAME.mpd")
    
    print("\nEl gestor de videos se ejecutará automáticamente cada minuto.")
    print(f"Los logs se guardarán en: /var/log/nginx/")
    print("="*80)
    print("\nColoca tus videos en la carpeta 'multimedia' y se transmitirán automáticamente.")

def install_filebrowser():
    """Instala y configura FileBrowser"""
    print("\nInstalando FileBrowser...")
    
    # Obtener la última versión de FileBrowser
    try:
        print("Obteniendo la última versión de FileBrowser...")
        filebrowser_version = 'v2.23.0'  # Puedes actualizar esto a la última versión
        
        # Determinar la arquitectura del sistema
        arch = platform.machine().lower()
        if arch in ['x86_64', 'amd64']:
            arch = 'linux-amd64'
        elif arch in ['arm', 'armv7l']:
            arch = 'linux-arm7'
        elif arch == 'aarch64':
            arch = 'linux-arm64'
        else:
            print(f"Arquitectura no soportada: {arch}. Instalación de FileBrowser omitida.")
            return
            
        # Crear directorio para FileBrowser
        fb_dir = '/opt/filebrowser'
        os.makedirs(fb_dir, exist_ok=True)
        
        # Descargar FileBrowser
        fb_url = f'https://github.com/filebrowser/filebrowser/releases/download/{filebrowser_version}/filebrowser-{arch}.tar.gz'
        fb_archive = os.path.join(fb_dir, 'filebrowser.tar.gz')
        download_file(fb_url, fb_archive)
        
        # Extraer archivos
        print("Extrayendo FileBrowser...")
        with tarfile.open(fb_archive, 'r:gz') as tar:
            tar.extractall(path=fb_dir)
        
        # Mover el binario a /usr/local/bin
        run_command(['mv', os.path.join(fb_dir, 'filebrowser'), '/usr/local/bin/'], sudo=True)
        run_command(['chmod', '+x', '/usr/local/bin/filebrowser'], sudo=True)
        
        # Crear directorio de configuración
        config_dir = '/etc/filebrowser'
        os.makedirs(config_dir, exist_ok=True)
        
        # Crear configuración básica
        config_path = os.path.join(config_dir, 'config.json')
        config = {
            "port": 8085,
            "baseURL": "",
            "address": "0.0.0.0",
            "log": "stdout",
            "database": "/etc/filebrowser/filebrowser.db",
            "root": "/home/signage/multimedia"
        }
        
        with open('temp_config.json', 'w') as f:
            json.dump(config, f, indent=4)
        run_command(['mv', 'temp_config.json', config_path], sudo=True)
        
        # Crear servicio systemd
        service_content = """[Unit]
Description=File Browser
After=network.target

[Service]
User=root
ExecStart=/usr/local/bin/filebrowser -c /etc/filebrowser/config.json
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""
        
        with open('filebrowser.service', 'w') as f:
            f.write(service_content)
            
        run_command(['mv', 'filebrowser.service', '/etc/systemd/system/'], sudo=True)
        
        # Recargar systemd y habilitar el servicio
        run_command(['systemctl', 'daemon-reload'], sudo=True)
        run_command(['systemctl', 'enable', 'filebrowser.service'], sudo=True)
        run_command(['systemctl', 'start', 'filebrowser.service'], sudo=True)
        
        print("\n¡FileBrowser instalado y configurado correctamente!")
        print(f"Accede a FileBrowser en: http://{get_local_ip()}:8085")
        print("Usuario por defecto: admin")
        print("Contraseña por defecto: admin")
        print("\nPor seguridad, cambia la contraseña después del primer inicio de sesión.")
        
    except Exception as e:
        print(f"Error al instalar FileBrowser: {e}")
        return False
    
    return True

def get_local_ip():
    """Obtiene la dirección IP local del servidor"""
    try:
        # Crear un socket para obtener la IP local
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        # No es necesario que se conecte realmente
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    main()
