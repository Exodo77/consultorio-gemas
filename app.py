from flask import Flask, render_template, request, redirect, url_for, g
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')

def connect_db():
    if not DATABASE_URL:
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
    conn = get_db() # Obtener la conexión
    cursor = conn.cursor() # Crear un cursor
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
        conn.commit() # Confirmar los cambios de la creación de tablas
    finally:
        cursor.close() # Asegurarse de cerrar el cursor

with app.app_context():
    try:
        init_db_postgres()
    except Exception as e:
        print(f"Error inicializando DB (puede que las tablas ya existan o haya otro error): {e}")

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor() # Crear un cursor
    search_query = request.args.get('search', '').strip()
    
    if search_query:
        cursor.execute('SELECT * FROM patients WHERE LOWER(name) LIKE %s ORDER BY name', 
                       ('%' + search_query.lower() + '%',))
    else:
        cursor.execute('SELECT * FROM patients ORDER BY name')
    
    patients = cursor.fetchall()
    cursor.close() # Cerrar el cursor
    
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

        conn = get_db()
        cursor = conn.cursor() # Crear un cursor
        cursor.execute('INSERT INTO patients (name, dob, gender, address, phone, email) VALUES (%s, %s, %s, %s, %s, %s)',
                       (name, dob, gender, address, phone, email))
        conn.commit() # Confirmar los cambios
        cursor.close() # Cerrar el cursor
        
        return redirect(url_for('index'))
    return render_template('add_patient.html')

@app.route('/patient/<int:patient_id>')
def patient_details(patient_id):
    conn = get_db()
    cursor = conn.cursor() # Crear un cursor
    
    cursor.execute('SELECT * FROM patients WHERE id = %s', (patient_id,))
    patient = cursor.fetchone()

    cursor.execute('SELECT * FROM medical_records WHERE patient_id = %s ORDER BY record_date DESC', (patient_id,))
    medical_records = cursor.fetchall()
    
    cursor.close() # Cerrar el cursor

    if patient is None:
        return "Paciente no encontrado", 404
    
    return render_template('patient_details.html', patient=patient, medical_records=medical_records)

@app.route('/add_medical_record/<int:patient_id>', methods=('GET', 'POST'))
def add_medical_record(patient_id):
    conn = get_db()
    cursor = conn.cursor() # Crear un cursor

    cursor.execute('SELECT * FROM patients WHERE id = %s', (patient_id,))
    patient = cursor.fetchone()
    
    if patient is None:
        cursor.close() # Cerrar cursor antes de retornar
        return "Paciente no encontrado", 404

    if request.method == 'POST':
        record_date = request.form['record_date']
        reason = request.form['reason']
        diagnosis = request.form['diagnosis']
        treatment = request.form['treatment']
        notes = request.form['notes']

        cursor.execute('INSERT INTO medical_records (patient_id, record_date, reason, diagnosis, treatment, notes) VALUES (%s, %s, %s, %s, %s, %s)',
                       (patient_id, record_date, reason, diagnosis, treatment, notes))
        conn.commit() # Confirmar los cambios
        cursor.close() # Cerrar el cursor
        
        return redirect(url_for('patient_details', patient_id=patient_id))
    
    cursor.close() # Cerrar cursor si es GET
    return render_template('add_medical_record.html', patient=patient)

@app.route('/edit_patient/<int:patient_id>', methods=('GET', 'POST'))
def edit_patient(patient_id):
    conn = get_db()
    cursor = conn.cursor() # Crear un cursor

    cursor.execute('SELECT * FROM patients WHERE id = %s', (patient_id,))
    patient = cursor.fetchone()

    if patient is None:
        cursor.close() # Cerrar cursor antes de retornar
        return "Paciente no encontrado", 404

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
        conn.commit() # Confirmar los cambios
        cursor.close() # Cerrar el cursor
        
        return redirect(url_for('patient_details', patient_id=patient_id))
    
    cursor.close() # Cerrar cursor si es GET
    return render_template('edit_patient.html', patient=patient)

@app.route('/delete_patient/<int:patient_id>', methods=('POST',))
def delete_patient(patient_id):
    conn = get_db()
    cursor = conn.cursor() # Crear un cursor
    
    # Si la base de datos tiene ON DELETE CASCADE, esta línea es redundante pero segura
    cursor.execute('DELETE FROM medical_records WHERE patient_id = %s', (patient_id,)) 
    cursor.execute('DELETE FROM patients WHERE id = %s', (patient_id,))
    conn.commit() # Confirmar los cambios
    cursor.close() # Cerrar el cursor
    
    return redirect(url_for('index'))

@app.route('/edit_medical_record/<int:record_id>', methods=('GET', 'POST'))
def edit_medical_record(record_id):
    conn = get_db()
    cursor = conn.cursor() # Crear un cursor

    cursor.execute('SELECT * FROM medical_records WHERE id = %s', (record_id,))
    record = cursor.fetchone()

    if record is None:
        cursor.close() # Cerrar cursor antes de retornar
        return "Historia clínica no encontrada", 404

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
        conn.commit() # Confirmar los cambios
        cursor.close() # Cerrar el cursor
        
        return redirect(url_for('patient_details', patient_id=patient_id))
    
    cursor.close() # Cerrar cursor si es GET
    return render_template('edit_medical_record.html', record=record, patient=patient)

@app.route('/delete_medical_record/<int:record_id>', methods=('POST',))
def delete_medical_record(record_id):
    conn = get_db()
    cursor = conn.cursor() # Crear un cursor

    cursor.execute('SELECT patient_id FROM medical_records WHERE id = %s', (record_id,))
    record = cursor.fetchone()
    if record is None:
        cursor.close() # Cerrar cursor antes de retornar
        return "Historia clínica no encontrada", 404
    
    patient_id = record['patient_id'] # Guardamos el patient_id antes de borrar
    
    cursor.execute('DELETE FROM medical_records WHERE id = %s', (record_id,))
    conn.commit() # Confirmar los cambios
    cursor.close() # Cerrar el cursor
    
    return redirect(url_for('patient_details', patient_id=patient_id))

if __name__ == '__main__':
    app.run(debug=True)