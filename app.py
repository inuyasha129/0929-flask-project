import os
import io
import base64
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, send_file, g
)
from werkzeug.security import check_password_hash
import qrcode

from db import get_db_connection, init_db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ordermaster-secret-key-2026-enterprise')

# 讓 Jinja2 模板中可以使用 Python 內建 enumerate
app.jinja_env.globals.update(enumerate=enumerate)

# 系統啟動時確保資料庫與初始測試資料已建妥
with app.app_context():
    init_db()

# ==========================================
# 權限驗證裝飾器 (Login Required)
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('請先登入管理員帳號以使用系統功能', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# 登入與登出路由
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    """管理員登入頁面"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db_connection()
        admin = conn.execute("SELECT * FROM admin WHERE username = ?", (username,)).fetchone()
        conn.close()

        if admin and check_password_hash(admin['password_hash'], password):
            session['user_id'] = admin['username']
            session['user_name'] = admin['name']
            flash(f"歡迎回來，{admin['name']}！登入成功。", 'success')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('dashboard'))
        else:
            flash("帳號或密碼輸入錯誤，請重新確認！(預設 admin / admin123)", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    """登出"""
    session.clear()
    flash('您已成功安全登出系統。', 'info')
    return redirect(url_for('login'))

# ==========================================
# 儀表板首頁 (Dashboard)
# ==========================================
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    """營運儀表板：關鍵指標統計與最新訂單列表"""
    conn = get_db_connection()

    # 1. 總客戶數
    customer_count = conn.execute("SELECT COUNT(*) FROM customer").fetchone()[0]

    # 2. 總商品數
    product_count = conn.execute("SELECT COUNT(*) FROM product").fetchone()[0]

    # 3. 總訂單數
    order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    # 4. 總訂單金額 (依據 order_item 當時單價與數量計算)
    total_rev_row = conn.execute("""
        SELECT COALESCE(SUM(oi.quantity * oi.price), 0) as total_rev
        FROM order_item oi
        JOIN orders o ON oi.order_id = o.order_id
        WHERE o.status != '已取消'
    """).fetchone()
    total_revenue = total_rev_row['total_rev'] if total_rev_row else 0.0

    # 5. 各狀態訂單計數
    status_counts = {'處理中': 0, '已出貨': 0, '已完成': 0, '已取消': 0}
    rows = conn.execute("SELECT status, COUNT(*) as cnt FROM orders GROUP BY status").fetchall()
    for r in rows:
        if r['status'] in status_counts:
            status_counts[r['status']] = r['cnt']

    # 6. 最近 5 筆訂單
    recent_orders = conn.execute("""
        SELECT o.order_id, o.customer_id, o.order_date, o.status, o.salesperson,
               c.name as customer_name,
               COALESCE(SUM(oi.quantity * oi.price), 0) as total_amount
        FROM orders o
        JOIN customer c ON o.customer_id = c.customer_id
        LEFT JOIN order_item oi ON o.order_id = oi.order_id
        GROUP BY o.order_id
        ORDER BY o.order_date DESC, o.order_id DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
        'dashboard.html',
        customer_count=customer_count,
        product_count=product_count,
        order_count=order_count,
        total_revenue=total_revenue,
        status_counts=status_counts,
        recent_orders=recent_orders
    )

# ==========================================
# 客戶管理 (Customer Maintenance)
# ==========================================
@app.route('/customers')
@login_required
def customers_list():
    """客戶資料列表與搜尋"""
    q = request.args.get('q', '').strip()
    conn = get_db_connection()

    if q:
        search_term = f"%{q}%"
        customers = conn.execute("""
            SELECT c.*, COUNT(o.order_id) as order_count
            FROM customer c
            LEFT JOIN orders o ON c.customer_id = o.customer_id
            WHERE c.customer_id LIKE ? OR c.name LIKE ? OR c.phone LIKE ? OR c.address LIKE ?
            GROUP BY c.customer_id
            ORDER BY c.customer_id ASC
        """, (search_term, search_term, search_term, search_term)).fetchall()
    else:
        customers = conn.execute("""
            SELECT c.*, COUNT(o.order_id) as order_count
            FROM customer c
            LEFT JOIN orders o ON c.customer_id = o.customer_id
            GROUP BY c.customer_id
            ORDER BY c.customer_id ASC
        """).fetchall()

    # 自動推算下一筆客戶編號 (CUST-00X)
    max_id_row = conn.execute("SELECT customer_id FROM customer ORDER BY customer_id DESC LIMIT 1").fetchone()
    next_id = "CUST-001"
    if max_id_row and max_id_row['customer_id'].startswith("CUST-"):
        try:
            num = int(max_id_row['customer_id'].split('-')[1]) + 1
            next_id = f"CUST-{num:03d}"
        except (IndexError, ValueError):
            pass

    conn.close()
    return render_template('customers.html', customers=customers, search_query=q, next_customer_id=next_id)

