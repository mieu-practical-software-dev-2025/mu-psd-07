hotate
hotate8770
画面共有しています

hotate — 2025/05/21 12:08
もう家出ていい？
orange0600 — 2025/05/21 12:08
いいよ
hotate — 2025/05/21 12:09
でるわ
orange0600 — 2025/05/22 0:23
今から服取り行くわ
カラオケくる？
hotate — 2025/05/22 0:26
いかん
hotate
が2分の通話を開始しました。 — 2025/05/23 12:34
hotate — 2025/06/09 12:09
もう出ていい？
orange0600 — 2025/06/09 12:09
いいよ
hotate — 2025/06/11 16:12
hotate — 2025/06/16 13:04
帰る時にマックスバリューでレトルトのご飯買ってきてもらってもいい？
弁当とかでもいいんやけど、２食分ぐらい
orange0600 — 2025/06/16 13:06
わかった
マックスバリュー行った時に電話するわ
hotate — 2025/06/16 13:08
あざす
orange0600 — 2025/06/16 15:37
ごめん遅くなるかも
hotate — 2025/06/16 15:51
おけ
そんなかってんの？
orange0600 — 2025/06/16 15:51
今はかってる
hotate — 2025/06/16 15:54
「今は」ね、了解
hotate — 2025/06/16 18:51
やっぱ適当に食ってくるわ
orange0600 — 2025/06/16 19:11
おけ
orange0600 — 2025/07/10 14:23
上着反対になっとるよ
hotate — 2025/07/15 16:50

#include <stdio.h>
#include "environment.h"
#include "tokenizer.h"
#include "parser.h"
#include "evaluator.h"
展開
c3.c
1 KB
hotate — 2025/07/23 10:43
添付ファイル種類：acrobat
proglang-report.pdf
67.79 KB
orange0600 — 2025/08/06 12:58
あれ7500しかもってないんだけど8500渡した？
渡す時おとしたか
hotate — 2025/08/06 12:58
ミスった？
普通に間違えたかも
orange0600 — 2025/08/06 12:59
7500しかないで
hotate — 2025/08/06 12:59
明日渡すわ
orange0600 — 2025/08/06 12:59
おけ
小銭おとしたよね？そん時札も落としたりしてない？
hotate — 2025/08/06 13:00
さすがに気づきそう
orange0600 — 2025/08/06 13:00
亜熱帯行く前に一応通ってみるわ
hotate — 2025/08/06 13:01
おけ
orange0600 — 2025/08/14 15:18
モンハン誰かとやってる？
hotate — 2025/08/14 15:19
いえす
orange0600 — 2025/08/14 15:19
おけ
orange0600 — 2025/09/01 21:35
いまから行くわ
hotate — 2025/09/01 21:37
おｋ
orange0600 — 2025/09/03 13:32
今から行っていい？
hotate — 2025/09/03 13:33
ええよ
orange0600 — 2025/09/03 13:33
いくわ
hotate — 2025/09/03 14:10
添付ファイル種類：unknown
01 参戦決定☆メタモリディオス.wma
4.03 MB
添付ファイル種類：unknown
02 Iキャラライン.wma
3.33 MB
添付ファイル種類：unknown
03 こいのね!.wma
3.33 MB
添付ファイル種類：unknown
04 Hai.wma
2.58 MB
添付ファイル種類：unknown
05 あんぶれらシンデレラ.wma
3.11 MB
添付ファイル種類：unknown
06 こいのね! (DE DE MOUSE Remix).wma
3.46 MB
orange0600 — 18:31
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Debate App</title>
展開
index.html
12 KB
import os
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from openai import OpenAI, APIError

# .envファイルから環境変数を読み込む
展開
app.py
9 KB
﻿
orange0600
orange0600
 
import os
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from openai import OpenAI, APIError

# .envファイルから環境変数を読み込む
load_dotenv()

# Flaskアプリケーションのインスタンスを作成
# static_folderのデフォルトは 'static' なので、
# このファイルと同じ階層に 'static' フォルダがあれば自動的にそこが使われます。
app = Flask(__name__)

