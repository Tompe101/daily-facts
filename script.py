import os
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
import time
import json
from datetime import datetime
from google import genai
from openai import OpenAI

SEEN_TOPICS_FILE = "_data/seen_topics.json"


def load_seen_topics():
    """Loads the persistent log of already-processed topics (across all past runs/days)."""
    if not os.path.exists(SEEN_TOPICS_FILE):
        return {}
    try:
        with open(SEEN_TOPICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: could not read {SEEN_TOPICS_FILE} ({e}); starting fresh.")
        return {}


def save_seen_topics(seen):
    os.makedirs(os.path.dirname(SEEN_TOPICS_FILE), exist_ok=True)
    with open(SEEN_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


def normalize_topic_key(topic):
    """Collapses whitespace/case so near-identical recurring headlines match."""
    return re.sub(r'\s+', ' ', topic.strip().lower())


def sanitize_category(raw_category):
    """Keeps the model's CATEGORY: output inside the expected enum and URL-safe."""
    allowed = ["Politics", "Business", "Technology", "India", "World",
               "Sports", "Science", "Entertainment", "Health"]
    if not raw_category:
        return "India"
    cleaned = re.sub(r'[^a-zA-Z]', '', raw_category.strip())
    for a in allowed:
        if cleaned.lower() == a.lower():
            return a
    # Fallback: model drifted from the enum (extra words/punctuation) - default safely
    print(f"Warning: unexpected CATEGORY '{raw_category}' - defaulting to 'India'")
    return "India"


def extract_image_from_rss(item):
    """Extracts actual news story photo directly from RSS item XML tags."""
    try:
        enclosure = item.find('enclosure')
        if enclosure is not None and enclosure.attrib.get('url'):
            url = enclosure.attrib.get('url')
            if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']) or 'image' in enclosure.attrib.get('type', ''):
                return url

        namespaces = [
            'http://search.yahoo.com/mrss/',
            'http://video.search.yahoo.com/mrss'
        ]
        for ns in namespaces:
            media_content = item.find(f'{{{ns}}}content')
            if media_content is not None and media_content.attrib.get('url'):
                return media_content.attrib.get('url')
            media_thumb = item.find(f'{{{ns}}}thumbnail')
            if media_thumb is not None and media_thumb.attrib.get('url'):
                return media_thumb.attrib.get('url')

        desc = item.find('description')
        if desc is not None and desc.text:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc.text)
            if img_match:
                img_url = img_match.group(1)
                if img_url.startswith('http'):
                    return img_url
    except Exception as e:
        print(f"Error parsing RSS image: {e}")

    return None


def get_fallback_topic_image(title):
    """30+ Category topic-matcher for accurate fallback photos."""
    t = title.lower()
    if any(k in t for k in ["modi", "pm ", "pmo", "prime minister", "bjp", "shah", "cabinet", "govt"]):
        return "https://images.unsplash.com/photo-1541872703-74c5e44368f9?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["rahul", "gandhi", "congress", "parliament", "lok sabha", "rajya sabha", "election", "polls"]):
        return "https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["trump", "biden", "white house", "us president", "washington"]):
        return "https://images.unsplash.com/photo-1580128660010-fd027e1e5f7a?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["court", "supreme court", "high court", "judge", "justice", "bail", "verdict"]):
        return "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["police", "cbi", "ed", "crime", "arrest", "investigation", "fir", "scam"]):
        return "https://images.unsplash.com/photo-1582139329536-e7284fece509?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["sensex", "nifty", "stock", "market", "share", "trading"]):
        return "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["bank", "rbi", "rupee", "economy", "gdp", "tax", "finance"]):
        return "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["cricket", "match", "bcci", "ipl", "rohit", "virat", "stadium"]):
        return "https://images.unsplash.com/photo-1531415074968-036ba1b575da?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["movie", "film", "actor", "bollywood", "cinema", "ott"]):
        return "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=1200&q=80"
    return "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?auto=format&fit=crop&w=1200&q=80"


def ping_indexnow(post_url):
    """Notifies search engines instantly upon publishing."""
    indexnow_key = os.environ.get("INDEXNOW_KEY", "pishorkartechkey123")
    try:
        api_url = f"https://api.indexnow.org/indexnow?url={urllib.parse.quote(post_url)}&key={indexnow_key}"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        urllib.request.urlopen(req)
        print(f"IndexNow Ping Sent for: {post_url}")
    except Exception as e:
        print(f"IndexNow ping failed: {e}")


def push_to_social_media(title, post_url):
    """Sends the new article to an n8n webhook to auto-post on social platforms."""
    webhook_url = os.environ.get("N8N_WEBHOOK_URL")

    if not webhook_url:
        return

    data = json.dumps({
        "title": title,
        "url": post_url,
        "message": f"🚨 Breaking News: {title}\n\nRead the full story here: {post_url}"
    }).encode("utf-8")

    try:
        req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req)
        print(f"Social Media Webhook Sent for: {title}")
    except Exception as e:
        print(f"Webhook failed: {e}")


