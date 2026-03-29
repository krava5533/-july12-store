import os
import sqlite3
import secrets
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "store.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg"}

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file_obj):
    if not file_obj or not getattr(file_obj, "filename", ""):
        return ""
    if not allowed_file(file_obj.filename):
        return ""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    filename = f"{secrets.token_hex(8)}_{secure_filename(file_obj.filename)}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file_obj.save(path)
    return f"/static/uploads/{filename}"


def get_settings() -> dict:
    conn = db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def set_setting(key: str, value: str) -> None:
    conn = db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_sections() -> dict:
    conn = db()
    rows = conn.execute("SELECT key, enabled FROM sections").fetchall()
    conn.close()
    return {r["key"]: bool(r["enabled"]) for r in rows}


def set_section(key: str, enabled: bool) -> None:
    conn = db()
    conn.execute("INSERT OR REPLACE INTO sections (key, enabled) VALUES (?, ?)", (key, int(bool(enabled))))
    conn.commit()
    conn.close()


def init_db():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price REAL,
            category TEXT,
            description TEXT,
            image_path TEXT,
            featured INTEGER DEFAULT 0,
            luxury INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            sort_order INTEGER DEFAULT 0,
            visible INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sections (
            key TEXT PRIMARY KEY,
            enabled INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT,
            customer_name TEXT,
            customer_phone TEXT,
            customer_email TEXT,
            city TEXT,
            address TEXT,
            postal_code TEXT,
            subtotal REAL,
            delivery_fee REAL,
            tax_amount REAL,
            total REAL,
            delivery_provider TEXT,
            order_status TEXT DEFAULT 'New',
            payment_status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_name TEXT,
            quantity INTEGER,
            price REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS custom_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            email TEXT,
            budget TEXT,
            colors TEXT,
            occasion TEXT,
            delivery_date TEXT,
            address TEXT,
            notes TEXT,
            reference_image TEXT,
            status TEXT DEFAULT 'New',
            created_at TEXT
        )
    """)

    defaults = {
        "store_name": "July12",
        "store_currency": "cad",
        "logo_url": "",
        "hero_title": "July12",
        "hero_subtitle": "Luxury Flowers & Same-Day Delivery in GTA",
        "hero_button_text": "Shop Now",
        "hero_background": "",
        "instagram_url": "https://www.instagram.com/july12.ca",
        "phone": "+1 (647) 000-0000",
        "email": "",
        "whatsapp": "",
        "tax_name": "HST",
        "tax_rate": "13",
        "zone1_name": "Zone 1",
        "zone1_cities": "Toronto,North York",
        "zone1_fee": "10",
        "zone2_name": "Zone 2",
        "zone2_cities": "Vaughan,Richmond Hill,Markham,Thornhill",
        "zone2_fee": "15",
        "zone3_name": "Zone 3",
        "zone3_cities": "Other GTA",
        "zone3_fee": "20",
        "delivery_provider_mode": "fixed",
        "uber_enabled": "off",
        "uber_mode": "manual_quote",
        "uber_margin": "0",
        "uber_pickup_address": "",
        "stripe_public_key": "",
        "stripe_secret_key": "",
        "announcement_bar": "",
        "footer_text": "July12 • Luxury Flower Studio",
    }

    for k, v in defaults.items():
        if not cur.execute("SELECT 1 FROM settings WHERE key=?", (k,)).fetchone():
            cur.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (k, v))

    for key in [
        "hero",
        "categories",
        "best_sellers",
        "luxury",
        "custom_bouquet",
        "info",
        "announcement",
    ]:
        if not cur.execute("SELECT 1 FROM sections WHERE key=?", (key,)).fetchone():
            cur.execute("INSERT INTO sections (key, enabled) VALUES (?, 1)", (key,))

    if cur.execute("SELECT COUNT(*) c FROM categories").fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO categories (name, sort_order, visible) VALUES (?, ?, ?)",
            [
                ("All Flowers", 1, 1),
                ("Bouquets", 2, 1),
                ("Luxury Collection", 3, 1),
                ("Flower Boxes", 4, 1),
                ("Baskets", 5, 1),
                ("Bridal", 6, 1),
                ("Gifts", 7, 1),
            ],
        )

    if cur.execute("SELECT COUNT(*) c FROM products").fetchone()["c"] == 0:
        cur.executemany(
            """
            INSERT INTO products
            (name, price, category, description, image_path, featured, luxury, active, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("Rose Couture Box", 149, "Flower Boxes", "Luxury roses in a premium box.", "", 1, 1, 1, 1),
                ("Signature Pink Bouquet", 89, "Bouquets", "Soft elegant bouquet for gifting.", "", 1, 0, 1, 2),
                ("White Orchid Luxe", 249, "Luxury Collection", "Premium arrangement for special moments.", "", 1, 1, 1, 3),
                ("Bridal Bloom", 299, "Bridal", "Editorial bridal bouquet.", "", 0, 1, 1, 4),
            ],
        )

    conn.commit()
    conn.close()


