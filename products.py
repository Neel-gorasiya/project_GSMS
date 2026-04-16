from flask import Blueprint, render_template, request, redirect, session
from models import get_db

products = Blueprint("products", __name__)
UNITS = ["kg", "g", "L", "ml", "pcs", "pack", "box"]


@products.route("/products", methods=["GET", "POST"])
def products_page():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        cost_price = float(request.form.get("cost_price") or 0)
        sell_price = float(request.form.get("sell_price") or 0)
        stock = int(request.form.get("stock") or 0)
        unit = request.form.get("unit") or "pcs"

        if name:
            cur.execute(
                """
                INSERT INTO products (user_id, name, cost_price, sell_price, stock, unit)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session["user_id"], name, cost_price, sell_price, stock, unit),
            )
            conn.commit()

    cur.execute("SELECT * FROM products WHERE user_id = ?", (session["user_id"],))
    items = cur.fetchall()
    conn.close()

    return render_template(
        "products.html",
        products=items,
        units=UNITS,
        show_nav=True,
    )


@products.route("/products/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ? AND user_id = ?", (product_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect("/products")


@products.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute(
            """
            UPDATE products
            SET name=?, cost_price=?, sell_price=?, stock=?, unit=?
            WHERE id=? AND user_id=?
            """,
            (
                request.form.get("name"),
                float(request.form.get("cost_price")),
                float(request.form.get("sell_price")),
                int(request.form.get("stock")),
                request.form.get("unit"),
                product_id,
                session["user_id"],
            ),
        )
        conn.commit()
        conn.close()
        return redirect("/products")

    cur.execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, session["user_id"]))
    product = cur.fetchone()
    conn.close()
    return render_template("edit_product.html", product=product, show_nav=True)