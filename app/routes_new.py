            # Iniciar el proceso FFmpeg con manejo adecuado de procesos
            try:
                # Configurar el proceso para que ignore las señales del teclado
                # y cree un nuevo grupo de procesos
                proceso = subprocess.Popen(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid,  # Crear un nuevo grupo de procesos
                    start_new_session=True,
                    close_fds=True  # Cerrar todos los descriptores de archivo heredados
                )
                
                # Obtener el ID del grupo de procesos
                pgid = os.getpgid(proceso.pid)
                
                # Guardar información del proceso
                canal.proceso_ffmpeg = {
                    'pid': proceso.pid,
                    'pgid': pgid,  # Guardar el ID del grupo
                    'inicio': datetime.now().isoformat(),
                    'comando': ' '.join(ffmpeg_cmd)
                }
                
                print(f"Proceso FFmpeg iniciado con PID: {proceso.pid}, PGID: {pgid}")
                
            except Exception as e:
                error_msg = f'Error al iniciar FFmpeg: {str(e)}'
                print(error_msg)
                raise Exception(error_msg)
