#!/usr/bin/env python3
import os
import glob
import subprocess
import socket
import time
import json
from pathlib import Path
from datetime import datetime

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

def get_video_files():
    """Obtiene la lista de archivos de video en la carpeta multimedia"""
    # Definir ruta absoluta a la carpeta multimedia
    media_dir = '/home/Signage/multimedia'
    
    # Crear la carpeta si no existe
    if not os.path.exists(media_dir):
        print(f"Creando carpeta multimedia en: {media_dir}")
        os.makedirs(media_dir, exist_ok=True)
    
    video_extensions = ['*.mp4', '*.mkv', '*.avi', '*.mov', '*.flv', '*.wmv']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(glob.glob(os.path.join(media_dir, ext)))
    
    print(f"Buscando videos en: {media_dir}")
    print(f"Archivos encontrados: {video_files}")
    
    return sorted(video_files)

def get_video_playlist(video_files):
    """Crea una lista de reproducción simple con los videos"""
    playlist_path = os.path.join(os.path.expanduser('~'), 'playlist.txt')
    with open(playlist_path, 'w') as f:
        for video in video_files:
            f.write(f"file '{os.path.abspath(video)}'\n")
    return playlist_path

def generate_m3u_playlist(streams, output_dir='/usr/local/nginx/html/stream'):
    """Genera un archivo M3U con la lista de streams activos"""
    m3u_content = "#EXTM3U\n"
    
    for stream in streams:
        m3u_content += f"#EXTINF:-1,{stream['name']}\n"
        m3u_content += f"http://{get_local_ip()}/hls/{stream['name']}.m3u8\n"
    
    m3u_path = os.path.join(output_dir, 'streams.m3u')
    with open(m3u_path, 'w') as f:
        f.write(m3u_content)
    
    # Asegurar permisos adecuados
    os.chmod(m3u_path, 0o644)
    return m3u_path

def start_streaming(playlist_path):
    """Inicia la transmisión con FFmpeg"""
    local_ip = get_local_ip()
    rtmp_url = f"rtmp://{local_ip}:1935/stream/live"
    
    ffmpeg_cmd = [
        'ffmpeg',
        '-re',
        '-stream_loop', '-1',
        '-f', 'concat',
        '-safe', '0',
        '-i', playlist_path,
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-b:v', '4000k',
        '-maxrate', '4000k',
        '-bufsize', '8000k',
        '-vf', 'scale=-1:720',
        '-r', '30',
        '-pix_fmt', 'yuv420p',
        '-g', '60',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-ar', '48000',
        '-f', 'flv',
        rtmp_url
    ]
    
    print(f"Iniciando transmisión a {rtmp_url}")
    try:
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Imprimir la salida en tiempo real
        for line in process.stdout:
            print(line.strip())
            
    except Exception as e:
        print(f"Error al iniciar la transmisión: {e}")
    finally:
        if 'process' in locals():
            process.terminate()

def stop_streaming():
    """Detiene cualquier instancia de FFmpeg en ejecución"""
    try:
        # Buscar y terminar procesos de FFmpeg
        subprocess.run(['pkill', '-f', 'ffmpeg.*rtmp://'], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE)
        print("Transmisión detenida (si estaba en ejecución).")
    except Exception as e:
        print(f"Error al detener la transmisión: {e}")

def main():
    # Verificar si hay archivos de video
    video_files = get_video_files()
    
    if not video_files:
        print("No se encontraron archivos de video en la carpeta multimedia.")
        return
    
    # Crear directorio de streams si no existe
    stream_dir = '/usr/local/nginx/html/stream'
    os.makedirs(stream_dir, exist_ok=True)
    
    # Generar lista M3U inicial
    streams = [{'name': 'live', 'path': 'live'}]
    generate_m3u_playlist(streams, stream_dir)
    
    # Crear lista de reproducción simple
    print("Creando lista de reproducción...")
    try:
        playlist_path = get_video_playlist(video_files)
        print(f"Lista de reproducción creada: {playlist_path}")
        
        # Iniciar la transmisión
        start_streaming(playlist_path)
    except Exception as e:
        print(f"Error al crear la lista de reproducción: {e}")
        raise  # Relanzar la excepción para ver el traceback completo

if __name__ == "__main__":
    main()