def delivery_quote(city: str, s: dict):
    city = (city or "").strip().lower()
    zones = [
        (s.get("zone1_name", "Zone 1"), s.get("zone1_cities", ""), float(s.get("zone1_fee", "10") or 10)),
        (s.get("zone2_name", "Zone 2"), s.get("zone2_cities", ""), float(s.get("zone2_fee", "15") or 15)),
        (s.get("zone3_name", "Zone 3"), s.get("zone3_cities", ""), float(s.get("zone3_fee", "20") or 20)),
    ]

    zone_name, fee = zones[-1][0], zones[-1][2]
    for name, cities, price in zones:
        if city in [c.strip().lower() for c in cities.split(",") if c.strip()]:
            zone_name, fee = name, price
            break

    if s.get("delivery_provider_mode") == "uber" and s.get("uber_enabled") == "on":
        fee += float(s.get("uber_margin", "0") or 0)
        return "Uber Direct", zone_name, round(fee, 2)

    return "Fixed GTA Delivery", zone_name, round(fee, 2)


def cart_items():
    cart = session.get("cart", {})
    if not cart:
        return [], 0.0

    conn = db()
    ids = list(cart.keys())
    rows = conn.execute(
        f"SELECT * FROM products WHERE id IN ({','.join('?' * len(ids))})",
        ids,
    ).fetchall()
    conn.close()

    mapping = {str(r["id"]): r for r in rows}
    items = []
    subtotal = 0.0

    for pid, qty in cart.items():
        r = mapping.get(str(pid))
        if not r:
            continue
        qty = int(qty)
        line_total = float(r["price"]) * qty
        subtotal += line_total
        items.append({
            "id": r["id"],
            "name": r["name"],
            "price": float(r["price"]),
            "qty": qty,
            "line_total": line_total,
            "image_path": r["image_path"] or "",
        })

    return items, round(subtotal, 2)


@app.context_processor
def inject_globals():
    s = get_settings()
    items, _ = cart_items()
    return {
        "settings": s,
        "sections": get_sections(),
        "store_name": s.get("store_name", "July12"),
        "cart_count": sum(i["qty"] for i in items),
    }


@app.route("/")
def home():
    conn = db()
    featured = conn.execute("SELECT * FROM products WHERE featured=1 AND active=1 ORDER BY sort_order, id").fetchall()
    luxury = conn.execute("SELECT * FROM products WHERE luxury=1 AND active=1 ORDER BY sort_order, id").fetchall()
    categories = conn.execute("SELECT * FROM categories WHERE visible=1 ORDER BY sort_order, id").fetchall()
    conn.close()
    return render_template("index.html", featured=featured, luxury=luxury, categories=categories)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn = db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    if not product:
        flash("Product not found")
        return redirect(url_for("home"))
    return render_template("product.html", product=product)


