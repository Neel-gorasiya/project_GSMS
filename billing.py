from flask import Blueprint, render_template, request, redirect, session
from models import get_db
from datetime import datetime, timedelta

billing = Blueprint("billing", __name__)


@billing.route("/billing", methods=["GET", "POST"])
def billing_page():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    error = None

    if request.method == "POST":
        # 1. Customer + payment info
        customer_id_raw = request.form.get("customer_id")
        payment_type = request.form.get("payment_type", "cash")
        due_date = request.form.get("due_date") or None

        if payment_type != "credit":
            due_date = None

        if customer_id_raw in (None, "", "cash"):
            customer_id = None
        else:
            customer_id = int(customer_id_raw)

        # 2. Items
        product_ids = request.form.getlist("product_id[]")
        quantities = request.form.getlist("quantity[]")
        prices = request.form.getlist("price[]")

        items = []
        total = 0.0

        for pid, qty, price in zip(product_ids, quantities, prices):
            if not pid:
                continue

            try:
                product_id = int(pid)
                quantity = int(float(qty)) if qty else 0
                price_val = float(price) if price else 0.0
            except ValueError:
                continue

            if quantity <= 0 or price_val <= 0:
                continue

            line_total = quantity * price_val
            total += line_total

            items.append({
                "product_id": product_id,
                "quantity": quantity,
                "price": price_val,
                "line_total": line_total,
            })

        if not items:
            error = "No valid items in bill."
        else:
            # 3. Stock check
            for item in items:
                cur.execute(
                    "SELECT name, stock FROM products WHERE id = ? AND user_id = ?",
                    (item["product_id"], session["user_id"]),
                )
                row = cur.fetchone()
                if not row:
                    error = "Some product does not exist."
                    break

                if item["quantity"] > row["stock"]:
                    error = (
                        f"Not enough stock for '{row['name']}'. "
                        f"Available: {row['stock']}, requested: {item['quantity']}."
                    )
                    break

        if error:
            cur.execute("SELECT id, name FROM customers WHERE user_id = ?", (session["user_id"],))
            customers = cur.fetchall()

            cur.execute("SELECT id, name, sell_price, unit FROM products WHERE user_id = ?", (session["user_id"],))
            products = cur.fetchall()

            conn.close()
            return render_template(
                "billing.html",
                customers=customers,
                products=products,
                error=error,
                show_nav=True,
            )

        # 4. Insert bill
        created_at = datetime.now().isoformat(timespec="seconds")
        cur.execute(
            """
            INSERT INTO bills (user_id, customer_id, total, payment_type, due_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session["user_id"], customer_id, total, payment_type, due_date, created_at),
        )
        bill_id = cur.lastrowid

        # 5. Insert items + update stock
        for item in items:
            cur.execute(
                """
                INSERT INTO bill_items (user_id, bill_id, product_id, quantity, price, line_total)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    bill_id,
                    item["product_id"],
                    item["quantity"],
                    item["price"],
                    item["line_total"],
                ),
            )

            cur.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ? AND user_id = ?",
                (item["quantity"], item["product_id"], session["user_id"]),
            )

        # 6. Update customer due
        if payment_type == "credit" and customer_id is not None:
            cur.execute(
                """
                UPDATE customers
                SET due = due + ?, next_payment_date = ?
                WHERE id = ? AND user_id = ?
                """,
                (total, due_date, customer_id, session["user_id"]),
            )

        conn.commit()
        conn.close()

        return redirect(f"/billing/{bill_id}")

    # ---------- GET ----------
    cur.execute("SELECT id, name FROM customers WHERE user_id = ?", (session["user_id"],))
    customers = cur.fetchall()

    cur.execute("SELECT id, name, sell_price, unit FROM products WHERE user_id = ?", (session["user_id"],))
    products = cur.fetchall()

    conn.close()

    return render_template(
        "billing.html",
        customers=customers,
        products=products,
        error=None,
        show_nav=True,
    )


