import os
import subprocess
import sys
import urllib.request
import zipfile
import tarfile
import time
import platform
import json
from pathlib import Path

def run_command(cmd, cwd=None, sudo=False):
    if sudo:
        cmd = ['sudo'] + cmd
    try:
        result = subprocess.run(cmd, check=True, cwd=cwd, text=True, capture_output=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar el comando: {' '.join(cmd)}")
        print(f"Error: {e.stderr}")
        sys.exit(1)

def download_file(url, filename):
    print(f"Descargando {filename}...")
    urllib.request.urlretrieve(url, filename)

def setup_firewall():
    print("Configurando el cortafuegos UFW...")
    # Instalar UFW si no está instalado
    run_command(['apt-get', 'install', '-y', 'ufw'], sudo=True)
    
    # Permitir SSH (puerto 22) para no bloquearnos
    run_command(['ufw', 'allow', '22/tcp'], sudo=True)
    
    # Permitir puertos HTTP y RTMP
    run_command(['ufw', 'allow', '80/tcp'], sudo=True)
    run_command(['ufw', 'allow', '1935/tcp'], sudo=True)

    # Permitir puerto 8085 para filebrowser
    run_command(['ufw', 'allow', '8085/tcp'], sudo=True)

    # Habilitar UFW (sin interacción)
    run_command(['ufw', '--force', 'enable'], sudo=True)
    print("Cortafuegos UFW configurado y habilitado correctamente")

def main():
    # Crear carpeta multimedia
    print("Creando carpeta multimedia...")
    os.makedirs('multimedia', exist_ok=True)
    run_command(['chmod', '777', 'multimedia'], sudo=True)
    
    # Instalar dependencias requeridas
    print("Instalando dependencias requeridas...")
    dependencies = [
        'build-essential',
        'libpcre3',
        'libpcre3-dev',
        'libssl-dev',
        'zlib1g',
        'zlib1g-dev',
        'unzip',
        'ffmpeg'
    ]
    run_command(['apt-get', 'update'], sudo=True)
    run_command(['apt-get', 'install', '-y'] + dependencies, sudo=True)
    
    # Configurar el cortafuegos
    setup_firewall()
    
    # Instalar FileBrowser
    install_filebrowser()
    
    # Crear directorio de trabajo
    os.makedirs('nginx_build', exist_ok=True)
    os.chdir('nginx_build')
    
    # Descargar Nginx y el módulo RTMP
    nginx_url = "http://nginx.org/download/nginx-1.22.1.tar.gz"
    rtmp_url = "https://github.com/arut/nginx-rtmp-module/archive/refs/heads/master.zip"
    
    download_file(nginx_url, "nginx-1.22.1.tar.gz")
    download_file(rtmp_url, "nginx-rtmp-module.zip")
    
    # Extraer archivos
    print("Extrayendo archivos...")
    with tarfile.open("nginx-1.22.1.tar.gz", "r:gz") as tar:
        tar.extractall()
    
    with zipfile.ZipFile("nginx-rtmp-module.zip", 'r') as zip_ref:
        zip_ref.extractall()
    
    # Compilar e instalar Nginx con el módulo RTMP
    print("Configurando e instalando Nginx...")
    os.chdir("nginx-1.22.1")
    
    configure_cmd = [
        "./configure",
        "--add-module=../nginx-rtmp-module-master",
        "--with-http_ssl_module"
    ]
    
    run_command(configure_cmd)
    run_command(['make'])
    run_command(['make', 'install'], sudo=True)
    
    # Crear directorios necesarios con los permisos adecuados
    print("Creando directorios requeridos con los permisos adecuados...")
    stream_dir = '/usr/local/nginx/html/stream'
    hls_dir = os.path.join(stream_dir, 'hls')
    dash_dir = os.path.join(stream_dir, 'dash')
    
    # Crear directorios principales si no existen
    run_command(['mkdir', '-p', stream_dir], sudo=True)
    run_command(['mkdir', '-p', hls_dir], sudo=True)
    run_command(['mkdir', '-p', dash_dir], sudo=True)
    
    # Establecer propietario a www-data (o el usuario que ejecuta nginx)
    run_command(['chown', '-R', 'www-data:www-data', stream_dir], sudo=True)
    
    # Establecer permisos 755 para directorios y 644 para archivos
    run_command(['find', stream_dir, '-type', 'd', '-exec', 'chmod', '755', '{}', '+'], sudo=True)
    run_command(['find', stream_dir, '-type', 'f', '-exec', 'chmod', '644', '{}', '+'], sudo=True)
    
    # Establecer bit setgid para que los nuevos archivos hereden el grupo del directorio
    run_command(['chmod', 'g+s', stream_dir], sudo=True)
    
    # Configurar Nginx
    print("Configurando Nginx...")
    nginx_config = """worker_processes  1;

events {
    worker_connections  1024;
}

# RTMP configuration
rtmp {
    server {
        listen 1935; # Listen on standard RTMP port
        chunk_size 4000;

        application stream {
            live on;

            # HLS
            hls on;
            hls_path /usr/local/nginx/html/stream/hls;
            hls_fragment 3;
            hls_playlist_length 60;

            # MPEG-DASH
            dash on;
            dash_path /usr/local/nginx/html/stream/dash;

            # disable consuming the stream from nginx as rtmp
            deny play all;
        }
    }
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    server {
        listen 80;

        # HLS fragments
        location /hls {
            types {
                application/vnd.apple.mpegurl m3u8;
                video/mp2t ts;
            }
            root /usr/local/nginx/html/stream;
            add_header Cache-Control no-cache;

            add_header 'Access-Control-Allow-Origin' '*' always;
            add_header 'Access-Control-Expose-Headers' 'Content-Length';

            if ($request_method = 'OPTIONS') {
                add_header 'Access-Control-Allow-Origin' '*';
                add_header 'Access-Control-Max-Age' 1728000;
                add_header 'Content-Type' 'text/plain charset=UTF-8';
                add_header 'Content-Length' 0;
                return 204;
            }
        }

        # DASH fragments
        location /dash {
            types {
                application/dash+xml mpd;
                video/mp4 mp4;
            }
            root /usr/local/nginx/html/stream;
            add_header Cache-Control no-cache;

            add_header 'Access-Control-Allow-Origin' '*' always;
            add_header 'Access-Control-Expose-Headers' 'Content-Length';

            if ($request_method = 'OPTIONS') {
                add_header 'Access-Control-Allow-Origin' '*';
                add_header 'Access-Control-Max-Age' 1728000;
                add_header 'Content-Type' 'text/plain charset=UTF-8';
                add_header 'Content-Length' 0;
                return 204;
            }
        }

        # M3U playlist
        location /streams.m3u {
            alias /usr/local/nginx/html/stream/streams.m3u;
            add_header 'Content-Type' 'application/vnd.apple.mpegurl';
            add_header 'Cache-Control' 'no-cache';
            add_header 'Access-Control-Allow-Origin' '*';
        }
    }
}"""
    
    with open('/usr/local/nginx/conf/nginx.conf', 'w') as f:
        f.write(nginx_config)
    
    # Iniciar Nginx
    print("Iniciando Nginx...")
    run_command(['/usr/local/nginx/sbin/nginx'], sudo=True)
    
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
    
    print("\n¡Configuración completada exitosamente!")
    print("\n¡Nginx con el módulo RTMP se ha instalado y configurado correctamente!")
    print("Servidor RTMP ejecutándose en rtmp://{get_local_ip()}:1935/stream")
    print("Stream HLS disponible en http://{get_local_ip()}/hls/")
    print("Stream DASH disponible en http://{get_local_ip()}/dash/")
    print("\nEl gestor de videos se ejecutará automáticamente cada minuto.")
    print(f"Los logs se guardarán en: {os.path.join(os.getcwd(), 'video_stream.log')}")
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
    if os.geteuid() != 0:
        print("Este script requiere privilegios de superusuario. Por favor, ejecútalo con sudo.")
        sys.exit(1)
    main()
