import os
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
import time
from datetime import datetime
from google import genai
from openai import OpenAI

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
    """30+ Category topic-matcher for accurate fallback photos when RSS feed lacks an embedded image."""
    t = title.lower()

    if any(k in t for k in ["modi", "pm ", "pmo", "prime minister", "bjp", "shah", "cabinet", "govt"]):
        return "https://images.unsplash.com/photo-1541872703-74c5e44368f9?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["rahul", "gandhi", "congress", "parliament", "lok sabha", "rajya sabha", "election", "polls", "vote"]):
        return "https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["trump", "biden", "white house", "us president", "washington", "senate", "america"]):
        return "https://images.unsplash.com/photo-1580128660010-fd027e1e5f7a?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["court", "supreme court", "high court", "judge", "justice", "bail", "verdict", "law", "legal"]):
        return "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["police", "cbi", "ed", "crime", "arrest", "investigation", "fir", "cop", "murder", "scam"]):
        return "https://images.unsplash.com/photo-1582139329536-e7284fece509?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["sensex", "nifty", "stock", "market", "share", "trading", "investor"]):
        return "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["bank", "rbi", "rupee", "dollar", "economy", "gdp", "inflation", "tax", "finance", "gold"]):
        return "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["flight", "airline", "airport", "plane", "aviation", "indigo", "air india"]):
        return "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["railway", "train", "express", "vande bharat", "station", "locomotive"]):
        return "https://images.unsplash.com/photo-1474487548417-781cb71495f3?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["navy", "army", "air force", "missile", "war", "defense", "military", "border", "soldier"]):
        return "https://images.unsplash.com/photo-1508614589041-895b88991e3e?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["isro", "space", "rocket", "satellite", "nasa", "moon", "chandrayaan"]):
        return "https://images.unsplash.com/photo-1517976487192-5754f72128f2?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["ai", "google", "apple", "microsoft", "tech", "cyber", "software", "smartphone", "mobile"]):
        return "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["rain", "monsoon", "flood", "weather", "cyclone", "heatwave", "storm", "earthquake"]):
        return "https://images.unsplash.com/photo-1515694346937-94d85e41e6f0?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["student", "exam", "neet", "ugc", "school", "college", "university", "cbse", "degree"]):
        return "https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["hospital", "doctor", "health", "virus", "vaccine", "disease", "medical", "patient"]):
        return "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["cricket", "match", "bcci", "ipl", "rohit", "virat", "stadium", "score", "wickets"]):
        return "https://images.unsplash.com/photo-1531415074968-036ba1b575da?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["football", "soccer", "olympic", "tennis", "race", "hockey", "athlete"]):
        return "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["movie", "film", "actor", "actress", "bollywood", "cinema", "ott", "box office"]):
        return "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=1200&q=80"

    return "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?auto=format&fit=crop&w=1200&q=80"

def ping_indexnow(post_url):
    """Notifies search engines instantly upon publishing."""
    try:
        api_url = f"https://api.indexnow.org/indexnow?url={urllib.parse.quote(post_url)}&key=pishorkartechkey123"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        urllib.request.urlopen(req)
        print(f"IndexNow Ping Sent for: {post_url}")
    except Exception as e:
        print(f"IndexNow ping failed: {e}")

