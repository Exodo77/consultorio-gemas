from flask import Flask, render_template, request, redirect, url_for, g, session, flash # Añadir 'session' y 'flash'
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from functools import wraps # Necesario para el decorador @login_required

app = Flask(__name__)
# --- AÑADIR CLAVE SECRETA para la gestión de sesiones de Flask ---
# ¡IMPORTANTE! Genera una clave compleja y única para producción.
# Por ahora, puedes usar una simple para probar, pero cámbiala.
app.config['SECRET_KEY'] = 'una_clave_secreta_facil_de_recordar_pero_insegura_para_prod'

# --- Credenciales de usuario fijas (NO SEGURO PARA PRODUCCIÓN) ---
USUARIO_ADMIN = "Lucreciaco"
PASSWORD_ADMIN = "trapos87"

# --- Configuración de la base de datos ---
DATABASE_URL = os.environ.get('DATABASE_URL')

def connect_db():
    if not DATABASE_URL:
        # Asegúrate de que esta URL funcione en tu entorno local si no usas DATABASE_URL de entorno
        # Por ejemplo, para una DB local: 'postgresql://user:password@localhost:5432/yourdb'
        # O la External URL de Render si tu IP está whitelisted y la necesitas
        # Esto es solo para depuración si DATABASE_URL no está establecida.
        # En Render, DATABASE_URL SIEMPRE estará establecida por Render.
        print("ADVERTENCIA: DATABASE_URL no está configurada. Intentando conexión local de prueba.")
        # Ejemplo de conexión local (MODIFICAR SEGÚN TU CONFIGURACIÓN LOCAL si no usas env var)
        # return psycopg2.connect("dbname=your_local_db user=your_local_user password=your_local_pass host=localhost")
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
    return render_template('login.html') # Necesitarás crear este archivo

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))


# --- RUTAS EXISTENTES (ahora protegidas con @login_required) ---

@app.route('/')
@login_required # <--- AÑADE ESTO para proteger la ruta
def index():
    conn = get_db()
    cursor = conn.cursor()
    search_query = request.args.get('search', '').strip()

    if search_query:
        cursor.execute('SELECT * FROM patients WHERE LOWER(name) LIKE %s ORDER BY name',
                       ('%' + search_query.lower() + '%',))
    else:
        cursor.execute('SELECT * FROM patients ORDER BY name')

    patients = cursor.fetchall()
    cursor.close()

    return render_template('index.html', patients=patients, search_query=search_query)

@app.route('/add_patient', methods=('GET', 'POST'))
@login_required # <--- AÑADE ESTO para proteger la ruta
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
        cursor.execute('INSERT INTO patients (name, dob, gender, address, phone, email) VALUES (%s, %s, %s, %s, %s, %s)',
                       (name, dob, gender, address, phone, email))
        conn.commit()
        cursor.close()

        flash('Paciente añadido exitosamente!', 'success') # Añadido flash message
        return redirect(url_for('index'))
    return render_template('add_patient.html')

