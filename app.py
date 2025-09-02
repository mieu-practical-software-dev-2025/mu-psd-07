import os
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from openai import OpenAI, APIError # Import the OpenAI library and specific errors

# .envファイルから環境変数を読み込む
load_dotenv()

# Flaskアプリケーションのインスタンスを作成
# static_folderのデフォルトは 'static' なので、
# このファイルと同じ階層に 'static' フォルダがあれば自動的にそこが使われます。
app = Flask(__name__)

# --- 定数/設定値 ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("YOUR_SITE_URL", "http://localhost:5000")
APP_NAME = os.getenv("YOUR_APP_NAME", "FlaskVueApp")
DEFAULT_SYSTEM_PROMPT = "140字以内で回答してください。"
DEFAULT_MODEL = "google/gemma-3-27b-it:free"

# 開発モード時に静的ファイルのキャッシュを無効にする
if app.debug:
    @app.after_request
    def add_header(response):
        # /static/ 以下のファイルに対するリクエストの場合
        if request.endpoint == 'static':
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache' # HTTP/1.0 backward compatibility
            response.headers['Expires'] = '0' # Proxies
        return response

# --- OpenAIクライアントの初期化 ---
# アプリケーション起動時に一度だけクライアントを初期化する
if OPENROUTER_API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        default_headers={ # Recommended by OpenRouter
            "HTTP-Referer": SITE_URL,
            "X-Title": APP_NAME,
        }
    )
else:
    client = None
    app.logger.warning("環境変数 OPENROUTER_API_KEY が設定されていません。API呼び出しは失敗します。")
# URL:/ に対して、static/index.htmlを表示して
    # クライアントサイドのVue.jsアプリケーションをホストする
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')
    
# URL:/send_api に対するメソッドを定義
@app.route('/send_api', methods=['POST'])
def send_api():
    if not client:
        app.logger.error("OpenRouter API key not configured.")
        return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500
    
    # POSTリクエストからJSONデータを取得
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request JSON is missing"}), 400

    messages = []

    # 新形式: 'messages' 配列を受け取り、会話履歴全体を処理する
    if 'messages' in data and isinstance(data['messages'], list):
        messages = data['messages']
        if not messages:
            return jsonify({"error": "'messages' array cannot be empty"}), 400
        # 簡単なバリデーション
        for msg in messages:
            if not all(k in msg for k in ('role', 'content')):
                 return jsonify({"error": "Each message must have 'role' and 'content'"}), 400
        app.logger.info(f"Received message history with {len(messages)} entries.")

    # 旧形式: 'text' と 'context' を受け取る（後方互換性のため）
    elif 'text' in data:
        received_text = data.get('text', '').strip()
        if not received_text:
            return jsonify({"error": "Input text cannot be empty"}), 400

        system_prompt = data.get('context', '').strip() or DEFAULT_SYSTEM_PROMPT
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": received_text}
        ]
        app.logger.info("Received single text input, creating new conversation.")
    
    else:
        return jsonify({"error": "Request must contain either 'messages' array or 'text' field"}), 400

    try:
        # OpenRouter APIを呼び出し
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=DEFAULT_MODEL,
        )
        
        # APIからのレスポンスを取得
        # .strip() を使って、応答の前後の不要な空白や改行を削除する
        if chat_completion.choices and chat_completion.choices[0].message and chat_completion.choices[0].message.content:
            processed_text = chat_completion.choices[0].message.content.strip()
        else:
            processed_text = "AIから有効な応答がありませんでした。" # No valid response from AI.
            
        return jsonify({"message": "AIによってデータが処理されました。", "processed_text": processed_text})

    except APIError as e:
        app.logger.error(f"OpenRouter API Error: {e}")
        return jsonify({"error": f"AIサービスでエラーが発生しました。ステータスコード: {e.status_code}"}), e.status_code or 500
    except Exception as e:
        app.logger.error(f"OpenRouter API call failed: {e}")
        # クライアントには具体的なエラー詳細を返しすぎないように注意
        return jsonify({"error": f"AIサービスとの通信中にエラーが発生しました。"}), 500

# スクリプトが直接実行された場合にのみ開発サーバーを起動
if __name__ == '__main__':
    # 起動時の警告はクライアント初期化時にapp.loggerで行うように変更
    app.run(debug=True, host='0.0.0.0', port=5000)