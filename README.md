# ANI-cumple

API REST para extraer y obtener la lista de cumpleaños de pacientes registrados en HermessApp mediante web scraping automatizado.

## 📋 Descripción

Este proyecto proporciona una API REST que permite extraer automáticamente los datos de cumpleaños de pacientes desde HermessApp. Utiliza Selenium para automatizar el proceso de login y extracción de datos, y proporciona los resultados en formato JSON.

## ✨ Características

- 🔐 Autenticación automática en HermessApp
- 📊 Extracción de datos de cumpleaños con formato estructurado
- 🔄 Sistema de colas para manejar múltiples solicitudes
- 📥 Descarga de resultados en formato JSON
- 🌐 API REST con endpoints documentados
- 🧹 Limpieza automática de datos duplicados
- 🔄 Reordenamiento automático de nombres (Apellidos → Nombres)
- 🌍 Compatible con hosting compartido y VPS
- 🐳 Soporte para Docker/Portainer

## 📦 Requisitos Previos

- Python 3.8 o superior
- Google Chrome instalado
- ChromeDriver (se gestiona automáticamente con webdriver-manager)
- Sistema operativo: Windows, Linux o macOS

## 🚀 Instalación

1. **Clona o descarga el repositorio:**
   ```bash
   cd ani-cumple
   ```

2. **Crea un entorno virtual (recomendado):**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/macOS
   source venv/bin/activate
   ```

3. **Instala las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configura las variables de entorno:**
   
   Copia el archivo de ejemplo y completa tus credenciales:
   ```bash
   cp config.env.example config.env
   ```
   
   Edita `config.env` y agrega tus credenciales:
   ```env
   HERMESS_EMAIL=tu_email@ejemplo.com
   HERMESS_PASSWORD=tu_contraseña
   HERMESS_LOGIN_URL=https://hermessapp.com/login
   HERMESS_BIRTHDAYS_URL=https://hermessapp.com/pacientescumple
   ```

## ⚙️ Configuración

### Variables de Entorno

El archivo `config.env` permite configurar:

- `HERMESS_EMAIL`: Tu email de acceso a HermessApp (requerido)
- `HERMESS_PASSWORD`: Tu contraseña de acceso (requerido)
- `HERMESS_LOGIN_URL`: URL de login (opcional, por defecto: https://hermessapp.com/login)
- `HERMESS_BIRTHDAYS_URL`: URL de la página de cumpleaños (opcional, por defecto: https://hermessapp.com/pacientescumple)
- `ENVIRONMENT`: Entorno de ejecución - `shared_hosting` o `vps` (opcional)
- `HEADLESS`: Modo headless del navegador - `true` o `false` (opcional, por defecto: `true`)
- `PORT`: Puerto del servidor (opcional, por defecto: 5000)
- `DEBUG`: Modo debug - `true` o `false` (opcional, por defecto: `false`)

## 🏃 Uso

### Desarrollo Local

Ejecuta el servidor de desarrollo:

```bash
python ani-cumple.py
```

La API estará disponible en `http://localhost:5000`

### Producción (Linux/Unix)

