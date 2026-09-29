from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def home():
    """首頁路由：渲染一頁式網站"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template('index.html', server_time=current_time)

@app.route('/api/greet', methods=['POST'])
def greet():
    """示範用 API：接收使用者名字並回傳問候訊息"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        name = "訪客"
    
    response_message = f"Hello, {name}! 歡迎來到 Python Flask 的世界！"
    return jsonify({
        "status": "success",
        "message": response_message,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

if __name__ == '__main__':
    # 啟動本機伺服器，監聽 5000 連接埠 (0.0.0.0 支援 localhost 與 127.0.0.1 連線)
    print("==================================================")
    print("Flask 網站伺服器已啟動！")
    print("本機瀏覽網址: http://127.0.0.1:5000 或 http://localhost:5000")
    print("==================================================")
    app.run(debug=True, host='0.0.0.0', port=5000)