@app.route("/add-to-cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    cart = session.get("cart", {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + max(1, int(request.form.get("qty", 1)))
    session["cart"] = cart
    flash("Added to cart")
    return redirect(request.referrer or url_for("home"))


@app.route("/cart")
def cart():
    items, subtotal = cart_items()
    return render_template("cart.html", items=items, subtotal=subtotal)


@app.route("/update-cart", methods=["POST"])
def update_cart():
    cart = session.get("cart", {})
    for key, value in request.form.items():
        if key.startswith("qty_"):
            pid = key.replace("qty_", "")
            qty = max(0, int(value or 0))
            if qty == 0:
                cart.pop(pid, None)
            else:
                cart[pid] = qty
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    items, subtotal = cart_items()
    if not items:
        flash("Cart is empty")
        return redirect(url_for("home"))

    s = get_settings()
    city_options = [c.strip() for c in (s.get("zone1_cities", "") + "," + s.get("zone2_cities", "")).split(",") if c.strip()]
    provider, zone_name, delivery_fee = delivery_quote(city_options[0] if city_options else "Toronto", s)
    tax_amount = round((subtotal + delivery_fee) * (float(s.get("tax_rate", "13") or 0) / 100.0), 2)
    total = round(subtotal + delivery_fee + tax_amount, 2)

    if request.method == "POST":
        name = request.form.get("customer_name", "").strip()
        phone = request.form.get("customer_phone", "").strip()
        email = request.form.get("customer_email", "").strip()
        city = request.form.get("city", "").strip()
        address = request.form.get("address", "").strip()
        postal = request.form.get("postal_code", "").strip()

        if not all([name, phone, email, city, address]):
            flash("Please fill all required fields")
            return render_template(
                "checkout.html",
                items=items,
                subtotal=subtotal,
                cities=city_options,
                delivery_fee=delivery_fee,
                tax_amount=tax_amount,
                tax_name=s.get("tax_name", "HST"),
                total=total,
                delivery_provider=provider,
                quote_note="Estimated delivery",
            )

        provider, zone_name, delivery_fee = delivery_quote(city, s)
        tax_amount = round((subtotal + delivery_fee) * (float(s.get("tax_rate", "13") or 0) / 100.0), 2)
        total = round(subtotal + delivery_fee + tax_amount, 2)

        conn = db()
        cur = conn.cursor()
        order_number = f"J12-{datetime.utcnow().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        cur.execute(
            """
            INSERT INTO orders
            (order_number, customer_name, customer_phone, customer_email, city, address, postal_code, subtotal, delivery_fee, tax_amount, total, delivery_provider, order_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'New', ?)
            """,
            (order_number, name, phone, email, city, address, postal, subtotal, delivery_fee, tax_amount, total, provider, now()),
        )
        order_id = cur.lastrowid

        for item in items:
            cur.execute(
                "INSERT INTO order_items (order_id, product_name, quantity, price) VALUES (?, ?, ?, ?)",
                (order_id, item["name"], item["qty"], item["price"]),
            )

        conn.commit()
        conn.close()
        session["cart"] = {}
        return redirect(url_for("success_manual", order_number=order_number))

    return render_template(
        "checkout.html",
        items=items,
        subtotal=subtotal,
        cities=city_options,
        delivery_fee=delivery_fee,
        tax_amount=tax_amount,
        tax_name=s.get("tax_name", "HST"),
        total=total,
        delivery_provider=provider,
        quote_note="Estimated delivery",
    )


@app.route("/success-manual/<order_number>")
def success_manual(order_number):
    conn = db()
    order = conn.execute("SELECT * FROM orders WHERE order_number=?", (order_number,)).fetchone()
    conn.close()
    return render_template("success.html", order=order)


