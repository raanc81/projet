import os
import re
import base64
import qrcode
from io import BytesIO
from datetime import datetime
from urllib.parse import quote, unquote

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy

# === Initialisation de l'application ===
app = Flask(__name__)
app.secret_key = 'ma_cle_secrete'
UPLOAD_FOLDER = 'static/photos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# === Configuration Base de Données ===
DATABASE_URL = os.environ.get('SCALINGO_POSTGRESQL_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///sorties.db'
db = SQLAlchemy(app)

BASE_URL = "https://gestion-entrer-sortie.osc-fr1.scalingo.io"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# === Modèle Élève ===
class Eleve(db.Model):
    nom_eleve = db.Column(db.String(100), primary_key=True)
    photo = db.Column(db.String(200))
    emploi_du_temps = db.Column(db.Text)

# === Routes ===

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin'))
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

    nom = request.form['nom_eleve']
    emploi = ", ".join([
        f"Lundi: {request.form['lundi']}",
        f"Mardi: {request.form['mardi']}",
        f"Mercredi: {request.form['mercredi']}",
        f"Jeudi: {request.form['jeudi']}",
        f"Vendredi: {request.form['vendredi']}"
    ])

    photo_path = None
    if 'photo' in request.files:
        photo = request.files['photo']
        if photo.filename:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
            photo.save(filepath)
            photo_path = '/' + filepath

    eleve = Eleve(nom_eleve=nom, photo=photo_path, emploi_du_temps=emploi)
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
    if not eleve:
        flash("Élève introuvable.", "danger")
        return redirect(url_for('admin'))

    if request.method == 'POST':
        emploi = ", ".join([
            f"Lundi: {request.form['lundi']}",
            f"Mardi: {request.form['mardi']}",
            f"Mercredi: {request.form['mercredi']}",
            f"Jeudi: {request.form['jeudi']}",
            f"Vendredi: {request.form['vendredi']}"
        ])
        eleve.emploi_du_temps = emploi
        db.session.commit()
        return redirect(url_for('admin'))

    edt = {j.split(':')[0].strip(): j.split(':')[1].strip() for j in eleve.emploi_du_temps.split(',')}
    return render_template('edit_eleve.html', nom_eleve=eleve.nom_eleve, emploi_du_temps=edt)

@app.route('/generate_qr', methods=['GET', 'POST'])
def generate_qr():
    if not session.get('admin'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        nom = request.form['nom_eleve']
        eleve = Eleve.query.get(nom)
        if eleve:
            edt_encoded = quote(eleve.emploi_du_temps)
            data = f"{BASE_URL}/eleve/{quote(nom)}/{edt_encoded}"
            qr = qrcode.make(data)
            io_img = BytesIO()
            qr.save(io_img, 'PNG')
            io_img.seek(0)
            qr_base64 = base64.b64encode(io_img.read()).decode('utf-8')
            return render_template('generate_qr.html', qr_code=qr_base64, nom_eleve=nom)

    noms = Eleve.query.with_entities(Eleve.nom_eleve).all()
    return render_template('generate_qr.html', eleves=noms)

@app.route('/eleve/<nom_eleve>/<emploi_du_temps>')
def afficher_eleve(nom_eleve, emploi_du_temps):
    emploi_du_temps = unquote(emploi_du_temps)
    eleve = Eleve.query.get(nom_eleve)
    if not eleve:
        flash("Élève non trouvé.", "danger")
        return redirect(url_for('index'))

    jour_actuel = datetime.now().strftime('%A')
    jours_fr = {
        "Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi",
        "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi", "Sunday": "Dimanche"
    }
    jour = jours_fr.get(jour_actuel, jour_actuel)
    heure = datetime.now().strftime('%H:%M')
    edt = {}

    for item in emploi_du_temps.split(','):
        try:
            j, h = item.split(':', 1)
            edt[j.strip()] = h.strip()
        except ValueError:
            continue

    horaire = edt.get(jour)
    peut_sortir = True

    if horaire:
        try:
            heure_actuelle = datetime.strptime(heure, '%H:%M').time()
            plages = re.findall(r'(\d{1,2}[h:]\d{2})\s*(?:-|à|a)?\s*(\d{1,2}[h:]\d{2})', horaire)
            for debut_str, fin_str in plages:
                debut = datetime.strptime(debut_str.replace('h', ':').replace('H', ':'), '%H:%M').time()
                fin = datetime.strptime(fin_str.replace('h', ':').replace('H', ':'), '%H:%M').time()
                if debut <= heure_actuelle <= fin:
                    peut_sortir = False
                    break
        except Exception as e:
            print("[DEBUG] Erreur parsing horaires:", e)

    return render_template('eleve.html', nom=eleve.nom_eleve, photo=eleve.photo,
                           emploi_du_temps=emploi_du_temps, peut_sortir=peut_sortir)

@app.route('/init_db')
def init_db():
    try:
        db.create_all()
        return "✅ Base de données initialisée avec succès."
    except Exception as e:
        return f"❌ Erreur d'initialisation : {e}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
