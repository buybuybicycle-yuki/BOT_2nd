import os
import random
import time
import logging
import requests
from bs4 import BeautifulSoup
import tweepy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

TARGET_SITE = "https://active-gyoseisyosi.com/"

# ====== 記事一覧を取得 ======
def fetch_articles():
    try:
        r = requests.get(TARGET_SITE, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        articles = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = (a.get_text() or "").strip()
            if len(text) > 10 and href.startswith("http"):
                articles.append((text, href))
        return list(dict.fromkeys(articles))
    except Exception as e:
        logging.error(f"Fetch error: {e}")
        return []

# ====== 記事本文とアイキャッチ画像を抽出 ======
def extract_article_data(url):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # --- 要約部分を抽出 ---
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text()) > 40])
        text = text.replace("\n", " ")

        summary = ""
        if len(text) > 60:
            snippet = text[:200]
            summary = snippet.split("。")[0] + "。" if "。" in snippet else snippet[:100]

        # --- OGP画像または本文中の画像を取得 ---
        og_image = None
        og_tag = soup.find("meta", property="og:image")
        if og_tag and og_tag.get("content"):
            og_image = og_tag["content"]
        else:
            img_tag = soup.find("img")
            if img_tag and img_tag.get("src"):
                og_image = img_tag["src"]

        # 相対パスを絶対URLに変換
        if og_image and og_image.startswith("/"):
            base = "/".join(url.split("/")[:3])
            og_image = base + og_image

        return summary, og_image
    except Exception as e:
        logging.warning(f"Extract failed: {e}")
        return "", None

# ====== 投稿テキスト作成 ======
def compose_text(title, url, summary=""):
    intros = [
        "📢 新しい記事を公開しました！",
        "📝 最新の記事をご紹介します。",
        "🚗 行政書士の視点から詳しく解説しました。",
        "💡 実務に役立つ情報をまとめています。",
    ]
    outros = [
        "ぜひチェックしてみてください👇",
        "詳しくは記事本文でご覧ください。",
        "気になる方はリンクからどうぞ！",
    ]
    hashtags = ["#行政書士", "#自動車登録", "#車手続き", "#横浜", "#バイク登録", "#許認可"]

    if summary:
        body = f"{summary}\n{random.choice(outros)}"
    else:
        body = random.choice(outros)

    text = f"{random.choice(intros)}\n{title}\n{url}\n{body}\n{' '.join(random.sample(hashtags, 2))}"

    if len(text) > 270:
        text = text[:267] + "..."
    return text

# ====== 画像を一時保存 ======
def download_temp_image(image_url):
    try:
        r = requests.get(image_url, timeout=10)
        if r.status_code == 200:
            temp_path = "temp_image.jpg"
            with open(temp_path, "wb") as f:
                f.write(r.content)
            return temp_path
    except Exception as e:
        logging.warning(f"Image download failed: {e}")
    return None

# ====== Twitter投稿 ======
def post_to_twitter(text, image_path=None):
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )

    if image_path:
        auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth)
        media = api.media_upload(filename=image_path)
        client.create_tweet(text=text, media_ids=[media.media_id])
        logging.info(f"✅ Posted with image: {image_path}")
    else:
        client.create_tweet(text=text)
        logging.info("✅ Posted text-only tweet")

# ====== メイン処理 ======
def main():
    articles = fetch_articles()
    if not articles:
        logging.error("No articles found.")
        return

    chosen = random.choice(articles)
    title, url = chosen
    summary, og_image_url = extract_article_data(url)

    text = compose_text(title, url, summary)

    image_path = None
    if og_image_url:
        image_path = download_temp_image(og_image_url)

    delay = random.randint(10, 90)
    logging.info(f"Sleeping {delay}s before posting...")
    time.sleep(delay)

    post_to_twitter(text, image_path)

    # 後処理：一時画像削除
    if image_path and os.path.exists(image_path):
        os.remove(image_path)

if __name__ == "__main__":
    main()
