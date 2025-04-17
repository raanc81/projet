import os
import sqlite3
import qrcode
import base64
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, flash, session
from urllib.parse import quote, unquote
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'ma_cle_secrete'
DB_FILE = 'sorties.db'
UPLOAD_FOLDER = 'static/photos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

BASE_URL = "https://projet-flrh.onrender.com"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

def update_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS eleves (
        nom_eleve TEXT PRIMARY KEY,
        photo TEXT,
        emploi_du_temps TEXT
    )''')
    cursor.execute("PRAGMA table_info(eleves)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'photo' not in columns:
        cursor.execute("ALTER TABLE eleves ADD COLUMN photo TEXT")
    if 'emploi_du_temps' not in columns:
        cursor.execute("ALTER TABLE eleves ADD COLUMN emploi_du_temps TEXT")
    conn.commit()
    conn.close()

update_db()

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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT nom_eleve, photo, emploi_du_temps FROM eleves")
    eleves = cursor.fetchall()
    conn.close()
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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO eleves (nom_eleve, photo, emploi_du_temps) VALUES (?, ?, ?)",
                   (nom_eleve, photo_path, emploi_du_temps))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_eleve/<nom_eleve>', methods=['POST'])
def delete_eleve(nom_eleve):
    if not session.get('admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM eleves WHERE nom_eleve = ?", (nom_eleve,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/edit_eleve/<nom_eleve>', methods=['GET', 'POST'])
def edit_eleve(nom_eleve):
    if not session.get('admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if request.method == 'POST':
        emploi_du_temps = f"Lundi: {request.form['lundi']}, Mardi: {request.form['mardi']}, Mercredi: {request.form['mercredi']}, Jeudi: {request.form['jeudi']}, Vendredi: {request.form['vendredi']}"
        cursor.execute("UPDATE eleves SET emploi_du_temps = ? WHERE nom_eleve = ?", (emploi_du_temps, nom_eleve))
        conn.commit()
        conn.close()
        return redirect(url_for('admin'))
    cursor.execute("SELECT emploi_du_temps FROM eleves WHERE nom_eleve = ?", (nom_eleve,))
    emploi_du_temps = cursor.fetchone()[0]
    conn.close()
    emploi_du_temps_dict = {jour.split(':')[0].strip(): jour.split(':')[1].strip() for jour in emploi_du_temps.split(',')}
    return render_template('edit_eleve.html', nom_eleve=nom_eleve, emploi_du_temps=emploi_du_temps_dict)

@app.route('/generate_qr', methods=['GET', 'POST'])
def generate_qr():
    if not session.get('admin'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        nom_eleve = request.form['nom_eleve']
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT emploi_du_temps FROM eleves WHERE nom_eleve = ?", (nom_eleve,))
        result = cursor.fetchone()
        if result:
            emploi_du_temps = result[0]
            emploi_du_temps_encode = quote(emploi_du_temps)
            qr_data = f"{BASE_URL}/eleve/{quote(nom_eleve)}/{emploi_du_temps_encode}"
            qr_image = qrcode.make(qr_data)
            qr_io = BytesIO()
            qr_image.save(qr_io, 'PNG')
            qr_io.seek(0)
            qr_code_base64 = base64.b64encode(qr_io.getvalue()).decode('utf-8')
            conn.close()
            return render_template('generate_qr.html', qr_code=qr_code_base64, nom_eleve=nom_eleve)
        conn.close()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT nom_eleve FROM eleves")
    eleves = cursor.fetchall()
    conn.close()
    return render_template('generate_qr.html', eleves=eleves)

@app.route('/eleve/<nom_eleve>/<emploi_du_temps>')
def afficher_eleve(nom_eleve, emploi_du_temps):
    emploi_du_temps = unquote(emploi_du_temps)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT nom_eleve, photo FROM eleves WHERE nom_eleve = ?", (nom_eleve,))
    eleve = cursor.fetchone()
    conn.close()
    if not eleve:
        flash("Élève non trouvé.", "danger")
        return redirect(url_for('index'))

    # Traitement de l'heure
    now = datetime.now()
    jour = now.strftime('%A')
    heure = now.strftime('%H:%M')
    emploi_du_temps_dict = {j.strip(): h.strip() for j, h in [item.split(':') for item in emploi_du_temps.split(',')]}
    heure_sortie = emploi_du_temps_dict.get(jour, None)

    peut_sortir = False
    if heure_sortie:
        try:
            heure_actuelle = datetime.strptime(heure, '%H:%M')
            heure_limite = datetime.strptime(heure_sortie, '%H:%M')
            peut_sortir = heure_actuelle >= heure_limite
        except ValueError:
            pass

    return render_template('eleve.html', nom=eleve[0], photo=eleve[1], emploi_du_temps=emploi_du_temps,
                           peut_sortir=peut_sortir)

if __name__ == '__main__':
    app.run(debug=True)
