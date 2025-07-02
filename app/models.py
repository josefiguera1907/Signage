import os
import json
from datetime import datetime

class Canal:
    """Clase que representa un canal de señalización."""
    
    _ultimo_id = 0
    _archivo_almacenamiento = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'canales.json')
    
    # Tipos de contenido disponibles
    TIPOS_CONTENIDO = [
        ('imagen', 'Imagen'),
        ('video', 'Video'),
        ('streaming', 'Streaming')
    ]
    
    def __init__(self, nombre, tipo_contenido, rotacion=0, repeticion='bucle', contenidos=None, id=None, proceso_ffmpeg=None, en_transmision=False):
        self.id = id if id is not None else self._generar_id()
        self.nombre = nombre
        self.tipo_contenido = tipo_contenido
        self.rotacion = int(rotacion)
        self.repeticion = repeticion
        self.contenidos = contenidos if contenidos is not None else []
        self.proceso_ffmpeg = proceso_ffmpeg  # ID del proceso FFmpeg si está en ejecución
        self.en_transmision = en_transmision  # Estado de la transmisión
        self.fecha_creacion = datetime.now().isoformat()
        self.fecha_actualizacion = self.fecha_creacion
    
    @classmethod
    def _generar_id(cls):
        """Genera un nuevo ID único para el canal."""
        cls._ultimo_id += 1
        return cls._ultimo_id
    
    def to_dict(self):
        """Convierte el objeto Canal a un diccionario."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'tipo_contenido': self.tipo_contenido,
            'rotacion': self.rotacion,
            'repeticion': self.repeticion,
            'contenidos': self.contenidos,
            'proceso_ffmpeg': self.proceso_ffmpeg,
            'en_transmision': self.en_transmision,
            'fecha_creacion': self.fecha_creacion,
            'fecha_actualizacion': self.fecha_actualizacion
        }
    
    @classmethod
    def from_dict(cls, data):
        """Crea un objeto Canal a partir de un diccionario."""
        # Asegurarse de que los campos opcionales tengan valores por defecto
        en_transmision = data.get('en_transmision', False)
        proceso_ffmpeg = data.get('proceso_ffmpeg')
        contenidos = data.get('contenidos', [])
        
        canal = cls(
            id=data['id'],
            nombre=data['nombre'],
            tipo_contenido=data['tipo_contenido'],
            rotacion=data['rotacion'],
            repeticion=data['repeticion'],
            en_transmision=en_transmision,
            contenidos=contenidos,
            proceso_ffmpeg=proceso_ffmpeg
        )
        
        # Asegurarse de que los atributos estén establecidos
        if not hasattr(canal, 'en_transmision'):
            canal.en_transmision = en_transmision
        if not hasattr(canal, 'proceso_ffmpeg'):
            canal.proceso_ffmpeg = proceso_ffmpeg
            
        canal.fecha_creacion = data.get('fecha_creacion', datetime.now().isoformat())
        canal.fecha_actualizacion = data.get('fecha_actualizacion', datetime.now().isoformat())
        return canal
    
    @classmethod
    def guardar_todos(cls, canales):
        """Guarda todos los canales en el archivo de almacenamiento."""
        try:
            # Convertir los objetos Canal a diccionarios
            datos = [canal.to_dict() for canal in canales]
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(os.path.abspath(cls._archivo_almacenamiento)), exist_ok=True)
            
            # Escribir en el archivo
            temp_file = f"{cls._archivo_almacenamiento}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(datos, f, indent=2)
                
            # Reemplazar el archivo original de forma atómica
            if os.path.exists(cls._archivo_almacenamiento):
                os.replace(temp_file, cls._archivo_almacenamiento)
            else:
                os.rename(temp_file, cls._archivo_almacenamiento)
                
        except Exception as e:
            print(f"Error al guardar canales: {e}")
            # Intentar limpiar el archivo temporal si existe
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise  # Relanzar la excepción para que el llamador la maneje
    
    @classmethod
    def cargar_todos(cls):
        """Carga todos los canales desde el archivo de almacenamiento."""
        try:
            if not os.path.exists(cls._archivo_almacenamiento):
                # Crear el archivo con una lista vacía si no existe
                with open(cls._archivo_almacenamiento, 'w') as f:
                    json.dump([], f)
                return []
                
            with open(cls._archivo_almacenamiento, 'r') as f:
                datos = json.load(f)
                
            canales = [cls.from_dict(canal) for canal in datos]
            if canales:
                cls._ultimo_id = max(canal.id for canal in canales)
                
            return canales
            
        except json.JSONDecodeError:
            # Si hay un error al decodificar el JSON, devolver lista vacía
            return []
        except Exception as e:
            print(f"Error al cargar canales: {e}")
            return []
    
    @classmethod
    def obtener_por_id(cls, canal_id):
        """Obtiene un canal por su ID."""
        canales = cls.cargar_todos()
        for canal in canales:
            if canal.id == canal_id:
                return canal
        return None
    
    @classmethod
    def guardar(cls, canal):
        """Guarda un canal, actualizándolo si ya existe o creándolo si no."""
        canales = cls.cargar_todos()
        
        # Buscar si el canal ya existe
        for i, c in enumerate(canales):
            if c.id == canal.id:
                canales[i] = canal
                break
        else:
            canales.append(canal)
            
        cls.guardar_todos(canales)
    
    @classmethod
    def eliminar_por_id(cls, canal_id):
        """Elimina un canal por su ID."""
        canales = cls.cargar_todos()
        canales = [c for c in canales if c.id != canal_id]
        cls.guardar_todos(canales)
        
        # Actualizar el último ID si es necesario
        if canales:
            cls._ultimo_id = max(canal.id for canal in canales)
        else:
            cls._ultimo_id = 0
