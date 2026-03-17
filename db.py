import hashlib
import json
import psycopg2
import streamlit as st


def get_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"], sslmode="require")


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            security_question TEXT NOT NULL DEFAULT '',
            security_answer TEXT NOT NULL DEFAULT '',
            supplier TEXT NOT NULL DEFAULT 'MSEDCL'
        )
    """)
    try:
        cur.execute("ALTER TABLE users ADD COLUMN supplier TEXT NOT NULL DEFAULT 'MSEDCL'")
        conn.commit()
    except:
        conn.rollback()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS electricity_data (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL, year INTEGER NOT NULL,
            month TEXT NOT NULL, units REAL NOT NULL,
            bill REAL NOT NULL, rate REAL NOT NULL,
            UNIQUE(username, year, month)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS appliance_data (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL, year INTEGER NOT NULL,
            month TEXT NOT NULL, appliance_hours JSONB NOT NULL,
            UNIQUE(username, year, month)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_survey (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            avg_appliance_hours JSONB NOT NULL,
            completed_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


# ── Auth ──────────────────────────────────────────────────────────────────────

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password, security_question, security_answer):
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password, security_question, security_answer) VALUES (%s,%s,%s,%s)",
            (username, hash_password(password), security_question, hash_password(security_answer.lower().strip()))
        )
        conn.commit(); cur.close(); conn.close()
        return True
    except psycopg2.IntegrityError:
        conn.rollback(); conn.close()
        return False

def verify_user(username, password):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username = %s", (username,))
    row = cur.fetchone(); cur.close(); conn.close()
    return row is not None and row[0] == hash_password(password)

def get_security_question(username):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT security_question FROM users WHERE username = %s", (username,))
    row = cur.fetchone(); cur.close(); conn.close()
    return row[0] if row else None

def verify_security_answer(username, answer):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT security_question, security_answer FROM users WHERE username = %s", (username,))
    row = cur.fetchone(); cur.close(); conn.close()
    if row is None: return False, None
    return row[1] == hash_password(answer.lower().strip()), row[0]

def reset_password(username, new_password):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("UPDATE users SET password = %s WHERE username = %s", (hash_password(new_password), username))
    conn.commit(); cur.close(); conn.close()

def save_supplier(username, supplier):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("UPDATE users SET supplier = %s WHERE username = %s", (supplier, username))
    conn.commit(); cur.close(); conn.close()

def load_supplier(username):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT supplier FROM users WHERE username = %s", (username,))
    row = cur.fetchone(); cur.close(); conn.close()
    return row[0] if row else "MSEDCL"


# ── Data helpers ──────────────────────────────────────────────────────────────

def save_entry(username, year, month, units, bill, rate):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO electricity_data (username, year, month, units, bill, rate)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT(username, year, month) DO UPDATE SET
            units=EXCLUDED.units, bill=EXCLUDED.bill, rate=EXCLUDED.rate
    """, (username, year, month, units, bill, rate))
    conn.commit(); cur.close(); conn.close()

def save_appliance_data(username, year, month, appliance_hours):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO appliance_data (username, year, month, appliance_hours)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT(username, year, month) DO UPDATE SET
            appliance_hours=EXCLUDED.appliance_hours
    """, (username, year, month, json.dumps(appliance_hours)))
    conn.commit(); cur.close(); conn.close()

def load_user_data(username, year):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT month, units, bill, rate FROM electricity_data WHERE username=%s AND year=%s", (username, year))
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

def load_appliance_data(username, year, month):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT appliance_hours FROM appliance_data WHERE username=%s AND year=%s AND month=%s", (username, year, month))
    row = cur.fetchone(); cur.close(); conn.close()
    return row[0] if row else {}

def load_all_appliance_data(username, year):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT month, appliance_hours FROM appliance_data WHERE username=%s AND year=%s", (username, year))
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

def delete_user_data(username, year):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM electricity_data WHERE username=%s AND year=%s", (username, year))
    cur.execute("DELETE FROM appliance_data WHERE username=%s AND year=%s", (username, year))
    conn.commit(); cur.close(); conn.close()

def has_completed_survey(username):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT avg_appliance_hours FROM user_survey WHERE username=%s", (username,))
    row = cur.fetchone(); cur.close(); conn.close()
    return row[0] if row else None

def save_user_survey(username, avg_hours):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_survey (username, avg_appliance_hours)
        VALUES (%s,%s)
        ON CONFLICT(username) DO UPDATE SET
            avg_appliance_hours=EXCLUDED.avg_appliance_hours, completed_at=NOW()
    """, (username, json.dumps(avg_hours)))
    conn.commit(); cur.close(); conn.close()
