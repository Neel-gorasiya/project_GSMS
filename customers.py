from flask import Blueprint, render_template, request, redirect, session
from models import get_db

customers_bp = Blueprint("customers", __name__)


@customers_bp.route("/customers", methods=["GET", "POST"])
def customers_page():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        mobile_number = (request.form.get("mobile_number") or "").strip()

        # ✅ Basic validation
        if name and mobile_number and mobile_number.isdigit() and len(mobile_number) == 10:
            cur.execute(
                """INSERT INTO customers 
                (user_id, name, mobile_number, due, next_payment_date) 
                VALUES (?, ?, ?, ?, ?)""",
                (session["user_id"], name, mobile_number, 0.0, None),
            )
            conn.commit()

    cur.execute("SELECT * FROM customers WHERE user_id = ?", (session["user_id"],))
    customers = cur.fetchall()
    conn.close()

    return render_template("customers.html", customers=customers, show_nav=True)


@customers_bp.route("/customers/<int:customer_id>/pay", methods=["POST"])
def pay_partial(customer_id):
    if "user_id" not in session:
        return redirect("/login")

    amount = float(request.form.get("amount") or 0)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT due FROM customers WHERE id = ? AND user_id = ?", (customer_id, session["user_id"]))
    row = cur.fetchone()

    if row:
        new_due = max(row["due"] - amount, 0)
        cur.execute(
            "UPDATE customers SET due = ? WHERE id = ? AND user_id = ?",
            (new_due, customer_id, session["user_id"])
        )
        conn.commit()

    conn.close()
    return redirect("/customers")


@customers_bp.route("/customers/<int:customer_id>/pay_full", methods=["POST"])
def pay_full(customer_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE customers SET due = 0 WHERE id = ? AND user_id = ?",
        (customer_id, session["user_id"])
    )
    conn.commit()
    conn.close()
    return redirect("/customers")


@customers_bp.route("/customers/<int:customer_id>/delete", methods=["POST"])
def delete_customer(customer_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM customers WHERE id = ? AND user_id = ?",
        (customer_id, session["user_id"])
    )
    conn.commit()
    conn.close()
    return redirect("/customers")