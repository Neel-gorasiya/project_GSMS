from flask import Blueprint, render_template, session, redirect
from models import get_db

stock = Blueprint("stock", __name__)


@stock.route("/stock")
def stock_page():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    # name, cost_price, stock, unit from products
    cur.execute("SELECT name, cost_price, stock, unit FROM products WHERE user_id = ?", (session["user_id"],))
    rows = cur.fetchall()
    conn.close()

    products = []
    total_invested = 0

    for row in rows:
        name = row["name"]
        cost_price = row["cost_price"]
        qty = row["stock"]
        unit = row["unit"]

        invested = cost_price * qty
        total_invested += invested

        products.append({
            "name": name,
            "cost_price": cost_price,
            "stock": qty,
            "unit": unit,
            "invested": invested,
        })

    return render_template(
        "stock.html",
        products=products,
        total_invested=total_invested,
        show_nav=True,
    )