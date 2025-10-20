# bot_v2_full.py（日本語ハッシュタグ対応版）
import os
import random
import time
import logging
import requests
from bs4 import BeautifulSoup
import tweepy
from dotenv import load_dotenv
import re

# -------------------------
# ログ設定
# -------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
load_dotenv()

# -------------------------
# APIキー
# -------------------------
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

# -------------------------
# 投稿先サイト
# -------------------------
TARGET_SITE = "https://active-gyoseisyosi.com/"

# -------------------------
# 投稿スタイル
# -------------------------
STYLE_B_WEIGHT = 0.8
TEMPLATES_B = [
    "この記事、気になった方多いみたい！ぜひ読んでみてください👇\n{title}\n{url}",
    "最近のおすすめ記事です✨\n{title}\n{url}",
    "お、面白い更新がありました！チェックしてみてください👇\n{title}\n{url}",
]
TEMPLATES_A = [
    "新しい記事を公開しました。ご興味あればご覧ください。\n{title}\n{url}",
    "最新の投稿をお知らせします。\n{title}\n{url}"
]

# -------------------------
# v2 APIクライアント（テキスト投稿用）
# -------------------------
client_v2 = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET,
    bearer_token=BEARER_TOKEN
)

# -------------------------
# v1.1 APIクライアント（画像アップロード用）
# -------------------------
auth_v1 = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api_v1 = tweepy.API(auth_v1)

# -------------------------
# 日本語ハッシュタグ生成
# -------------------------
def make_hashtags(title, max_tags=3):
    # 記号や空白を除去
    clean = re.sub(r"[^\w\u4e00-\u9fff]", "", title)
    # 長さ10文字以上なら切る
    if len(clean) > 20:
        clean = clean[:20]
    return " ".join([f"#{clean}"])

# -------------------------
# 投稿文生成（直接リンク対応）
# -------------------------
def compose_text(title, url):
    template = random.choice(TEMPLATES_B) if random.random() < STYLE_B_WEIGHT else random.choice(TEMPLATES_A)

    hashtags = make_hashtags(title)
    prefixes = ["", "🔔 ", "※", "✨ ", ""]
    
    # 直接リンクを使う
    text = f"{random.choice(prefixes)}{template.format(title=title, url=url)} {hashtags}"

    if len(text) > 270:
        text = text[:267] + "..."
    return text

# -------------------------
# fetch_article_list の部分で相対 URL は絶対 URL に変換済み
# -------------------------
# 例：
# if not link.startswith("http"):
#     link = base_url.rstrip("/") + "/" + link.lstrip("/"

# -------------------------
# 投稿処理（v2 + v1.1 API併用）
# -------------------------
def post_to_twitter(text, image_url=None):
    logging.info("Posting to Twitter: %s", text[:80].replace("\n"," ") + ("..." if len(text)>80 else ""))
    media_ids = None
    try:
        if image_url:
            r = requests.get(image_url, timeout=15)
            r.raise_for_status()
            tmp_path = "/tmp/temp_image.jpg"
            with open(tmp_path, "wb") as f:
                f.write(r.content)
            media = api_v1.media_upload(tmp_path)
            media_ids = [media.media_id]

        response = client_v2.create_tweet(text=text, media_ids=media_ids)
        logging.info("Posted successfully. Tweet ID: %s", response.data['id'])
    except Exception as e:
        logging.error("Failed to post: %s", e)

# -------------------------
# 記事スクレイピング
# -------------------------
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
            img = art.find("img")
            img_url = img["src"] if img else None
            candidates.append((title, link, img_url))
    return candidates

# -------------------------
# メイン処理
# -------------------------
def main():
    articles = fetch_article_list(TARGET_SITE)
    if not articles:
        logging.error("No articles found; aborting.")
        return

    # 最新記事優先 60% / 過去記事掘り起こし 40%
    if random.random() < 0.6:
        chosen = articles[0]
        logging.info("Choosing latest article")
    else:
        chosen = random.choice(articles)
        logging.info("Choosing random past article")

    title, url, img_url = chosen
    tweet = compose_text(title, url)

    if os.getenv("TWITTER_DRY_RUN") == "1":
        logging.info("DRY RUN: would post:\n%s", tweet)
    else:
        delay = random.randint(5, 90)
        logging.info("Sleeping %d seconds before posting (human-like delay)", delay)
        time.sleep(delay)
        post_to_twitter(tweet, image_url=img_url)

if __name__ == "__main__":
    main()