def save_article(topic, content, image_url):
    """Parses model response and writes clean Jekyll Markdown file."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    category = "India"
    tags = "news, trending, india"
    
    lines = content.split('\n')
    clean_lines = []
    
    for line in lines:
        if line.startswith("CATEGORY:"):
            category = line.replace("CATEGORY:", "").strip()
        elif line.startswith("TAGS:"):
            tags = line.replace("TAGS:", "").strip()
        else:
            clean_lines.append(line)
    
    content = '\n'.join(clean_lines).strip()
    
    safe_title_slug = re.sub(r'[^a-zA-Z0-9]', '-', topic).lower()
    safe_title_slug = re.sub(r'-+', '-', safe_title_slug).strip('-')
    safe_alt_text = re.sub(r'[^a-zA-Z0-9 ]', '', topic).strip()
    
    filename = f"_posts/{date_str}-{safe_title_slug}.md"
    if os.path.exists(filename):
        return False

    image_markdown = f"\n\n![{safe_alt_text}]({image_url})\n\n"
    if "## In-Depth Report" in content:
        content = content.replace("## In-Depth Report", f"{image_markdown}## In-Depth Report")
    else:
        content = image_markdown + content

    clean_title = topic.replace('"', '\\"')
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("layout: post\n")
        f.write(f'title: "{clean_title}"\n')
        f.write(f"categories: [{category}]\n")
        f.write(f"tags: [{tags}]\n")
        f.write("---\n\n")
        f.write(content)
        
    print(f"Successfully generated: {filename}")
    published_post_url = f"https://pishorkar.tech/{category.lower()}/{datetime.now().strftime('%Y/%m/%d')}/{safe_title_slug}.html"
    ping_indexnow(published_post_url)
    return True

# Read engine target from command line: 'gemini', 'github', or default 'all'
target_engine = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

RSS_FEEDS = [
    "https://trends.google.co.in/trends/trendingsearches/daily/rss?geo=IN",
    "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "https://feeds.feedburner.com/NDTV-LatestNews",
    "https://www.hindustantimes.com/feeds/rss/top-news/rssfeed.xml"
]

os.makedirs("_posts", exist_ok=True)
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
            if len(topic) >= 15 and topic not in processed_topics:
                feed_items.append((topic, item))
                processed_topics.add(topic)
    except Exception as feed_err:
        print(f"Failed to fetch RSS feed from {feed_url}: {feed_err}")

prompt_template = """
You are an authoritative senior journalist for 'India Daily Facts' (pishorkar.tech).
Write a comprehensive, in-depth, and engaging news article about this trending topic: "{topic}".
The article MUST be comprehensive, aiming for 800 to 1000 words.

Follow this EXACT structure for the output:

CATEGORY: <Choose ONE: Politics, Business, Technology, India, World, Sports, Science, Entertainment, Health>
TAGS: <Provide 4-5 comma-separated SEO keywords based on the topic>

## TL;DR Summary
* <Bullet point 1 summarizing headline>
* <Bullet point 2 summarizing key context>
* <Bullet point 3 summarizing current status>

## In-Depth Report
<Write 4-5 paragraphs explaining the current event comprehensively. Use subheadings (###), clear paragraphs, and a neutral journalistic tone.>

## Background & Context
<Write 2-3 paragraphs explaining the history or previous events that led up to this moment.>

## Why It Matters (Impact Analysis)
<Write 2-3 paragraphs explaining how this impacts the public, industry, or the economy.>

## Key Takeaways
* <Key insight or future implication 1>
* <Key insight or future implication 2>

Do NOT include Jekyll front matter (---) or title heading (#). Start directly with CATEGORY:
"""

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
            prompt = prompt_template.format(topic=topic)
            try:
                res = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                )
                if save_article(topic, res.text.strip(), image_url):
                    count += 1
                    time.sleep(3)
            except Exception as e:
                print(f"Gemini error for '{topic}': {e}")

# RUN GITHUB GPT-4o ENGINE
if target_engine in ["github", "all"]:
    print("--- RUNNING GITHUB GPT-4o ENGINE ---")
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("Error: GITHUB_TOKEN is not set. Skipping GPT-4o execution.")
    else:
        github_client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=github_token,
        )
        count = 0
        for topic, item in feed_items:
            if count >= 3:
                break
            image_url = extract_image_from_rss(item) or get_fallback_topic_image(topic)
            prompt = prompt_template.format(topic=topic)
            try:
                res = github_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                if save_article(topic, res.choices[0].message.content.strip(), image_url):
                    count += 1
                    time.sleep(3)
            except Exception as e:
                print(f"GitHub GPT-4o error for '{topic}': {e}")
