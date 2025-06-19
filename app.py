from flask import Flask, render_template, request, redirect, url_for, g, session, flash
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'una_clave_secreta_facil_de_recordar_pero_insegura_para_prod' # ¡CAMBIA ESTO!

# --- Credenciales de usuario fijas (NO SEGURO PARA PRODUCCIÓN) ---
USUARIO_ADMIN = "Lucreciaco"
PASSWORD_ADMIN = "trapos87"

# --- Configuración de la base de datos ---
DATABASE_URL = os.environ.get('DATABASE_URL')

def connect_db():
    if not DATABASE_URL:
        # Mensaje más claro para el entorno local si DATABASE_URL no está configurada
        print("ADVERTENCIA: La variable de entorno 'DATABASE_URL' no está configurada.")
        print("Para ejecutar localmente, configúrala (ej. en PowerShell: $env:DATABASE_URL='postgres://user:pass@host:port/dbname')")
        raise ValueError("DATABASE_URL no está configurada. Necesaria para la conexión a PostgreSQL.")

    conn = psycopg2.connect(DATABASE_URL)
    return conn

def get_db():
    if 'db' not in g:
        g.db = connect_db()
        g.db.cursor_factory = RealDictCursor
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db_postgres():
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
    finally:
        cursor.close()

with app.app_context():
    try:
        init_db_postgres()
    except Exception as e:
        print(f"Error inicializando DB (puede que las tablas ya existan o haya otro error): {e}")


# --- DECORADOR para requerir inicio de sesión ---
def login_required(f):
    @wraps(f)
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
            flash('¡Sesión iniciada con éxito!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))


# --- RUTA PRINCIPAL CON PAGINACIÓN ---
@app.route('/')
@login_required
def index():
    # --- CAMBIO IMPORTANTE AQUÍ: Obtener la conexión y luego el cursor ---
    conn = get_db()
    cur_db = conn.cursor()
    # --- FIN CAMBIO ---

    # Parámetros de paginación
    page = request.args.get('page', 1, type=int)
    per_page = 10 # Número de pacientes por página
    offset = (page - 1) * per_page

    search_query = request.args.get('search', '').strip()

    try:
        # 1. Obtener el número total de pacientes (para calcular el total de páginas)
        if search_query:
            cur_db.execute('SELECT COUNT(*) FROM patients WHERE LOWER(name) LIKE %s',
                           ('%' + search_query.lower() + '%',))
        else:
            cur_db.execute('SELECT COUNT(*) FROM patients')
        total_patients = cur_db.fetchone()['count']
        total_pages = (total_patients + per_page - 1) // per_page # Cálculo para redondear hacia arriba

        # 2. Obtener los pacientes para la página actual
        if search_query:
            cur_db.execute('SELECT * FROM patients WHERE LOWER(name) LIKE %s ORDER BY name LIMIT %s OFFSET %s',
                           ('%' + search_query.lower() + '%', per_page, offset))
        else:
            cur_db.execute('SELECT * FROM patients ORDER BY name LIMIT %s OFFSET %s',
                           (per_page, offset))

        patients = cur_db.fetchall()
        
    except Exception as e:
        flash(f"Error al cargar pacientes: {e}", "danger")
        patients = [] # Si hay error, la lista de pacientes estará vacía
        total_patients = 0
        total_pages = 0
    finally:
        # El cursor debe cerrarse explícitamente si se abrió dentro de la función.
        # La conexión 'conn' es gestionada por @app.teardown_appcontext.
        if cur_db:
            cur_db.close()


    return render_template('index.html',
                           patients=patients,
                           search_query=search_query,
                           page=page,
                           per_page=per_page,
                           total_pages=total_pages,
                           total_patients=total_patients)

# --- Resto de tus rutas (sin cambios significativos, solo asegúrate de que @login_required esté ahí) ---

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
            conn.rollback()
            flash(f"Error al añadir paciente: {e}", "danger")
            # Renderiza el formulario de nuevo con los datos ingresados
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
        # No cierres la conexión aquí, la gestiona @app.teardown_appcontext

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
        cursor.execute('DELETE FROM medical_records WHERE patient_id = %s', (patient_id,))
        cursor.execute('DELETE FROM patients WHERE id = %s', (patient_id,))
        conn.commit()
        flash('Paciente y registros eliminados exitosamente!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error al eliminar paciente: {e}', 'danger')
        print(f"Error al eliminar paciente: {e}")
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
            return redirect(url_for('index')) # Redirige a index si no encuentra el registro

        patient_id = record['patient_id']
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
        cursor.execute('SELECT patient_id FROM medical_records WHERE id = %s', (record_id,))
        record = cursor.fetchone()
        if record is None:
            flash('Historia clínica no encontrada.', 'danger')
            return redirect(url_for('index'))

        patient_id = record['patient_id']

        cursor.execute('DELETE FROM medical_records WHERE id = %s', (record_id,))
        conn.commit()
        flash('Historia clínica eliminada exitosamente!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error al eliminar historia clínica: {e}', 'danger')
        print(f"Error al eliminar historia clínica: {e}")
    finally:
        if cursor: cursor.close()

    return redirect(url_for('patient_details', patient_id=patient_id))


if __name__ == '__main__':
    app.run(debug=True)