@app.route('/customers/add', methods=['POST'])
@login_required
def customer_add():
    """新增客戶"""
    cid = request.form.get('customer_id', '').strip()
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()

    if not name or not phone or not address:
        flash('請填寫完整的客戶名稱、電話與送貨地址！', 'danger')
        return redirect(url_for('customers_list'))

    conn = get_db_connection()
    if not cid:
        # 自動指派
        max_id_row = conn.execute("SELECT customer_id FROM customer ORDER BY customer_id DESC LIMIT 1").fetchone()
        num = 1
        if max_id_row and max_id_row['customer_id'].startswith("CUST-"):
            try:
                num = int(max_id_row['customer_id'].split('-')[1]) + 1
            except (IndexError, ValueError):
                pass
        cid = f"CUST-{num:03d}"

    try:
        conn.execute(
            "INSERT INTO customer (customer_id, name, phone, address) VALUES (?, ?, ?, ?)",
            (cid, name, phone, address)
        )
        conn.commit()
        flash(f"已成功新增客戶【{name}】（編號：{cid}）！", "success")
    except Exception as e:
        flash(f"新增客戶失敗：客戶編號【{cid}】可能已存在或資料不符！", "danger")
    finally:
        conn.close()

    return redirect(url_for('customers_list'))

@app.route('/customers/edit/<customer_id>', methods=['POST'])
@login_required
def customer_edit(customer_id):
    """編輯客戶"""
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()

    if not name or not phone or not address:
        flash('請填寫完整的修改資訊！', 'danger')
        return redirect(url_for('customers_list'))

    conn = get_db_connection()
    conn.execute(
        "UPDATE customer SET name = ?, phone = ?, address = ? WHERE customer_id = ?",
        (name, phone, address, customer_id)
    )
    conn.commit()
    conn.close()
    flash(f"客戶【{name}】資料已成功儲存變更！", "success")
    return redirect(url_for('customers_list'))

@app.route('/customers/delete/<customer_id>', methods=['POST'])
@login_required
def customer_delete(customer_id):
    """刪除客戶 (有外鍵保護)"""
    conn = get_db_connection()
    # 檢查是否有建立關聯訂單
    orders_cnt = conn.execute("SELECT COUNT(*) FROM orders WHERE customer_id = ?", (customer_id,)).fetchone()[0]
    if orders_cnt > 0:
        flash(f"無法刪除客戶【{customer_id}】：該客戶尚有 {orders_cnt} 筆關聯歷史訂單！", "danger")
        conn.close()
        return redirect(url_for('customers_list'))

    conn.execute("DELETE FROM customer WHERE customer_id = ?", (customer_id,))
    conn.commit()
    conn.close()
    flash(f"客戶【{customer_id}】已刪除！", "info")
    return redirect(url_for('customers_list'))

# ==========================================
# 商品管理 (Product Maintenance)
# ==========================================
@app.route('/products')
@login_required
def products_list():
    """商品列表、搜尋與分類篩選"""
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()

    conn = get_db_connection()
    categories = [r['category'] for r in conn.execute("SELECT DISTINCT category FROM product ORDER BY category").fetchall()]

    query = "SELECT * FROM product WHERE 1=1"
    params = []
    if q:
        query += " AND (product_id LIKE ? OR name LIKE ? OR category LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY product_id ASC"
    products = conn.execute(query, params).fetchall()

    # 自動推算下一個商品編號
    max_id_row = conn.execute("SELECT product_id FROM product ORDER BY product_id DESC LIMIT 1").fetchone()
    next_id = "PROD-001"
    if max_id_row and max_id_row['product_id'].startswith("PROD-"):
        try:
            num = int(max_id_row['product_id'].split('-')[1]) + 1
            next_id = f"PROD-{num:03d}"
        except (IndexError, ValueError):
            pass

    conn.close()
    return render_template(
        'products.html',
        products=products,
        categories=categories,
        search_query=q,
        selected_category=category,
        next_product_id=next_id
    )

