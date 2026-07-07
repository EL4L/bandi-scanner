import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("ALTER TABLE clienti ADD COLUMN IF NOT EXISTS forma_giuridica TEXT")
conn.commit()
print("OK - forma_giuridica aggiunta")
conn.close()
