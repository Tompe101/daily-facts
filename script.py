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

def push_to_facebook(title, post_url):
    """Auto-posts the new article to a Facebook Page using Graph API."""
    page_id = os.environ.get("FACEBOOK_PAGE_ID")
    access_token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")

    if not page_id or not access_token:
        print("Facebook credentials not fully set in GitHub Secrets. Skipping Facebook post.")
        return

    try:
        url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
        message = f"🚨 {title}\n\nRead the full report here: {post_url}\n\n#Trending #News"
        
        # Facebook Graph API automatically grabs the og:image from the link!
        payload = urllib.parse.urlencode({
            'message': message, 
            'link': post_url, 
            'access_token': access_token
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=payload)
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        print(f"✅ Successfully posted to Facebook! Post ID: {result.get('id')}")
    except Exception as e:
        print(f"❌ Facebook post failed: {e}")

def save_article(topic, content, image_url, language="English"):
    """Parses model response, writes clean Jekyll Markdown file, AND auto-generates a Web Story."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    category = "India"
    tags = f"news, trending, india, {language.lower()}"
    description = topic
    translated_title = topic

    lines = content.split('\n')
    clean_lines = []
    tldr_bullets = []
    in_tldr = False

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

        if "## TL;DR" in line:
            in_tldr = True
            continue
        if in_tldr and line.strip().startswith("*"):
            tldr_bullets.append(line.strip().lstrip("*").strip())
        elif in_tldr and line.startswith("## "):
            in_tldr = False

    content = '\n'.join(clean_lines).strip()

    safe_title_slug = re.sub(r'[^a-zA-Z0-9]', '-', topic).lower()
    safe_title_slug = re.sub(r'-+', '-', safe_title_slug).strip('-')
    
    # 🎯 SEO FIX 1: Guaranteed Alt Text for images
    safe_alt_text = re.sub(r'[^a-zA-Z0-9 ]', '', translated_title).strip()
    if not safe_alt_text:
        safe_alt_text = "News update from India Daily Facts"

    lang_suffix = f"-{language.lower()}" if language != "English" else ""
    filename = f"_posts/{date_str}-{safe_title_slug}{lang_suffix}.md"

    if os.path.exists(filename):
        return False

    image_markdown = f"\n\n![{safe_alt_text}]({image_url})\n\n"
    if "## " in content:
        content = re.sub(r'(## )', f'{image_markdown}\\1', content, count=1)
    else:
        content = image_markdown + content

    # 🎯 SEO FIX 2: Strict Title and Description lengths (Python Fallback)
    clean_title = translated_title.replace('"', '\\"')
    seo_title = clean_title if len(clean_title) <= 55 else clean_title[:52].strip() + "..."

    clean_desc = description.replace('"', '\\"')
    seo_desc = clean_desc if len(clean_desc) <= 150 else clean_desc[:147].strip() + "..."

    # 1. Write standard news post with SEO-optimized front matter
    with open(filename, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("layout: post\n")
        f.write(f'title: "{seo_title}"\n')
        f.write(f'description: "{seo_desc}"\n')
        f.write(f"categories: [{category}, {language}]\n")
        f.write(f"tags: [{tags}]\n")
        f.write("---\n\n")
        f.write(content)

    print(f"Successfully generated post: {filename}")
    published_post_url = f"https://pishorkar.tech/{category.lower()}/{language.lower()}/{datetime.now().strftime('%Y/%m/%d')}/{safe_title_slug}{lang_suffix}.html"

    # 2. Write Google Web Story
    if len(tldr_bullets) >= 3:
        story_filename = f"_posts/{date_str}-story-{safe_title_slug}{lang_suffix}.md"
        s1 = tldr_bullets[0].replace('"', '\\"')
        s2 = tldr_bullets[1].replace('"', '\\"')
        s3 = tldr_bullets[2].replace('"', '\\"')
        article_path = f"/{category.lower()}/{language.lower()}/{datetime.now().strftime('%Y/%m/%d')}/{safe_title_slug}{lang_suffix}.html"

        with open(story_filename, "w", encoding="utf-8") as sf:
            sf.write("---\n")
            sf.write("layout: webstory\n")
            sf.write(f'title: "{seo_title}"\n')
            sf.write(f'image: "{image_url}"\n')
            sf.write(f'slide1: "{s1}"\n')
            sf.write(f'slide2: "{s2}"\n')
            sf.write(f'slide3: "{s3}"\n')
            sf.write(f'article_url: "{article_path}"\n')
            sf.write(f"categories: [WebStories, {language}]\n")
            sf.write("---\n")
            
        print(f"Successfully generated Web Story: {story_filename}")

    ping_indexnow(published_post_url)
    
    # Push English articles directly to Facebook Page
    if language == "English":
        push_to_facebook(seo_title, published_post_url)

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
        print(f"Bing ping failed (Expected as Bing retired this): {e}")

target_engine = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

RSS_FEEDS = [
    "https://news.google.com/rss?gl=IN&hl=en-IN&ceid=IN:en",
    "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "https://feeds.feedburner.com/NDTV-LatestNews"
]

os.makedirs("_posts", exist_ok=True)

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

# 🎯 SEO FIX 3: Updated Prompt with Strict Rules for Viral Titles & Tags
prompt_template = """
You are an expert viral news copywriter for 'India Daily Facts' (pishorkar.tech).
Write a comprehensive, in-depth, and highly engaging news article about this trending topic: "{topic}".
The ENTIRE output must be written in strict, formal {language} for the main content, but the Title and Description should use smart click-inducing hooks.

CRITICAL EDITORIAL & SEO RULES:
1. STRICTLY FORMAL TONE (BODY): The main body text must remain factual and professional.
2. NO LANGUAGE MIXING: If the target language is Marathi, use 100% pure Marathi.
3. MAGNETIC TITLE: Act as an expert viral news copywriter. Write a highly catchy, curiosity-driven headline containing the exact trending keyword. It must sound like urgent breaking news but remain factual. STRICTLY UNDER 55 CHARACTERS.
4. SUSPENSEFUL DESCRIPTION: Write a click-worthy, suspenseful meta description that forces the user to click and read the full story. MUST contain the trending keyword. STRICTLY UNDER 150 CHARACTERS.
5. TAGS: Provide exactly 3 to 5 highly searched, long-tail trending keywords relevant to the topic.

Follow this EXACT structure for the output:

TITLE: <Write a highly catchy, curiosity-driven headline in {language}. MAXIMUM 55 CHARACTERS.>
CATEGORY: <Choose ONE from this exact English list (DO NOT TRANSLATE): Politics, Business, Technology, India, World, Sports, Science, Entertainment, Health>
TAGS: <Provide exactly 3 to 5 comma-separated high-volume SEO keywords in {language}>
DESCRIPTION: <Write a suspenseful, click-worthy meta description in {language}. MAXIMUM 150 CHARACTERS.>

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

def mark_topic_seen(topic):
    seen_topics[normalize_topic_key(topic)] = datetime.now().strftime("%Y-%m-%d")
    save_seen_topics(seen_topics)


# --- 1. RUN GEMINI ENGINE ---
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
            for lang in LANGUAGES:
                prompt = prompt_template.format(topic=topic, language=lang)
                try:
                    res = gemini_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                    )
                    if save_article(topic, res.text.strip(), image_url, language=lang):
                        topic_had_success = True
                    
                    # ✅ FIXED: 15 seconds rate-limit brake to prevent 429 Error
                    print(f"⏳ Waiting 15 seconds to avoid Gemini rate limits...")
                    time.sleep(15) 
                    
                except Exception as e:
                    print(f"❌ Gemini error for '{topic}' in {lang}: {e}")
            if topic_had_success:
                mark_topic_seen(topic)
            count += 1


