# bot_v2.py
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

# ローカル開発やテスト時に .env を使えるようにする
load_dotenv()

# X / Twitter のキー（GitHub Actions では secrets 経由で環境変数に入ります）
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")  # v2 API用

# 投稿先サイト
TARGET_SITE = "https://active-gyoseisyosi.com/"

# 投稿スタイルの割合（B:フレンドリー80% / A:丁寧20%）
STYLE_B_WEIGHT = 0.8

# 投稿テンプレート
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

# v2 API クライアント作成
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET,
    bearer_token=BEARER_TOKEN
)

# 投稿テンプレート選択
def compose_text(title, url):
    if random.random() < STYLE_B_WEIGHT:
        template = random.choice(TEMPLATES_B)
    else:
        template = random.choice(TEMPLATES_A)

    prefixes = ["", "🔔 ", "※", "✨ ", ""]
    suffixes = ["", " #お知らせ", " #行政書士", ""]

    text = f"{random.choice(prefixes)}{template.format(title=title, url=url)}{random.choice(suffixes)}"

    if len(text) > 270:
        text = text[:267] + "..."
    return text

# 投稿処理 v2 API 用
def post_to_twitter(text):
    logging.info("Posting to Twitter (v2 API): %s", text[:80].replace("\n"," ") + ("..." if len(text)>80 else ""))
    try:
        response = client.create_tweet(text=text)
        logging.info("Posted successfully (v2 API). Tweet ID: %s", response.data['id'])
    except Exception as e:
        logging.error("Failed to post (v2 API): %s", e)

# 記事スクレイピング
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

    for art in soup.find_all("article"):
        a = art.find("a", href=True)
        if a:
            title = (a.get_text() or "").strip()
            link = a["href"]
            candidates.append((title, link))

    if not candidates:
        selectors = ["h2 a", ".post a", ".entry-title a", ".article a", ".post-title a"]
        for sel in selectors:
            for a in soup.select(sel):
                if a and a.get("href"):
                    title = (a.get_text() or "").strip()
                    link = a["href"]
                    candidates.append((title, link))

    if not candidates:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/") or base_url in href:
                text = (a.get_text() or "").strip()
                if len(text) > 10 and len(text) < 200:
                    link = href if href.startswith("http") else base_url.rstrip("/") + href
                    candidates.append((text, link))

    normalized = []
    for title, link in candidates:
        if not link.startswith("http"):
            link = base_url.rstrip("/") + "/" + link.lstrip("/")
        normalized.append((title, link))

    seen = set()
    out = []
    for t, l in normalized:
        if l not in seen:
            seen.add(l)
            out.append((t, l))
    logging.info("Found %d candidate articles", len(out))
    return out

# メイン処理
def main():
    articles = fetch_article_list(TARGET_SITE)
    if not articles:
        logging.error("No articles found; aborting.")
        return

    if random.random() < 0.6:
        chosen = articles[0]
        logging.info("Choosing latest article")
    else:
        chosen = random.choice(articles)
        logging.info("Choosing random past article")

    title, url = chosen
    tweet = compose_text(title, url)

    if os.getenv("TWITTER_DRY_RUN") == "1":
        logging.info("DRY RUN: would post:\n%s", tweet)
    else:
        delay = random.randint(5, 90)
        logging.info("Sleeping %d seconds before posting (human-like delay)", delay)
        time.sleep(delay)
        post_to_twitter(tweet)

if __name__ == "__main__":
    main()