def save_article(topic, content, image_url, language="English"):
    """Parses model response and writes clean Jekyll Markdown file."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    category = "India"
    tags = f"news, trending, india, {language.lower()}"
    description = topic
    translated_title = topic

    lines = content.split('\n')
    clean_lines = []

    for line in lines:
        if line.startswith("TITLE:"):
            translated_title = line.replace("TITLE:", "").strip()
        elif line.startswith("CATEGORY:"):
            category = sanitize_category(line.replace("CATEGORY:", "").strip())
        elif line.startswith("TAGS:"):
            tags = line.replace("TAGS:", "").strip()
        elif line.startswith("DESCRIPTION:"):
            description = line.replace("DESCRIPTION:", "").strip()
        else:
            clean_lines.append(line)

    content = '\n'.join(clean_lines).strip()

    # Keep the URL slug in English for clean routing, but append the language
    safe_title_slug = re.sub(r'[^a-zA-Z0-9]', '-', topic).lower()
    safe_title_slug = re.sub(r'-+', '-', safe_title_slug).strip('-')
    safe_alt_text = re.sub(r'[^a-zA-Z0-9 ]', '', translated_title).strip()

    lang_suffix = f"-{language.lower()}" if language != "English" else ""
    filename = f"_posts/{date_str}-{safe_title_slug}{lang_suffix}.md"

    if os.path.exists(filename):
        return False

    image_markdown = f"\n\n![{safe_alt_text}]({image_url})\n\n"
    if "## " in content:
        # Insert image right before the first major heading (usually TL;DR or In-Depth)
        content = re.sub(r'(## )', f'{image_markdown}\\1', content, count=1)
    else:
        content = image_markdown + content

    clean_title = translated_title.replace('"', '\\"')
    clean_desc = description.replace('"', '\\"')

    with open(filename, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("layout: post\n")
        f.write(f'title: "{clean_title}"\n')
        f.write(f'description: "{clean_desc}"\n')
        f.write(f"categories: [{category}, {language}]\n")
        f.write(f"tags: [{tags}]\n")
        f.write("---\n\n")
        f.write(content)

    print(f"Successfully generated: {filename}")
    published_post_url = f"https://pishorkar.tech/{category.lower()}/{language.lower()}/{datetime.now().strftime('%Y/%m/%d')}/{safe_title_slug}{lang_suffix}.html"

    ping_indexnow(published_post_url)
    push_to_social_media(clean_title, published_post_url)

    return True


def ping_sitemaps():
    """Force Google and Bing to crawl the new articles immediately."""
    sitemap_url = urllib.parse.quote("https://pishorkar.tech/sitemap.xml")
    print("\n--- PINGING SITEMAPS ---")
    try:
        urllib.request.urlopen(f"https://www.google.com/ping?sitemap={sitemap_url}")
        print("Successfully pinged Google Sitemap")
    except Exception:
        pass

    try:
        urllib.request.urlopen(f"https://www.bing.com/ping?sitemap={sitemap_url}")
        print("Successfully pinged Bing Sitemap")
    except Exception as e:
        print(f"Bing ping failed: {e}")


target_engine = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

RSS_FEEDS = [
    "https://trends.google.co.in/trends/trendingsearches/daily/rss?geo=IN",
    "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "https://feeds.feedburner.com/NDTV-LatestNews"
]

os.makedirs("_posts", exist_ok=True)

# Cross-run duplicate protection: a topic that already produced a post on any
# previous day (not just today) will be skipped, since RSS "trending" feeds
# frequently resurface the same headline over several days.
seen_topics = load_seen_topics()
processed_topics = set()
feed_items = []

for feed_url in RSS_FEEDS:
    try:
        req = urllib.request.Request(feed_url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req).read()
        root = ET.fromstring(response)
        items = root.findall('.//item')
        for item in items:
            title_node = item.find('title')
            if title_node is None or not title_node.text:
                continue
            topic = title_node.text.strip()
            topic_key = normalize_topic_key(topic)
            if len(topic) < 15:
                continue
            if topic in processed_topics:
                continue
            if topic_key in seen_topics:
                print(f"Skipping already-published topic: {topic}")
                continue
            feed_items.append((topic, item))
            processed_topics.add(topic)
    except Exception as feed_err:
        print(f"Failed to fetch RSS feed from {feed_url}: {feed_err}")

prompt_template = """
You are an authoritative senior journalist for 'India Daily Facts' (pishorkar.tech).
Write a comprehensive, in-depth, and engaging news article about this trending topic: "{topic}".
The ENTIRE output must be written in strict, formal {language}.

