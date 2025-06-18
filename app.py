from flask import Flask, render_template, request, redirect, url_for, g
import os # ### CAMBIO PARA POSTGRESQL ###
import psycopg2 # ### CAMBIO PARA POSTGRESQL ###
from psycopg2.extras import RealDictCursor # ### CAMBIO PARA POSTGRESQL ###

# ### CAMBIO PARA POSTGRESQL: Eliminamos la importación de database.py y DATABASE ###
# from database import init_db, DATABASE

app = Flask(__name__)

# ### CAMBIO PARA POSTGRESQL: Configuración de la base de datos para PostgreSQL ###
# Render proveerá esta URL como una variable de entorno llamada DATABASE_URL.
# Para desarrollo local, si quieres probar con PostgreSQL, necesitarías configurar esta variable
# en tu entorno antes de ejecutar la app (ej. set DATABASE_URL="postgresql://user:pass@host:port/dbname" en Windows,
# o export DATABASE_URL="..." en Linux/macOS).
# Si no la configuras localmente, la aplicación lanzará un error al intentar conectarse
# a la base de datos, lo cual es esperado para obligarte a usar PostgreSQL en producción.
DATABASE_URL = os.environ.get('DATABASE_URL')

# ### CAMBIO PARA POSTGRESQL: Función para obtener la conexión a la base de datos (PostgreSQL) ###
def connect_db():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL no está configurada. Necesaria para la conexión a PostgreSQL.")
    
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def get_db():
    if 'db' not in g:
        g.db = connect_db()
        # Usar RealDictCursor para acceder a las columnas por nombre como en sqlite3.Row
        g.db.cursor_factory = RealDictCursor
    return g.db

# Función para cerrar la conexión a la base de datos al finalizar la solicitud
@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# ### CAMBIO PARA POSTGRESQL: Función para inicializar las tablas en PostgreSQL ###
# Esta función creará las tablas si no existen.
# Se ejecutará una vez al inicio de la aplicación en Render.
def init_db_postgres():
    with get_db() as db:
        cursor = db.cursor()
        # Tabla de Pacientes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id SERIAL PRIMARY KEY, -- SERIAL PRIMARY KEY para PostgreSQL (autoincremental)
                name TEXT NOT NULL,
                dob TEXT,
                gender TEXT,
                address TEXT,
                phone TEXT,
                email TEXT
            )
        ''')
        # Tabla de Historias Clínicas
        # SERIAL PRIMARY KEY para id en PostgreSQL, y ON DELETE CASCADE para la clave foránea
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medical_records (
                id SERIAL PRIMARY KEY, -- SERIAL PRIMARY KEY para PostgreSQL
                patient_id INTEGER NOT NULL,
                record_date TEXT NOT NULL,
                reason TEXT,
                diagnosis TEXT,
                treatment TEXT,
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE
            )
        ''')
        db.commit()

# ### CAMBIO PARA POSTGRESQL: Inicializar la base de datos al iniciar la aplicación ###
with app.app_context():
    try:
        init_db_postgres()
    except Exception as e:
        print(f"Error inicializando DB (puede que las tablas ya existan o haya otro error): {e}")

@app.route('/')
def index():
    db = get_db()
    search_query = request.args.get('search', '').strip()
    
    if search_query:
        # ### CAMBIO PARA POSTGRESQL: Usar %s como marcador de posición para LIKE ###
        patients = db.execute('SELECT * FROM patients WHERE LOWER(name) LIKE %s ORDER BY name', 
                              ('%' + search_query.lower() + '%',)).fetchall()
    else:
        patients = db.execute('SELECT * FROM patients ORDER BY name').fetchall()
    
    return render_template('index.html', patients=patients, search_query=search_query)

@app.route('/add_patient', methods=('GET', 'POST'))
def add_patient():
    if request.method == 'POST':
        name = request.form['name']
        dob = request.form['dob']
        gender = request.form['gender']
        address = request.form['address']
        phone = request.form['phone']
        email = request.form['email']

        db = get_db()
        # ### CAMBIO PARA POSTGRESQL: Usar %s como marcadores de posición ###
        db.execute('INSERT INTO patients (name, dob, gender, address, phone, email) VALUES (%s, %s, %s, %s, %s, %s)',
                   (name, dob, gender, address, phone, email))
        db.commit()
        return redirect(url_for('index'))
    return render_template('add_patient.html')

@app.route('/patient/<int:patient_id>')
def patient_details(patient_id):
    db = get_db()
    # ### CAMBIO PARA POSTGRESQL: Usar %s como marcador de posición ###
    patient = db.execute('SELECT * FROM patients WHERE id = %s', (patient_id,)).fetchone()
    # ### CAMBIO PARA POSTGRESQL: Usar %s como marcador de posición ###
    medical_records = db.execute('SELECT * FROM medical_records WHERE patient_id = %s ORDER BY record_date DESC', (patient_id,)).fetchall()

    if patient is None:
        return "Paciente no encontrado", 404
    
    return render_template('patient_details.html', patient=patient, medical_records=medical_records)

