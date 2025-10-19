# bot.py
import os
import random
import time
import logging
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import tweepy
from dotenv import load_dotenv

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# ローカル開発やテスト時に .env を使えるようにする（Actionsではenv varsを使うので無効でもOK）
load_dotenv()

# X / Twitter のキー（GitHub Actions では secrets 経由で環境変数に入ります）
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

# 投稿先サイト（あなたのサイト）
TARGET_SITE = "https://active-gyoseisyosi.com/"

# 投稿スタイルの割合（B:フレンドリー80% / A:丁寧20%）
STYLE_B_WEIGHT = 0.8

# 投稿テンプレート（B寄りが多め）
TEMPLATES_B = [
    "この記事、気になった方多いみたい！ぜひ読んでみてください👇\n{title}\n{url}",
    "最近のおすすめ記事です✨\n{title}\n{url}",
    "お、面白い更新がありました！チェックしてみてください👇\n{title}\n{url}",
    "この記事、ためになりました！共有します📝\n{title}\n{url}",
    "久しぶりに読み返したら良かったです。良ければどうぞ👇\n{title}\n{url}"
]
TEMPLATES_A = [
    "新しい記事を公開しました。ご興味あればご覧ください。\n{title}\n{url}",
    "最新の投稿をお知らせします。\n{title}\n{url}"
]

# スクレイピング：複数の方法で記事リンクを探す（堅牢化）
def fetch_article_list(base_url):
    logging.info("Fetching site: %s", base_url)
    try:
        r = requests.get(base_url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logging.error("Failed to fetch site: %s", e)
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    candidates = []

    # 1) HTML5 <article> タグを探す
    for art in soup.find_all("article"):
        a = art.find("a", href=True)
        if a:
            title = (a.get_text() or "").strip()
            link = a["href"]
            candidates.append((title, link))

    # 2) クラス名に 'post' 'entry' 'article' を含む要素から探す
    if not candidates:
        selectors = ["h2 a", ".post a", ".entry-title a", ".article a", ".post-title a"]
        for sel in selectors:
            for a in soup.select(sel):
                if a and a.get("href"):
                    title = (a.get_text() or "").strip()
                    link = a["href"]
                    candidates.append((title, link))

    # 3) リンク群からドメイン内の有力候補を拾う（フォールバック）
    if not candidates:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/") or base_url in href:
                text = (a.get_text() or "").strip()
                if len(text) > 10 and len(text) < 200:  # 簡易フィルタ
                    link = href if href.startswith("http") else base_url.rstrip("/") + href
                    candidates.append((text, link))

    # 正規化（相対パスを絶対にする）
    normalized = []
    for title, link in candidates:
        if not link.startswith("http"):
            link = base_url.rstrip("/") + "/" + link.lstrip("/")
        normalized.append((title, link))

    # 重複除去（URL優先）
    seen = set()
    out = []
    for t, l in normalized:
        if l not in seen:
            seen.add(l)
            out.append((t, l))
    logging.info("Found %d candidate articles", len(out))
    return out

# 投稿文生成（人間らしさを演出）
def compose_text(title, url):
    # スタイル選択（B 80% / A 20%）
    if random.random() < STYLE_B_WEIGHT:
        template = random.choice(TEMPLATES_B)
    else:
        template = random.choice(TEMPLATES_A)

    # 軽いランダム要素：前置き・絵文字
    prefixes = ["", "🔔 ", "※", "✨ ", ""]
    suffixes = ["", " #お知らせ", " #行政書士", ""]

    text = f"{random.choice(prefixes)}{template.format(title=title, url=url)}{random.choice(suffixes)}"

    # 文字数調整（Twitter は 280 文字）
    if len(text) > 270:
        text = text[:267] + "..."
    return text

# 投稿処理（Tweepy を使う）
def post_to_twitter(text):
    logging.info("Posting to Twitter: %s", text[:80].replace("\n"," ") + ("..." if len(text)>80 else ""))
    auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth, wait_on_rate_limit=True)
    try:
        api.update_status(status=text)
        logging.info("Posted successfully.")
    except Exception as e:
        logging.error("Failed to post: %s", e)

# メインの流れ
def main():
    articles = fetch_article_list(TARGET_SITE)
    if not articles:
        logging.error("No articles found; aborting.")
        return

    # 新着（最初の1件）を優先して投稿する確率を高める
    # たとえば: 60%で最新、40%で過去記事ランダム掘り起こし
    if random.random() < 0.6:
        chosen = articles[0]  # ページ内最初の候補を「最新」と仮定
        logging.info("Choosing latest article")
    else:
        chosen = random.choice(articles)
        logging.info("Choosing random past article")

    title, url = chosen

    # URLが記事内アンカーならきれいに整形（オプション）
    tweet = compose_text(title, url)

    # 実行環境変数 TWITTER_DRY_RUN が set されていると投稿しない（テスト用）
    if os.getenv("TWITTER_DRY_RUN") == "1":
        logging.info("DRY RUN: would post:\n%s", tweet)
    else:
        # 投稿前の小さなランダム待機（人間っぽさ）
        delay = random.randint(5, 90)  # 5～90秒ランダム待ち
        logging.info("Sleeping %d seconds before posting (human-like delay)", delay)
        time.sleep(delay)
        post_to_twitter(tweet)

if __name__ == "__main__":
    main()