@app.route('/products/add', methods=['POST'])
@login_required
def product_add():
    """新增商品"""
    pid = request.form.get('product_id', '').strip()
    name = request.form.get('name', '').strip()
    price_raw = request.form.get('price', '').strip()
    stock_raw = request.form.get('stock', '').strip()
    category = request.form.get('category', '').strip()

    try:
        price = float(price_raw)
        stock = int(stock_raw)
    except ValueError:
        flash('商品單價與庫存數量必須為有效數值！', 'danger')
        return redirect(url_for('products_list'))

    conn = get_db_connection()
    if not pid:
        max_id_row = conn.execute("SELECT product_id FROM product ORDER BY product_id DESC LIMIT 1").fetchone()
        num = 1
        if max_id_row and max_id_row['product_id'].startswith("PROD-"):
            try:
                num = int(max_id_row['product_id'].split('-')[1]) + 1
            except (IndexError, ValueError):
                pass
        pid = f"PROD-{num:03d}"

    try:
        conn.execute(
            "INSERT INTO product (product_id, name, price, stock, category) VALUES (?, ?, ?, ?, ?)",
            (pid, name, price, stock, category)
        )
        conn.commit()
        flash(f"已新增商品【{name}】（編號：{pid}，牌價：NT$ {price:,.0f}）！", "success")
    except Exception as e:
        flash(f"新增商品失敗：商品編號【{pid}】重複或格式錯誤！", "danger")
    finally:
        conn.close()

    return redirect(url_for('products_list'))

@app.route('/products/edit/<product_id>', methods=['POST'])
@login_required
def product_edit(product_id):
    """編輯商品 (含改價功能，需求 7 驗證：改價不影響歷史訂單)"""
    name = request.form.get('name', '').strip()
    price_raw = request.form.get('price', '').strip()
    stock_raw = request.form.get('stock', '').strip()
    category = request.form.get('category', '').strip()

    try:
        price = float(price_raw)
        stock = int(stock_raw)
    except ValueError:
        flash('請輸入正確的單價與庫存數值！', 'danger')
        return redirect(url_for('products_list'))

    conn = get_db_connection()
    conn.execute(
        "UPDATE product SET name = ?, price = ?, stock = ?, category = ? WHERE product_id = ?",
        (name, price, stock, category, product_id)
    )
    conn.commit()
    conn.close()

    flash(f"商品【{name}】已更新！新牌價為 NT$ {price:,.0f}（歷史訂單價格不受任何影響）。", "success")
    return redirect(url_for('products_list'))

@app.route('/products/delete/<product_id>', methods=['POST'])
@login_required
def product_delete(product_id):
    """刪除商品"""
    conn = get_db_connection()
    items_cnt = conn.execute("SELECT COUNT(*) FROM order_item WHERE product_id = ?", (product_id,)).fetchone()[0]
    if items_cnt > 0:
        flash(f"無法刪除商品【{product_id}】：該商品已記錄在 {items_cnt} 筆訂單明細中！", "danger")
        conn.close()
        return redirect(url_for('products_list'))

    conn.execute("DELETE FROM product WHERE product_id = ?", (product_id,))
    conn.commit()
    conn.close()
    flash(f"商品【{product_id}】已刪除！", "info")
    return redirect(url_for('products_list'))

# ==========================================
# 訂單管理 (Orders Maintenance & Creation)
# ==========================================
@app.route('/orders')
@login_required
def orders_list():
    """訂單列表與依狀態篩選"""
    status_filter = request.args.get('status', '').strip()
    conn = get_db_connection()

    query = """
        SELECT o.order_id, o.customer_id, o.order_date, o.status, o.salesperson,
               c.name as customer_name, c.phone as customer_phone,
               COUNT(oi.product_id) as item_count,
               COALESCE(SUM(oi.quantity), 0) as total_quantity,
               COALESCE(SUM(oi.quantity * oi.price), 0) as total_amount
        FROM orders o
        JOIN customer c ON o.customer_id = c.customer_id
        LEFT JOIN order_item oi ON o.order_id = oi.order_id
    """
    params = []
    if status_filter:
        query += " WHERE o.status = ?"
        params.append(status_filter)

    query += " GROUP BY o.order_id ORDER BY o.order_date DESC, o.order_id DESC"
    orders = conn.execute(query, params).fetchall()

    # 計算各狀態數量
    counts = {'全部': 0, '處理中': 0, '已出貨': 0, '已完成': 0, '已取消': 0}
    all_cnt = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    counts['全部'] = all_cnt
    st_rows = conn.execute("SELECT status, COUNT(*) as cnt FROM orders GROUP BY status").fetchall()
    for r in st_rows:
        if r['status'] in counts:
            counts[r['status']] = r['cnt']

    conn.close()

    return render_template(
        'orders.html',
        orders=orders,
        current_status=status_filter,
        counts=counts
    )

