import unittest
import json
import sqlite3
from app import app
from db import init_db, get_db_connection

class OrderManagementSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 初始化資料庫結構與測試資料
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def login(self, username='admin', password='admin123'):
        """輔助函式：執行登入"""
        return self.app.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def test_01_werkzeug_hash_and_no_plaintext(self):
        """
        測試需求 1:
        1. 登入頁正常渲染
        2. 畫面與原始碼不得出現密碼明碼 (admin123)
        3. 資料庫中密碼以 Werkzeug 雜湊儲存
        """
        response = self.app.get('/login')
        self.assertEqual(response.status_code, 200)
        page_html = response.data.decode('utf-8')

        # 驗證頁面內容不含密碼明碼
        self.assertNotIn('admin123', page_html, "登入畫面不得出現密碼明碼！")

        # 驗證資料庫中的密碼為 Werkzeug 雜湊字串 (例如 scrypt:...)
        conn = get_db_connection()
        admin_row = conn.execute("SELECT password_hash FROM admin WHERE username = ?", ('admin',)).fetchone()
        conn.close()
        self.assertIsNotNone(admin_row)
        self.assertTrue(
            admin_row['password_hash'].startswith('scrypt:') or admin_row['password_hash'].startswith('pbkdf2:'),
            "資料庫應以 Werkzeug 安全雜湊儲存密碼！"
        )

    def test_02_backend_pages_require_admin_role_session(self):
        """
        測試需求 2:
        後台所有頁面需登入 (session) 且角色為管理員才能進入
        """
        # 1. 未登入狀態訪問後台各頁面均應被導向登入頁
        backend_urls = ['/', '/dashboard', '/customers', '/products', '/orders', '/orders/new']
        for url in backend_urls:
            resp = self.app.get(url, follow_redirects=False)
            self.assertEqual(resp.status_code, 302, f"未登入存取 {url} 應被重導向！")
            self.assertIn('/login', resp.headers['Location'])

        # 2. 偽造非管理員 session (角色為 guest) 應被阻擋
        with self.app.session_transaction() as sess:
            sess['user_id'] = 'guest_user'
            sess['role'] = 'guest'

        resp_guest = self.app.get('/dashboard', follow_redirects=False)
        self.assertEqual(resp_guest.status_code, 302, "非 admin 角色應被阻擋！")

        # 3. 正確管理員登入後 session['role'] 應為 admin 且可順利進入後台
        resp_login = self.login('admin', 'admin123')
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn('營運資訊總覽'.encode('utf-8'), resp_login.data)

    def test_03_parameterized_queries_protection(self):
        """
        測試需求 3:
        所有 SQL 皆改為參數化查詢，阻擋 SQL 注入攻擊
        """
        self.login('admin', 'admin123')
        # 注入嘗試：搜尋客戶時帶入 SQL 注入字串
        sql_injection = "' OR '1'='1"
        resp = self.app.get(f'/customers?q={sql_injection}')
        self.assertEqual(resp.status_code, 200)

        # 注入嘗試：商品分類篩選
        resp_prod = self.app.get(f'/products?category={sql_injection}')
        self.assertEqual(resp_prod.status_code, 200)

    def test_04_order_id_format_so_validation(self):
        """
        測試需求 4:
        訂單編號加上 SO+數字 的格式驗證 (前端與後端防護)
        """
        self.login('admin', 'admin123')

        # 1. 前端頁面需包含 SO+數字 之 pattern 屬性
        resp_get = self.app.get('/orders/new')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn('pattern="^SO[0-9]+$"', resp_get.data.decode('utf-8'))

        # 2. 不合法格式：ORD-20261001-001 (非 SO 開頭)
        resp_invalid1 = self.app.post('/orders/new', data={
            'order_id': 'ORD-20261001-001',
            'customer_id': 'CUST-001',
            'product_id': ['PROD-001'],
            'quantity': ['1']
        }, follow_redirects=True)
        self.assertIn('訂單編號格式不符'.encode('utf-8'), resp_invalid1.data)

        # 3. 不合法格式：SO-12345 (包含破折號)
        resp_invalid2 = self.app.post('/orders/new', data={
            'order_id': 'SO-12345',
            'customer_id': 'CUST-001',
            'product_id': ['PROD-001'],
            'quantity': ['1']
        }, follow_redirects=True)
        self.assertIn('訂單編號格式不符'.encode('utf-8'), resp_invalid2.data)

        # 4. 不合法格式：SOabc (非純數字)
        resp_invalid3 = self.app.post('/orders/new', data={
            'order_id': 'SOabc',
            'customer_id': 'CUST-001',
            'product_id': ['PROD-001'],
            'quantity': ['1']
        }, follow_redirects=True)
        self.assertIn('訂單編號格式不符'.encode('utf-8'), resp_invalid3.data)

        # 5. 合法格式：SO999001 (SO + 純數字) 應成功建立
        valid_order_id = "SO999001"
        resp_valid = self.app.post('/orders/new', data={
            'order_id': valid_order_id,
            'customer_id': 'CUST-001',
            'product_id': ['PROD-001'],
            'quantity': ['1']
        }, follow_redirects=True)
        self.assertEqual(resp_valid.status_code, 200)

        # 清理測試訂單
        conn = get_db_connection()
        conn.execute("DELETE FROM orders WHERE order_id = ?", (valid_order_id,))
        conn.commit()
        conn.close()

    def test_05_dropdown_order_creation_and_price_snapshot(self):
        """
        測試需求 4 & 7:
        客戶與商品使用下拉選單建立訂單，且單價歷史固化保價
        """
        self.login('admin', 'admin123')
        conn = get_db_connection()
        prod = conn.execute("SELECT product_id, price FROM product WHERE product_id = ?", ('PROD-001',)).fetchone()
        original_price = prod['price']
        conn.close()

        test_order_id = "SO99999"
        # 透過商品下拉選單傳送 product_id 與 quantity
        resp = self.app.post('/orders/new', data={
            'order_id': test_order_id,
            'customer_id': 'CUST-001',
            'order_date': '2026-10-03',
            'status': '處理中',
            'salesperson': '陳家豪',
            'product_id': ['PROD-001'],
            'quantity': ['2']
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # 驗證 order_item 中的單價等於當時牌價
        conn = get_db_connection()
        item = conn.execute("SELECT price, quantity FROM order_item WHERE order_id = ? AND product_id = ?", (test_order_id, 'PROD-001')).fetchone()
        self.assertIsNotNone(item)
        self.assertEqual(item['price'], original_price)

        # 模擬商品改價 (8800 -> 9999)
        conn.execute("UPDATE product SET price = ? WHERE product_id = ?", (9999.0, 'PROD-001'))
        conn.commit()

        # 歷史訂單價格不應受改價影響
        item_after = conn.execute("SELECT price FROM order_item WHERE order_id = ? AND product_id = ?", (test_order_id, 'PROD-001')).fetchone()
        self.assertEqual(item_after['price'], original_price)

        # 清理測試訂單並還原商品牌價
        conn.execute("DELETE FROM orders WHERE order_id = ?", (test_order_id,))
        conn.execute("UPDATE product SET price = ? WHERE product_id = ?", (original_price, 'PROD-001'))
        conn.commit()
        conn.close()

    def test_06_quantity_three_layer_validation(self):
        """
        測試需求 5:
        數量必須是正整數，前端、後端、資料庫 CHECK 三層都要擋
        """
        self.login('admin', 'admin123')

        # === 第一層：前端 HTML 屬性檢驗 ===
        resp_page = self.app.get('/orders/new')
        html = resp_page.data.decode('utf-8')
        self.assertIn('min="1"', html, "前端輸入框需設定 min=1")
        self.assertIn('step="1"', html, "前端輸入框需設定 step=1")

        # === 第二層：後端 Python 驗證 (阻擋 0, 負數, 浮點數, 字串) ===
        invalid_quantities = ['0', '-3', '1.5', 'abc']
        for bad_qty in invalid_quantities:
            bad_order_id = f"SO888{hash(bad_qty) % 10000:04d}"
            resp = self.app.post('/orders/new', data={
                'order_id': bad_order_id,
                'customer_id': 'CUST-001',
                'product_id': ['PROD-001'],
                'quantity': [bad_qty]
            }, follow_redirects=True)
            self.assertIn('數量必須為大於 0 的正整數'.encode('utf-8'), resp.data, f"後端應阻擋數量: {bad_qty}")

            # 確保訂單未寫入資料庫
            conn = get_db_connection()
            check_order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (bad_order_id,)).fetchone()
            conn.close()
            self.assertIsNone(check_order, f"無效數量 {bad_qty} 不得在資料庫建立訂單！")

        # === 第三層：資料庫 CHECK 約束驗證 (CHECK(quantity > 0 AND TYPEOF(quantity) = 'integer')) ===
        conn = get_db_connection()
        test_db_order_id = "SO777001"
        conn.execute("INSERT OR IGNORE INTO orders (order_id, customer_id, order_date, status, salesperson) VALUES (?, ?, ?, ?, ?)",
                     (test_db_order_id, 'CUST-001', '2026-10-06', '處理中', '測試員'))
        conn.commit()

        # 1. 嘗試插入 quantity = 0
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO order_item (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                         (test_db_order_id, 'PROD-001', 0, 100.0))

        # 2. 嘗試插入 quantity = -2
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO order_item (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                         (test_db_order_id, 'PROD-001', -2, 100.0))

        # 3. 嘗試插入 quantity = 1.5 (浮點數)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO order_item (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                         (test_db_order_id, 'PROD-001', 1.5, 100.0))

        # 清理測試紀錄
        conn.execute("DELETE FROM orders WHERE order_id = ?", (test_db_order_id,))
        conn.commit()
        conn.close()

    def test_07_inline_status_update(self):
        """測試在列表中直接更新訂單狀態"""
        self.login('admin', 'admin123')
        response = self.app.post('/orders/update-status', json={
            'order_id': 'ORD-20261001-001',
            'status': '已出貨'
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['new_status'], '已出貨')

        # 還原為已完成
        self.app.post('/orders/update-status', json={
            'order_id': 'ORD-20261001-001',
            'status': '已完成'
        })

    def test_08_order_detail_page_and_qrcode(self):
        """測試專屬訂單頁面 /order/<id> 與出貨單 QRCode"""
        response = self.app.get('/order/ORD-20261001-001')
        self.assertEqual(response.status_code, 200)
        self.assertIn('出貨裝箱單'.encode('utf-8'), response.data)
        self.assertIn('data:image/png;base64,'.encode('utf-8'), response.data)

        resp_qr = self.app.get('/order/ORD-20261001-001/qrcode')
        self.assertEqual(resp_qr.status_code, 200)
        self.assertEqual(resp_qr.content_type, 'image/png')

    def test_09_admin_dashboard_kpis_and_charts(self):
        """
        測試 /admin 營運儀表板:
        1. 未登入被重導向至 /login
        2. 登入後可存取 /admin (HTTP 200)
        3. 上方 4 張 KPI 卡片:
           - 累計營收 (排除已取消訂單)
           - 有效訂單數 (排除已取消訂單)
           - 平均客單價
           - 客戶數
        4. 每月營收趨勢折線圖 (Chart.js)
        5. 訂單狀態分布環圈圖 (Chart.js)
        6. 熱銷商品 Top 5 表格
        7. 客戶消費排行 Top 5 表格
        8. 金額千分位顯示與響應式單欄佈局
        """
        # 未登入需重導向
        resp_unauth = self.app.get('/admin', follow_redirects=False)
        self.assertEqual(resp_unauth.status_code, 302)

        # 登入管理員
        self.login('admin', 'admin123')
        resp = self.app.get('/admin')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # 1. 驗證標題與 4 張 KPI 卡片
        self.assertIn('營運儀表板', html)
        self.assertIn('累計營收', html)
        self.assertIn('有效訂單數', html)
        self.assertIn('平均客單價', html)
        self.assertIn('客戶數', html)

        # 2. 驗證會計規範：已取消訂單（ORD-20261003-001，金額 8,400）不列入累計營收
        # 總營收若含取消為 103,610，排除取消應精確為 95,210
        self.assertIn('95,210', html, "累計營收應為 95,210（排除已取消之 8,400）")
        self.assertNotIn('103,610', html, "已取消訂單金額不得計入累計營收！")

        # 3. 驗證 Chart.js 折線圖與環圈圖 Canvas 元件
        self.assertIn('id="monthlyTrendChart"', html, "需包含每月營收趨勢折線圖 canvas")
        self.assertIn('id="orderStatusChart"', html, "需包含訂單狀態分布環圈圖 canvas")
        self.assertIn('chart.umd.min.js', html, "需載入 Chart.js 函式庫")

        # 4. 驗證熱銷商品 Top 5 與客戶消費排行 Top 5
        self.assertIn('熱銷商品 Top 5', html)
        self.assertIn('客戶消費排行 Top 5', html)

        # 5. 驗證響應式佈局支援手機單欄 (包含 col-12)
        self.assertIn('col-12', html)

if __name__ == '__main__':
    unittest.main()
