from flask import Blueprint, render_template, request, redirect, session
from werkzeug.security import check_password_hash, generate_password_hash
from models import get_db

auth = Blueprint("auth", __name__)


@auth.route("/register", methods=["GET", "POST"])
def register():
    # If already logged in, go to dashboard
    if "user_id" in session:
        return redirect("/dashboard")

    error = None

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        shop_name = (request.form.get("shop_name") or "").strip()
        gst_number = (request.form.get("gst_number") or "").strip()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        # Validation
        if not full_name or not phone or not shop_name or not username or not password:
            error = "All fields except GST are required."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            conn = get_db()
            cur = conn.cursor()

            # Check username uniqueness
            cur.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cur.fetchone():
                error = "Username already exists."
            else:
                pw_hash = generate_password_hash(password)
                cur.execute(
                    """
                    INSERT INTO users
                    (username, password_hash, full_name, phone, shop_name, gst_number)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (username, pw_hash, full_name, phone, shop_name, gst_number),
                )
                conn.commit()

                # Auto-login after registration
                session["user_id"] = cur.lastrowid
                conn.close()
                return redirect("/dashboard")

            conn.close()

    return render_template("register.html", error=error, show_nav=False)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            if user["is_active"] == 0:
                return render_template("login.html", error="Your account has been suspended. Please contact administrator.")

            session["user_id"] = user["id"]
            session["is_admin"] = user["is_admin"]
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


@auth.route("/logout")
def logout():
    session.clear()
    return redirect("/login")