# --- 定数/設定値 ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("YOUR_SITE_URL", "http://localhost:5000")
APP_NAME = os.getenv("YOUR_APP_NAME", "DebateApp")
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
        default_headers={
            "HTTP-Referer": SITE_URL,
            "X-Title": APP_NAME,
        }
    )
else:
    client = None
    app.logger.warning("環境変数 OPENROUTER_API_KEY が設定されていません。API呼び出しは失敗します。")

# ディベートの文脈を保持するための変数
debate_system_prompt = ""

# URL:/ に対して、static/index.htmlを表示して
    # クライアントサイドのVue.jsアプリケーションをホストする
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')
    
# URL:/start_debate に対するメソッドを定義
@app.route('/start_debate', methods=['POST'])
def start_debate():
    global debate_system_prompt
    data = request.get_json()
    if not data or 'topic' not in data or 'user_position' not in data:
        return jsonify({"error": "Request must contain 'topic' and 'user_position'"}), 400

    topic = data['topic']
    user_position = data['user_position'] # 'affirmative' or 'negative'

    if user_position == 'affirmative':
        ai_position_jp = "否定側"
        ai_position_en = "negative"
    elif user_position == 'negative':
        ai_position_jp = "肯定側"
        ai_position_en = "affirmative"
    else:
        return jsonify({"error": "user_position must be 'affirmative' or 'negative'"}), 400

    debate_system_prompt = (
        f"これは「{topic}」というテーマに関するディベートです。"
        f"あなたは{ai_position_jp}の立場です。ユーザーは反対の立場にいます。"
        "あなたの役割は、提供された情報や一般的な知識に基づいて、説得力のある反対意見を述べることです。"
        "感情的にならず、論理的かつ簡潔に反論してください。回答は140字以内でお願いします。"
    )

    app.logger.info(f"Debate started. Topic: '{topic}', AI position: {ai_position_en}")
    return jsonify({"message": "Debate context has been set.", "ai_position": ai_position_en, "ai_position_jp": ai_position_jp})

# URL:/validate_topic に対するメソッドを定義
@app.route('/validate_topic', methods=['POST'])
def validate_topic():
    if not client:
        app.logger.error("OpenRouter API key not configured.")
        return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500

    data = request.get_json()
    if not data or 'topic' not in data:
        return jsonify({"error": "Request must contain 'topic'"}), 400

    topic = data['topic']
    validation_prompt = (
        f"このテーマ「{topic}」は、2者間のディベートのテーマとして適切ですか？ "
        "以下のいずれかで答えてください:「適切」または「不適切」。"
    )

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": validation_prompt}],
            model=DEFAULT_MODEL,
        )

        if chat_completion.choices and chat_completion.choices[0].message and chat_completion.choices[0].message.content:
            validation_result = chat_completion.choices[0].message.content.strip()
            is_appropriate = validation_result == "適切"
            return jsonify({"is_appropriate": is_appropriate, "validation_result": validation_result})
        else:
            return jsonify({"is_appropriate": False, "validation_result": "AIから有効な応答がありませんでした。"}), 500

    except APIError as e:
        app.logger.error(f"OpenRouter API Error: {e}")
        return jsonify({"error": f"AIサービスでエラーが発生しました。ステータスコード: {e.status_code}"}), e.status_code or 500
    except Exception as e:
        app.logger.error(f"OpenRouter API call failed: {e}")
        return jsonify({"error": "AIサービスとの通信中にエラーが発生しました。"}), 500
# URL:/send_api に対するメソッドを定義
@app.route('/send_api', methods=['POST'])
def send_api():
    if not client:
        app.logger.error("OpenRouter API key not configured.")
        return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500

    if not debate_system_prompt:
        return jsonify({"error": "Debate has not been started. Please call /start_debate first."}), 400

    # POSTリクエストからJSONデータを取得
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "Request must contain 'text' field"}), 400 # 'text'は必須

    user_text = data.get('text', '').strip()

    # 過去の会話履歴を取得（フロントエンドから送られてくる想定）
    messages = [{"role": "system", "content": debate_system_prompt}] + [{"role": "user", "content": user_text}]

    app.logger.info(f"Received debate message with {len(history)} history entries.")

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
            processed_text = "AIから有効な応答がありませんでした。"
            
        return jsonify({"processed_text": processed_text})

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
app.py
9 KB