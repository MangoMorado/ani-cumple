#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Scraper para HermessApp - Lista de Cumpleaños
Script que puede ejecutarse vía API para hacer scraping de HermessApp
Compatible con hosting compartido y VPS con Portainer
"""

import os
import json
import time
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv
import threading
import queue
import tempfile
import shutil

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Permitir CORS para llamadas desde cualquier origen

# Cola para manejar las tareas de scraping
scraping_queue = queue.Queue()
scraping_results = {}

class HermessAPIScraper:
    def __init__(self):
        """Inicializa el scraper con configuración desde variables de entorno"""
        load_dotenv('config.env')
        
        self.email = os.getenv('HERMESS_EMAIL')
        self.password = os.getenv('HERMESS_PASSWORD')
        self.login_url = os.getenv('HERMESS_LOGIN_URL', 'https://hermessapp.com/login')
        self.birthdays_url = os.getenv('HERMESS_BIRTHDAYS_URL', 'https://hermessapp.com/pacientescumple')
        
        if not self.email or not self.password:
            raise ValueError("Debes configurar HERMESS_EMAIL y HERMESS_PASSWORD en config.env")
        
        self.driver = None
        self.wait = None
        
    def setup_driver(self, headless=True):
        """Configura el driver de Chrome con opciones optimizadas para diferentes entornos"""
        chrome_options = Options()
        
        # Opciones básicas para todos los entornos
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Configuración específica para hosting compartido
        if os.getenv('ENVIRONMENT') == 'shared_hosting':
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--disable-javascript")
            chrome_options.add_argument("--disable-css")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
        
        # Configuración específica para VPS/Docker
        elif os.getenv('ENVIRONMENT') == 'vps':
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
        
        # Configuración headless
        if headless:
            chrome_options.add_argument("--headless")
        
        # Intentar usar ChromeDriverManager si está disponible
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            logger.warning(f"No se pudo usar ChromeDriverManager: {e}")
            # Fallback a ChromeDriver local
            self.driver = webdriver.Chrome(options=chrome_options)
        
        self.wait = WebDriverWait(self.driver, 15)
        
    def login(self):
        """Inicia sesión en HermessApp"""
        try:
            logger.info("🔄 Iniciando sesión en HermessApp...")
            self.driver.get(self.login_url)
            
            # Esperar a que cargue la página de login
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form[action*='login']"))
            )
            
            # Buscar campos de login usando los selectores correctos del HTML
            email_field = self.driver.find_element(By.CSS_SELECTOR, "input[name='email']")
            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[name='password']")
            
            # Ingresar credenciales
            email_field.clear()
            email_field.send_keys(self.email)
            
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Buscar y hacer clic en el botón de login
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Esperar a que se complete el login
            time.sleep(3)
            
            logger.info("✅ Sesión iniciada exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error durante el login: {str(e)}")
            return False
    
    def navigate_to_birthdays(self):
        """Navega a la página de cumpleaños"""
        try:
            logger.info("🔄 Navegando a la página de cumpleaños...")
            self.driver.get(self.birthdays_url)
            time.sleep(3)
            
            # Esperar a que cargue algún contenido
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                )
            except:
                pass
            
            logger.info("✅ Página de cumpleaños cargada")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error navegando a la página de cumpleaños: {str(e)}")
            return False
    
    def extract_birthday_data(self):
        """Extrae los datos de cumpleaños de la tabla"""
        try:
            logger.info("🔄 Extrayendo datos de cumpleaños...")
            
            # Esperar un poco más para que la página cargue completamente
            time.sleep(2)
            
            # Buscar la tabla con selectores más específicos
            table_selectors = [
                "table",
                ".table",
                "[class*='table']",
                "div[role='table']",
                "[class*='list']",
                "div[class*='overflow']",
                "div[class*='container']"
            ]
            
            table = None
            for selector in table_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if self._contains_birthday_data(element):
                            table = element
                            break
                    if table:
                        break
                except NoSuchElementException:
                    continue
            
            if not table:
                try:
                    birthday_text = self.driver.find_element(By.XPATH, "//*[contains(text(), 'cumpleaños') or contains(text(), 'cumpleañeros')]")
                    logger.info(f"📍 Encontrado texto relacionado: {birthday_text.text}")
                    table = birthday_text.find_element(By.XPATH, "./ancestor::div[contains(@class, 'container') or contains(@class, 'table') or contains(@class, 'list')]")
                except:
                    pass
            
            if not table:
                raise Exception("No se pudo encontrar la tabla de cumpleaños")
            
            logger.info(f"📍 Tabla encontrada con selector: {table.tag_name}")
            
            # Extraer filas de la tabla
            rows = table.find_elements(By.CSS_SELECTOR, "tr, [role='row'], div[class*='row']")
            
            if not rows:
                rows = table.find_elements(By.CSS_SELECTOR, "div[class*='item'], div[class*='entry'], div[class*='data']")
            
            logger.info(f"📍 Encontradas {len(rows)} filas potenciales")
            
            birthdays_data = []
            
            for i, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.CSS_SELECTOR, "td, [role='cell'], div[class*='cell'], span, div")
                    
                    if len(cells) >= 3:
                        cell_texts = [cell.text.strip() for cell in cells if cell.text.strip()]
                        
                        if len(cell_texts) >= 3:
                            birthday_entry = self._parse_birthday_row(cell_texts)
                            if birthday_entry:
                                birthdays_data.append(birthday_entry)
                                logger.info(f"  ✅ Fila {i+1}: {birthday_entry['nombre']} - {birthday_entry['cumpleanos']}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Error procesando fila {i+1}: {str(e)}")
                    continue
            
            logger.info(f"✅ Se extrajeron {len(birthdays_data)} registros de cumpleaños")
            return birthdays_data
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo datos: {str(e)}")
            return []
    
    def _contains_birthday_data(self, element):
        """Verifica si un elemento contiene datos de cumpleaños"""
        try:
            text = element.text.lower()
            birthday_keywords = ['cumpleaños', 'cumpleañeros', 'fecha', 'edad', 'nombre']
            return any(keyword in text for keyword in birthday_keywords)
        except:
            return False
    
    def _parse_birthday_row(self, cell_texts):
        """Parsea una fila de datos de cumpleaños"""
        try:
            nombre = ""
            fecha = ""
            celular = ""
            edad = ""
            
            for text in cell_texts:
                text = text.strip()
                if not text:
                    continue
                
                if len(text) > 5 and not any(char.isdigit() for char in text) and not nombre:
                    nombre = text
                elif '/' in text and len(text) <= 5 and not fecha:
                    fecha = text
                elif text.isdigit() and len(text) == 10 and not celular:
                    celular = text
                elif text.isdigit() and 1 <= len(text) <= 3 and not edad:
                    edad = text
            
            if nombre and fecha:
                cumpleanos = self._convert_date_to_n8n_format(fecha)
                nombre_formateado = self._format_name(nombre)
                
                return {
                    "nombre": nombre_formateado,
                    "cumpleanos": cumpleanos,
                    "celular": celular,
                    "edad": edad
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Error parseando fila: {str(e)}")
            return None
    
    def _reorder_name(self, nombre):
        """Reordena el nombre de 'Apellido1 Apellido2 Nombre1 Nombre2' a 'Nombre1 Nombre2 Apellido1 Apellido2'"""
        try:
            if not nombre:
                return nombre
            
            palabras = nombre.split()
            
            if len(palabras) < 2:
                return nombre
            
            if len(palabras) == 5:
                apellidos_compuestos_inicio = ['DE', 'DEL', 'VAN', 'VON', 'MAC', 'MC']
                
                if palabras[0].upper() in apellidos_compuestos_inicio:
                    if palabras[0].upper() in ['DE', 'DEL'] and palabras[1].upper() in ['LA', 'LOS', 'LAS']:
                        return f"{palabras[3]} {palabras[4]} {palabras[0]} {palabras[1]} {palabras[2]}"
                    elif palabras[0].upper() in ['VAN', 'VON'] and palabras[1].upper() == 'DER':
                        return f"{palabras[3]} {palabras[4]} {palabras[0]} {palabras[1]} {palabras[2]}"
                    else:
                        return f"{palabras[3]} {palabras[4]} {palabras[0]} {palabras[1]} {palabras[2]}"
                else:
                    return f"{palabras[3]} {palabras[4]} {palabras[0]} {palabras[1]} {palabras[2]}"
            
            elif len(palabras) == 6:
                apellidos_compuestos_inicio = ['DE', 'DEL', 'VAN', 'VON']
                
                if palabras[0].upper() in apellidos_compuestos_inicio:
                    if palabras[0].upper() in ['DE', 'DEL'] and palabras[1].upper() in ['LA', 'LOS', 'LAS']:
                        return f"{palabras[3]} {palabras[4]} {palabras[5]} {palabras[0]} {palabras[1]} {palabras[2]}"
                    else:
                        mitad = len(palabras) // 2
                        apellidos = palabras[:mitad]
                        nombres = palabras[mitad:]
                        return f"{' '.join(nombres)} {' '.join(apellidos)}"
                else:
                    mitad = len(palabras) // 2
                    apellidos = palabras[:mitad]
                    nombres = palabras[mitad:]
                    return f"{' '.join(nombres)} {' '.join(apellidos)}"
            
            elif len(palabras) == 4:
                return f"{palabras[2]} {palabras[3]} {palabras[0]} {palabras[1]}"
            
            elif len(palabras) == 3:
                return f"{palabras[2]} {palabras[0]} {palabras[1]}"
            
            elif len(palabras) == 2:
                return f"{palabras[1]} {palabras[0]}"
            
            else:
                mitad = len(palabras) // 2
                apellidos = palabras[:mitad]
                nombres = palabras[mitad:]
                return f"{' '.join(nombres)} {' '.join(apellidos)}"
            
        except Exception as e:
            logger.warning(f"⚠️ Error reordenando nombre '{nombre}': {str(e)}")
            return nombre
    
    def _format_name(self, nombre):
        """Formatea el nombre con primera letra en mayúscula y resto en minúsculas"""
        try:
            if not nombre:
                return nombre
            
            nombre_reordenado = self._reorder_name(nombre)
            palabras = nombre_reordenado.split()
            
            palabras_formateadas = []
            for palabra in palabras:
                if palabra:
                    palabra_formateada = palabra[0].upper() + palabra[1:].lower()
                    palabras_formateadas.append(palabra_formateada)
            
            return " ".join(palabras_formateadas)
            
        except Exception as e:
            logger.warning(f"⚠️ Error formateando nombre '{nombre}': {str(e)}")
            return nombre
    
    def _convert_date_to_n8n_format(self, fecha_dd_mm):
        """Convierte fecha DD/MM a formato YYYY-MM-DD usando siempre el año de ejecución"""
        try:
            if '/' not in fecha_dd_mm:
                return fecha_dd_mm
            
            partes = fecha_dd_mm.split('/')
            if len(partes) != 2:
                return fecha_dd_mm
            
            dia = int(partes[0])
            mes = int(partes[1])
            
            año_ejecucion = datetime.now().year
            fecha_completa = datetime(año_ejecucion, mes, dia)
            
            return fecha_completa.strftime("%Y-%m-%d")
            
        except Exception as e:
            logger.warning(f"⚠️ Error convirtiendo fecha {fecha_dd_mm}: {str(e)}")
            return fecha_dd_mm
    
    def _remove_duplicates(self, data):
        """Elimina registros duplicados basados en nombre y celular"""
        try:
            seen = set()
            unique_data = []
            duplicates_removed = 0
            
            for entry in data:
                key = (entry.get('nombre', ''), entry.get('celular', ''))
                
                if key not in seen:
                    seen.add(key)
                    unique_data.append(entry)
                else:
                    duplicates_removed += 1
                    logger.info(f"🔄 Duplicado eliminado: {entry.get('nombre', 'Sin nombre')}")
            
            if duplicates_removed > 0:
                logger.info(f"✅ Se eliminaron {duplicates_removed} registros duplicados")
            
            return unique_data
            
        except Exception as e:
            logger.warning(f"⚠️ Error eliminando duplicados: {str(e)}")
            return data
    
    def run_scraping(self, task_id):
        """Ejecuta el scraping completo"""
        try:
            logger.info(f"🚀 Iniciando scraping para tarea {task_id}...")
            
            # Configurar driver según el entorno
            headless = os.getenv('HEADLESS', 'true').lower() == 'true'
            self.setup_driver(headless=headless)
            
            if not self.login():
                scraping_results[task_id] = {
                    'status': 'error',
                    'message': 'Error durante el login',
                    'data': None
                }
                return
            
            if not self.navigate_to_birthdays():
                scraping_results[task_id] = {
                    'status': 'error',
                    'message': 'Error navegando a la página de cumpleaños',
                    'data': None
                }
                return
            
            birthdays_data = self.extract_birthday_data()
            
            if birthdays_data:
                data_unique = self._remove_duplicates(birthdays_data)
                
                scraping_results[task_id] = {
                    'status': 'success',
                    'message': f'Scraping completado exitosamente',
                    'data': data_unique,
                    'total_records': len(data_unique),
                    'timestamp': datetime.now().isoformat()
                }
                logger.info(f"✅ Scraping completado para tarea {task_id}: {len(data_unique)} registros")
            else:
                scraping_results[task_id] = {
                    'status': 'error',
                    'message': 'No se pudieron extraer datos',
                    'data': None
                }
                logger.error(f"❌ No se pudieron extraer datos para tarea {task_id}")
                
        except Exception as e:
            logger.error(f"❌ Error general en scraping para tarea {task_id}: {str(e)}")
            scraping_results[task_id] = {
                'status': 'error',
                'message': f'Error general: {str(e)}',
                'data': None
            }
            
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🔒 Navegador cerrado")

def worker():
    """Worker que procesa las tareas de scraping en segundo plano"""
    while True:
        try:
            task_id = scraping_queue.get()
            if task_id is None:
                break
            
            scraper = HermessAPIScraper()
            scraper.run_scraping(task_id)
            
            scraping_queue.task_done()
            
        except Exception as e:
            logger.error(f"Error en worker: {str(e)}")
            scraping_queue.task_done()

# Iniciar worker en segundo plano
worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()

@app.route('/')
def home():
    """Endpoint principal con información de la API"""
    return jsonify({
        'message': 'API Scraper para HermessApp - Lista de Cumpleaños',
        'version': '1.0.0',
        'endpoints': {
            '/scrape': 'POST - Iniciar scraping de cumpleaños',
            '/status/<task_id>': 'GET - Verificar estado de una tarea',
            '/download/<task_id>': 'GET - Descargar archivo JSON con los datos',
            '/health': 'GET - Verificar estado de la API'
        },
        'environment': os.getenv('ENVIRONMENT', 'unknown')
    })

@app.route('/scrape', methods=['POST'])
def start_scraping():
    """Inicia el proceso de scraping"""
    try:
        # Generar ID único para la tarea
        task_id = f"task_{int(time.time())}"
        
        # Agregar tarea a la cola
        scraping_queue.put(task_id)
        
        # Inicializar resultado
        scraping_results[task_id] = {
            'status': 'processing',
            'message': 'Scraping iniciado',
            'data': None
        }
        
        logger.info(f"📋 Tarea de scraping {task_id} agregada a la cola")
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Scraping iniciado exitosamente',
            'status_url': f'/status/{task_id}',
            'download_url': f'/download/{task_id}'
        }), 202
        
    except Exception as e:
        logger.error(f"Error iniciando scraping: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/status/<task_id>')
def get_status(task_id):
    """Obtiene el estado de una tarea de scraping"""
    try:
        if task_id not in scraping_results:
            return jsonify({
                'success': False,
                'error': 'Tarea no encontrada'
            }), 404
        
        result = scraping_results[task_id]
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'status': result['status'],
            'message': result['message'],
            'total_records': result.get('total_records', 0),
            'timestamp': result.get('timestamp'),
            'has_data': result['data'] is not None
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo estado: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/download/<task_id>')
def download_data(task_id):
    """Descarga los datos extraídos en formato JSON"""
    try:
        if task_id not in scraping_results:
            return jsonify({
                'success': False,
                'error': 'Tarea no encontrada'
            }), 404
        
        result = scraping_results[task_id]
        
        if result['status'] != 'success' or not result['data']:
            return jsonify({
                'success': False,
                'error': 'No hay datos disponibles para descargar'
            }), 400
        
        # Crear archivo temporal
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
        
        # Preparar datos para exportar
        meses = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        mes_actual = meses[datetime.now().month]
        
        output_data = {
            "metadata": {
                "fecha_extraccion": datetime.now().isoformat(),
                "total_registros": len(result['data']),
                "formato_fecha": "YYYY-MM-DD",
                "año_ejecucion": datetime.now().year,
                "fuente": "HermessApp",
                "descripcion": "Lista de cumpleaños de pacientes extraída automáticamente",
                "task_id": task_id
            },
            "cumpleanos": result['data']
        }
        
        json.dump(output_data, temp_file, ensure_ascii=False, indent=2)
        temp_file.close()
        
        filename = f"cumpleanos_{mes_actual}_{task_id}.json"
        
        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Error descargando datos: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health')
def health_check():
    """Verifica el estado de la API"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'environment': os.getenv('ENVIRONMENT', 'unknown'),
        'queue_size': scraping_queue.qsize(),
        'active_tasks': len([r for r in scraping_results.values() if r['status'] == 'processing'])
    })

