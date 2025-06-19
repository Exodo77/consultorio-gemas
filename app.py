# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
from datetime import date
from forms import PatientForm, MedicalRecordForm # <--- IMPORTA TUS FORMULARIOS

# Opcional pero recomendado: Para acceder a las columnas de la BD por nombre
import psycopg2.extras

app = Flask(__name__)
# <--- AÑADE ESTA LÍNEA (Genera una clave fuerte y cámbiala en producción)
app.config['SECRET_KEY'] = 'una_clave_secreta_muy_larga_y_aleatoria_para_flask_wtf'

# Tu función de conexión a la base de datos
# MODIFICADO: Usar DictCursor para acceder a las columnas por nombre
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="dpg-cpqt1f2cn0vc73f1dpt0-a",
            database="consultorio_gemas_1bxx",
            user="consultorio_gemas_1bxx_user",
            password="tu_password_aqui" # <--- ASEGÚRATE DE PONER TU CONTRASEÑA REAL AQUÍ
        )
        # Retorna un cursor que permite acceder a los resultados por nombre de columna (diccionario)
        return conn.cursor(cursor_factory=psycopg2.extras.DictCursor), conn
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        # Considera manejar este error de forma más robusta en un entorno de producción
        return None, None


@app.route('/')
def index():
    conn, db_conn = get_db_connection()
    patients = []
    search_query = request.args.get('search', '')
    if conn is None:
        flash('No se pudo conectar a la base de datos.', 'danger')
        return render_template('index.html', patients=patients, search_query=search_query)

    try:
        if search_query:
            cur = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # Usa DictCursor aquí también
            cur.execute("SELECT * FROM patients WHERE name ILIKE %s ORDER BY name", ('%' + search_query + '%',))
            patients = cur.fetchall()
            cur.close()
        else:
            cur = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # Y aquí
            cur.execute("SELECT * FROM patients ORDER BY name")
            patients = cur.fetchall()
            cur.close()
    except Exception as e:
        flash(f'Error al cargar pacientes: {e}', 'danger')
        print(f"Error al cargar pacientes: {e}")
    finally:
        db_conn.close()

    return render_template('index.html', patients=patients, search_query=search_query)


@app.route('/add_patient', methods=['GET', 'POST'])
def add_patient():
    form = PatientForm() # Instancia el formulario

    if form.validate_on_submit(): # Esta es la validación del servidor
        try:
            name = form.name.data
            dob = form.dob.data
            gender = form.gender.data
            address = form.address.data
            phone = form.phone.data
            email = form.email.data

            # Convierte la fecha a string si es necesario para tu DB (si dob es None, guarda None)
            dob_str = dob.strftime('%Y-%m-%d') if dob else None

            cur, conn = get_db_connection()
            if cur is None:
                flash('No se pudo conectar a la base de datos.', 'danger')
                return render_template('add_patient.html', form=form) # Pasa el formulario de nuevo

            cur.execute(
                "INSERT INTO patients (name, dob, gender, address, phone, email) VALUES (%s, %s, %s, %s, %s, %s)",
                (name, dob_str, gender, address, phone, email)
            )
            conn.commit()
            cur.close()
            conn.close()
            flash('Paciente añadido exitosamente!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Error al añadir paciente: {e}', 'danger')
            print(f"Error al añadir paciente: {e}")
    elif request.method == 'POST': # Si el método es POST pero la validación falla
        flash('Por favor, corrige los errores del formulario.', 'danger')

    return render_template('add_patient.html', form=form) # Pasa el formulario a la plantilla


@app.route('/patient_details/<int:patient_id>')
def patient_details(patient_id):
    cur, conn = get_db_connection()
    if cur is None:
        flash('No se pudo conectar a la base de datos.', 'danger')
        return redirect(url_for('index'))

    patient = None
    medical_records = []
    try:
        # Usa DictCursor para obtener el paciente por nombre de columna
        cur.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
        patient = cur.fetchone()

        if patient:
            # Usa DictCursor para obtener los registros médicos
            cur.execute("SELECT * FROM medical_records WHERE patient_id = %s ORDER BY record_date DESC", (patient_id,))
            medical_records = cur.fetchall()

    except Exception as e:
        flash(f'Error al cargar detalles del paciente: {e}', 'danger')
        print(f"Error al cargar detalles del paciente: {e}")
    finally:
        cur.close()
        conn.close()

    if patient is None:
        flash('Paciente no encontrado.', 'danger')
        return redirect(url_for('index'))

    return render_template('patient_details.html', patient=patient, medical_records=medical_records)


@app.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
def edit_patient(patient_id):
    cur, conn = get_db_connection()
    if cur is None:
        flash('No se pudo conectar a la base de datos.', 'danger')
        return redirect(url_for('index'))

    cur.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
    patient = cur.fetchone()

    if patient is None:
        flash('Paciente no encontrado.', 'danger')
        cur.close()
        conn.close()
        return redirect(url_for('index'))

    # Si el método es GET, pre-llenar el formulario con los datos existentes
    # Si el método es POST y la validación falla, los datos del form ya estarán
    # disponibles para re-renderizar.
    form = PatientForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                name = form.name.data
                dob = form.dob.data
                gender = form.gender.data
                address = form.address.data
                phone = form.phone.data
                email = form.email.data

                dob_str = dob.strftime('%Y-%m-%d') if dob else None

                cur.execute(
                    "UPDATE patients SET name = %s, dob = %s, gender = %s, address = %s, phone = %s, email = %s WHERE id = %s",
                    (name, dob_str, gender, address, phone, email, patient_id)
                )
                conn.commit()
                flash('Paciente actualizado exitosamente!', 'success')
                return redirect(url_for('patient_details', patient_id=patient_id))
            except Exception as e:
                flash(f'Error al actualizar paciente: {e}', 'danger')
                print(f"Error al actualizar paciente: {e}")
        else:
            flash('Por favor, corrige los errores del formulario.', 'danger')
    else: # GET request
        # Convertir DictRow a un objeto para que form.populate_obj o form = Form(obj=...) funcione
        # patient es un DictRow de psycopg2.extras.DictCursor, ya se comporta como un diccionario
        form = PatientForm(obj=patient) # Esto pre-llena el formulario automáticamente

    cur.close()
    conn.close()
    return render_template('edit_patient.html', patient=patient, form=form) # Pasa el formulario

