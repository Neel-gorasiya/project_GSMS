import os
from datetime import datetime
from flask import Flask, redirect, url_for, session, render_template, request

from auth import auth
from products import products
from stock import stock
from billing import billing
from customers import customers_bp
from models import get_db, init_db, create_admin, migrate_db

# ----------------- APP SETUP -----------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# blueprints
app.register_blueprint(auth)
app.register_blueprint(products)
app.register_blueprint(stock)
app.register_blueprint(billing)
app.register_blueprint(customers_bp)

# ----------------- ROUTES -----------------

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect("/login")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute(
        "SELECT COALESCE(SUM(total), 0) FROM bills WHERE user_id = ? AND substr(created_at,1,10)=?",
        (session["user_id"], today),
    )
    today_sales = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(due), 0) FROM customers WHERE user_id = ?", (session["user_id"],))
    total_outstanding = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM bills WHERE user_id = ? AND substr(created_at,1,10)=?",
        (session["user_id"], today),
    )
    bills_today = cur.fetchone()[0]

    cur.execute(
        "SELECT name, stock, unit FROM products WHERE user_id = ? AND stock <= 10 ORDER BY stock ASC LIMIT 5",
        (session["user_id"],)
    )
    low_stock = cur.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        show_nav=True,
        today_sales=today_sales,
        total_outstanding=total_outstanding,
        bills_today=bills_today,
        low_stock=low_stock,
    )


@app.route("/bills/today")
def bills_today_page():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute(
        """
        SELECT id, total, payment_type, created_at
        FROM bills
        WHERE user_id = ? AND substr(created_at,1,10)=?
        ORDER BY created_at DESC
        """,
        (session["user_id"], today),
    )
    bills = cur.fetchall()

    conn.close()

    return render_template(
        "bills_today.html",
        bills=bills,
        show_nav=True,
    )


@app.route("/daily-report")
def daily_report():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute(
        """
        SELECT 
            b.id,
            b.total,
            b.payment_type,
            b.created_at,
            COALESCE(c.name, 'Walk-in / Cash Customer') as customer_name
        FROM bills b
        LEFT JOIN customers c ON b.customer_id = c.id
        WHERE b.user_id = ? AND substr(b.created_at,1,10)=?
        ORDER BY b.created_at DESC
        """,
        (session["user_id"], today),
    )
    bills = cur.fetchall()

    customer_sales = {}
    total_sales = 0
    total_bills = 0

    for bill in bills:
        customer = bill["customer_name"]
        if customer not in customer_sales:
            customer_sales[customer] = {
                "bills": [],
                "total": 0,
                "count": 0
            }

        customer_sales[customer]["bills"].append(bill)
        customer_sales[customer]["total"] += bill["total"]
        customer_sales[customer]["count"] += 1
        total_sales += bill["total"]
        total_bills += 1

    conn.close()

    return render_template(
        "daily_report.html",
        customer_sales=customer_sales,
        total_sales=total_sales,
        total_bills=total_bills,
        report_date=datetime.now().strftime("%d %b %Y"),
        show_nav=True,
    )

# ----------------- ADMIN ROUTES -----------------

@app.route("/admin")
def admin_panel():
    if "user_id" not in session or session.get("is_admin", 0) != 1:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            u.id,
            u.username,
            u.full_name,
            u.shop_name,
            u.phone,
            u.created_at,
            u.is_active,
            u.suspended_at,
            COUNT(DISTINCT p.id) as product_count,
            COUNT(DISTINCT c.id) as customer_count,
            COUNT(DISTINCT b.id) as bill_count,
            COALESCE(SUM(b.total), 0) as total_sales
        FROM users u
        LEFT JOIN products p ON u.id = p.user_id
        LEFT JOIN customers c ON u.id = c.user_id
        LEFT JOIN bills b ON u.id = b.user_id
        WHERE u.is_admin = 0
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """)

    users_data = cur.fetchall()

    users = []
    for user in users_data:
        user_dict = dict(user)
        if user_dict['created_at']:
            try:
                created_date = datetime.fromisoformat(user_dict['created_at'])
                current_date = datetime.now()
                user_dict['tenure_days'] = (current_date - created_date).days
            except:
                user_dict['tenure_days'] = 0
        else:
            user_dict['tenure_days'] = 0
        users.append(user_dict)

    conn.close()

    return render_template("admin.html", users=users, show_nav=True)


@app.route("/admin/users/<int:user_id>/suspend", methods=["POST"])
def suspend_user(user_id):
    if "user_id" not in session or session.get("is_admin", 0) != 1:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    suspended_at = datetime.now().isoformat()
    cur.execute(
        "UPDATE users SET is_active = 0, suspended_at = ? WHERE id = ?",
        (suspended_at, user_id)
    )

    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/admin/users/<int:user_id>/activate", methods=["POST"])
def activate_user(user_id):
    if "user_id" not in session or session.get("is_admin", 0) != 1:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET is_active = 1, suspended_at = NULL WHERE id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):
    if "user_id" not in session or session.get("is_admin", 0) != 1:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM bill_items WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM bills WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM customers WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM products WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))

    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/admin/add_owner", methods=["GET", "POST"])
def add_owner():
    if "user_id" not in session or session.get("is_admin", 0) != 1:
        return redirect("/login")

    error = None
    success = None

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        shop_name = (request.form.get("shop_name") or "").strip()
        gst_number = (request.form.get("gst_number") or "").strip()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not full_name or not phone or not shop_name or not username or not password:
            error = "All fields except GST are required."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cur.fetchone():
                error = "Username already exists."
            else:
                from werkzeug.security import generate_password_hash
                pw_hash = generate_password_hash(password)
                cur.execute(
                    """
                    INSERT INTO users
                    (username, password_hash, full_name, phone, shop_name, gst_number, is_admin, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 0, 1, CURRENT_TIMESTAMP)
                    """,
                    (username, pw_hash, full_name, phone, shop_name, gst_number),
                )
                conn.commit()
                success = f"Owner '{full_name}' has been added successfully!"

            conn.close()

    return render_template("add_owner.html", error=error, success=success, show_nav=True)


@app.context_processor
def inject_now():
    return {'now': datetime.utcnow}

# ----------------- ENTRY POINT -----------------

if __name__ == "__main__":
    init_db()
    migrate_db()
    create_admin()

    app.run(debug=True)