@app.route('/orders/new', methods=['GET', 'POST'])
@login_required
def order_create():
    """
    建立新訂單 (需求 6 & 需求 7):
    - 客戶用下拉選單
    - 商品可一次勾選多項並填數量
    - order_item 存下單當時的單價
    """
    conn = get_db_connection()

    if request.method == 'POST':
        order_id = request.form.get('order_id', '').strip()
        customer_id = request.form.get('customer_id', '').strip()
        order_date = request.form.get('order_date', '').strip()
        status = request.form.get('status', '處理中').strip()
        salesperson = request.form.get('salesperson', '').strip()

        # 勾選的多項商品
        selected_products = request.form.getlist('selected_products')

        if not customer_id:
            flash("請由下拉選單選取訂購客戶！", "danger")
            conn.close()
            return redirect(url_for('order_create'))

        if not selected_products:
            flash("請至少勾選一項要購買的商品！", "danger")
            conn.close()
            return redirect(url_for('order_create'))

        if not order_id:
            today_prefix = datetime.now().strftime("%Y%m%d")
            order_id = f"ORD-{today_prefix}-{datetime.now().strftime('%H%M%S')}"

        if not order_date:
            order_date = datetime.now().strftime("%Y-%m-%d")

        try:
            # 1. 寫入 orders 主表
            conn.execute(
                "INSERT INTO orders (order_id, customer_id, order_date, status, salesperson) VALUES (?, ?, ?, ?, ?)",
                (order_id, customer_id, order_date, status, salesperson)
            )

            # 2. 處理勾選的商品，存入當下的單價 (Snapshot Price)
            for pid in selected_products:
                qty_raw = request.form.get(f'quantity_{pid}', '1')
                try:
                    qty = int(qty_raw)
                    if qty <= 0:
                        qty = 1
                except ValueError:
                    qty = 1

                # 查詢該商品當下的即時單價與庫存
                prod = conn.execute("SELECT price, stock, name FROM product WHERE product_id = ?", (pid,)).fetchone()
                if not prod:
                    continue

                snapshot_price = prod['price']  # 下單當時的商品單價

                # 寫入 order_item (複合主鍵)
                conn.execute(
                    "INSERT INTO order_item (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                    (order_id, pid, qty, snapshot_price)
                )

                # 扣減庫存
                new_stock = max(0, prod['stock'] - qty)
                conn.execute("UPDATE product SET stock = ? WHERE product_id = ?", (new_stock, pid))

            conn.commit()
            flash(f"訂單【{order_id}】已成功建立！下單單價已固化存入明細。", "success")
            return redirect(url_for('order_detail', order_id=order_id))

        except Exception as e:
            conn.rollback()
            flash(f"建立訂單失敗：{str(e)}", "danger")
            return redirect(url_for('order_create'))
        finally:
            conn.close()

    # GET 頁面載入
    customers = conn.execute("SELECT customer_id, name, phone, address FROM customer ORDER BY customer_id ASC").fetchall()
    products = conn.execute("SELECT product_id, name, price, stock, category FROM product ORDER BY product_id ASC").fetchall()

    # 自動推算新訂單編號
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_code = datetime.now().strftime("%Y%m%d")
    count_today = conn.execute("SELECT COUNT(*) FROM orders WHERE order_date = ?", (today_str,)).fetchone()[0] + 1
    new_order_id = f"ORD-{today_code}-{count_today:03d}"

    conn.close()
    return render_template(
        'order_create.html',
        customers=customers,
        products=products,
        today_str=today_str,
        new_order_id=new_order_id
    )