# --- 2. RUN OFFICIAL OPENAI (GPT-4o) ENGINE ---
# Updated from deprecated GitHub Models to the Official OpenAI Python SDK
if target_engine in ["openai", "all"]:
    print("--- RUNNING OFFICIAL GPT-4o ENGINE ---")
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        print("Error: OPENAI_API_KEY is not set. Skipping GPT-4o execution.")
    else:
        # Base URL removed so it natively targets the official OpenAI endpoints
        openai_client = OpenAI(api_key=openai_key)
        count = 0
        for topic, item in feed_items:
            if count >= 3:
                break
            image_url = extract_image_from_rss(item) or get_fallback_topic_image(topic)

            topic_had_success = False
            for lang in LANGUAGES:
                prompt = prompt_template.format(topic=topic, language=lang)
                try:
                    res = openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7
                    )
                    if save_article(topic, res.choices[0].message.content.strip(), image_url, language=lang):
                        topic_had_success = True
                    
                    # ✅ Added a standard safety delay here too
                    print(f"⏳ Waiting 5 seconds for OpenAI safety...")
                    time.sleep(5)
                except Exception as e:
                    print(f"❌ OpenAI GPT-4o error for '{topic}' in {lang}: {e}")
            if topic_had_success:
                mark_topic_seen(topic)
            count += 1

ping_sitemaps()
