import os
import psycopg2
from urllib.parse import urlparse

def main():
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("Erreur : la variable d'environnement DATABASE_URL n'est pas définie.")
        return

    result = urlparse(DATABASE_URL)

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(
            dbname=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port,
            sslmode='require'  # modifié ici
        )
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS eleves (
            id SERIAL PRIMARY KEY,
            nom TEXT NOT NULL UNIQUE,
            photo_url TEXT,
            emploi_du_temps TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sorties (
            id SERIAL PRIMARY KEY,
            eleve_id INTEGER NOT NULL REFERENCES eleves(id) ON DELETE CASCADE,
            peut_sortir BOOLEAN NOT NULL DEFAULT FALSE,
            heure_sortie TIME
        );
        """)

        conn.commit()
        print("Tables créées avec succès !")

    except Exception as e:
        print("Erreur lors de la création des tables :", e)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