@app.route('/cleanup', methods=['POST'])
def cleanup_old_tasks():
    """Limpia tareas antiguas para liberar memoria"""
    try:
        current_time = time.time()
        cleaned_count = 0
        
        # Eliminar tareas más antiguas que 1 hora
        tasks_to_remove = []
        for task_id, result in scraping_results.items():
            if result.get('timestamp'):
                task_time = datetime.fromisoformat(result['timestamp']).timestamp()
                if current_time - task_time > 3600:  # 1 hora
                    tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del scraping_results[task_id]
            cleaned_count += 1
        
        logger.info(f"🧹 Limpieza completada: {cleaned_count} tareas eliminadas")
        
        return jsonify({
            'success': True,
            'cleaned_tasks': cleaned_count,
            'remaining_tasks': len(scraping_results)
        })
        
    except Exception as e:
        logger.error(f"Error en limpieza: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Configurar variables de entorno por defecto
    if not os.getenv('ENVIRONMENT'):
        os.environ['ENVIRONMENT'] = 'shared_hosting'  # Por defecto hosting compartido
    
    if not os.getenv('HEADLESS'):
        os.environ['HEADLESS'] = 'true'  # Por defecto headless
    
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"🚀 Iniciando API Scraper en puerto {port}")
    logger.info(f"🌍 Entorno: {os.getenv('ENVIRONMENT')}")
    logger.info(f"👻 Headless: {os.getenv('HEADLESS')}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
