import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
import qrcode
import base64
from io import BytesIO
from urllib.parse import quote, unquote
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = 'ma_cle_secrete'
UPLOAD_FOLDER = 'static/photos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Connexion à la base de données PostgreSQL Scalingo
DATABASE_URL = os.environ.get('SCALINGO_POSTGRESQL_URL')

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL:
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sorties.db'

db = SQLAlchemy(app)

BASE_URL = "https://gestion-entrer-sortie.osc-fr1.scalingo.io"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

class Eleve(db.Model):
    nom_eleve = db.Column(db.String(100), primary_key=True)
    photo = db.Column(db.String(200))
    emploi_du_temps = db.Column(db.Text)

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin'))
        else:
            flash("Identifiant ou mot de passe incorrect", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('login'))
    eleves = Eleve.query.all()
    return render_template('admin.html', eleves=eleves)

@app.route('/add_eleve', methods=['POST'])
def add_eleve():
    if not session.get('admin'):
        return redirect(url_for('login'))
    nom_eleve = request.form['nom_eleve']
    emploi_du_temps = f"Lundi: {request.form['lundi']}, Mardi: {request.form['mardi']}, Mercredi: {request.form['mercredi']}, Jeudi: {request.form['jeudi']}, Vendredi: {request.form['vendredi']}"
    photo_path = None
    if 'photo' in request.files:
        photo = request.files['photo']
        if photo.filename:
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
            photo.save(photo_path)
            photo_path = '/' + photo_path
    eleve = Eleve(nom_eleve=nom_eleve, photo=photo_path, emploi_du_temps=emploi_du_temps)
    db.session.add(eleve)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/delete_eleve/<nom_eleve>', methods=['POST'])
def delete_eleve(nom_eleve):
    if not session.get('admin'):
        return redirect(url_for('login'))
    eleve = Eleve.query.get(nom_eleve)
    if eleve:
        db.session.delete(eleve)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/edit_eleve/<nom_eleve>', methods=['GET', 'POST'])
def edit_eleve(nom_eleve):
    if not session.get('admin'):
        return redirect(url_for('login'))
    eleve = Eleve.query.get(nom_eleve)
    if request.method == 'POST':
        emploi_du_temps = f"Lundi: {request.form['lundi']}, Mardi: {request.form['mardi']}, Mercredi: {request.form['mercredi']}, Jeudi: {request.form['jeudi']}, Vendredi: {request.form['vendredi']}"
        eleve.emploi_du_temps = emploi_du_temps
        db.session.commit()
        return redirect(url_for('admin'))
    emploi_du_temps_dict = {jour.split(':')[0].strip(): jour.split(':')[1].strip() for jour in eleve.emploi_du_temps.split(',')}
    return render_template('edit_eleve.html', nom_eleve=nom_eleve, emploi_du_temps=emploi_du_temps_dict)

@app.route('/generate_qr', methods=['GET', 'POST'])
def generate_qr():
    if not session.get('admin'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        nom_eleve = request.form['nom_eleve']
        eleve = Eleve.query.get(nom_eleve)
        if eleve:
            emploi_du_temps_encode = quote(eleve.emploi_du_temps)
            qr_data = f"{BASE_URL}/eleve/{quote(nom_eleve)}/{emploi_du_temps_encode}"
            qr_image = qrcode.make(qr_data)
            qr_io = BytesIO()
            qr_image.save(qr_io, 'PNG')
            qr_io.seek(0)
            qr_code_base64 = base64.b64encode(qr_io.getvalue()).decode('utf-8')
            return render_template('generate_qr.html', qr_code=qr_code_base64, nom_eleve=nom_eleve)
    eleves = Eleve.query.with_entities(Eleve.nom_eleve).all()
    return render_template('generate_qr.html', eleves=eleves)

@app.route('/eleve/<nom_eleve>/<emploi_du_temps>')
def afficher_eleve(nom_eleve, emploi_du_temps):
    emploi_du_temps = unquote(emploi_du_temps)
    eleve = Eleve.query.get(nom_eleve)
    if not eleve:
        flash("Élève non trouvé.", "danger")
        return redirect(url_for('index'))

    now = datetime.now()
    jour = now.strftime('%A')
    jour_fr = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche"
    }
    jour = jour_fr.get(jour, jour)
    heure_actuelle = now.strftime('%H:%M')

    emploi_du_temps_dict = {}
    for item in emploi_du_temps.split(','):
        try:
            jour_item, horaires = item.split(':', 1)
            emploi_du_temps_dict[jour_item.strip()] = horaires.strip()
        except ValueError:
            continue

    horaire_du_jour = emploi_du_temps_dict.get(jour)
    peut_sortir = True  # Par défaut on autorise

    if horaire_du_jour:
        try:
            heure_now = datetime.strptime(heure_actuelle, '%H:%M').time()
            horaires = re.findall(r'(\d{1,2}[h:]\d{2})\s*(?:-|\u00e0|à)\s*(\d{1,2}[h:]\d{2})', horaire_du_jour)

            for debut_str, fin_str in horaires:
                debut = datetime.strptime(debut_str.replace('h', ':').replace('H', ':'), '%H:%M').time()
                fin = datetime.strptime(fin_str.replace('h', ':').replace('H', ':'), '%H:%M').time()
                # Si l'heure actuelle est entre debut et fin -> on bloque la sortie
                if debut <= heure_now <= fin:
                    peut_sortir = False
                    break
        except Exception as e:
            print("Erreur dans le parsing de l'horaire:", e)
            peut_sortir = True

    return render_template('eleve.html', nom=eleve.nom_eleve, photo=eleve.photo,
                           emploi_du_temps=emploi_du_temps, peut_sortir=peut_sortir)

@app.route('/init_db')
def init_db():
    try:
        db.create_all()
        return "✅ Tables créées avec succès sur PostgreSQL Scalingo."
    except Exception as e:
        return f"❌ Erreur : {e}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
