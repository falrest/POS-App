import customtkinter as ctk
from tkinter import ttk, messagebox
import csv
from datetime import datetime

import db
import receipt as receipt_module

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

PRIMARY_COLOR = "#2563EB"
SUCCESS_COLOR = "#16A34A"
DANGER_COLOR = "#DC2626"
BG_COLOR = "#F1F5F9"
CARD_COLOR = "#FFFFFF"
TEXT_MUTED = "#64748B"


def rupiah(n):
    return f"Rp{n:,.0f}".replace(",", ".")


class POSApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Kasir Modern - Point of Sale")
        self.geometry("1280x760")
        self.minsize(1100, 650)
        self.configure(fg_color=BG_COLOR)

        db.init_db()

        # cart state: list of dict {product_id, barcode, name, price, qty, subtotal, stock}
        self.cart = []
        self.discount_percent = 0.0
        self.discount_amount_manual = 0.0

        self._build_layout()
        self.show_kasir()

    # ---------------------------------------------------------------
    # LAYOUT UTAMA (Sidebar + Content area)
    # ---------------------------------------------------------------
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color="#0F172A")
        sidebar.grid(row=0, column=0, sticky="nswe")
        sidebar.grid_propagate(False)

        logo = ctk.CTkLabel(sidebar, text="🛒 Kasir Modern", font=ctk.CTkFont(size=20, weight="bold"),
                             text_color="white")
        logo.pack(pady=(28, 30), padx=20, anchor="w")

        self.nav_buttons = {}
        nav_items = [
            ("kasir", "🧾  Kasir"),
            ("produk", "📦  Produk"),
            ("laporan", "📊  Laporan"),
        ]
        for key, label in nav_items:
            btn = ctk.CTkButton(
                sidebar, text=label, anchor="w", height=44,
                fg_color="transparent", hover_color="#1E293B",
                font=ctk.CTkFont(size=14),
                command=lambda k=key: self._switch_page(k),
            )
            btn.pack(fill="x", padx=14, pady=4)
            self.nav_buttons[key] = btn

        bottom_info = ctk.CTkLabel(
            sidebar, text="POS Python Project\nv1.0", font=ctk.CTkFont(size=11),
            text_color="#64748B", justify="left"
        )
        bottom_info.pack(side="bottom", pady=20, padx=20, anchor="w")

        # Content container
        self.content = ctk.CTkFrame(self, fg_color=BG_COLOR)
        self.content.grid(row=0, column=1, sticky="nswe")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.pages = {}

    def _switch_page(self, key):
        for k, btn in self.nav_buttons.items():
            btn.configure(fg_color=PRIMARY_COLOR if k == key else "transparent")
        for page in self.pages.values():
            page.grid_forget()

        if key == "kasir":
            self.show_kasir()
        elif key == "produk":
            self.show_produk()
        elif key == "laporan":
            self.show_laporan()

    # ---------------------------------------------------------------
    # HALAMAN KASIR
    # ---------------------------------------------------------------
    def show_kasir(self):
        if "kasir" in self.pages:
            self.pages["kasir"].grid(row=0, column=0, sticky="nswe")
            self.nav_buttons["kasir"].configure(fg_color=PRIMARY_COLOR)
            self._refresh_product_grid()
            return

        page = ctk.CTkFrame(self.content, fg_color=BG_COLOR)
        page.grid(row=0, column=0, sticky="nswe")
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(0, weight=1)
        self.pages["kasir"] = page
        self.nav_buttons["kasir"].configure(fg_color=PRIMARY_COLOR)

        # ---------- LEFT: Scan barcode + grid produk ----------
        left = ctk.CTkFrame(page, fg_color=CARD_COLOR, corner_radius=14)
        left.grid(row=0, column=0, sticky="nswe", padx=(20, 10), pady=20)
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        scan_frame = ctk.CTkFrame(left, fg_color="transparent")
        scan_frame.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(scan_frame, text="📷 Scan Barcode", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")

        self.barcode_entry = ctk.CTkEntry(
            scan_frame, placeholder_text="Arahkan scanner ke sini lalu scan / ketik barcode + Enter...",
            height=42, font=ctk.CTkFont(size=14)
        )
        self.barcode_entry.pack(fill="x", pady=(8, 0))
        self.barcode_entry.bind("<Return>", self._on_scan_barcode)
        self.barcode_entry.focus()

        search_frame = ctk.CTkFrame(left, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(6, 10))
        ctk.CTkLabel(search_frame, text="Atau cari produk manual:", font=ctk.CTkFont(size=12),
                     text_color=TEXT_MUTED).pack(anchor="w")
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Ketik nama produk...", height=36)
        self.search_entry.pack(fill="x", pady=(4, 0))
        self.search_entry.bind("<KeyRelease>", lambda e: self._refresh_product_grid())

        self.product_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.product_scroll.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # ---------- RIGHT: Keranjang / Cart ----------
        right = ctk.CTkFrame(page, fg_color=CARD_COLOR, corner_radius=14)
        right.grid(row=0, column=1, sticky="nswe", padx=(10, 20), pady=20)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="🛒 Keranjang Belanja", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 8))

        # Treeview untuk cart (pakai ttk karena tabel scrollable rapi)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Cart.Treeview", rowheight=30, font=("Segoe UI", 10), background="white",
                         fieldbackground="white")
        style.configure("Cart.Treeview.Heading", font=("Segoe UI", 10, "bold"))

        cart_frame = ctk.CTkFrame(right, fg_color="transparent")
        cart_frame.grid(row=1, column=0, sticky="nswe", padx=16)
        cart_frame.grid_rowconfigure(0, weight=1)
        cart_frame.grid_columnconfigure(0, weight=1)

        columns = ("nama", "harga", "qty", "subtotal")
        self.cart_tree = ttk.Treeview(cart_frame, columns=columns, show="headings", style="Cart.Treeview")
        self.cart_tree.heading("nama", text="Produk")
        self.cart_tree.heading("harga", text="Harga")
        self.cart_tree.heading("qty", text="Qty")
        self.cart_tree.heading("subtotal", text="Subtotal")
        self.cart_tree.column("nama", width=150, anchor="w")
        self.cart_tree.column("harga", width=85, anchor="e")
        self.cart_tree.column("qty", width=50, anchor="center")
        self.cart_tree.column("subtotal", width=95, anchor="e")
        self.cart_tree.grid(row=0, column=0, sticky="nswe")

        cart_scroll = ttk.Scrollbar(cart_frame, orient="vertical", command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=cart_scroll.set)
        cart_scroll.grid(row=0, column=1, sticky="ns")

        # Tombol qty +/- dan hapus
        cart_btns = ctk.CTkFrame(right, fg_color="transparent")
        cart_btns.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 0))
        ctk.CTkButton(cart_btns, text="➖ Kurangi", width=90, height=30, fg_color="#F59E0B",
                      command=self._decrease_qty).pack(side="left", padx=(0, 6))
        ctk.CTkButton(cart_btns, text="➕ Tambah", width=90, height=30, fg_color=SUCCESS_COLOR,
                      command=self._increase_qty).pack(side="left", padx=(0, 6))
        ctk.CTkButton(cart_btns, text="🗑 Hapus", width=90, height=30, fg_color=DANGER_COLOR,
                      command=self._remove_selected).pack(side="left", padx=(0, 6))
        ctk.CTkButton(cart_btns, text="Kosongkan", width=90, height=30, fg_color="#94A3B8",
                      command=self._clear_cart).pack(side="left")

        # ---------- Diskon & Total ----------
        summary = ctk.CTkFrame(right, fg_color="#F8FAFC", corner_radius=12)
        summary.grid(row=3, column=0, sticky="ew", padx=16, pady=14)
        summary.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(summary, text="Diskon (%)", font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 4))
        self.discount_percent_entry = ctk.CTkEntry(summary, width=90, placeholder_text="0")
        self.discount_percent_entry.grid(row=0, column=1, sticky="e", padx=14, pady=(12, 4))
        self.discount_percent_entry.bind("<KeyRelease>", lambda e: self._recalculate())

        ctk.CTkLabel(summary, text="Diskon Nominal (Rp)", font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, sticky="w", padx=14, pady=4)
        self.discount_amount_entry = ctk.CTkEntry(summary, width=90, placeholder_text="0")
        self.discount_amount_entry.grid(row=1, column=1, sticky="e", padx=14, pady=4)
        self.discount_amount_entry.bind("<KeyRelease>", lambda e: self._recalculate())

        ttk.Separator(summary, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=6)

        self.subtotal_label = self._summary_row(summary, 3, "Subtotal")
        self.discount_label = self._summary_row(summary, 4, "Diskon")
        self.total_label = self._summary_row(summary, 5, "TOTAL", big=True)

        pay_btn = ctk.CTkButton(right, text="💳  BAYAR", height=50, font=ctk.CTkFont(size=16, weight="bold"),
                                 fg_color=SUCCESS_COLOR, hover_color="#15803D", command=self._open_payment_dialog)
        pay_btn.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 18))

        self._refresh_product_grid()
        self._recalculate()

    def _summary_row(self, parent, row, label_text, big=False):
        ctk.CTkLabel(parent, text=label_text,
                     font=ctk.CTkFont(size=15 if big else 12, weight="bold" if big else "normal")
                     ).grid(row=row, column=0, sticky="w", padx=14, pady=(4, 12 if big else 4))
        value_label = ctk.CTkLabel(parent, text="Rp0",
                                    font=ctk.CTkFont(size=17 if big else 13, weight="bold"),
                                    text_color=PRIMARY_COLOR if big else "black")
        value_label.grid(row=row, column=1, sticky="e", padx=14, pady=(4, 12 if big else 4))
        return value_label

    # ---------------- Product grid (kasir) ----------------
    def _refresh_product_grid(self):
        for w in self.product_scroll.winfo_children():
            w.destroy()

        keyword = self.search_entry.get().strip() if hasattr(self, "search_entry") else ""
        products = db.get_all_products(keyword if keyword else None)

        cols = 3
        for idx, p in enumerate(products):
            r, c = divmod(idx, cols)
            card = ctk.CTkFrame(self.product_scroll, fg_color="#F8FAFC", corner_radius=10,
                                 border_width=1, border_color="#E2E8F0")
            card.grid(row=r, column=c, padx=6, pady=6, sticky="nswe")
            self.product_scroll.grid_columnconfigure(c, weight=1)

            name_lbl = ctk.CTkLabel(card, text=p["name"], font=ctk.CTkFont(size=12, weight="bold"),
                                     wraplength=140, justify="left")
            name_lbl.pack(anchor="w", padx=10, pady=(10, 0))
            ctk.CTkLabel(card, text=rupiah(p["price"]), font=ctk.CTkFont(size=12),
                         text_color=PRIMARY_COLOR).pack(anchor="w", padx=10)
            stock_color = DANGER_COLOR if p["stock"] <= 0 else TEXT_MUTED
            ctk.CTkLabel(card, text=f"Stok: {p['stock']}", font=ctk.CTkFont(size=10),
                         text_color=stock_color).pack(anchor="w", padx=10, pady=(0, 6))
            add_btn = ctk.CTkButton(card, text="+ Keranjang", height=26, font=ctk.CTkFont(size=11),
                                     command=lambda pid=p["id"]: self._add_product_to_cart_by_id(pid))
            add_btn.pack(fill="x", padx=10, pady=(0, 10))

        if not products:
            ctk.CTkLabel(self.product_scroll, text="Produk tidak ditemukan.", text_color=TEXT_MUTED).pack(pady=30)

    # ---------------- Barcode scan ----------------
    def _on_scan_barcode(self, event=None):
        code = self.barcode_entry.get().strip()
        self.barcode_entry.delete(0, "end")
        if not code:
            return
        product = db.get_product_by_barcode(code)
        if not product:
            messagebox.showwarning("Tidak ditemukan", f"Produk dengan barcode '{code}' tidak ditemukan.")
            return
        self._add_product_to_cart(product)

    def _add_product_to_cart_by_id(self, product_id):
        product = db.get_product_by_id(product_id)
        if product:
            self._add_product_to_cart(product)

    def _add_product_to_cart(self, product):
        if product["stock"] <= 0:
            messagebox.showwarning("Stok habis", f"Stok '{product['name']}' habis.")
            return

        for item in self.cart:
            if item["product_id"] == product["id"]:
                if item["qty"] + 1 > product["stock"]:
                    messagebox.showwarning("Stok tidak cukup", f"Stok '{product['name']}' tidak mencukupi.")
                    return
                item["qty"] += 1
                item["subtotal"] = item["qty"] * item["price"]
                self._render_cart()
                return

        self.cart.append({
            "product_id": product["id"],
            "barcode": product["barcode"],
            "name": product["name"],
            "price": product["price"],
            "qty": 1,
            "subtotal": product["price"],
            "stock": product["stock"],
        })
        self._render_cart()

    def _render_cart(self):
        self.cart_tree.delete(*self.cart_tree.get_children())
        for idx, item in enumerate(self.cart):
            self.cart_tree.insert("", "end", iid=str(idx), values=(
                item["name"], rupiah(item["price"]), item["qty"], rupiah(item["subtotal"])
            ))
        self._recalculate()

    def _get_selected_cart_index(self):
        sel = self.cart_tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _increase_qty(self):
        idx = self._get_selected_cart_index()
        if idx is None:
            return
        item = self.cart[idx]
        if item["qty"] + 1 > item["stock"]:
            messagebox.showwarning("Stok tidak cukup", "Jumlah melebihi stok tersedia.")
            return
        item["qty"] += 1
        item["subtotal"] = item["qty"] * item["price"]
        self._render_cart()

    def _decrease_qty(self):
        idx = self._get_selected_cart_index()
        if idx is None:
            return
        item = self.cart[idx]
        item["qty"] -= 1
        if item["qty"] <= 0:
            self.cart.pop(idx)
        else:
            item["subtotal"] = item["qty"] * item["price"]
        self._render_cart()

    def _remove_selected(self):
        idx = self._get_selected_cart_index()
        if idx is None:
            return
        self.cart.pop(idx)
        self._render_cart()

    def _clear_cart(self):
        if self.cart and messagebox.askyesno("Konfirmasi", "Kosongkan keranjang?"):
            self.cart = []
            self._render_cart()

    # ---------------- Diskon & Kalkulasi ----------------
    def _get_subtotal(self):
        return sum(item["subtotal"] for item in self.cart)

    def _recalculate(self):
        subtotal = self._get_subtotal()

        try:
            percent = float(self.discount_percent_entry.get() or 0)
        except ValueError:
            percent = 0
        try:
            nominal = float(self.discount_amount_entry.get() or 0)
        except ValueError:
            nominal = 0

        percent = max(0, min(percent, 100))
        discount_from_percent = subtotal * (percent / 100)
        total_discount = discount_from_percent + max(0, nominal)
        total_discount = min(total_discount, subtotal)  # tidak boleh negatif

        total = subtotal - total_discount

        self.discount_percent = percent
        self.discount_amount_manual = nominal

        self.subtotal_label.configure(text=rupiah(subtotal))
        self.discount_label.configure(text="-" + rupiah(total_discount))
        self.total_label.configure(text=rupiah(total))

        return subtotal, total_discount, total

    # ---------------- Pembayaran & Struk ----------------
    def _open_payment_dialog(self):
        if not self.cart:
            messagebox.showinfo("Keranjang kosong", "Silakan tambahkan produk ke keranjang terlebih dahulu.")
            return

        subtotal, total_discount, total = self._recalculate()

        dialog = ctk.CTkToplevel(self)
        dialog.title("Pembayaran")
        dialog.geometry("380x420")
        dialog.grab_set()
        dialog.resizable(False, False)

        ctk.CTkLabel(dialog, text="💳 Pembayaran", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 10))

        ctk.CTkLabel(dialog, text=f"Total Belanja", font=ctk.CTkFont(size=13), text_color=TEXT_MUTED).pack()
        ctk.CTkLabel(dialog, text=rupiah(total), font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=PRIMARY_COLOR).pack(pady=(0, 16))

        ctk.CTkLabel(dialog, text="Metode Pembayaran").pack(anchor="w", padx=30)
        method_var = ctk.StringVar(value="Tunai")
        method_menu = ctk.CTkOptionMenu(dialog, values=["Tunai", "Kartu Debit/Kredit", "QRIS", "Transfer"],
                                         variable=method_var)
        method_menu.pack(fill="x", padx=30, pady=(4, 14))

        ctk.CTkLabel(dialog, text="Jumlah Dibayar (Rp)").pack(anchor="w", padx=30)
        paid_entry = ctk.CTkEntry(dialog, placeholder_text="0", height=40, font=ctk.CTkFont(size=15))
        paid_entry.pack(fill="x", padx=30, pady=(4, 6))
        paid_entry.insert(0, str(int(total)))
        paid_entry.focus()

        change_label = ctk.CTkLabel(dialog, text="Kembalian: Rp0", font=ctk.CTkFont(size=14, weight="bold"),
                                     text_color=SUCCESS_COLOR)
        change_label.pack(pady=(4, 10))

        def update_change(event=None):
            try:
                paid = float(paid_entry.get() or 0)
            except ValueError:
                paid = 0
            change = paid - total
            change_label.configure(
                text=f"Kembalian: {rupiah(change)}" if change >= 0 else "Uang tidak cukup!",
                text_color=SUCCESS_COLOR if change >= 0 else DANGER_COLOR
            )

        paid_entry.bind("<KeyRelease>", update_change)
        update_change()

        def confirm_payment():
            try:
                paid = float(paid_entry.get() or 0)
            except ValueError:
                messagebox.showerror("Error", "Jumlah bayar tidak valid.")
                return
            if paid < total:
                messagebox.showerror("Error", "Jumlah bayar kurang dari total belanja.")
                return

            change_amount = paid - total
            invoice_no, transaction_id, dt_str = db.save_transaction(
                cart_items=self.cart,
                subtotal=subtotal,
                discount_percent=self.discount_percent,
                discount_amount=total_discount,
                total=total,
                paid=paid,
                change_amount=change_amount,
                cashier="Kasir",
                payment_method=method_var.get(),
            )

            receipt_text = receipt_module.build_receipt_text(
                invoice_no, dt_str, self.cart, subtotal, self.discount_percent,
                total_discount, total, paid, change_amount, cashier="Kasir"
            )
            path = receipt_module.save_receipt_file(invoice_no, receipt_text)

            dialog.destroy()
            self._show_receipt_window(receipt_text, path)

            # reset kasir
            self.cart = []
            self.discount_percent_entry.delete(0, "end")
            self.discount_amount_entry.delete(0, "end")
            self._render_cart()
            self._refresh_product_grid()

        ctk.CTkButton(dialog, text="✅ Konfirmasi & Cetak Struk", height=44, fg_color=SUCCESS_COLOR,
                      font=ctk.CTkFont(size=14, weight="bold"), command=confirm_payment).pack(
            fill="x", padx=30, pady=(6, 20))

    def _show_receipt_window(self, receipt_text, path):
        win = ctk.CTkToplevel(self)
        win.title("Struk Belanja")
        win.geometry("380x560")
        win.grab_set()

        ctk.CTkLabel(win, text="🧾 Struk Belanja", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(16, 6))

        textbox = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Courier New", size=12), wrap="none")
        textbox.pack(fill="both", expand=True, padx=16, pady=6)
        textbox.insert("1.0", receipt_text)
        textbox.configure(state="disabled")

        ctk.CTkLabel(win, text=f"Tersimpan di: {path}", font=ctk.CTkFont(size=10),
                     text_color=TEXT_MUTED, wraplength=340).pack(pady=(0, 6))

        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(btn_frame, text="🖨 Cetak (Print)", command=lambda: self._print_receipt(path)).pack(
            side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(btn_frame, text="Tutup", fg_color="#94A3B8", command=win.destroy).pack(
            side="left", expand=True, fill="x", padx=(6, 0))

    def _print_receipt(self, path):
        import sys
        try:
            if sys.platform.startswith("win"):
                import os as _os
                _os.startfile(path, "print")
            else:
                import subprocess
                subprocess.run(["lp", path], check=False)
            messagebox.showinfo("Cetak", "Perintah cetak dikirim ke printer default.")
        except Exception as e:
            messagebox.showwarning("Cetak", f"Tidak bisa mencetak otomatis di sistem ini.\n"
                                             f"File struk tersimpan di:\n{path}\n\nDetail: {e}")

    # =================================================================
    # HALAMAN PRODUK (CRUD)
    # =================================================================
    def show_produk(self):
        self.nav_buttons["produk"].configure(fg_color=PRIMARY_COLOR)
        if "produk" in self.pages:
            self.pages["produk"].grid(row=0, column=0, sticky="nswe")
            self._refresh_produk_table()
            return

        page = ctk.CTkFrame(self.content, fg_color=BG_COLOR)
        page.grid(row=0, column=0, sticky="nswe")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self.pages["produk"] = page

        header = ctk.CTkFrame(page, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="📦 Manajemen Produk", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Tambah Produk", fg_color=SUCCESS_COLOR,
                      command=lambda: self._open_product_form()).pack(side="right")

        self.produk_search_entry = ctk.CTkEntry(header, placeholder_text="🔍 Cari produk / barcode...", width=260)
        self.produk_search_entry.pack(side="right", padx=10)
        self.produk_search_entry.bind("<KeyRelease>", lambda e: self._refresh_produk_table())

        table_card = ctk.CTkFrame(page, fg_color=CARD_COLOR, corner_radius=14)
        table_card.grid(row=1, column=0, sticky="nswe", padx=20, pady=(0, 20))
        table_card.grid_rowconfigure(0, weight=1)
        table_card.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("Produk.Treeview", rowheight=32, font=("Segoe UI", 10))
        style.configure("Produk.Treeview.Heading", font=("Segoe UI", 10, "bold"))

        cols = ("barcode", "nama", "kategori", "harga", "modal", "stok")
        self.produk_tree = ttk.Treeview(table_card, columns=cols, show="headings", style="Produk.Treeview")
        headers = {"barcode": "Barcode", "nama": "Nama Produk", "kategori": "Kategori",
                   "harga": "Harga Jual", "modal": "Harga Modal", "stok": "Stok"}
        widths = {"barcode": 140, "nama": 220, "kategori": 110, "harga": 100, "modal": 100, "stok": 70}
        for c in cols:
            self.produk_tree.heading(c, text=headers[c])
            self.produk_tree.column(c, width=widths[c], anchor="center" if c in ("stok",) else "w")
        self.produk_tree.grid(row=0, column=0, sticky="nswe", padx=(16, 0), pady=16)
        self.produk_tree.bind("<Double-1>", lambda e: self._edit_selected_product())

        pscroll = ttk.Scrollbar(table_card, orient="vertical", command=self.produk_tree.yview)
        self.produk_tree.configure(yscrollcommand=pscroll.set)
        pscroll.grid(row=0, column=1, sticky="ns", pady=16)

        action_bar = ctk.CTkFrame(table_card, fg_color="transparent")
        action_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))
        ctk.CTkButton(action_bar, text="✏ Edit", width=100, command=self._edit_selected_product).pack(side="left")
        ctk.CTkButton(action_bar, text="🗑 Hapus", width=100, fg_color=DANGER_COLOR,
                      command=self._delete_selected_product).pack(side="left", padx=8)

        self._refresh_produk_table()

    def _refresh_produk_table(self):
        self.produk_tree.delete(*self.produk_tree.get_children())
        keyword = self.produk_search_entry.get().strip() if hasattr(self, "produk_search_entry") else ""
        products = db.get_all_products(keyword if keyword else None)
        for p in products:
            self.produk_tree.insert("", "end", iid=str(p["id"]), values=(
                p["barcode"], p["name"], p["category"], rupiah(p["price"]), rupiah(p["cost"]), p["stock"]
            ))

    def _get_selected_product_id(self):
        sel = self.produk_tree.selection()
        if not sel:
            messagebox.showinfo("Pilih produk", "Silakan pilih produk terlebih dahulu.")
            return None
        return int(sel[0])

    def _edit_selected_product(self):
        pid = self._get_selected_product_id()
        if pid is None:
            return
        product = db.get_product_by_id(pid)
        self._open_product_form(product)

    def _delete_selected_product(self):
        pid = self._get_selected_product_id()
        if pid is None:
            return
        if messagebox.askyesno("Konfirmasi", "Hapus produk ini? Data transaksi lama tidak akan terhapus."):
            db.delete_product(pid)
            self._refresh_produk_table()

    def _open_product_form(self, product=None):
        is_edit = product is not None
        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Produk" if is_edit else "Tambah Produk")
        dialog.geometry("380x460")
        dialog.grab_set()

        ctk.CTkLabel(dialog, text=("✏ Edit Produk" if is_edit else "➕ Tambah Produk"),
                     font=ctk.CTkFont(size=17, weight="bold")).pack(pady=(20, 14))

        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=30)

        def field(label, default=""):
            ctk.CTkLabel(form, text=label, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(8, 2))
            entry = ctk.CTkEntry(form, height=36)
            entry.pack(fill="x")
            if default != "":
                entry.insert(0, str(default))
            return entry

        barcode_entry = field("Barcode", product["barcode"] if is_edit else "")
        name_entry = field("Nama Produk", product["name"] if is_edit else "")
        category_entry = field("Kategori", product["category"] if is_edit else "Umum")
        price_entry = field("Harga Jual (Rp)", product["price"] if is_edit else "")
        cost_entry = field("Harga Modal (Rp)", product["cost"] if is_edit else "")
        stock_entry = field("Stok", product["stock"] if is_edit else "")

        def save():
            try:
                barcode = barcode_entry.get().strip()
                name = name_entry.get().strip()
                category = category_entry.get().strip() or "Umum"
                price = float(price_entry.get() or 0)
                cost = float(cost_entry.get() or 0)
                stock = int(stock_entry.get() or 0)
            except ValueError:
                messagebox.showerror("Error", "Pastikan harga & stok berupa angka.")
                return

            if not barcode or not name:
                messagebox.showerror("Error", "Barcode dan nama produk wajib diisi.")
                return

            try:
                if is_edit:
                    db.update_product(product["id"], barcode, name, category, price, cost, stock)
                else:
                    db.add_product(barcode, name, category, price, cost, stock)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menyimpan (barcode mungkin sudah ada).\n{e}")
                return

            dialog.destroy()
            self._refresh_produk_table()
            if "kasir" in self.pages:
                self._refresh_product_grid()

        ctk.CTkButton(dialog, text="💾 Simpan", height=42, fg_color=SUCCESS_COLOR,
                      font=ctk.CTkFont(size=14, weight="bold"), command=save).pack(fill="x", padx=30, pady=20)

    # =================================================================
    # HALAMAN LAPORAN PENJUALAN
    # =================================================================
    def show_laporan(self):
        self.nav_buttons["laporan"].configure(fg_color=PRIMARY_COLOR)
        if "laporan" in self.pages:
            self.pages["laporan"].grid(row=0, column=0, sticky="nswe")
            return

        page = ctk.CTkFrame(self.content, fg_color=BG_COLOR)
        page.grid(row=0, column=0, sticky="nswe")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)
        self.pages["laporan"] = page

        ctk.CTkLabel(page, text="📊 Laporan Penjualan", font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        filter_bar = ctk.CTkFrame(page, fg_color=CARD_COLOR, corner_radius=12)
        filter_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 14))

        today = datetime.now().strftime("%Y-%m-%d")
        ctk.CTkLabel(filter_bar, text="Dari (YYYY-MM-DD)").pack(side="left", padx=(16, 6), pady=14)
        self.report_start_entry = ctk.CTkEntry(filter_bar, width=120)
        self.report_start_entry.insert(0, today)
        self.report_start_entry.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(filter_bar, text="Sampai (YYYY-MM-DD)").pack(side="left", padx=(0, 6))
        self.report_end_entry = ctk.CTkEntry(filter_bar, width=120)
        self.report_end_entry.insert(0, today)
        self.report_end_entry.pack(side="left", padx=(0, 14))

        ctk.CTkButton(filter_bar, text="🔍 Tampilkan", command=self._refresh_report).pack(side="left", padx=6)
        ctk.CTkButton(filter_bar, text="⬇ Export CSV", fg_color="#0EA5E9",
                      command=self._export_report_csv).pack(side="left", padx=6)

        self.summary_label = ctk.CTkLabel(filter_bar, text="", font=ctk.CTkFont(size=12, weight="bold"),
                                           text_color=PRIMARY_COLOR)
        self.summary_label.pack(side="right", padx=16)

        body = ctk.CTkFrame(page, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nswe", padx=20, pady=(0, 20))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        trans_card = ctk.CTkFrame(body, fg_color=CARD_COLOR, corner_radius=14)
        trans_card.grid(row=0, column=0, sticky="nswe", padx=(0, 10))
        trans_card.grid_rowconfigure(1, weight=1)
        trans_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(trans_card, text="Riwayat Transaksi", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        cols = ("invoice", "tanggal", "total", "metode")
        self.report_tree = ttk.Treeview(trans_card, columns=cols, show="headings")
        headers = {"invoice": "No Invoice", "tanggal": "Tanggal", "total": "Total", "metode": "Metode"}
        widths = {"invoice": 130, "tanggal": 140, "total": 100, "metode": 110}
        for c in cols:
            self.report_tree.heading(c, text=headers[c])
            self.report_tree.column(c, width=widths[c])
        self.report_tree.grid(row=1, column=0, sticky="nswe", padx=(16, 0), pady=(0, 16))
        rscroll = ttk.Scrollbar(trans_card, orient="vertical", command=self.report_tree.yview)
        self.report_tree.configure(yscrollcommand=rscroll.set)
        rscroll.grid(row=1, column=1, sticky="ns", pady=(0, 16))

        top_card = ctk.CTkFrame(body, fg_color=CARD_COLOR, corner_radius=14)
        top_card.grid(row=0, column=1, sticky="nswe", padx=(10, 0))
        top_card.grid_rowconfigure(1, weight=1)
        top_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(top_card, text="🏆 Produk Terlaris", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        top_cols = ("nama", "qty", "omzet")
        self.top_tree = ttk.Treeview(top_card, columns=top_cols, show="headings")
        top_headers = {"nama": "Produk", "qty": "Terjual", "omzet": "Omzet"}
        for c in top_cols:
            self.top_tree.heading(c, text=top_headers[c])
            self.top_tree.column(c, width=110)
        self.top_tree.grid(row=1, column=0, sticky="nswe", padx=(16, 0), pady=(0, 16))
        tscroll = ttk.Scrollbar(top_card, orient="vertical", command=self.top_tree.yview)
        self.top_tree.configure(yscrollcommand=tscroll.set)
        tscroll.grid(row=1, column=1, sticky="ns", pady=(0, 16))

        self._refresh_report()

    def _refresh_report(self):
        start = self.report_start_entry.get().strip()
        end = self.report_end_entry.get().strip()
        try:
            datetime.strptime(start, "%Y-%m-%d")
            datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Format tanggal harus YYYY-MM-DD")
            return

        summary = db.get_sales_summary(start, end)
        self.summary_label.configure(
            text=f"Transaksi: {summary['jumlah_transaksi']}  |  "
                 f"Total: {rupiah(summary['total_penjualan'])}  |  "
                 f"Diskon: {rupiah(summary['total_diskon'])}"
        )

        self.report_tree.delete(*self.report_tree.get_children())
        for t in db.get_transactions_between(start, end):
            self.report_tree.insert("", "end", values=(
                t["invoice_no"], t["datetime"], rupiah(t["total"]), t["payment_method"]
            ))

        self.top_tree.delete(*self.top_tree.get_children())
        for tp in db.get_top_products(start, end):
            self.top_tree.insert("", "end", values=(tp["name"], tp["total_qty"], rupiah(tp["total_omzet"])))

    def _export_report_csv(self):
        start = self.report_start_entry.get().strip()
        end = self.report_end_entry.get().strip()
        transactions = db.get_transactions_between(start, end)
        if not transactions:
            messagebox.showinfo("Kosong", "Tidak ada data transaksi pada rentang tanggal ini.")
            return

        import os
        export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
        os.makedirs(export_dir, exist_ok=True)
        filename = f"laporan_{start}_sd_{end}.csv"
        path = os.path.join(export_dir, filename)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["No Invoice", "Tanggal", "Subtotal", "Diskon", "Total", "Dibayar", "Kembalian", "Metode"])
            for t in transactions:
                writer.writerow([t["invoice_no"], t["datetime"], t["subtotal"], t["discount_amount"],
                                  t["total"], t["paid"], t["change_amount"], t["payment_method"]])

        messagebox.showinfo("Export Berhasil", f"Laporan berhasil diexport ke:\n{path}")


if __name__ == "__main__":
    app = POSApp()
    app.mainloop()
