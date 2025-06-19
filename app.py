from flask import Flask, render_template, request, redirect, url_for, g, session, flash
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from functools import wraps

app = Flask(__name__)
# ¡IMPORTANTE! Cambia esto por una clave secreta fuerte y única en producción
# Se recomienda usar una variable de entorno para esto en producción
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una_clave_secreta_facil_de_recordar_pero_insegura_para_prod') 

# --- Credenciales de usuario fijas (NO SEGURO PARA PRODUCCIÓN) ---
# En una aplicación real, esto debería estar en una base de datos con contraseñas hasheadas.
USUARIO_ADMIN = "Lucreciaco"
PASSWORD_ADMIN = "trapos87"

# --- Configuración de la base de datos ---
# La variable DATABASE_URL debe estar configurada en el entorno de Render.
DATABASE_URL = os.environ.get('DATABASE_URL')

def connect_db():
    if not DATABASE_URL:
        # Mensaje más claro para el entorno local si DATABASE_URL no está configurada
        print("ADVERTENCIA: La variable de entorno 'DATABASE_URL' no está configurada.")
        print("Para ejecutar localmente, configúrala (ej. en PowerShell: $env:DATABASE_URL='postgres://user:pass@host:port/dbname')")
        # En producción (Render), esta ValueError hará que la aplicación falle si la variable no está.
        raise ValueError("DATABASE_URL no está configurada. Necesaria para la conexión a PostgreSQL.")

    conn = psycopg2.connect(DATABASE_URL)
    return conn

def get_db():
    # Almacena la conexión a la DB en el objeto 'g' (global para la solicitud)
    # para que cada solicitud use la misma conexión y se cierre correctamente.
    if 'db' not in g:
        g.db = connect_db()
        # Configura el cursor para devolver diccionarios (útil para acceder a columnas por nombre)
        g.db.cursor_factory = RealDictCursor
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    # Cierra la conexión a la base de datos al final de cada contexto de aplicación (solicitud).
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db_postgres():
    # Función para inicializar las tablas de la base de datos.
    # Se ejecuta una vez al inicio de la aplicación.
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                dob TEXT,
                gender TEXT,
                address TEXT,
                phone TEXT,
                email TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medical_records (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER NOT NULL,
                record_date TEXT NOT NULL,
                reason TEXT,
                diagnosis TEXT,
                treatment TEXT,
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
    except Exception as e:
        # Imprime el error en la consola del servidor (útil para depuración en Render logs).
        print(f"Error inicializando DB (puede que las tablas ya existan o haya otro error): {e}")
        # No se usa flash aquí porque no hay un contexto de solicitud activa para el usuario.
    finally:
        # Asegúrate de cerrar el cursor en todos los casos.
        if cursor:
            cursor.close()

# Se ejecuta la inicialización de la DB al cargar la aplicación.
with app.app_context():
    try:
        init_db_postgres()
    except Exception as e:
        print(f"Error general al intentar inicializar la base de datos al iniciar la app: {e}")


# --- DECORADOR para requerir inicio de sesión ---
def login_required(f):
    @wraps(f) # Mantiene el nombre y la documentación de la función original.
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == USUARIO_ADMIN and password == PASSWORD_ADMIN:
            session['logged_in'] = True
            # Mensaje de éxito con categoría 'success' para SweetAlert2
            flash('¡Sesión iniciada con éxito!', 'success')
            return redirect(url_for('index'))
        else:
            # Mensaje de error con categoría 'danger' para SweetAlert2 (se mapea a 'error' en JS)
            flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    # Mensaje informativo con categoría 'info' para SweetAlert2
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))