@app.route('/add_medical_record/<int:patient_id>', methods=('GET', 'POST'))
def add_medical_record(patient_id):
    db = get_db()
    # ### CAMBIO PARA POSTGRESQL: Usar %s como marcador de posición ###
    patient = db.execute('SELECT * FROM patients WHERE id = %s', (patient_id,)).fetchone()

    if patient is None:
        return "Paciente no encontrado", 404

    if request.method == 'POST':
        record_date = request.form['record_date']
        reason = request.form['reason']
        diagnosis = request.form['diagnosis']
        treatment = request.form['treatment']
        notes = request.form['notes']

        db.execute('INSERT INTO medical_records (patient_id, record_date, reason, diagnosis, treatment, notes) VALUES (%s, %s, %s, %s, %s, %s)',
                   (patient_id, record_date, reason, diagnosis, treatment, notes))
        db.commit()
        return redirect(url_for('patient_details', patient_id=patient_id))
    
    return render_template('add_medical_record.html', patient=patient)

@app.route('/edit_patient/<int:patient_id>', methods=('GET', 'POST'))
def edit_patient(patient_id):
    db = get_db()
    # ### CAMBIO PARA POSTGRESQL: Usar %s como marcador de posición ###
    patient = db.execute('SELECT * FROM patients WHERE id = %s', (patient_id,)).fetchone()

    if patient is None:
        return "Paciente no encontrado", 404

    if request.method == 'POST':
        name = request.form['name']
        dob = request.form['dob']
        gender = request.form['gender']
        address = request.form['address']
        phone = request.form['phone']
        email = request.form['email']

        db.execute('''
            UPDATE patients SET name = %s, dob = %s, gender = %s, address = %s, phone = %s, email = %s
            WHERE id = %s
        ''', (name, dob, gender, address, phone, email, patient_id)) # ### CAMBIO PARA POSTGRESQL ###
        db.commit()
        return redirect(url_for('patient_details', patient_id=patient_id))
    
    return render_template('edit_patient.html', patient=patient)

@app.route('/delete_patient/<int:patient_id>', methods=('POST',))
def delete_patient(patient_id):
    db = get_db()
    # ### CAMBIO PARA POSTGRESQL: Usar %s como marcador de posición ###
    # Si la base de datos tiene ON DELETE CASCADE, esta línea es redundante pero segura
    db.execute('DELETE FROM medical_records WHERE patient_id = %s', (patient_id,)) 
    # ### CAMBIO PARA POSTGRESQL: Usar %s como marcador de posición ###
    db.execute('DELETE FROM patients WHERE id = %s', (patient_id,))
    db.commit()
    return redirect(url_for('index'))


@app.route('/edit_medical_record/<int:record_id>', methods=('GET', 'POST'))
def edit_medical_record(record_id):
    db = get_db()
    # ### CAMBIO PARA POSTGRESQL: Usar %s como marcador de posición ###
    record = db.execute('SELECT * FROM medical_records WHERE id = %s', (record_id,)).fetchone()

    if record is None:
        return "Historia clínica no encontrada", 404

    patient_id = record['patient_id']
    # ### CAMBIO PARA POSTGRESQL: Usar %s como marcador de posición ###
    patient = db.execute('SELECT * FROM patients WHERE id = %s', (patient_id,)).fetchone()

    if request.method == 'POST':
        record_date = request.form['record_date']
        reason = request.form['reason']
        diagnosis = request.form['diagnosis']
        treatment = request.form['treatment']
        notes = request.form['notes']

        db.execute('''
            UPDATE medical_records SET record_date = %s, reason = %s, diagnosis = %s, treatment = %s, notes = %s
            WHERE id = %s
        ''', (record_date, reason, diagnosis, treatment, notes, record_id)) # ### CAMBIO PARA POSTGRESQL ###
        db.commit()
        return redirect(url_for('patient_details', patient_id=patient_id))
    
    return render_template('edit_medical_record.html', record=record, patient=patient)


@app.route('/delete_medical_record/<int:record_id>', methods=('POST',))
def delete_medical_record(record_id):
    db = get_db()
    # ### CAMBIO PARA POSTGRESQL: Usar %s como marcador de posición ###
    record = db.execute('SELECT patient_id FROM medical_records WHERE id = %s', (record_id,)).fetchone()
    if record is None:
        return "Historia clínica no encontrada", 404
    
    patient_id = record['patient_id'] # Guardamos el patient_id antes de borrar
    
    # ### CAMBIO PARA POSTGRESQL: Usar %s como marcador de posición ###
    db.execute('DELETE FROM medical_records WHERE id = %s', (record_id,))
    db.commit()
    return redirect(url_for('patient_details', patient_id=patient_id))


if __name__ == '__main__':
    # ### CAMBIO PARA POSTGRESQL: Aquí puedes decidir cómo quieres ejecutarlo localmente ###
    # Si quieres probarlo con PostgreSQL localmente, asegúrate de tener un servidor PostgreSQL
    # corriendo y de haber configurado la variable de entorno DATABASE_URL antes de ejecutar.
    # Si DATABASE_URL no está configurada, el programa lanzará un ValueError al intentar conectarse.
    app.run(debug=True)