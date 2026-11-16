from flask import Flask, render_template, request, redirect, session, make_response
import sqlite3, os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO

app = Flask(__name__)
app.secret_key = "super_secure_key"

DB = "instance/cafe.db"


# ---------------- DB CONNECT ----------------
def db():
    return sqlite3.connect(DB)


# ---------------- INIT DB ----------------
def init_db():
    if not os.path.exists("instance"):
        os.makedirs("instance")

    con = db()
    cur = con.cursor()

    # Categories
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)

    # Items
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price REAL,
            category_id INTEGER,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
    """)

    # Bills
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total REAL,
            created_at TEXT
        )
    """)

    # Bill Items
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bill_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER,
            item_name TEXT,
            qty INTEGER,
            price REAL,
            FOREIGN KEY(bill_id) REFERENCES bills(id)
        )
    """)

    con.commit()
    con.close()


init_db()


# ---------------- LOGIN PAGE ----------------
@app.route("/")
def login_page():
    return render_template("login.html", title="Login")


@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]

    if username == "admin" and password == "admin":
        session["user"] = "admin"
        return redirect("/dashboard")

    return "Wrong username or password!"


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    total_items = cur.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    total_value = cur.execute("SELECT SUM(price) FROM items").fetchone()[0] or 0
    cat_count = cur.execute("SELECT COUNT(*) FROM categories").fetchone()[0]

    con.close()

    return render_template("dashboard.html",
                           total_items=total_items,
                           total_value=total_value,
                           cat_count=cat_count,
                           title="Dashboard")


# ---------------- CATEGORY CRUD ----------------
@app.route("/categories", methods=["GET", "POST"])
def categories():
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            return "Category name required!"
        cur.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        con.commit()

    categories = cur.execute("SELECT * FROM categories").fetchall()
    con.close()

    return render_template("categories.html", categories=categories, title="Categories")


@app.route("/categories/edit/<int:id>", methods=["GET", "POST"])
def edit_category(id):
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    category = cur.execute("SELECT * FROM categories WHERE id=?", (id,)).fetchone()

    if request.method == "POST":
        name = request.form["name"].strip()
        cur.execute("UPDATE categories SET name=? WHERE id=?", (name, id))
        con.commit()
        con.close()
        return redirect("/categories")

    con.close()
    return render_template("edit_category.html", category=category, title="Edit Category")


@app.route("/categories/delete/<int:id>")
def delete_category(id):
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    linked_items = cur.execute("SELECT COUNT(*) FROM items WHERE category_id=?", (id,)).fetchone()[0]

    if linked_items > 0:
        con.close()
        return f"Cannot delete category. {linked_items} items linked."

    cur.execute("DELETE FROM categories WHERE id=?", (id,))
    con.commit()
    con.close()

    return redirect("/categories")


# ---------------- ITEMS CRUD ----------------
@app.route("/items")
def items():
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    data = cur.execute("""
        SELECT items.id, items.name, items.price, categories.name 
        FROM items 
        LEFT JOIN categories ON categories.id = items.category_id
    """).fetchall()

    con.close()

    return render_template("items.html", items=data, title="Menu Items")


@app.route("/add", methods=["GET", "POST"])
def add_item():
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()
    categories = cur.execute("SELECT * FROM categories").fetchall()

    if request.method == "POST":
        name = request.form["name"].strip()
        price = float(request.form["price"].strip())
        cat = request.form["category"]

        cur.execute("INSERT INTO items (name, price, category_id) VALUES (?, ?, ?)", (name, price, cat))
        con.commit()
        con.close()

        return redirect("/items")

    con.close()
    return render_template("add_item.html", categories=categories)


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_item(id):
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    item = cur.execute("SELECT * FROM items WHERE id=?", (id,)).fetchone()
    categories = cur.execute("SELECT * FROM categories").fetchall()

    if request.method == "POST":
        name = request.form["name"]
        price = float(request.form["price"])
        cat = request.form["category"]

        cur.execute("UPDATE items SET name=?, price=?, category_id=? WHERE id=?",
                    (name, price, cat, id))
        con.commit()
        con.close()
        return redirect("/items")

    con.close()
    return render_template("edit_item.html", item=item, categories=categories)


@app.route("/delete/<int:id>")
def delete_item(id):
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    cur.execute("DELETE FROM items WHERE id=?", (id,))
    con.commit()
    con.close()

    return redirect("/items")


# ---------------- POS WITH CATEGORY FILTER ----------------
@app.route("/pos")
def pos():
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    categories = cur.execute("SELECT * FROM categories").fetchall()

    items = cur.execute("""
        SELECT items.id, items.name, items.price, categories.name
        FROM items 
        LEFT JOIN categories ON categories.id = items.category_id
    """).fetchall()

    con.close()

    return render_template("pos.html", categories=categories, items=items)


# ---------------- CHECKOUT ----------------
@app.route("/checkout", methods=["POST"])
def checkout():
    if "user" not in session:
        return redirect("/")

    cart = request.json

    con = db()
    cur = con.cursor()

    total = sum(item["price"] * item["qty"] for item in cart)

    cur.execute("INSERT INTO bills (total, created_at) VALUES (?, ?)",
                (total, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    bill_id = cur.lastrowid

    for item in cart:
        cur.execute("""INSERT INTO bill_items (bill_id, item_name, qty, price)
                       VALUES (?, ?, ?, ?)""",
                    (bill_id, item["name"], item["qty"], item["price"]))

    con.commit()
    con.close()

    return {"bill_id": bill_id}


# ---------------- INVOICE ----------------
@app.route("/invoice/<int:bill_id>")
def invoice(bill_id):
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    bill = cur.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    items = cur.execute("SELECT item_name, qty, price FROM bill_items WHERE bill_id=?", (bill_id,)).fetchall()

    con.close()

    return render_template("invoice.html", bill=bill, items=items)


# ---------------- PDF INVOICE ----------------
@app.route("/invoice/<int:bill_id>/pdf")
def invoice_pdf(bill_id):
    con = db()
    cur = con.cursor()

    bill = cur.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    items = cur.execute("SELECT item_name, qty, price FROM bill_items WHERE bill_id=?", (bill_id,)).fetchall()

    con.close()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, f"ROYAL CAFE #{bill_id}")
    y -= 40

    pdf.setFont("Helvetica", 12)
    for name, qty, price in items:
        pdf.drawString(50, y, f"{name} x{qty}  =  Rs.{qty * price}")
        y -= 20

    pdf.drawString(50, y - 20, f"Total: Rs.{bill[1]}")
    pdf.save()

    buffer.seek(0)
    resp = make_response(buffer.getvalue())
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f"attachment; filename=bill_{bill_id}.pdf"
    return resp


# ---------------- BILL HISTORY ----------------
@app.route("/bills")
def bills():
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    rows = cur.execute("SELECT * FROM bills ORDER BY id DESC").fetchall()
    con.close()

    return render_template("bills.html", bills=rows)


# ---------------- SALES RANGE ----------------
@app.route("/sales-range", methods=["GET", "POST"])
def sales_range():
    if "user" not in session:
        return redirect("/")

    today = datetime.now().strftime("%Y-%m-%d")

    if request.method == "POST":
        start = request.form["start"]
        end = request.form["end"]
    else:
        start = end = today

    con = db()
    cur = con.cursor()

    rows = cur.execute("""
        SELECT id, total, created_at 
        FROM bills 
        WHERE DATE(created_at) BETWEEN ? AND ?
    """, (start, end)).fetchall()

    total = sum(r[1] for r in rows)
    con.close()

    return render_template("sales_range.html", data=rows, total=total, start=start, end=end)

@app.route("/analytics")
def analytics():
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    # TODAY TOTAL
    today = datetime.now().strftime("%Y-%m-%d")
    today_total = cur.execute("""
        SELECT SUM(total) FROM bills 
        WHERE DATE(created_at)=?
    """, (today,)).fetchone()[0] or 0

    # LAST 7 DAYS
    weekly_total = cur.execute("""
        SELECT SUM(total) FROM bills 
        WHERE DATE(created_at) >= DATE('now','-6 days')
    """).fetchone()[0] or 0

    # THIS MONTH
    monthly_total = cur.execute("""
        SELECT SUM(total) FROM bills
        WHERE strftime('%Y-%m', created_at)=strftime('%Y-%m', 'now')
    """).fetchone()[0] or 0

    # TOTAL REVENUE
    total_revenue = cur.execute("SELECT SUM(total) FROM bills").fetchone()[0] or 0

    # BEST SELLING ITEMS
    best_items = cur.execute("""
        SELECT item_name, SUM(qty) AS total_qty
        FROM bill_items 
        GROUP BY item_name
        ORDER BY total_qty DESC 
        LIMIT 5
    """).fetchall()

    # CATEGORY SALES
    category_sales = cur.execute("""
        SELECT categories.name, SUM(bill_items.qty * bill_items.price)
        FROM bill_items
        JOIN items ON bill_items.item_name = items.name
        JOIN categories ON items.category_id = categories.id
        GROUP BY categories.name
    """).fetchall()

    con.close()

    # FINAL RETURN (YOURS WAS MISSING)
    return render_template(
        "analytics.html",
        today_total=today_total,
        weekly_total=weekly_total,
        monthly_total=monthly_total,
        total_revenue=total_revenue,
        best_items=best_items,
        category_sales=category_sales
    )


@app.route("/sales", methods=["GET", "POST"])
def sales():
    if "user" not in session:
        return redirect("/")

    # Default date = today
    if request.method == "POST":
        selected_date = request.form["date"]
    else:
        selected_date = datetime.now().strftime("%Y-%m-%d")

    con = db()
    cur = con.cursor()

    rows = cur.execute("""
        SELECT id, total, created_at 
        FROM bills
        WHERE DATE(created_at)=?
    """, (selected_date,)).fetchall()

    day_total = sum(r[1] for r in rows)
    con.close()

    return render_template(
        "sales.html",
        data=rows,
        day_total=day_total,
        date=selected_date
    )


    # Category sales
    category_sales = cur.execute("""
        SELECT categories.name, SUM(bill_items.qty * bill_items.price)
        FROM bill_items
        JOIN items ON bill_items.item_name = items.name
        JOIN categories ON items.category_id = categories.id
        GROUP BY categories.name
    """).fetchall()

    con.close()

    return render_template(
        "analytics.html",
        today_total=today_total,
        weekly_total=weekly_total,
        monthly_total=monthly_total,
        total_revenue=total_revenue,
        best_items=best_items,
        category_sales=category_sales
    )

@app.route("/slip/<int:bill_id>")
def slip(bill_id):
    if "user" not in session:
        return redirect("/")

    con = db()
    cur = con.cursor()

    bill = cur.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    items = cur.execute("SELECT item_name, qty, price FROM bill_items WHERE bill_id=?", (bill_id,)).fetchall()

    con.close()

    return render_template("slip.html", bill=bill, items=items)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