@app.route('/patient/<int:patient_id>')
@login_required # <--- AÑADE ESTO para proteger la ruta
def patient_details(patient_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM patients WHERE id = %s', (patient_id,))
    patient = cursor.fetchone()

    cursor.execute('SELECT * FROM medical_records WHERE patient_id = %s ORDER BY record_date DESC', (patient_id,))
    medical_records = cursor.fetchall()

    cursor.close()

    if patient is None:
        flash('Paciente no encontrado.', 'danger') # Añadido flash message
        return redirect(url_for('index')) # Redirige si no se encuentra
        # return "Paciente no encontrado", 404 # Opción anterior, mejor redirigir con flash

    return render_template('patient_details.html', patient=patient, medical_records=medical_records)

@app.route('/add_medical_record/<int:patient_id>', methods=('GET', 'POST'))
@login_required # <--- AÑADE ESTO para proteger la ruta
def add_medical_record(patient_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM patients WHERE id = %s', (patient_id,))
    patient = cursor.fetchone()

    if patient is None:
        cursor.close()
        flash('Paciente no encontrado.', 'danger') # Añadido flash message
        return redirect(url_for('index')) # Redirige si no se encuentra

    if request.method == 'POST':
        record_date = request.form['record_date']
        reason = request.form['reason']
        diagnosis = request.form['diagnosis']
        treatment = request.form['treatment']
        notes = request.form['notes']

        cursor.execute('INSERT INTO medical_records (patient_id, record_date, reason, diagnosis, treatment, notes) VALUES (%s, %s, %s, %s, %s, %s)',
                       (patient_id, record_date, reason, diagnosis, treatment, notes))
        conn.commit()
        cursor.close()

        flash('Historia clínica añadida exitosamente!', 'success') # Añadido flash message
        return redirect(url_for('patient_details', patient_id=patient_id))

    cursor.close()
    return render_template('add_medical_record.html', patient=patient)

@app.route('/edit_patient/<int:patient_id>', methods=('GET', 'POST'))
@login_required # <--- AÑADE ESTO para proteger la ruta
def edit_patient(patient_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM patients WHERE id = %s', (patient_id,))
    patient = cursor.fetchone()

    if patient is None:
        cursor.close()
        flash('Paciente no encontrado.', 'danger') # Añadido flash message
        return redirect(url_for('index')) # Redirige si no se encuentra

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
        cursor.close()

        flash('Paciente actualizado exitosamente!', 'success') # Añadido flash message
        return redirect(url_for('patient_details', patient_id=patient_id))

    cursor.close()
    return render_template('edit_patient.html', patient=patient)

@app.route('/delete_patient/<int:patient_id>', methods=('POST',))
@login_required # <--- AÑADE ESTO para proteger la ruta
def delete_patient(patient_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Si la base de datos tiene ON DELETE CASCADE, esta línea es redundante pero segura
        cursor.execute('DELETE FROM medical_records WHERE patient_id = %s', (patient_id,))
        cursor.execute('DELETE FROM patients WHERE id = %s', (patient_id,))
        conn.commit()
        flash('Paciente y registros eliminados exitosamente!', 'success') # Añadido flash message
    except Exception as e:
        conn.rollback()
        flash(f'Error al eliminar paciente: {e}', 'danger') # Añadido flash message
        print(f"Error al eliminar paciente: {e}")
    finally:
        cursor.close()

    return redirect(url_for('index'))

@app.route('/edit_medical_record/<int:record_id>', methods=('GET', 'POST'))
@login_required # <--- AÑADE ESTO para proteger la ruta
def edit_medical_record(record_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM medical_records WHERE id = %s', (record_id,))
    record = cursor.fetchone()

    if record is None:
        cursor.close()
        flash('Historia clínica no encontrada.', 'danger') # Añadido flash message
        return redirect(url_for('index')) # Redirige si no se encuentra

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
        cursor.close()

        flash('Historia clínica actualizada exitosamente!', 'success') # Añadido flash message
        return redirect(url_for('patient_details', patient_id=patient_id))

    cursor.close()
    return render_template('edit_medical_record.html', record=record, patient=patient)

@app.route('/delete_medical_record/<int:record_id>', methods=('POST',))
@login_required # <--- AÑADE ESTO para proteger la ruta
def delete_medical_record(record_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT patient_id FROM medical_records WHERE id = %s', (record_id,))
    record = cursor.fetchone()
    if record is None:
        cursor.close()
        flash('Historia clínica no encontrada.', 'danger') # Añadido flash message
        return redirect(url_for('index')) # Redirige si no se encuentra

    patient_id = record['patient_id']

    try:
        cursor.execute('DELETE FROM medical_records WHERE id = %s', (record_id,))
        conn.commit()
        flash('Historia clínica eliminada exitosamente!', 'success') # Añadido flash message
    except Exception as e:
        conn.rollback()
        flash(f'Error al eliminar historia clínica: {e}', 'danger') # Añadido flash message
        print(f"Error al eliminar historia clínica: {e}")
    finally:
        cursor.close()

    return redirect(url_for('patient_details', patient_id=patient_id))

if __name__ == '__main__':
    app.run(debug=True)