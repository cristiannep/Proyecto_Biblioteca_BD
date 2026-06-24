# ============================================================================
# SISTEMA DE PRÉSTAMO DE LIBROS PARA BIBLIOTECA ESCOLAR
# Aplicación Flask con Conexión a PostgreSQL
# ============================================================================

from flask import Flask, render_template, request, jsonify, redirect, url_for
import psycopg2
from psycopg2 import sql, Error
from datetime import datetime, timedelta
import logging

# ============================================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# ============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'biblioteca_escolar_2024'

# Configuración de logging para registrar errores
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN DE LA CONEXIÓN A POSTGRESQL
# ============================================================================

DATABASE_CONFIG = {
    'host': 'localhost',
    'database': 'biblioteca_escolar',
    'user': 'postgres',
    'password': 'tu_contraseña_postgres',  # Cambia esto con tu contraseña
    'port': 5432
}

def get_db_connection():
    """
    Establece una conexión con la base de datos PostgreSQL.
    Retorna: conexión de psycopg2 o None si hay error.
    """
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        return conn
    except Error as e:
        logger.error(f"Error al conectar a la base de datos: {e}")
        return None

# ============================================================================
# RUTA: PÁGINA PRINCIPAL
# ============================================================================

@app.route('/')
def index():
    """
    Carga la página principal con información general del sistema.
    """
    return render_template('index.html')

# ============================================================================
# RUTAS CRUD: LIBROS
# ============================================================================

@app.route('/libros', methods=['GET'])
def obtener_libros():
    """
    Obtiene la lista de todos los libros disponibles en la biblioteca.
    Retorna: JSON con los datos de los libros o error.
    """
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        
        # Consulta para obtener libros con información del autor
        query = """
            SELECT l.id_libro, l.titulo, a.nombre, a.apellido, 
                   l.isbn, l.anio_publicacion, l.cantidad_disponible,
                   l.estado
            FROM libros l
            INNER JOIN autores a ON l.id_autor = a.id_autor
            ORDER BY l.titulo ASC;
        """
        
        cur.execute(query)
        libros = cur.fetchall()
        
        # Convertir resultados a formato JSON
        libros_list = []
        for libro in libros:
            libros_list.append({
                'id_libro': libro[0],
                'titulo': libro[1],
                'autor': f"{libro[2]} {libro[3]}",
                'isbn': libro[4],
                'anio_publicacion': libro[5],
                'cantidad_disponible': libro[6],
                'estado': libro[7]
            })
        
        cur.close()
        return jsonify(libros_list), 200
    
    except Error as e:
        logger.error(f"Error al obtener libros: {e}")
        return jsonify({'error': 'Error al obtener libros'}), 500
    finally:
        conn.close()

@app.route('/libro/<int:id_libro>', methods=['GET'])
def obtener_libro(id_libro):
    """
    Obtiene los detalles de un libro específico.
    Parámetro: id_libro (ID del libro)
    Retorna: JSON con datos del libro.
    """
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    try:
        cur = conn.cursor()
        query = """
            SELECT l.id_libro, l.titulo, a.nombre, a.apellido, 
                   l.isbn, l.anio_publicacion, l.cantidad_disponible,
                   l.estado
            FROM libros l
            INNER JOIN autores a ON l.id_autor = a.id_autor
            WHERE l.id_libro = %s;
        """
        
        cur.execute(query, (id_libro,))
        libro = cur.fetchone()
        
        if libro is None:
            return jsonify({'error': 'Libro no encontrado'}), 404
        
        libro_dict = {
            'id_libro': libro[0],
            'titulo': libro[1],
            'autor': f"{libro[2]} {libro[3]}",
            'isbn': libro[4],
            'anio_publicacion': libro[5],
            'cantidad_disponible': libro[6],
            'estado': libro[7]
        }
        
        cur.close()
        return jsonify(libro_dict), 200
    
    except Error as e:
        logger.error(f"Error al obtener libro: {e}")
        return jsonify({'error': 'Error al obtener libro'}), 500
    finally:
        conn.close()

@app.route('/libro/crear', methods=['POST'])
def crear_libro():
    """
    Crea un nuevo libro en la biblioteca.
    Parámetros esperados: titulo, id_autor, isbn, anio_publicacion, cantidad_total
    Retorna: JSON con confirmación o error.
    """
    data = request.json
    
    # Validar que los parámetros requeridos estén presentes
    if not all(key in data for key in ['titulo', 'id_autor', 'isbn', 'cantidad_total']):
        return jsonify({'error': 'Faltan parámetros requeridos'}), 400
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    try:
        cur = conn.cursor()
        
        query = """
            INSERT INTO libros (titulo, id_autor, isbn, anio_publicacion, cantidad_total, cantidad_disponible, estado)
            VALUES (%s, %s, %s, %s, %s, %s, 'Disponible')
            RETURNING id_libro;
        """
        
        cur.execute(query, (
            data['titulo'],
            data['id_autor'],
            data['isbn'],
            data.get('anio_publicacion'),
            data['cantidad_total']
        ))
        
        id_libro = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        return jsonify({'mensaje': 'Libro creado exitosamente', 'id_libro': id_libro}), 201
    
    except Error as e:
        logger.error(f"Error al crear libro: {e}")
        conn.rollback()
        return jsonify({'error': 'Error al crear libro'}), 500
    finally:
        conn.close()

