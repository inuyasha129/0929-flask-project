import unittest
import json
from app import app
from db import init_db, get_db_connection

class OrderManagementSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 初始化資料庫結構與 5 筆繁體中文種子資料
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

    def test_01_login_page_renders(self):
        """測試登入頁面是否正常渲染 (HTTP 200)"""
        response = self.app.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn('管理員登入'.encode('utf-8'), response.data)

    def test_02_admin_login_and_dashboard(self):
        """測試管理員帳號登入與儀表板存取"""
        # 未登入存取應被重導向至 /login
        resp_unauth = self.app.get('/', follow_redirects=False)
        self.assertEqual(resp_unauth.status_code, 302)

        # 成功登入
        resp_login = self.login('admin', 'admin123')
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn('營運資訊總覽'.encode('utf-8'), resp_login.data)

    def test_03_seed_customers_and_products_exist(self):
        """測試 5 筆繁體中文客戶與商品資料庫紀錄"""
        conn = get_db_connection()
        cust_cnt = conn.execute("SELECT COUNT(*) FROM customer").fetchone()[0]
        prod_cnt = conn.execute("SELECT COUNT(*) FROM product").fetchone()[0]
        orders_cnt = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        conn.close()

        self.assertGreaterEqual(cust_cnt, 5)
        self.assertGreaterEqual(prod_cnt, 5)
        self.assertGreaterEqual(orders_cnt, 5)

    def test_04_order_creation_and_price_snapshot(self):
        """
        核心測試 (需求 6 & 7):
        1. 建立訂單時以客戶下拉選單與多選商品建立
        2. 商品改價後，歷史訂單的 order_item.price 絕不受影響
        """
        self.login('admin', 'admin123')
        conn = get_db_connection()
        prod = conn.execute("SELECT product_id, price FROM product WHERE product_id = 'PROD-001'").fetchone()
        original_price = prod['price']
        conn.close()

        test_order_id = "ORD-TEST-99999"
        # 建立新訂單，勾選 PROD-001，數量 2
        resp = self.app.post('/orders/new', data={
            'order_id': test_order_id,
            'customer_id': 'CUST-001',
            'order_date': '2026-10-03',
            'status': '處理中',
            'salesperson': '陳家豪',
            'selected_products': ['PROD-001'],
            'quantity_PROD-001': '2'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)

        # 驗證 order_item 中的單價是否精確等於下單時的 original_price
        conn = get_db_connection()
        item = conn.execute("SELECT price, quantity FROM order_item WHERE order_id = ? AND product_id = ?", (test_order_id, 'PROD-001')).fetchone()
        self.assertIsNotNone(item)
        self.assertEqual(item['price'], original_price)

        # 模擬商品改價 (例如由 8800 改為 9999)
        new_price = 9999.0
        conn.execute("UPDATE product SET price = ? WHERE product_id = 'PROD-001'", (new_price,))
        conn.commit()

        # 重新驗證歷史訂單 order_item.price 是否依然保持原始價格 (未被竄改)
        item_after = conn.execute("SELECT price FROM order_item WHERE order_id = ? AND product_id = ?", (test_order_id, 'PROD-001')).fetchone()
        self.assertEqual(item_after['price'], original_price)

        # 清理測試訂單並還原商品價格
        conn.execute("DELETE FROM orders WHERE order_id = ?", (test_order_id,))
        conn.execute("UPDATE product SET price = ? WHERE product_id = 'PROD-001'", (original_price,))
        conn.commit()
        conn.close()

    def test_05_inline_status_update(self):
        """測試需求 8: 在列表中直接更新訂單狀態"""
        self.login('admin', 'admin123')
        # 測試 AJAX 更新狀態
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

    def test_06_order_detail_page_and_qrcode(self):
        """測試需求 9: 專屬訂單頁面 /order/<id> 與出貨單 QRCode"""
        response = self.app.get('/order/ORD-20261001-001')
        self.assertEqual(response.status_code, 200)
        # 驗證頁面包含出貨單與 QRCode base64 圖片
        self.assertIn('出貨裝箱單'.encode('utf-8'), response.data)
        self.assertIn('data:image/png;base64,'.encode('utf-8'), response.data)

        # 測試原始 QRCode 路由
        resp_qr = self.app.get('/order/ORD-20261001-001/qrcode')
        self.assertEqual(resp_qr.status_code, 200)
        self.assertEqual(resp_qr.content_type, 'image/png')

if __name__ == '__main__':
    unittest.main()