@app.route('/delete_patient/<int:patient_id>', methods=['POST'])
def delete_patient(patient_id):
    cur, conn = get_db_connection()
    if cur is None:
        flash('No se pudo conectar a la base de datos.', 'danger')
        return redirect(url_for('index'))

    try:
        # Eliminar registros médicos primero (si tienes FK on CASCADE DELETE, esto no es necesario)
        cur.execute("DELETE FROM medical_records WHERE patient_id = %s", (patient_id,))
        cur.execute("DELETE FROM patients WHERE id = %s", (patient_id,))
        conn.commit()
        flash('Paciente y todos sus registros eliminados exitosamente!', 'success')
    except Exception as e:
        flash(f'Error al eliminar paciente: {e}', 'danger')
        print(f"Error al eliminar paciente: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))

@app.route('/add_medical_record/<int:patient_id>', methods=['GET', 'POST'])
def add_medical_record(patient_id):
    cur, conn = get_db_connection()
    if cur is None:
        flash('No se pudo conectar a la base de datos.', 'danger')
        return redirect(url_for('patient_details', patient_id=patient_id)) # Redirigir a detalles del paciente

    cur.execute("SELECT id, name FROM patients WHERE id = %s", (patient_id,))
    patient = cur.fetchone()
    cur.close()
    conn.close()

    if patient is None:
        flash('Paciente no encontrado.', 'danger')
        return redirect(url_for('index'))

    form = MedicalRecordForm() # Instancia el formulario de historia clínica

    if form.validate_on_submit():
        try:
            record_date = form.record_date.data
            reason = form.reason.data
            diagnosis = form.diagnosis.data
            treatment = form.treatment.data
            notes = form.notes.data

            cur, conn = get_db_connection()
            if cur is None:
                flash('No se pudo conectar a la base de datos.', 'danger')
                return render_template('add_medical_record.html', patient=patient, form=form)

            cur.execute(
                "INSERT INTO medical_records (patient_id, record_date, reason, diagnosis, treatment, notes) VALUES (%s, %s, %s, %s, %s, %s)",
                (patient['id'], record_date, reason, diagnosis, treatment, notes) # Usa patient['id']
            )
            conn.commit()
            cur.close()
            conn.close()
            flash('Historia clínica añadida exitosamente!', 'success')
            return redirect(url_for('patient_details', patient_id=patient['id'])) # Usa patient['id']
        except Exception as e:
            flash(f'Error al añadir historia clínica: {e}', 'danger')
            print(f"Error al añadir historia clínica: {e}")
    elif request.method == 'POST':
        flash('Por favor, corrige los errores del formulario.', 'danger')

    return render_template('add_medical_record.html', patient=patient, form=form)


@app.route('/edit_medical_record/<int:record_id>', methods=['GET', 'POST'])
def edit_medical_record(record_id):
    cur, conn = get_db_connection()
    if cur is None:
        flash('No se pudo conectar a la base de datos.', 'danger')
        return redirect(url_for('index')) # Redirigir si no hay conexión

    cur.execute("SELECT mr.*, p.name FROM medical_records mr JOIN patients p ON mr.patient_id = p.id WHERE mr.id = %s", (record_id,))
    record = cur.fetchone()
    cur.close()
    conn.close() # Cierra la conexión inicial aquí

    if record is None:
        flash('Historia clínica no encontrada.', 'danger')
        return redirect(url_for('index'))

    patient_id = record['patient_id'] # Accede por nombre de columna
    patient_name = record['name'] # Accede por nombre de columna (nombre del paciente)

    form = MedicalRecordForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                record_date = form.record_date.data
                reason = form.reason.data
                diagnosis = form.diagnosis.data
                treatment = form.treatment.data
                notes = form.notes.data

                cur, conn = get_db_connection() # Nueva conexión para la actualización
                if cur is None:
                    flash('No se pudo conectar a la base de datos.', 'danger')
                    return render_template('edit_medical_record.html', record=record, patient_name=patient_name, form=form)

                cur.execute(
                    "UPDATE medical_records SET record_date = %s, reason = %s, diagnosis = %s, treatment = %s, notes = %s WHERE id = %s",
                    (record_date, reason, diagnosis, treatment, notes, record_id)
                )
                conn.commit()
                cur.close()
                conn.close()
                flash('Historia clínica actualizada exitosamente!', 'success')
                return redirect(url_for('patient_details', patient_id=patient_id))
            except Exception as e:
                flash(f'Error al actualizar historia clínica: {e}', 'danger')
                print(f"Error al actualizar historia clínica: {e}")
        else:
            flash('Por favor, corrige los errores del formulario.', 'danger')
    else: # GET request
        form = MedicalRecordForm(obj=record) # Pre-llena el formulario

    return render_template('edit_medical_record.html', record=record, patient_name=patient_name, form=form)

# Punto de entrada de la aplicación
if __name__ == '__main__':
    app.run(debug=True)