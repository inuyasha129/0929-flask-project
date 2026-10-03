import unittest
from app import app

class FlaskTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_home(self):
        """測試首頁是否正常渲染 (HTTP 200)"""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_greet_with_name(self):
        """測試問候 API (帶有名稱)"""
        response = self.app.post('/api/greet', json={'name': 'Alice'})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('Hello, Alice!', data['message'])

    def test_greet_default(self):
        """測試問候 API (預設訪客)"""
        response = self.app.post('/api/greet', json={})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('Hello, 訪客!', data['message'])

if __name__ == '__main__':
    unittest.main()