# --- RUTA PRINCIPAL CON PAGINACIÓN Y BÚSQUEDA ---
@app.route('/')
@login_required
def index():
    conn = get_db()
    cur_db = conn.cursor()

    page = request.args.get('page', 1, type=int)
    per_page = 10 
    offset = (page - 1) * per_page

    search_query = request.args.get('search', '').strip()

    try:
        if search_query:
            cur_db.execute('SELECT COUNT(*) FROM patients WHERE LOWER(name) LIKE %s',
                           ('%' + search_query.lower() + '%',))
        else:
            cur_db.execute('SELECT COUNT(*) FROM patients')
        total_patients = cur_db.fetchone()['count']
        total_pages = (total_patients + per_page - 1) // per_page 

        if search_query:
            cur_db.execute('SELECT * FROM patients WHERE LOWER(name) LIKE %s ORDER BY name LIMIT %s OFFSET %s',
                           ('%' + search_query.lower() + '%', per_page, offset))
        else:
            cur_db.execute('SELECT * FROM patients ORDER BY name LIMIT %s OFFSET %s',
                           (per_page, offset))

        patients = cur_db.fetchall()
        
    except Exception as e:
        # Captura y reporta errores de base de datos para el usuario.
        flash(f"Error al cargar pacientes: {e}", "danger")
        patients = [] # Asegura que la lista de pacientes esté vacía en caso de error.
        total_patients = 0
        total_pages = 0
    finally:
        if cur_db:
            cur_db.close()

    return render_template('index.html',
                           patients=patients,
                           search_query=search_query,
                           page=page,
                           per_page=per_page,
                           total_pages=total_pages,
                           total_patients=total_patients)

# --- RUTAS DE GESTIÓN DE PACIENTES Y REGISTROS ---