CRITICAL EDITORIAL RULES:
1. STRICTLY FORMAL TONE: Do NOT use any slang, clickbait, informal phrases, or derogatory words (e.g., absolutely no words like "झंडू", "बकवास", or colloquial street slang).
2. NO LANGUAGE MIXING: If the target language is Marathi, use 100% pure, professional Marathi. Do NOT mix Hindi slang into Marathi headlines or articles.
3. Maintain strict journalistic integrity, neutrality, and respect in your wording.

Follow this EXACT structure for the output:

TITLE: <Write a formal, highly professional news headline in {language}>
CATEGORY: <Choose ONE: Politics, Business, Technology, India, World, Sports, Science, Entertainment, Health>
TAGS: <Provide 4-5 comma-separated SEO keywords in {language}>
DESCRIPTION: <Write a keyword-rich meta description under 150 characters in {language}>

## TL;DR Summary
* <Bullet point 1 summarizing headline formally in {language}>
* <Bullet point 2 summarizing key context formally in {language}>
* <Bullet point 3 summarizing current status formally in {language}>

## In-Depth Report
<Write 4-5 paragraphs explaining the current event comprehensively in {language}. Use subheadings (###), clear paragraphs, and a formal, neutral journalistic tone.>

## Background & Context
<Write 2-3 paragraphs explaining the history or previous events that led up to this moment in {language}.>

## Why It Matters (Impact Analysis)
<Write 2-3 paragraphs explaining how this impacts the public, industry, or the economy in {language}.>

## Key Takeaways
* <Key insight or future implication 1 in {language}>
* <Key insight or future implication 2 in {language}>

Do NOT include Jekyll front matter (---) or a title markdown heading (#). Start directly with TITLE:
"""

LANGUAGES = ["English", "Marathi", "Hindi"]

# Topics that successfully generated at least one article this run get marked
# seen immediately, so a mid-run crash doesn't lose the dedup record.
def mark_topic_seen(topic):
    seen_topics[normalize_topic_key(topic)] = datetime.now().strftime("%Y-%m-%d")
    save_seen_topics(seen_topics)


# RUN GEMINI ENGINE
if target_engine in ["gemini", "all"]:
    print("--- RUNNING GEMINI ENGINE ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        print("Error: GEMINI_API_KEY is not set. Skipping Gemini execution.")
    else:
        gemini_client = genai.Client(api_key=gemini_key)
        count = 0
        for topic, item in feed_items:
            if count >= 3:
                break
            image_url = extract_image_from_rss(item) or get_fallback_topic_image(topic)

            topic_had_success = False
            # Loop through all 3 languages for the same topic
            for lang in LANGUAGES:
                prompt = prompt_template.format(topic=topic, language=lang)
                try:
                    res = gemini_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                    )
                    if save_article(topic, res.text.strip(), image_url, language=lang):
                        topic_had_success = True
                    time.sleep(4)  # Pause to prevent API rate limits
                except Exception as e:
                    print(f"Gemini error for '{topic}' in {lang}: {e}")
            if topic_had_success:
                mark_topic_seen(topic)
            count += 1

# RUN GITHUB GPT-4o ENGINE
if target_engine in ["github", "all"]:
    print("--- RUNNING GITHUB GPT-4o ENGINE ---")
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("Error: GITHUB_TOKEN is not set. Skipping GPT-4o execution.")
    else:
        # NOTE: models.inference.ai.azure.com was deprecated Oct 17, 2025.
        # New endpoint is models.github.ai/inference, and model names now
        # require the provider prefix (e.g. "openai/gpt-4o").
        github_client = OpenAI(
            base_url="https://models.github.ai/inference",
            api_key=github_token,
        )
        count = 0
        for topic, item in feed_items:
            if count >= 3:
                break
            image_url = extract_image_from_rss(item) or get_fallback_topic_image(topic)

            topic_had_success = False
            # Loop through all 3 languages for the same topic
            for lang in LANGUAGES:
                prompt = prompt_template.format(topic=topic, language=lang)
                try:
                    res = github_client.chat.completions.create(
                        model="openai/gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7
                    )
                    if save_article(topic, res.choices[0].message.content.strip(), image_url, language=lang):
                        topic_had_success = True
                    time.sleep(4)  # Pause to prevent API rate limits
                except Exception as e:
                    print(f"GitHub GPT-4o error for '{topic}' in {lang}: {e}")
            if topic_had_success:
                mark_topic_seen(topic)
            count += 1

# Finally, ping sitemaps after all content is generated
ping_sitemaps()
