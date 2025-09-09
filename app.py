import os
import json
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

# URL:/validate_theme に対するメソッドを定義
@app.route('/validate_theme', methods=['POST'])
def validate_theme():
    """ディベートのテーマが適切かAIに判断させるエンドポイント"""
    if not client:
        app.logger.error("OpenRouter API key not configured.")
        return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500

    data = request.get_json()
    if not data or 'theme' not in data:
        return jsonify({"error": "Request must contain 'theme'"}), 400

    theme = data['theme'].strip()
    if not theme:
        return jsonify({"error": "'theme' cannot be empty"}), 400

    # AIにテーマの妥当性を判断させるためのシステムプロンプト
    validation_system_prompt = """あなたはディベートの審判です。ユーザーから提案されたテーマが、2者間でのディベートのテーマとして適切かどうかを判断してください。
判断基準は以下の通りです。
1. 賛成と反対の明確な立場が存在するか？
2. 倫理的に問題のあるテーマではないか？
3. 非常に個人的な、または主観的すぎるテーマではないか？
4. ある程度の議論の広がりが期待できるか？

上記の基準に基づき、最終的な判断を「適切」または「不適切」のいずれかで示し、その理由を簡潔に説明してください。
回答はJSON形式で、'judgement' (適切/不適切) と 'reason' (理由) の2つのキーを持つオブジェクトとしてください。
例: {"judgement": "適切", "reason": "賛成と反対の立場が明確で、公共の関心事について多角的な議論が期待できるため。"}
例: {"judgement": "不適切", "reason": "これは個人の好みの問題であり、客観的な議論には向いていません。"}
"""

    messages = [
        {"role": "system", "content": validation_system_prompt},
        {"role": "user", "content": theme}
    ]

    try:
        app.logger.info(f"Validating debate theme: {theme}")
        chat_completion = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
        )

        ai_response = chat_completion.choices[0].message.content
        app.logger.info(f"AI validation response: {ai_response}")

        # AIの応答がMarkdownのコードブロック（```json ... ```）で囲まれている場合を考慮して、
        # 中身のJSON部分だけを抽出する
        cleaned_response = ai_response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:] # "```json" を削除
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3] # "```" を削除

        try:
            # JSON文字列をPythonの辞書にパース
            json_response = json.loads(cleaned_response.strip())
            return jsonify(json_response)
        except json.JSONDecodeError:
            app.logger.error(f"Failed to parse AI response as JSON: {cleaned_response}")
            return jsonify({"error": "AIからの応答をJSONとして解釈できませんでした。"}), 500

    except Exception as e:
        app.logger.error(f"Error during theme validation: {e}")
        return jsonify({"error": "テーマの妥当性チェック中にAIサービスでエラーが発生しました。"}), 500

@app.route('/end_debate', methods=['POST'])
def end_debate():
    """ディベート全体の内容についてAIにフィードバックを生成させるエンドポイント"""
    if not client:
        app.logger.error("OpenRouter API key not configured.")
        return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500

    data = request.get_json()
    if not data or 'messages' not in data:
        return jsonify({"error": "Request must contain 'messages'"}), 400

    conversation_history = data['messages']

    # フィードバックを生成するためのシステムプロンプト
    feedback_system_prompt = """あなたは経験豊富なディベートの審査員です。
これまでのディベートの会話履歴全体をレビューし、以下の観点からユーザーの議論を評価してください。

1.  **論理の一貫性**: 主張に一貫性があったか。
2.  **説得力**: 根拠は適切で、説得力があったか。
3.  **反論の質**: 相手の意見に対して、的確な反論ができていたか。
4.  **改善点**: 次にディベートを行う際の具体的なアドバイス。

上記の4つの項目について、**太字**の見出しを使って、それぞれ簡潔にフィードバックをまとめてください。
"""

    # 既存の会話履歴の先頭に、フィードバック用のシステムプロンプトを追加
    messages_for_feedback = [{"role": "system", "content": feedback_system_prompt}] + conversation_history

    try:
        app.logger.info(f"Generating debate feedback for a conversation with {len(conversation_history)} messages.")
        chat_completion = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages_for_feedback,
        )

        feedback_text = chat_completion.choices[0].message.content.strip()
        app.logger.info(f"AI feedback response: {feedback_text}")

        return jsonify({"feedback": feedback_text})

    except Exception as e:
        app.logger.error(f"Error during debate feedback generation: {e}")
        return jsonify({"error": "フィードバックの生成中にAIサービスでエラーが発生しました。"}), 500

# スクリプトが直接実行された場合にのみ開発サーバーを起動
if __name__ == '__main__':
    # 起動時の警告はクライアント初期化時にapp.loggerで行うように変更
    app.run(debug=True, host='0.0.0.0', port=5000)