@app.route('/add_patient', methods=('GET', 'POST'))
@login_required
def add_patient():
    if request.method == 'POST':
        name = request.form['name']
        dob = request.form['dob']
        gender = request.form['gender']
        address = request.form['address']
        phone = request.form['phone']
        email = request.form['email']

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO patients (name, dob, gender, address, phone, email) VALUES (%s, %s, %s, %s, %s, %s)',
                           (name, dob, gender, address, phone, email))
            conn.commit()
            flash('Paciente añadido exitosamente!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            conn.rollback() # Deshace cualquier cambio en la transacción de la DB.
            flash(f"Error al añadir paciente: {e}", "danger")
            # Renderiza el formulario de nuevo con los datos ingresados para que el usuario no pierda el input
            return render_template('add_patient.html',
                                   patient={'name': name, 'dob': dob, 'gender': gender,
                                            'address': address, 'phone': phone, 'email': email})
        finally:
            if cursor: cursor.close()
    return render_template('add_patient.html', patient=None)

@app.route('/patient/<int:patient_id>')
@login_required
def patient_details(patient_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM patients WHERE id = %s', (patient_id,))
        patient = cursor.fetchone()

        if patient is None:
            flash('Paciente no encontrado.', 'danger')
            return redirect(url_for('index'))

        cursor.execute('SELECT * FROM medical_records WHERE patient_id = %s ORDER BY record_date DESC', (patient_id,))
        medical_records = cursor.fetchall()
    except Exception as e:
        flash(f"Error al cargar detalles del paciente: {e}", "danger")
        patient = None
        medical_records = []
    finally:
        if cursor: cursor.close()

    return render_template('patient_details.html', patient=patient, medical_records=medical_records)


@app.route('/add_medical_record/<int:patient_id>', methods=('GET', 'POST'))
@login_required
def add_medical_record(patient_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM patients WHERE id = %s', (patient_id,))
        patient = cursor.fetchone()

        if patient is None:
            flash('Paciente no encontrado.', 'danger')
            return redirect(url_for('index'))

        if request.method == 'POST':
            record_date = request.form['record_date']
            reason = request.form['reason']
            diagnosis = request.form['diagnosis']
            treatment = request.form['treatment']
            notes = request.form['notes']

            cursor.execute('INSERT INTO medical_records (patient_id, record_date, reason, diagnosis, treatment, notes) VALUES (%s, %s, %s, %s, %s, %s)',
                           (patient_id, record_date, reason, diagnosis, treatment, notes))
            conn.commit()
            flash('Historia clínica añadida exitosamente!', 'success')
            return redirect(url_for('patient_details', patient_id=patient_id))
    except Exception as e:
        conn.rollback()
        flash(f"Error al añadir historia clínica: {e}", "danger")
    finally:
        if cursor: cursor.close()

    return render_template('add_medical_record.html', patient=patient)

@app.route('/edit_patient/<int:patient_id>', methods=('GET', 'POST'))
@login_required
def edit_patient(patient_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM patients WHERE id = %s', (patient_id,))
        patient = cursor.fetchone()

        if patient is None:
            flash('Paciente no encontrado.', 'danger')
            return redirect(url_for('index'))

        if request.method == 'POST':
            name = request.form['name']
            dob = request.form['dob']
            gender = request.form['gender']
            address = request.form['address']
            phone = request.form['phone']
            email = request.form['email']

            cursor.execute('''
                UPDATE patients SET name = %s, dob = %s, gender = %s, address = %s, phone = %s, email = %s
                WHERE id = %s
            ''', (name, dob, gender, address, phone, email, patient_id))
            conn.commit()
            flash('Paciente actualizado exitosamente!', 'success')
            return redirect(url_for('patient_details', patient_id=patient_id))
    except Exception as e:
        conn.rollback()
        flash(f"Error al editar paciente: {e}", "danger")
    finally:
        if cursor: cursor.close()

    return render_template('edit_patient.html', patient=patient)

@app.route('/delete_patient/<int:patient_id>', methods=('POST',))
@login_required
def delete_patient(patient_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Primero eliminar registros médicos asociados
        cursor.execute('DELETE FROM medical_records WHERE patient_id = %s', (patient_id,))
        # Luego eliminar al paciente
        cursor.execute('DELETE FROM patients WHERE id = %s', (patient_id,))
        conn.commit()
        flash('Paciente y registros eliminados exitosamente!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error al eliminar paciente: {e}', 'danger')
        print(f"Error al eliminar paciente: {e}") # Para depuración en consola/logs de Render
    finally:
        if cursor: cursor.close()

    return redirect(url_for('index'))

@app.route('/edit_medical_record/<int:record_id>', methods=('GET', 'POST'))
@login_required
def edit_medical_record(record_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM medical_records WHERE id = %s', (record_id,))
        record = cursor.fetchone()

        if record is None:
            flash('Historia clínica no encontrada.', 'danger')
            return redirect(url_for('index')) # Redirige a index si el registro no existe.

        patient_id = record['patient_id'] # Necesitamos el patient_id para volver a la página de detalles del paciente.
        cursor.execute('SELECT * FROM patients WHERE id = %s', (patient_id,))
        patient = cursor.fetchone()

        if request.method == 'POST':
            record_date = request.form['record_date']
            reason = request.form['reason']
            diagnosis = request.form['diagnosis']
            treatment = request.form['treatment']
            notes = request.form['notes']

            cursor.execute('''
                UPDATE medical_records SET record_date = %s, reason = %s, diagnosis = %s, treatment = %s, notes = %s
                WHERE id = %s
            ''', (record_date, reason, diagnosis, treatment, notes, record_id))
            conn.commit()
            flash('Historia clínica actualizada exitosamente!', 'success')
            return redirect(url_for('patient_details', patient_id=patient_id))
    except Exception as e:
        conn.rollback()
        flash(f'Error al editar historia clínica: {e}', 'danger')
    finally:
        if cursor: cursor.close()

    return render_template('edit_medical_record.html', record=record, patient=patient)

@app.route('/delete_medical_record/<int:record_id>', methods=('POST',))
@login_required
def delete_medical_record(record_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Obtener el patient_id antes de eliminar el registro para poder redirigir correctamente.
        cursor.execute('SELECT patient_id FROM medical_records WHERE id = %s', (record_id,))
        record = cursor.fetchone()
        if record is None:
            flash('Historia clínica no encontrada.', 'danger')
            return redirect(url_for('index')) # Si el registro no existe, redirige a la lista de pacientes.

        patient_id = record['patient_id'] # Guarda el patient_id.

        cursor.execute('DELETE FROM medical_records WHERE id = %s', (record_id,))
        conn.commit()
        flash('Historia clínica eliminada exitosamente!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error al eliminar historia clínica: {e}', 'danger')
        print(f"Error al eliminar historia clínica: {e}") # Para depuración en consola/logs de Render
    finally:
        if cursor: cursor.close()

    return redirect(url_for('patient_details', patient_id=patient_id))


if __name__ == '__main__':
    app.run(debug=True)