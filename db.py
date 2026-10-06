import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'order_system.db')

# 預設管理員密碼之 Werkzeug scrypt 安全雜湊（原始碼與畫面均不存放明碼）
DEFAULT_ADMIN_HASH = os.environ.get(
    'ADMIN_PASSWORD_HASH',
    'scrypt:32768:8:1$1f2MWiZARdlU91Y6$0c9c1826cad242fbbfa2af4928c2c5af0bf90e5b86e6980c6ad56ae9533caf3532190f6f68b80257013efa5ae32a0f1cd4490c188e5b6bb5313e8bf7b7f6c844'
)

def get_db_connection():
    """建立並取得 SQLite 資料庫連線，設定 Row Factory 與外鍵約束"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """初始化資料庫表格並插入 5 筆繁體中文測試資料"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. 建立管理員資料表 (含角色欄位 role)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin'
    );
    ''')

    # 確保現有 admin 資料表具備 role 欄位
    cursor.execute("PRAGMA table_info(admin);")
    admin_columns = [col[1] for col in cursor.fetchall()]
    if 'role' not in admin_columns:
        cursor.execute("ALTER TABLE admin ADD COLUMN role TEXT NOT NULL DEFAULT 'admin';")
        cursor.execute("UPDATE admin SET role = 'admin' WHERE role IS NULL OR role = '';")

    # 2. 建立客戶資料表 (customer)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS customer (
        customer_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    # 3. 建立商品資料表 (product)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS product (
        product_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL NOT NULL CHECK(price >= 0),
        stock INTEGER NOT NULL CHECK(stock >= 0),
        category TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    # 4. 建立訂單資料表 (orders)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        order_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('處理中', '已出貨', '已完成', '已取消')),
        salesperson TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customer (customer_id) ON DELETE RESTRICT
    );
    ''')

    # 5. 建立訂單明細資料表 (order_item) - 數量三層防護之資料庫 CHECK (必須為正整數)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_item (
        order_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0 AND TYPEOF(quantity) = 'integer'),
        price REAL NOT NULL CHECK(price >= 0),
        PRIMARY KEY (order_id, product_id),
        FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES product (product_id) ON DELETE RESTRICT
    );
    ''')

    # 檢查現有 order_item 是否已升級 TYPEOF(quantity) 檢查約束，若未升級則進行安全轉移
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='order_item';")
    oi_row = cursor.fetchone()
    if oi_row and 'TYPEOF' not in oi_row[0]:
        cursor.execute("PRAGMA foreign_keys = OFF;")
        cursor.execute("ALTER TABLE order_item RENAME TO order_item_old;")
        cursor.execute('''
        CREATE TABLE order_item (
            order_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0 AND TYPEOF(quantity) = 'integer'),
            price REAL NOT NULL CHECK(price >= 0),
            PRIMARY KEY (order_id, product_id),
            FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES product (product_id) ON DELETE RESTRICT
        );
        ''')
        cursor.execute("INSERT INTO order_item SELECT * FROM order_item_old;")
        cursor.execute("DROP TABLE order_item_old;")
        cursor.execute("PRAGMA foreign_keys = ON;")

    # 檢查是否需要插入初始管理員資料 (使用 Werkzeug 安全雜湊，程式碼無明碼)
    cursor.execute("SELECT COUNT(*) FROM admin;")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO admin (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
            ('admin', DEFAULT_ADMIN_HASH, '系統管理員', 'admin')
        )

    # 檢查是否需要插入客戶測試資料 (5 筆繁體中文)
    cursor.execute("SELECT COUNT(*) FROM customer;")
    if cursor.fetchone()[0] == 0:
        customers_data = [
            ('CUST-001', '宏達數位科技有限公司', '02-2345-6789', '台北市信義區信義路五段7號85樓'),
            ('CUST-002', '永慶精密機械股份有限公司', '04-2258-9988', '台中市西屯區台灣大道三段99號'),
            ('CUST-003', '綠意生機連鎖事業部', '07-555-1234', '高雄市左營區博愛二路100號'),
            ('CUST-004', '晨曦國際貿易行', '03-333-8866', '桃園市中壢區中正路200號'),
            ('CUST-005', '睿智創新教育顧問社', '06-200-5588', '台南市東區大學路1號')
        ]
        cursor.executemany(
            "INSERT INTO customer (customer_id, name, phone, address) VALUES (?, ?, ?, ?)",
            customers_data
        )

    # 檢查是否需要插入商品測試資料 (5 筆繁體中文)
    cursor.execute("SELECT COUNT(*) FROM product;")
    if cursor.fetchone()[0] == 0:
        products_data = [
            ('PROD-001', '旗艦級人體工學辦公椅', 8800.0, 45, '辦公家具'),
            ('PROD-002', '4K UltraHD 智慧降噪視訊鏡頭', 3600.0, 80, '電腦周邊'),
            ('PROD-003', '雙模無線機械式鍵盤 (青軸)', 2450.0, 120, '電腦周邊'),
            ('PROD-004', '專業抗藍光雙臂螢幕支架', 1890.0, 65, '辦公配件'),
            ('PROD-005', '節能恆溫智能泡茶機', 4200.0, 30, '生活電器')
        ]
        cursor.executemany(
            "INSERT INTO product (product_id, name, price, stock, category) VALUES (?, ?, ?, ?, ?)",
            products_data
        )

    # 檢查是否需要插入訂單與訂單明細 (5 筆繁體中文)
    cursor.execute("SELECT COUNT(*) FROM orders;")
    if cursor.fetchone()[0] == 0:
        orders_data = [
            ('ORD-20261001-001', 'CUST-001', '2026-10-01', '已完成', '陳家豪'),
            ('ORD-20261001-002', 'CUST-002', '2026-10-01', '已出貨', '林佩芬'),
            ('ORD-20261002-001', 'CUST-003', '2026-10-02', '處理中', '王建銘'),
            ('ORD-20261002-002', 'CUST-004', '2026-10-02', '處理中', '張雅婷'),
            ('ORD-20261003-001', 'CUST-005', '2026-10-03', '已取消', '陳家豪')
        ]
        cursor.executemany(
            "INSERT INTO orders (order_id, customer_id, order_date, status, salesperson) VALUES (?, ?, ?, ?, ?)",
            orders_data
        )

        # 訂單明細 (order_item) 存入當時單價
        items_data = [
            # ORD-20261001-001
            ('ORD-20261001-001', 'PROD-001', 2, 8800.0),
            ('ORD-20261001-001', 'PROD-003', 3, 2450.0),
            # ORD-20261001-002
            ('ORD-20261001-002', 'PROD-002', 5, 3600.0),
            ('ORD-20261001-002', 'PROD-004', 4, 1890.0),
            # ORD-20261002-001
            ('ORD-20261002-001', 'PROD-001', 1, 8800.0),
            ('ORD-20261002-001', 'PROD-002', 2, 3600.0),
            ('ORD-20261002-001', 'PROD-005', 1, 4200.0),
            # ORD-20261002-002
            ('ORD-20261002-002', 'PROD-003', 10, 2450.0),
            # ORD-20261003-001
            ('ORD-20261003-001', 'PROD-005', 2, 4200.0)
        ]
        cursor.executemany(
            "INSERT INTO order_item (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
            items_data
        )

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("SQLite 資料庫初始化完成，5 筆繁體中文測試資料已就緒！")
