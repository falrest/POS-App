import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pos.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(seed_sample_data=True):
    """Membuat tabel jika belum ada, dan mengisi data contoh (sekali saja)."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Umum',
            price REAL NOT NULL,
            cost REAL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT UNIQUE NOT NULL,
            datetime TEXT NOT NULL,
            subtotal REAL NOT NULL,
            discount_percent REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            total REAL NOT NULL,
            paid REAL NOT NULL,
            change_amount REAL NOT NULL,
            cashier TEXT DEFAULT 'Kasir',
            payment_method TEXT DEFAULT 'Tunai'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transaction_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL,
            product_id INTEGER,
            barcode TEXT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            qty INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
        )
    """)

    conn.commit()

    
    if seed_sample_data:
        cur.execute("SELECT COUNT(*) AS c FROM products")
        if cur.fetchone()["c"] == 0:
            sample = [
                ("8991002101012", "Indomie Goreng", "Makanan", 3500, 2800, 100),
                ("8992388101019", "Aqua Botol 600ml", "Minuman", 4000, 3000, 150),
                ("8991102201028", "Teh Botol Sosro", "Minuman", 5000, 3800, 80),
                ("8992753101036", "Roti Tawar Sari Roti", "Makanan", 15000, 12000, 40),
                ("8993675101045", "Kopi Kapal Api Sachet", "Minuman", 1500, 1000, 200),
                ("8994989101053", "Sabun Mandi Lifebuoy", "Kebersihan", 6000, 4500, 60),
                ("8995787101062", "Beras 5kg", "Sembako", 65000, 58000, 25),
                ("8996055101071", "Minyak Goreng 1L", "Sembako", 18000, 15500, 30),
                ("8997219101080", "Rokok Sampoerna Mild", "Rokok", 32000, 29000, 50),
                ("8998866101099", "Pulsa Elektrik 10rb", "Lainnya", 11000, 10200, 999),
            ]
            cur.executemany(
                "INSERT INTO products (barcode, name, category, price, cost, stock) VALUES (?,?,?,?,?,?)",
                sample,
            )
            conn.commit()

    conn.close()


def get_all_products(search=None):
    conn = get_conn()
    if search:
        rows = conn.execute(
            "SELECT * FROM products WHERE name LIKE ? OR barcode LIKE ? ORDER BY name",
            (f"%{search}%", f"%{search}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    conn.close()
    return rows


def get_product_by_barcode(barcode):
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE barcode = ?", (barcode,)).fetchone()
    conn.close()
    return row


def get_product_by_id(pid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    conn.close()
    return row


def add_product(barcode, name, category, price, cost, stock):
    conn = get_conn()
    conn.execute(
        "INSERT INTO products (barcode, name, category, price, cost, stock) VALUES (?,?,?,?,?,?)",
        (barcode, name, category, price, cost, stock),
    )
    conn.commit()
    conn.close()


def update_product(pid, barcode, name, category, price, cost, stock):
    conn = get_conn()
    conn.execute(
        "UPDATE products SET barcode=?, name=?, category=?, price=?, cost=?, stock=? WHERE id=?",
        (barcode, name, category, price, cost, stock, pid),
    )
    conn.commit()
    conn.close()


def delete_product(pid):
    conn = get_conn()
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()


def adjust_stock(pid, delta):
    """delta negatif = mengurangi stok (penjualan), positif = menambah stok."""
    conn = get_conn()
    conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (delta, pid))
    conn.commit()
    conn.close()


def generate_invoice_no():
    return "INV" + datetime.now().strftime("%Y%m%d%H%M%S")


def save_transaction(cart_items, subtotal, discount_percent, discount_amount, total,
                      paid, change_amount, cashier="Kasir", payment_method="Tunai"):
    """
    cart_items: list of dict {product_id, barcode, name, price, qty, subtotal}
    Mengembalikan invoice_no dan id transaksi.
    """
    conn = get_conn()
    cur = conn.cursor()
    invoice_no = generate_invoice_no()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        INSERT INTO transactions
        (invoice_no, datetime, subtotal, discount_percent, discount_amount, total, paid, change_amount, cashier, payment_method)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (invoice_no, now, subtotal, discount_percent, discount_amount, total, paid, change_amount, cashier, payment_method))

    transaction_id = cur.lastrowid

    for item in cart_items:
        cur.execute("""
            INSERT INTO transaction_items (transaction_id, product_id, barcode, name, price, qty, subtotal)
            VALUES (?,?,?,?,?,?,?)
        """, (transaction_id, item["product_id"], item["barcode"], item["name"],
              item["price"], item["qty"], item["subtotal"]))
        # kurangi stok
        cur.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item["qty"], item["product_id"]))

    conn.commit()
    conn.close()
    return invoice_no, transaction_id, now

def get_sales_summary(start_date, end_date):
    """start_date/end_date format 'YYYY-MM-DD'. Rentang inklusif sepanjang hari."""
    conn = get_conn()
    row = conn.execute("""
        SELECT COUNT(*) AS jumlah_transaksi,
               COALESCE(SUM(total), 0) AS total_penjualan,
               COALESCE(SUM(discount_amount), 0) AS total_diskon,
               COALESCE(AVG(total), 0) AS rata_rata
        FROM transactions
        WHERE date(datetime) BETWEEN date(?) AND date(?)
    """, (start_date, end_date)).fetchone()
    conn.close()
    return row


def get_transactions_between(start_date, end_date):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM transactions
        WHERE date(datetime) BETWEEN date(?) AND date(?)
        ORDER BY datetime DESC
    """, (start_date, end_date)).fetchall()
    conn.close()
    return rows


def get_top_products(start_date, end_date, limit=10):
    conn = get_conn()
    rows = conn.execute("""
        SELECT ti.name, SUM(ti.qty) AS total_qty, SUM(ti.subtotal) AS total_omzet
        FROM transaction_items ti
        JOIN transactions t ON t.id = ti.transaction_id
        WHERE date(t.datetime) BETWEEN date(?) AND date(?)
        GROUP BY ti.name
        ORDER BY total_qty DESC
        LIMIT ?
    """, (start_date, end_date, limit)).fetchall()
    conn.close()
    return rows


def get_transaction_items(transaction_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM transaction_items WHERE transaction_id = ?", (transaction_id,)
    ).fetchall()
    conn.close()
    return rows