@app.route('/libro/editar/<int:id_libro>', methods=['PUT'])
def editar_libro(id_libro):
    """
    Edita los datos de un libro existente.
    Parámetro: id_libro (ID del libro)
    Parámetros esperados: titulo, isbn, anio_publicacion (opcionales)
    Retorna: JSON con confirmación o error.
    """
    data = request.json
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    try:
        cur = conn.cursor()
        
        # Construir la consulta dinámicamente según los parámetros recibidos
        updates = []
        params = []
        
        if 'titulo' in data:
            updates.append('titulo = %s')
            params.append(data['titulo'])
        if 'isbn' in data:
            updates.append('isbn = %s')
            params.append(data['isbn'])
        if 'anio_publicacion' in data:
            updates.append('anio_publicacion = %s')
            params.append(data['anio_publicacion'])
        
        if not updates:
            return jsonify({'error': 'No hay datos para actualizar'}), 400
        
        params.append(id_libro)
        
        query = f"UPDATE libros SET {', '.join(updates)} WHERE id_libro = %s;"
        
        cur.execute(query, params)
        conn.commit()
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Libro no encontrado'}), 404
        
        cur.close()
        return jsonify({'mensaje': 'Libro actualizado exitosamente'}), 200
    
    except Error as e:
        logger.error(f"Error al editar libro: {e}")
        conn.rollback()
        return jsonify({'error': 'Error al editar libro'}), 500
    finally:
        conn.close()

@app.route('/libro/eliminar/<int:id_libro>', methods=['DELETE'])
def eliminar_libro(id_libro):
    """
    Elimina un libro de la base de datos.
    Parámetro: id_libro (ID del libro)
    Retorna: JSON con confirmación o error.
    """
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    try:
        cur = conn.cursor()
        
        query = "DELETE FROM libros WHERE id_libro = %s;"
        cur.execute(query, (id_libro,))
        conn.commit()
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Libro no encontrado'}), 404
        
        cur.close()
        return jsonify({'mensaje': 'Libro eliminado exitosamente'}), 200
    
    except Error as e:
        logger.error(f"Error al eliminar libro: {e}")
        conn.rollback()
        return jsonify({'error': 'Error al eliminar libro'}), 500
    finally:
        conn.close()

# ============================================================================
# RUTAS CRUD: ALUMNOS
# ============================================================================

@app.route('/alumnos', methods=['GET'])
def obtener_alumnos():
    """
    Obtiene la lista de todos los alumnos registrados.
    Retorna: JSON con los datos de los alumnos.
    """
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    try:
        cur = conn.cursor()
        
        query = """
            SELECT id_alumno, nombre, apellido, email, grado, activo
            FROM alumnos
            ORDER BY apellido, nombre ASC;
        """
        
        cur.execute(query)
        alumnos = cur.fetchall()
        
        alumnos_list = []
        for alumno in alumnos:
            alumnos_list.append({
                'id_alumno': alumno[0],
                'nombre': alumno[1],
                'apellido': alumno[2],
                'email': alumno[3],
                'grado': alumno[4],
                'activo': alumno[5]
            })
        
        cur.close()
        return jsonify(alumnos_list), 200
    
    except Error as e:
        logger.error(f"Error al obtener alumnos: {e}")
        return jsonify({'error': 'Error al obtener alumnos'}), 500
    finally:
        conn.close()

# ============================================================================
# RUTA: REALIZAR PRÉSTAMO (OPERACIÓN PRINCIPAL)
# ============================================================================