@app.route("/custom-bouquet", methods=["GET", "POST"])
def custom_bouquet():
    if request.method == "POST":
        ref_image = save_uploaded_file(request.files.get("reference_image"))
        conn = db()
        conn.execute(
            """
            INSERT INTO custom_orders
            (name, phone, email, budget, colors, occasion, delivery_date, address, notes, reference_image, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form.get("name", ""),
                request.form.get("phone", ""),
                request.form.get("email", ""),
                request.form.get("budget", ""),
                request.form.get("colors", ""),
                request.form.get("occasion", ""),
                request.form.get("delivery_date", ""),
                request.form.get("address", ""),
                request.form.get("notes", ""),
                ref_image,
                now(),
            ),
        )
        conn.commit()
        conn.close()
        flash("Custom bouquet request sent")
        return redirect(url_for("home"))
    return render_template("custom_bouquet.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Wrong password")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = db()
    total_products = conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
    total_orders = conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
    total_custom = conn.execute("SELECT COUNT(*) c FROM custom_orders").fetchone()["c"]
    latest_orders = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 8").fetchall()
    conn.close()
    return render_template("admin/dashboard.html", total_products=total_products, total_orders=total_orders, total_custom=total_custom, latest_orders=latest_orders)


@app.route("/admin/products")
@admin_required
def admin_products():
    conn = db()
    products = conn.execute("SELECT * FROM products ORDER BY sort_order, id").fetchall()
    conn.close()
    return render_template("admin/products.html", products=products)


@app.route("/admin/products/new", methods=["GET", "POST"])
@admin_required
def admin_new_product():
    if request.method == "POST":
        image_path = request.form.get("image_url", "").strip()
        uploaded = save_uploaded_file(request.files.get("image_file"))
        if uploaded:
            image_path = uploaded

        conn = db()
        conn.execute(
            """
            INSERT INTO products
            (name, price, category, description, image_path, featured, luxury, active, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form.get("name", ""),
                float(request.form.get("price", 0) or 0),
                request.form.get("category", ""),
                request.form.get("description", ""),
                image_path,
                1 if request.form.get("featured") == "on" else 0,
                1 if request.form.get("luxury") == "on" else 0,
                1 if request.form.get("active") == "on" else 0,
                int(request.form.get("sort_order", 0) or 0),
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", product=None)


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_product(product_id):
    conn = db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()

    if request.method == "POST":
        image_path = request.form.get("current_image", "").strip() or request.form.get("image_url", "").strip()
        uploaded = save_uploaded_file(request.files.get("image_file"))
        if uploaded:
            image_path = uploaded
        elif request.form.get("image_url", "").strip():
            image_path = request.form.get("image_url", "").strip()

        conn.execute(
            """
            UPDATE products
            SET name=?, price=?, category=?, description=?, image_path=?, featured=?, luxury=?, active=?, sort_order=?
            WHERE id=?
            """,
            (
                request.form.get("name", ""),
                float(request.form.get("price", 0) or 0),
                request.form.get("category", ""),
                request.form.get("description", ""),
                image_path,
                1 if request.form.get("featured") == "on" else 0,
                1 if request.form.get("luxury") == "on" else 0,
                1 if request.form.get("active") == "on" else 0,
                int(request.form.get("sort_order", 0) or 0),
                product_id,
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_products"))

    conn.close()
    return render_template("admin/product_form.html", product=product)


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def admin_delete_product(product_id):
    conn = db()
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_products"))


@app.route("/admin/categories", methods=["GET", "POST"])
@admin_required
def admin_categories():
    conn = db()
    if request.method == "POST":
        conn.execute(
            "INSERT INTO categories (name, sort_order, visible) VALUES (?, ?, ?)",
            (
                request.form.get("name", ""),
                int(request.form.get("sort_order", 0) or 0),
                1 if request.form.get("visible") == "on" else 0,
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_categories"))

    categories = conn.execute("SELECT * FROM categories ORDER BY sort_order, id").fetchall()
    conn.close()
    return render_template("admin/categories.html", categories=categories)


@app.route("/admin/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_category(category_id):
    conn = db()
    category = conn.execute("SELECT * FROM categories WHERE id=?", (category_id,)).fetchone()
    if request.method == "POST":
        conn.execute(
            "UPDATE categories SET name=?, sort_order=?, visible=? WHERE id=?",
            (
                request.form.get("name", ""),
                int(request.form.get("sort_order", 0) or 0),
                1 if request.form.get("visible") == "on" else 0,
                category_id,
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_categories"))
    conn.close()
    return render_template("admin/category_form.html", category=category)


@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def admin_delete_category(category_id):
    conn = db()
    conn.execute("DELETE FROM categories WHERE id=?", (category_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_categories"))


@app.route("/admin/homepage", methods=["GET", "POST"])
@admin_required
def admin_homepage():
    s = get_settings()
    if request.method == "POST":
        for key in ["hero_title", "hero_subtitle", "hero_button_text", "announcement_bar", "footer_text"]:
            set_setting(key, request.form.get(key, ""))

        hero_background = request.form.get("hero_background", "").strip()
        uploaded = save_uploaded_file(request.files.get("hero_background_file"))
        if uploaded:
            hero_background = uploaded
        elif not hero_background:
            hero_background = s.get("hero_background", "")
        set_setting("hero_background", hero_background)

        return redirect(url_for("admin_homepage"))

    return render_template("admin/homepage.html", settings=s)


@app.route("/admin/sections", methods=["GET", "POST"])
@admin_required
def admin_sections():
    sec = get_sections()
    if request.method == "POST":
        for key in ["announcement", "hero", "categories", "best_sellers", "luxury", "custom_bouquet", "info"]:
            set_section(key, request.form.get(key) == "on")
        return redirect(url_for("admin_sections"))
    return render_template("admin/sections.html", sections=sec)


@app.route("/admin/orders")
@admin_required
def admin_orders():
    conn = db()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin/orders.html", orders=orders)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def admin_order_status(order_id):
    conn = db()
    conn.execute(
        "UPDATE orders SET order_status=? WHERE id=?",
        (request.form.get("order_status", "New"), order_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_orders"))


@app.route("/admin/custom-orders")
@admin_required
def admin_custom_orders():
    conn = db()
    orders = conn.execute("SELECT * FROM custom_orders ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin/custom_orders.html", orders=orders)


@app.route("/admin/custom-orders/<int:order_id>/status", methods=["POST"])
@admin_required
def admin_custom_order_status(order_id):
    conn = db()
    conn.execute(
        "UPDATE custom_orders SET status=? WHERE id=?",
        (request.form.get("status", "New"), order_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_custom_orders"))


@app.route("/admin/delivery", methods=["GET", "POST"])
@admin_required
def admin_delivery():
    s = get_settings()
    if request.method == "POST":
        for key in [
            "zone1_name", "zone1_cities", "zone1_fee",
            "zone2_name", "zone2_cities", "zone2_fee",
            "zone3_name", "zone3_cities", "zone3_fee",
            "delivery_provider_mode", "uber_enabled", "uber_mode", "uber_margin", "uber_pickup_address",
        ]:
            set_setting(key, request.form.get(key, ""))
        return redirect(url_for("admin_delivery"))
    return render_template("admin/delivery.html", settings=s)


@app.route("/admin/payments", methods=["GET", "POST"])
@admin_required
def admin_payments():
    s = get_settings()
    if request.method == "POST":
        set_setting("stripe_public_key", request.form.get("stripe_public_key", ""))
        set_setting("stripe_secret_key", request.form.get("stripe_secret_key", ""))
        return redirect(url_for("admin_payments"))
    return render_template("admin/payments.html", settings=s)


@app.route("/admin/taxes", methods=["GET", "POST"])
@admin_required
def admin_taxes():
    s = get_settings()
    if request.method == "POST":
        set_setting("tax_name", request.form.get("tax_name", "HST"))
        set_setting("tax_rate", request.form.get("tax_rate", "13"))
        return redirect(url_for("admin_taxes"))
    return render_template("admin/taxes.html", settings=s)


@app.route("/admin/social", methods=["GET", "POST"])
@admin_required
def admin_social():
    s = get_settings()
    if request.method == "POST":
        for key in ["instagram_url", "phone", "email", "whatsapp"]:
            set_setting(key, request.form.get(key, ""))

        logo_url = request.form.get("logo_url", "").strip()
        uploaded = save_uploaded_file(request.files.get("logo_file"))
        if uploaded:
            logo_url = uploaded
        elif not logo_url:
            logo_url = s.get("logo_url", "")
        set_setting("logo_url", logo_url)
        return redirect(url_for("admin_social"))

    return render_template("admin/social.html", settings=s)


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    s = get_settings()
    if request.method == "POST":
        set_setting("store_name", request.form.get("store_name", "July12"))
        set_setting("store_currency", request.form.get("store_currency", "cad"))
        return redirect(url_for("admin_settings"))
    return render_template("admin/settings.html", settings=s)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
