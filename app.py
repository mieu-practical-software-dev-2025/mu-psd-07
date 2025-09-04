import os
import uuid
import re
import atexit
import json
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory, session, stream_with_context
from openai import OpenAI, APIError # Import the OpenAI library and specific errors

# .envファイルから環境変数を読み込む
load_dotenv()

# Flaskアプリケーションのインスタンスを作成
app = Flask(__name__)
# セッション機能のためにSECRET_KEYを設定。本番環境では推測されにくい値に変更してください。
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-for-flask-session")

# --- 定数/設定値 ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("YOUR_SITE_URL", "http://localhost:5000")
APP_NAME = os.getenv("YOUR_APP_NAME", "FlaskVueApp")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "google/gemma-3-27b-it:free")
DEBATES_FILE = "debates.json"

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

# --- 履歴保存/読み込み関数 ---
def load_debates():
    """JSONファイルからすべてのディベート履歴を読み込む"""
    if not os.path.exists(DEBATES_FILE):
        return {}
    try:
        with open(DEBATES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_debates(debates):
    """すべてのディベート履歴をJSONファイルに保存する"""
    with open(DEBATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(debates, f, ensure_ascii=False, indent=2)

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

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/debates', methods=['GET'])
def get_all_debates():
    """保存されているすべてのディベートのリストを返す"""
    debates = load_debates()
    # 各ディベートのテーマ（systemプロンプトから抽出）とIDをリスト化
    debate_list = []
    for session_id, data in debates.items():
        theme = "不明なテーマ"
        if data and data.get('history'):
            system_prompt = next((msg['content'] for msg in data['history'] if msg['role'] == 'system'), None)
            if system_prompt:
                # "テーマは「...」です。" の部分を抽出
                start_index = system_prompt.find('「')
                end_index = system_prompt.find('」', start_index)
                if start_index != -1 and end_index != -1:
                    theme = system_prompt[start_index + 1:end_index]
        debate_list.append({"session_id": session_id, "theme": theme})
    return jsonify(sorted(debate_list, key=lambda x: x['session_id'], reverse=True))

@app.route('/api/debate/<session_id>', methods=['GET'])
def get_specific_debate(session_id):
    """指定されたIDのディベート履歴を返す"""
    debates = load_debates()
    debate_data = debates.get(session_id)
    if not debate_data:
        return jsonify({"error": "Debate not found"}), 404
    
    # メタデータを抽出
    theme = "不明なテーマ"
    ai_stance = "不明"
    system_prompt_content = next((msg['content'] for msg in debate_data['history'] if msg['role'] == 'system'), None)
    if system_prompt_content:
        # テーマを抽出
        theme_match = re.search(r'テーマは「([^」]+)」', system_prompt_content)
        if theme_match:
            theme = theme_match.group(1)
        # AIの立場を抽出
        stance_match = re.search(r'あなたは「([^」]+)」の立場で議論します', system_prompt_content)
        if stance_match:
            ai_stance = stance_match.group(1)

    # 現在のセッションにこのディベートをロードする
    session['session_id'] = session_id
    session['history'] = debate_data['history']
    session.modified = True

    return jsonify({"session_id": session_id, "history": debate_data['history'], "theme": theme, "ai_stance": ai_stance})

@app.route('/api/debate/start', methods=['POST'])
def start_debate():
    """新しいディベートセッションを開始し、セッションIDと初期メッセージを返す"""
    data = request.get_json()
    if not data or 'system_prompt' not in data or 'initial_message' not in data:
        return jsonify({"error": "system_prompt and initial_message are required"}), 400
    
    session_id = str(uuid.uuid4())
    history = [
        {"role": "system", "content": data['system_prompt']},
        {"role": "assistant", "content": data['initial_message']}
    ]
    
    # セッションとファイルの両方に保存
    session['session_id'] = session_id
    session['history'] = history
    session.modified = True

    debates = load_debates()
    debates[session_id] = {"history": history}
    save_debates(debates)

    app.logger.info(f"New debate started. Session ID: {session_id}")
    return jsonify({"session_id": session_id, "history": history})

@app.route('/api/debate/history', methods=['GET'])
def get_history():
    """現在のセッションの会話履歴を返す"""
    if 'session_id' in session and 'history' in session:
        return jsonify({"session_id": session['session_id'], "history": session['history']})
    return jsonify({"error": "No active session found"}), 404

@app.route('/api/debates/clear', methods=['POST'])
def clear_all_debates():
    """すべてのディベート履歴と現在のセッションをクリアする"""
    # debates.jsonを空にする
    save_debates({})
    # Flaskのセッションをクリアする
    session.clear()
    app.logger.info("All debate histories and session have been cleared.")
    return jsonify({"message": "すべての履歴が正常にクリアされました。"}), 200

@app.route('/api/debate/message', methods=['POST'])
def post_message():
    """ユーザーのメッセージを受け取り、AIの応答をストリーミングで返す"""
    if not client:
        app.logger.error("OpenRouter API key not configured.")
        return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500

    if 'session_id' not in session or 'history' not in session:
        return jsonify({"error": "Session not found. Please start a new debate."}), 400

    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "Request must contain 'message' field"}), 400

    user_message = data['message']
    is_ai_first_turn = data.get('is_ai_first_turn', False)

    # AIが先攻の場合はユーザーメッセージを追加しない
    if not is_ai_first_turn:
        session['history'].append({"role": "user", "content": user_message})

    # --- モデルに合わせたメッセージ形式の変換 ---
    # google/gemmaモデルはsystemプロンプトをサポートしていないため、
    # systemロールをuserロールに変換し、直後にassistantロールを挿入する
    messages_to_send = []
    original_history = session.get('history', [])
    for i, msg in enumerate(original_history):
        if msg.get('role') == 'system':
            # systemをuserに変換
            messages_to_send.append({'role': 'user', 'content': msg['content']})
            # 次がassistantメッセージでなければ、空のassistantメッセージを挿入
            if i + 1 >= len(original_history) or original_history[i+1].get('role') != 'assistant':
                messages_to_send.append({'role': 'assistant', 'content': ''})
        else:
            messages_to_send.append(msg)
    # -----------------------------------------

    try:
        # ストリーミング応答
        def generate():
            completion_stream = client.chat.completions.create(
                messages=messages_to_send,
                model=DEFAULT_MODEL,
                stream=True
            )
            
            # AIの完全な応答を組み立ててからセッションに保存する
            full_response = ""
            for chunk in completion_stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_response += content
                    yield content
            
            # with app.app_context() を使わなくてもセッションはリクエストコンテキスト内で利用可能
            if 'history' in session:
                # セッション履歴を更新
                session['history'].append({"role": "assistant", "content": full_response})
                session.modified = True
                # ファイル履歴も更新
                debates = load_debates()
                if session['session_id'] in debates:
                    debates[session['session_id']]['history'] = session['history']
                    save_debates(debates)
                app.logger.info(f"AI response saved to session {session.get('session_id')}")

        return Response(stream_with_context(generate()), mimetype='text/plain')

    except APIError as e:
        app.logger.error(f"OpenRouter API Error: {e}")
        return jsonify({"error": f"AIサービスでエラーが発生しました。ステータスコード: {e.status_code}"}), e.status_code or 500
    except Exception as e:
        app.logger.error(f"OpenRouter API call failed: {e}")
        return jsonify({"error": f"AIサービスとの通信中にエラーが発生しました。"}), 500

# --- 終了時処理 ---
import atexit
def cleanup_on_exit():
    """アプリケーション終了時にdebates.jsonの中身を空にする"""
    save_debates({})
    print(f"Info: Contents of {DEBATES_FILE} have been cleared on exit.")

atexit.register(cleanup_on_exit)

# スクリプトが直接実行された場合にのみ開発サーバーを起動
if __name__ == '__main__':
    # 起動時の警告はクライアント初期化時にapp.loggerで行うように変更
    app.run(debug=True, host='0.0.0.0', port=5000)