@billing.route("/billing/<int:bill_id>")
def invoice_page(bill_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM bills WHERE id = ? AND user_id = ?", (bill_id, session["user_id"]))
    bill = cur.fetchone()

    if not bill:
        conn.close()
        return "Bill not found", 404

    customer = None
    if bill["customer_id"] is not None:
        cur.execute("SELECT * FROM customers WHERE id = ? AND user_id = ?", (bill["customer_id"], session["user_id"]))
        customer = cur.fetchone()

    cur.execute(
        """
        SELECT bi.quantity, bi.price, bi.line_total, p.name, p.unit
        FROM bill_items bi
        JOIN products p ON bi.product_id = p.id
        WHERE bi.bill_id = ? AND bi.user_id = ?
        """,
        (bill_id, session["user_id"]),
    )
    items = cur.fetchall()

    owner = None
    if "user_id" in session:
        cur.execute(
            """
            SELECT shop_name, gst_number, full_name, phone
            FROM users
            WHERE id = ?
            """,
            (session["user_id"],),
        )
        owner = cur.fetchone()

    conn.close()

    return render_template(
        "invoice.html",
        bill=bill,
        customer=customer,
        items=items,
        owner=owner,
        show_nav=True,
    )


@billing.route("/bills/history", methods=["GET"])
def bills_history():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    # Get selected date from query parameter or default to today
    selected_date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    # Validate date format
    try:
        selected_dt = datetime.strptime(selected_date, "%Y-%m-%d")
    except ValueError:
        selected_date = datetime.now().strftime("%Y-%m-%d")
        selected_dt = datetime.now()

    # Get one month before
    month_ago = (selected_dt - timedelta(days=30)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    # Get all dates with bills in the last month
    cur.execute(
        """
        SELECT DISTINCT substr(created_at, 1, 10) as bill_date
        FROM bills
        WHERE user_id = ? AND substr(created_at, 1, 10) >= ?
        ORDER BY bill_date DESC
        """,
        (session["user_id"], month_ago),
    )
    available_dates = [row[0] for row in cur.fetchall()]

    # Get bills for the selected date
    cur.execute(
        """
        SELECT id, total, payment_type, created_at, customer_id
        FROM bills
        WHERE user_id = ? AND substr(created_at, 1, 10) = ?
        ORDER BY created_at DESC
        """,
        (session["user_id"], selected_date),
    )
    bills = cur.fetchall()

    # Get customer names for bills
    bills_with_customers = []
    for bill in bills:
        customer_name = "Walk-in / Cash"
        if bill["customer_id"]:
            cur.execute(
                "SELECT name FROM customers WHERE id = ? AND user_id = ?",
                (bill["customer_id"], session["user_id"]),
            )
            customer = cur.fetchone()
            if customer:
                customer_name = customer["name"]
        
        bills_with_customers.append({
            "id": bill["id"],
            "total": bill["total"],
            "payment_type": bill["payment_type"],
            "created_at": bill["created_at"],
            "customer_name": customer_name,
        })

    # Calculate totals for selected date
    cur.execute(
        """
        SELECT 
            COUNT(*) as total_bills,
            COALESCE(SUM(total), 0) as total_sales,
            SUM(CASE WHEN payment_type = 'cash' THEN total ELSE 0 END) as cash_sales,
            SUM(CASE WHEN payment_type = 'online' THEN total ELSE 0 END) as online_sales,
            SUM(CASE WHEN payment_type = 'credit' THEN total ELSE 0 END) as credit_sales
        FROM bills
        WHERE user_id = ? AND substr(created_at, 1, 10) = ?
        """,
        (session["user_id"], selected_date),
    )
    stats = cur.fetchone()

    conn.close()

    return render_template(
        "bills_history.html",
        bills=bills_with_customers,
        selected_date=selected_date,
        available_dates=available_dates,
        month_ago=month_ago,
        today=today,
        stats=stats,
        show_nav=True,
    )