@app.route('/prestamo/realizar', methods=['POST'])
def realizar_prestamo():
    """
    Realiza un nuevo préstamo de un libro a un alumno.
    Este endpoint dispara el trigger trig_verificar_prestamo automáticamente.
    
    Parámetros esperados (JSON):
    - id_alumno: ID del alumno
    - id_libro: ID del libro
    - dias_prestamo: Cantidad de días para el préstamo (default: 14)
    
    Retorna: JSON con confirmación o mensaje de error (del trigger).
    
    NOTA: El trigger verificará automáticamente:
    - Que el alumno no tenga 3 libros en préstamo activo
    - Que el alumno no tenga multas sin pagar
    - Que el libro esté disponible
    
    Si se cumple, el trigger también cambiará automáticamente el estado del libro a 'Prestado'.
    """
    data = request.json
    
    # Validar parámetros requeridos
    if not all(key in data for key in ['id_alumno', 'id_libro']):
        return jsonify({'error': 'Faltan parámetros: id_alumno e id_libro requeridos'}), 400
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        
        # Calcular fecha de devolución esperada (default: 14 días)
        dias_prestamo = data.get('dias_prestamo', 14)
        fecha_devolucion = datetime.now() + timedelta(days=dias_prestamo)
        
        # Insertar el préstamo
        # El TRIGGER trig_verificar_prestamo se ejecutará automáticamente ANTES
        query = """
            INSERT INTO prestamos (id_alumno, id_libro, fecha_devolucion_esperada, estado)
            VALUES (%s, %s, %s, 'Activo')
            RETURNING id_prestamo;
        """
        
        cur.execute(query, (
            data['id_alumno'],
            data['id_libro'],
            fecha_devolucion.date()
        ))
        
        id_prestamo = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        return jsonify({
            'mensaje': 'Préstamo realizado exitosamente',
            'id_prestamo': id_prestamo,
            'fecha_devolucion_esperada': fecha_devolucion.strftime('%Y-%m-%d')
        }), 201
    
    except psycopg2.IntegrityError as e:
        conn.rollback()
        logger.error(f"Error de integridad: {e}")
        return jsonify({'error': 'El alumno o libro no existe'}), 400
    
    except psycopg2.ProgrammingError as e:
        conn.rollback()
        # Capturar mensajes del trigger
        error_msg = str(e)
        if 'máximo' in error_msg.lower() or 'multa' in error_msg.lower():
            return jsonify({'error': error_msg.split('\n')[-1]}), 403
        logger.error(f"Error en la base de datos: {e}")
        return jsonify({'error': 'Error al realizar el préstamo'}), 500
    
    except Error as e:
        conn.rollback()
        logger.error(f"Error al realizar préstamo: {e}")
        return jsonify({'error': 'Error al realizar el préstamo'}), 500
    finally:
        conn.close()

# ============================================================================
# RUTA: DEVOLVER LIBRO (PROCEDIMIENTO ALMACENADO)
# ============================================================================

@app.route('/prestamo/devolver/<int:id_prestamo>', methods=['POST'])
def devolver_libro(id_prestamo):
    """
    Realiza la devolución de un libro y calcula automáticamente las multas.
    Este endpoint llama al procedimiento almacenado 'realizar_devolucion'.
    
    Parámetro: id_prestamo (ID del préstamo)
    
    Retorna: JSON con confirmación, multa asignada (si aplica), o error.
    
    NOTA: El procedimiento realiza:
    - Actualiza la fecha de devolución real
    - Calcula multa si hay atraso ($1.000 por día)
    - Libera el libro (aumenta cantidad_disponible)
    - Registra la multa en la tabla de multas
    """
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    try:
        cur = conn.cursor()
        
        # Llamar al procedimiento almacenado realizar_devolucion
        # Este procedimiento maneja toda la lógica de devolución y cálculo de multas
        cur.callproc('realizar_devolucion', (id_prestamo,))
        conn.commit()
        
        # Obtener información del préstamo actualizado para la respuesta
        query = """
            SELECT p.fecha_devolucion_real, p.multa_asignada, l.titulo
            FROM prestamos p
            INNER JOIN libros l ON p.id_libro = l.id_libro
            WHERE p.id_prestamo = %s;
        """
        
        cur.execute(query, (id_prestamo,))
        resultado = cur.fetchone()
        
        if resultado is None:
            return jsonify({'error': 'Préstamo no encontrado'}), 404
        
        cur.close()
        
        return jsonify({
            'mensaje': 'Devolución realizada exitosamente',
            'fecha_devolucion': resultado[0].strftime('%Y-%m-%d'),
            'multa_asignada': float(resultado[1]),
            'libro': resultado[2]
        }), 200
    
    except psycopg2.ProgrammingError as e:
        conn.rollback()
        error_msg = str(e)
        logger.error(f"Error del procedimiento: {e}")
        return jsonify({'error': error_msg.split('\n')[-1]}), 400
    
    except Error as e:
        conn.rollback()
        logger.error(f"Error al devolver libro: {e}")
        return jsonify({'error': 'Error al procesar la devolución'}), 500
    finally:
        conn.close()

# ============================================================================
# RUTA: OBTENER PRÉSTAMOS DEL ALUMNO
# ============================================================================

