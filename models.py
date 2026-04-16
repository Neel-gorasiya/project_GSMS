import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "grocery.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        phone TEXT,
        shop_name TEXT,
        gst_number TEXT,
        is_admin INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        suspended_at TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        cost_price REAL NOT NULL,
        sell_price REAL NOT NULL,
        stock INTEGER NOT NULL,
        unit TEXT NOT NULL DEFAULT 'pcs',
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    # ✅ UPDATED CUSTOMERS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        mobile_number TEXT NOT NULL,
        due REAL NOT NULL DEFAULT 0,
        next_payment_date TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        customer_id INTEGER,
        total REAL NOT NULL,
        payment_type TEXT NOT NULL,
        due_date TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (customer_id) REFERENCES customers (id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bill_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        bill_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        line_total REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (bill_id) REFERENCES bills (id),
        FOREIGN KEY (product_id) REFERENCES products (id)
    );
    """)

    conn.commit()
    conn.close()


def migrate_db():
    conn = get_db()
    cur = conn.cursor()

    # ✅ ADD NEW COLUMNS SAFELY
    cur.execute("PRAGMA table_info(customers)")
    columns = [col['name'] for col in cur.fetchall()]

    if "mobile_number" not in columns:
        try:
            cur.execute("ALTER TABLE customers ADD COLUMN mobile_number TEXT")
        except:
            pass

    # Existing migration logic
    cur.execute("PRAGMA table_info(products)")
    columns = cur.fetchall()
    has_user_id = any(col['name'] == 'user_id' for col in columns)

    if not has_user_id:
        cur.execute("SELECT id FROM users WHERE username = 'admin'")
        admin_user = cur.fetchone()

        if admin_user:
            admin_id = admin_user['id']

            try:
                cur.execute("ALTER TABLE products ADD COLUMN user_id INTEGER")
                cur.execute("UPDATE products SET user_id = ?", (admin_id,))
            except:
                pass
            try:
                cur.execute("ALTER TABLE customers ADD COLUMN user_id INTEGER")
                cur.execute("UPDATE customers SET user_id = ?", (admin_id,))
            except:
                pass
            try:
                cur.execute("ALTER TABLE bills ADD COLUMN user_id INTEGER")
                cur.execute("UPDATE bills SET user_id = ?", (admin_id,))
            except:
                pass
            try:
                cur.execute("ALTER TABLE bill_items ADD COLUMN user_id INTEGER")
                cur.execute("UPDATE bill_items SET user_id = ?", (admin_id,))
            except:
                pass

            conn.commit()

    conn.commit()
    conn.close()


def create_admin():
    conn = get_db()
    cur = conn.cursor()

    password_hash = generate_password_hash("admin123")
    cur.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, is_admin, is_active) VALUES (?, ?, 1, 1)",
        ("admin", password_hash),
    )

    conn.commit()
    conn.close()