# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, EmailField, TextAreaField, PasswordField
from wtforms.validators import DataRequired, Length, Email, Optional, ValidationError, EqualTo
import re
from datetime import date

# Custom validator for phone number format
def validate_phone(form, field):
    # Allow empty or valid phone number format (e.g., 7-15 digits, optional + at start)
    if field.data and not re.fullmatch(r'^\+?[0-9]{7,15}$', field.data):
        raise ValidationError('Número de teléfono inválido. Debe contener entre 7 y 15 dígitos y opcionalmente empezar con "+".')

# Custom validator for date of birth (not in the future)
def validate_dob_not_future(form, field):
    if field.data and field.data > date.today():
        raise ValidationError('La fecha de nacimiento no puede ser en el futuro.')

class PatientForm(FlaskForm):
    name = StringField('Nombre', validators=[DataRequired(message="El nombre es obligatorio."), Length(min=2, max=100, message="El nombre debe tener entre 2 y 100 caracteres.")])
    dob = DateField('Fecha de Nacimiento', format='%Y-%m-%d', validators=[Optional(), validate_dob_not_future])
    gender = SelectField('Género', choices=[('', 'Seleccionar'), ('Masculino', 'Masculino'), ('Femenino', 'Femenino'), ('Otro', 'Otro')], validators=[Optional()])
    address = StringField('Dirección', validators=[Optional(), Length(max=200, message="La dirección no puede exceder los 200 caracteres.")])
    phone = StringField('Teléfono', validators=[Optional(), validate_phone])
    email = EmailField('Email', validators=[Optional(), Email(message="Formato de email inválido.")])

class MedicalRecordForm(FlaskForm):
    record_date = DateField('Fecha del Registro', format='%Y-%m-%d', validators=[DataRequired(message="La fecha del registro es obligatoria."), validate_dob_not_future])
    reason = TextAreaField('Razón de la Consulta', validators=[Optional(), Length(max=500, message="La razón no puede exceder los 500 caracteres.")])
    diagnosis = TextAreaField('Diagnóstico', validators=[Optional(), Length(max=500, message="El diagnóstico no puede exceder los 500 caracteres.")])
    treatment = TextAreaField('Tratamiento', validators=[Optional(), Length(max=500, message="El tratamiento no puede exceder los 500 caracteres.")])
    notes = TextAreaField('Notas', validators=[Optional(), Length(max=1000, message="Las notas no pueden exceder los 1000 caracteres.")])

# --------------- FORMULARIOS PARA AUTENTICACIÓN (PARA MÁS ADELANTE) ---------------
class RegistrationForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired(message="El nombre de usuario es obligatorio."), Length(min=4, max=50, message="El nombre de usuario debe tener entre 4 y 50 caracteres.")])
    password = PasswordField('Contraseña', validators=[DataRequired(message="La contraseña es obligatoria."), Length(min=6, message="La contraseña debe tener al menos 6 caracteres.")])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[DataRequired(message="Confirme la contraseña."), EqualTo('password', message='Las contraseñas no coinciden.')])

class LoginForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired(message="El nombre de usuario es obligatorio.")])
    password = PasswordField('Contraseña', validators=[DataRequired(message="La contraseña es obligatoria.")])