@app.route('/prestamos/alumno/<int:id_alumno>', methods=['GET'])
def obtener_prestamos_alumno(id_alumno):
    """
    Obtiene todos los préstamos de un alumno específico.
    Parámetro: id_alumno (ID del alumno)
    Retorna: JSON con lista de préstamos activos y completados.
    """
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    try:
        cur = conn.cursor()
        
        query = """
            SELECT p.id_prestamo, l.titulo, p.fecha_prestamo, 
                   p.fecha_devolucion_esperada, p.fecha_devolucion_real,
                   p.estado, p.multa_asignada
            FROM prestamos p
            INNER JOIN libros l ON p.id_libro = l.id_libro
            WHERE p.id_alumno = %s
            ORDER BY p.fecha_prestamo DESC;
        """
        
        cur.execute(query, (id_alumno,))
        prestamos = cur.fetchall()
        
        prestamos_list = []
        for prestamo in prestamos:
            prestamos_list.append({
                'id_prestamo': prestamo[0],
                'titulo_libro': prestamo[1],
                'fecha_prestamo': prestamo[2].strftime('%Y-%m-%d'),
                'fecha_devolucion_esperada': prestamo[3].strftime('%Y-%m-%d'),
                'fecha_devolucion_real': prestamo[4].strftime('%Y-%m-%d') if prestamo[4] else None,
                'estado': prestamo[5],
                'multa_asignada': float(prestamo[6])
            })
        
        cur.close()
        return jsonify(prestamos_list), 200
    
    except Error as e:
        logger.error(f"Error al obtener préstamos: {e}")
        return jsonify({'error': 'Error al obtener préstamos'}), 500
    finally:
        conn.close()

# ============================================================================
# RUTA: PAGAR MULTA (PROCEDIMIENTO ALMACENADO)
# ============================================================================

@app.route('/multa/pagar/<int:id_multa>', methods=['POST'])
def pagar_multa(id_multa):
    """
    Registra el pago de una multa pendiente.
    Este endpoint llama al procedimiento almacenado 'pagar_multa'.
    
    Parámetro: id_multa (ID de la multa)
    Retorna: JSON con confirmación o error.
    """
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    try:
        cur = conn.cursor()
        
        # Llamar al procedimiento almacenado pagar_multa
        cur.callproc('pagar_multa', (id_multa,))
        conn.commit()
        
        cur.close()
        return jsonify({'mensaje': 'Multa pagada exitosamente'}), 200
    
    except psycopg2.ProgrammingError as e:
        conn.rollback()
        error_msg = str(e)
        logger.error(f"Error del procedimiento: {e}")
        return jsonify({'error': error_msg.split('\n')[-1]}), 400
    
    except Error as e:
        conn.rollback()
        logger.error(f"Error al pagar multa: {e}")
        return jsonify({'error': 'Error al procesar el pago'}), 500
    finally:
        conn.close()

# ============================================================================
# RUTA: OBTENER MULTAS DEL ALUMNO
# ============================================================================

@app.route('/multas/alumno/<int:id_alumno>', methods=['GET'])
def obtener_multas_alumno(id_alumno):
    """
    Obtiene todas las multas de un alumno.
    Parámetro: id_alumno (ID del alumno)
    Retorna: JSON con lista de multas pendientes y pagadas.
    """
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    try:
        cur = conn.cursor()
        
        query = """
            SELECT id_multa, monto, motivo, fecha_generacion, pagada, fecha_pago
            FROM multas
            WHERE id_alumno = %s
            ORDER BY fecha_generacion DESC;
        """
        
        cur.execute(query, (id_alumno,))
        multas = cur.fetchall()
        
        multas_list = []
        for multa in multas:
            multas_list.append({
                'id_multa': multa[0],
                'monto': float(multa[1]),
                'motivo': multa[2],
                'fecha_generacion': multa[3].strftime('%Y-%m-%d %H:%M:%S'),
                'pagada': multa[4],
                'fecha_pago': multa[5].strftime('%Y-%m-%d %H:%M:%S') if multa[5] else None
            })
        
        cur.close()
        return jsonify(multas_list), 200
    
    except Error as e:
        logger.error(f"Error al obtener multas: {e}")
        return jsonify({'error': 'Error al obtener multas'}), 500
    finally:
        conn.close()

# ============================================================================
# MANEJO DE ERRORES GLOBAL
# ============================================================================

@app.errorhandler(404)
def pagina_no_encontrada(error):
    """Maneja errores 404 (página no encontrada)"""
    return jsonify({'error': 'Recurso no encontrado'}), 404

@app.errorhandler(500)
def error_interno(error):
    """Maneja errores 500 (error interno del servidor)"""
    logger.error(f"Error interno del servidor: {error}")
    return jsonify({'error': 'Error interno del servidor'}), 500

# ============================================================================
# EJECUCIÓN DE LA APLICACIÓN
# ============================================================================

if __name__ == '__main__':
    # Ejecutar en modo desarrollo
    # Cambiar debug=False en producción
    app.run(debug=True, host='localhost', port=5000)
