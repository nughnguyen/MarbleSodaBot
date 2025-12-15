from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Marble Soda Bot</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                margin: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                color: white;
            }
            .container {
                text-align: center;
                padding: 40px;
                background: rgba(255,255,255,0.1);
                border-radius: 20px;
                backdrop-filter: blur(10px);
            }
            h1 {
                font-size: 3em;
                margin-bottom: 10px;
            }
            p {
                font-size: 1.2em;
                opacity: 0.9;
            }
            .status {
                display: inline-block;
                padding: 10px 20px;
                background: #4CAF50;
                border-radius: 20px;
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎮 Marble Soda Bot</h1>
            <p>Discord Word Chain & Mini Games Bot</p>
            <div class="status">✅ Bot is Online</div>
        </div>
    </body>
    </html>
    '''

@app.route('/health')
def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