Usa Gunicorn para ejecutar en producción:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 ani-cumple:app
```

## 📡 Endpoints de la API

### `GET /`

Obtiene información sobre la API y endpoints disponibles.

**Respuesta:**
```json
{
  "message": "API Scraper para HermessApp - Lista de Cumpleaños",
  "version": "1.0.0",
  "endpoints": {
    "/scrape": "POST - Iniciar scraping de cumpleaños",
    "/status/<task_id>": "GET - Verificar estado de una tarea",
    "/download/<task_id>": "GET - Descargar archivo JSON con los datos",
    "/health": "GET - Verificar estado de la API"
  }
}
```

### `POST /scrape`

Inicia el proceso de scraping de cumpleaños.

**Respuesta:**
```json
{
  "success": true,
  "task_id": "task_1234567890",
  "message": "Scraping iniciado exitosamente",
  "status_url": "/status/task_1234567890",
  "download_url": "/download/task_1234567890"
}
```

### `GET /status/<task_id>`

Verifica el estado de una tarea de scraping.

**Respuesta:**
```json
{
  "success": true,
  "task_id": "task_1234567890",
  "status": "success",
  "message": "Scraping completado exitosamente",
  "total_records": 25,
  "timestamp": "2024-01-15T10:30:00",
  "has_data": true
}
```

**Estados posibles:**
- `processing`: El scraping está en proceso
- `success`: El scraping se completó exitosamente
- `error`: Ocurrió un error durante el scraping

### `GET /download/<task_id>`

Descarga los datos extraídos en formato JSON.

**Respuesta:** Archivo JSON con los siguientes campos:

```json
{
  "metadata": {
    "fecha_extraccion": "2024-01-15T10:30:00",
    "total_registros": 25,
    "formato_fecha": "YYYY-MM-DD",
    "año_ejecucion": 2024,
    "fuente": "HermessApp",
    "descripcion": "Lista de cumpleaños de pacientes extraída automáticamente",
    "task_id": "task_1234567890"
  },
  "cumpleanos": [
    {
      "nombre": "Juan Pérez García",
      "cumpleanos": "2024-03-15",
      "celular": "3001234567",
      "edad": "30"
    }
  ]
}
```

### `GET /health`

Verifica el estado de la API.

**Respuesta:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "environment": "shared_hosting",
  "queue_size": 0,
  "active_tasks": 0
}
```

### `POST /cleanup`

Limpia tareas antiguas (más de 1 hora) para liberar memoria.

**Respuesta:**
```json
{
  "success": true,
  "cleaned_tasks": 5,
  "remaining_tasks": 2
}
```

## 📝 Ejemplos de Uso

### Ejemplo con cURL

1. **Iniciar scraping:**
   ```bash
   curl -X POST http://localhost:5000/scrape
   ```

2. **Verificar estado:**
   ```bash
   curl http://localhost:5000/status/task_1234567890
   ```

3. **Descargar datos:**
   ```bash
   curl http://localhost:5000/download/task_1234567890 -o cumpleanos.json
   ```

### Ejemplo con Python

```python
import requests

# Iniciar scraping
response = requests.post('http://localhost:5000/scrape')
task_id = response.json()['task_id']

# Verificar estado
import time
while True:
    status = requests.get(f'http://localhost:5000/status/{task_id}').json()
    if status['status'] != 'processing':
        break
    time.sleep(2)

# Descargar datos
if status['status'] == 'success':
    data = requests.get(f'http://localhost:5000/download/{task_id}').json()
    print(f"Total de registros: {data['metadata']['total_registros']}")
```

## 🏗️ Estructura del Proyecto

```
ani-cumple/
├── ani-cumple.py          # Código principal de la aplicación
├── config.env             # Variables de entorno (no incluir en git)
├── config.env.example     # Ejemplo de configuración
├── requirements.txt       # Dependencias del proyecto
├── README.md             # Documentación
├── scraper.log           # Logs de la aplicación (generado automáticamente)
└── .gitignore           # Archivos a ignorar en git
```

## 📌 Notas Importantes

- ⚠️ **Seguridad**: Nunca subas el archivo `config.env` con tus credenciales a un repositorio público.
- 🔒 El archivo `config.env` está en `.gitignore` por defecto.
- 🌐 La API permite CORS desde cualquier origen por defecto.
- 🕐 Los datos extraídos se mantienen en memoria durante 1 hora (usa `/cleanup` para limpiar antes).
- 🐛 Los logs se guardan en `scraper.log` para facilitar el debugging.

## 🐳 Despliegue

### Docker/Portainer

El proyecto es compatible con Docker y Portainer. Asegúrate de configurar:

- Variables de entorno en el contenedor
- Chrome/Chromium instalado en la imagen
- Permisos adecuados para Selenium

### Hosting Compartido

Configura `ENVIRONMENT=shared_hosting` en `config.env` para optimizar el uso de recursos.

### VPS

Configura `ENVIRONMENT=vps` en `config.env` para aprovechar mejor los recursos del servidor.

## 📄 Licencia

Este proyecto es de uso privado.
