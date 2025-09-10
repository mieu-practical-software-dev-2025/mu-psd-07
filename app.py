import os
import json
import re
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
DEFAULT_SYSTEM_PROMPT = "あなたは親切なアシスタントです。丁寧な言葉遣いで、140字以内で簡潔に回答してください。"
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
    validation_system_prompt = """あなたはディベートテーマを考えるのを手伝うアシスタントです。ユーザーから提案されたテーマが、2者間でのディベートに適しているか、以下の観点からアドバイスをしてください。
判断基準は以下の通りです。
1. 賛成と反対の明確な立場が存在するか？
2. 倫理的に問題のあるテーマではないか？
3. 非常に個人的な、または主観的すぎるテーマではないか？
4. ある程度の議論の広がりが期待できるか？

上記の基準に基づき、あなたの評価を「適切」または「不適切」のいずれかで示し、その理由を簡潔に説明してください。あくまで提案として、決めつけるような表現は避けてください。
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

        # AIの応答からJSONオブジェクト/配列を抽出する
        # AIが説明文などを付けてもJSON部分だけを取り出せるようにする
        json_match = re.search(r'\{.*\}|\[.*\]', ai_response, re.DOTALL)
        if not json_match:
            app.logger.error(f"No JSON object found in AI response: {ai_response}")
            return jsonify({"error": "AIの応答から有効なJSON形式のデータを見つけられませんでした。"}), 500

        try:
            # JSON文字列をPythonの辞書にパース
            json_response = json.loads(json_match.group())
            return jsonify(json_response)
        except json.JSONDecodeError:
            app.logger.error(f"Failed to parse extracted JSON string: {json_match.group()}")
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
    user_message_count = sum(1 for msg in conversation_history if msg.get('role') == 'user')

    # 会話の長さに応じてプロンプトを切り替える
    if user_message_count < 3:
        # 会話が短い場合のプロンプト：健闘を称えるシンプルなメッセージ
        feedback_system_prompt = """あなたはディベートのコーチです。いかなる場合でも、挨拶、相槌、前置き（「しかし、」「一方で、」など）、そしてあなた自身の立場を示す言葉（例:【否定派】）を一切含めず、文章の最初から評価の核心部分だけを記述してください。
提供された会話履歴を読み、ディベートの参加者を励ます短いメッセージを作成してください。
会話がまだ始まったばかりであることを踏まえ、最初の意見交換を称賛し、今後の議論への期待感を示す、ポジティブで短いコメントをお願いします。
"""
    else:
        # 会話が十分長い場合のプロンプト：詳細なフィードバック
        feedback_system_prompt = """あなたはディベートのコーチです。いかなる場合でも、挨拶、相槌、前置き（「しかし、」「一方で、」など）、そしてあなた自身の立場を示す言葉（例:【否定派】）を一切含めず、文章の最初から評価の核心部分だけを記述してください。
提供されたディベートの会話履歴全体を分析し、建設的なフィードバックを提供してください。

以下の手順に従って、フィードバックを作成してください。

1.  **全体的な評価**: まず、ディベート全体の簡単な総評を述べてください。
2.  **評価項目**: 次に、以下の3つの観点について、それぞれ100点満点で採点し、その点数を付けた理由を簡潔に説明してください。
    *   **論理の一貫性**: 主張や議論に矛盾がなく、一貫していたか。
    *   **説得力**: 提示された根拠や例が主張を効果的に裏付けていたか。
    *   **反論の質**: 相手の意見の要点を的確に捉え、有効な反論ができていたか。
3.  **改善点**: 最後に、今後のディベートでさらに議論を深めるための具体的なアドバイスや改善点を1〜2点挙げてください。
4.  **締め**: 全体をポジティブな言葉で締めくくってください。
"""

    # 既存の会話履歴の先頭に、フィードバック用のシステムプロンプトを追加
    messages_for_feedback = [{"role": "system", "content": feedback_system_prompt}] + conversation_history

    # ユーザーの最後の発言が指示だと誤解されるのを防ぎつつ、その発言も評価対象に含めるため、
    # 会話履歴の最後に「ここまでがディベートです」という区切りを追加する。
    # これにより、AIは会話履歴の全体を評価対象として明確に認識できる。
    # history_for_feedback = conversation_history + [{"role": "system", "content": "--- ここまでがディベートの会話です ---"}]

    messages_for_feedback = [{"role": "system", "content": feedback_system_prompt}]

    try:
        app.logger.info(f"Generating debate feedback for a conversation with {len(conversation_history)} messages.")
        chat_completion = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages_for_feedback,
        )

        feedback_text = chat_completion.choices[0].message.content.strip()
        feedback_text = ""
        # APIからのレスポンスが期待通りかチェックし、内容を取得
        if chat_completion.choices and chat_completion.choices[0].message and chat_completion.choices[0].message.content:
            feedback_text = chat_completion.choices[0].message.content.strip()

        # AIからの応答が空だった場合に備えて、デフォルトのメッセージを設定
        if not feedback_text:
            app.logger.warning("AI returned empty feedback. Providing a default message.")
            feedback_text = "AIからのフィードバックがありませんでした。会話が短すぎるか、内容を解釈できなかった可能性があります。"

        app.logger.info(f"AI feedback response: {feedback_text}")
        app.logger.info(f"AI feedback response: {chat_completion}")

        return jsonify({"feedback": feedback_text})

    except APIError as e:
        app.logger.error(f"OpenRouter API Error during feedback generation: {e}")
        return jsonify({"error": f"フィードバック生成中にAIサービスでエラーが発生しました。ステータスコード: {e.status_code}"}), e.status_code or 500
    except Exception as e:
        app.logger.error(f"Error during debate feedback generation: {e}")
        return jsonify({"error": "フィードバックの生成中に予期せぬサーバーエラーが発生しました。"}), 500

# スクリプトが直接実行された場合にのみ開発サーバーを起動
if __name__ == '__main__':
    # 起動時の警告はクライアント初期化時にapp.loggerで行うように変更
    app.run(debug=True, host='0.0.0.0', port=5000)