@app.route('/orders/update-status', methods=['POST'])
@login_required
def update_order_status():
    """
    列表直接更新訂單狀態 (需求 8):
    處理中 / 已出貨 / 已完成 / 已取消
    """
    valid_statuses = ['處理中', '已出貨', '已完成', '已取消']

    if request.is_json:
        data = request.get_json() or {}
        order_id = data.get('order_id')
        new_status = data.get('status')
    else:
        order_id = request.form.get('order_id')
        new_status = request.form.get('status')

    if not order_id or new_status not in valid_statuses:
        if request.is_json:
            return jsonify({'status': 'error', 'message': '無效的訂單狀態或編號'}), 400
        flash('狀態不合法！', 'danger')
        return redirect(url_for('orders_list'))

    conn = get_db_connection()
    conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

    if request.is_json:
        return jsonify({
            'status': 'success',
            'order_id': order_id,
            'new_status': new_status,
            'message': f'訂單 {order_id} 狀態已更新為【{new_status}】'
        })

    flash(f"訂單【{order_id}】狀態已更新為【{new_status}】！", "success")
    return redirect(request.referrer or url_for('orders_list'))

@app.route('/orders/delete/<order_id>', methods=['POST'])
@login_required
def order_delete(order_id):
    """刪除訂單 (級聯刪除 order_item)"""
    conn = get_db_connection()
    conn.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
    conn.commit()
    conn.close()
    flash(f"訂單【{order_id}】及其明細已成功刪除！", "info")
    return redirect(url_for('orders_list'))

# ==========================================
# 訂單專屬頁面與出貨單 QRCode (需求 9)
# ==========================================
def generate_order_qrcode_base64(target_url: str) -> str:
    """生成 QRCode 並轉為 Base64 PNG 圖片格式"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=5,
        border=2,
    )
    qr.add_data(target_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e293b", back_color="#ffffff")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_b64}"

@app.route('/order/<order_id>')
def order_detail(order_id):
    """
    每張訂單的專屬出貨單頁面 (需求 9)
    包含出貨單 QRCode，任何人持單據 QRCode 均可掃描檢視出貨單明細
    """
    conn = get_db_connection()

    order = conn.execute("""
        SELECT o.*, c.name as customer_name, c.phone as customer_phone, c.address as customer_address
        FROM orders o
        JOIN customer c ON o.customer_id = c.customer_id
        WHERE o.order_id = ?
    """, (order_id,)).fetchone()

    if not order:
        conn.close()
        flash(f"找不到訂單編號【{order_id}】！", "danger")
        return redirect(url_for('orders_list'))

    # 取得訂單明細 (使用下單時儲存的 price)
    items = conn.execute("""
        SELECT oi.*, p.name as product_name, p.category
        FROM order_item oi
        JOIN product p ON oi.product_id = p.product_id
        WHERE oi.order_id = ?
        ORDER BY oi.product_id ASC
    """, (order_id,)).fetchall()

    conn.close()

    total_amount = sum(item['price'] * item['quantity'] for item in items)
    total_qty = sum(item['quantity'] for item in items)

    # 產生專屬 QRCode：直接連結至此出貨單頁面
    order_url = request.url_root.rstrip('/') + url_for('order_detail', order_id=order_id)
    qr_b64 = generate_order_qrcode_base64(order_url)

    return render_template(
        'order_detail.html',
        order=order,
        items=items,
        total_amount=total_amount,
        total_qty=total_qty,
        qr_b64=qr_b64,
        order_url=order_url
    )

@app.route('/order/<order_id>/qrcode')
def order_qrcode_raw(order_id):
    """回傳純 PNG 格式的 QRCode 圖片，方便第三方列印或下載"""
    order_url = request.url_root.rstrip('/') + url_for('order_detail', order_id=order_id)
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(order_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype='image/png', download_name=f"qrcode_{order_id}.png")

# ==========================================
# 啟動伺服器 (本機開發)
# ==========================================
if __name__ == '__main__':
    print("==================================================")
    print("OrderMaster Pro 訂單管理系統已啟動！")
    print("本機瀏覽網址: http://127.0.0.1:5000 或 http://localhost:5000")
    print("預設管理員帳號：admin  密碼：admin123")
    print("==================================================")
    app.run(debug=True, host='0.0.0.0', port=5000)

