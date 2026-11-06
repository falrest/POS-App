"""
receipt.py - Membuat teks struk belanja (format thermal printer 32/40 kolom)
dan menyimpannya sebagai file .txt di folder receipts/.
"""

import os
from datetime import datetime

RECEIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "receipts")
os.makedirs(RECEIPT_DIR, exist_ok=True)

STORE_NAME = "TOKO FALREST"
STORE_ADDRESS = "Jl. Kudus"
STORE_PHONE = "0850-0000-0000"

WIDTH = 38  


def rupiah(n):
    return f"Rp{n:,.0f}".replace(",", ".")


def line(char="-"):
    return char * WIDTH


def center(text):
    return text.center(WIDTH)


def two_col(left, right):
    space = WIDTH - len(left) - len(right)
    if space < 1:
        space = 1
    return left + (" " * space) + right


def build_receipt_text(invoice_no, dt_str, cart_items, subtotal, discount_percent,
                        discount_amount, total, paid, change_amount, cashier="Kasir"):
    out = []
    out.append(center(STORE_NAME))
    out.append(center(STORE_ADDRESS))
    out.append(center(STORE_PHONE))
    out.append(line("="))
    out.append(f"No: {invoice_no}")
    out.append(f"Tgl: {dt_str}")
    out.append(f"Kasir: {cashier}")
    out.append(line("-"))

    for item in cart_items:
        out.append(item["name"])
        qty_price = f"{item['qty']} x {rupiah(item['price'])}"
        out.append(two_col(qty_price, rupiah(item["subtotal"])))

    out.append(line("-"))
    out.append(two_col("Subtotal", rupiah(subtotal)))
    if discount_amount > 0:
        disc_label = f"Diskon ({discount_percent:.0f}%)" if discount_percent > 0 else "Diskon"
        out.append(two_col(disc_label, "-" + rupiah(discount_amount)))
    out.append(two_col("TOTAL", rupiah(total)))
    out.append(two_col("Bayar", rupiah(paid)))
    out.append(two_col("Kembali", rupiah(change_amount)))
    out.append(line("="))
    out.append(center("Terima kasih atas"))
    out.append(center("kunjungan Anda!"))
    out.append(line("="))
    return "\n".join(out)


def save_receipt_file(invoice_no, text):
    path = os.path.join(RECEIPT_DIR, f"{invoice_no}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
