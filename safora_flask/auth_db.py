# auth_db.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("appdata.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      firebase_uid TEXT UNIQUE,
      email TEXT,
      name TEXT
    );""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      firebase_uid TEXT,
      name TEXT,
      phone TEXT,
      UNIQUE(firebase_uid, phone)
    );""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS emergency_contacts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      firebase_uid TEXT NOT NULL,
      name TEXT NOT NULL,
      phone_number TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(firebase_uid, phone_number),
      FOREIGN KEY (firebase_uid) REFERENCES users(firebase_uid)
    );""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS user_email_config (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      firebase_uid TEXT UNIQUE,
      alert_email TEXT,
      alert_email_password TEXT,
      smtp_server TEXT DEFAULT 'smtp.gmail.com',
      smtp_port INTEGER DEFAULT 587,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (firebase_uid) REFERENCES users(firebase_uid)
    );""")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
