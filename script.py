import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
import time
from datetime import datetime
from google import genai

def extract_image_from_rss(item):
    """Extracts actual news story photo directly from RSS item XML tags."""
    try:
        # Check <enclosure url="..."> tag
        enclosure = item.find('enclosure')
        if enclosure is not None and enclosure.attrib.get('url'):
            url = enclosure.attrib.get('url')
            if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']) or 'image' in enclosure.attrib.get('type', ''):
                return url

        # Check Yahoo MRSS tags (<media:content>, <media:thumbnail>)
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

        # Check HTML inside <description>
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

    # Politics & Government Leaders
    if any(k in t for k in ["modi", "pm ", "pmo", "prime minister", "bjp", "shah", "cabinet", "govt"]):
        return "https://images.unsplash.com/photo-1541872703-74c5e44368f9?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["rahul", "gandhi", "congress", "parliament", "lok sabha", "rajya sabha", "election", "polls", "vote"]):
        return "https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["trump", "biden", "white house", "us president", "washington", "senate", "america"]):
        return "https://images.unsplash.com/photo-1580128660010-fd027e1e5f7a?auto=format&fit=crop&w=1200&q=80"

    # Judiciary, Police & Crime
    if any(k in t for k in ["court", "supreme court", "high court", "judge", "justice", "bail", "verdict", "law", "legal"]):
        return "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["police", "cbi", "ed", "crime", "arrest", "investigation", "fir", "cop", "murder", "scam"]):
        return "https://images.unsplash.com/photo-1582139329536-e7284fece509?auto=format&fit=crop&w=1200&q=80"

    # Business, Finance & Stock Markets
    if any(k in t for k in ["sensex", "nifty", "stock", "market", "share", "trading", "investor"]):
        return "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["bank", "rbi", "rupee", "dollar", "economy", "gdp", "inflation", "tax", "finance", "gold"]):
        return "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=1200&q=80"

    # Aviation, Railways & Military
    if any(k in t for k in ["flight", "airline", "airport", "plane", "aviation", "indigo", "air india"]):
        return "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["railway", "train", "express", "vande bharat", "station", "locomotive"]):
        return "https://images.unsplash.com/photo-1474487548417-781cb71495f3?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["navy", "army", "air force", "missile", "war", "defense", "military", "border", "soldier"]):
        return "https://images.unsplash.com/photo-1508614589041-895b88991e3e?auto=format&fit=crop&w=1200&q=80"

    # Science, Tech & Space
    if any(k in t for k in ["isro", "space", "rocket", "satellite", "nasa", "moon", "chandrayaan"]):
        return "https://images.unsplash.com/photo-1517976487192-5754f72128f2?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["ai", "google", "apple", "microsoft", "tech", "cyber", "software", "smartphone", "mobile"]):
        return "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80"

    # Weather & Disasters
    if any(k in t for k in ["rain", "monsoon", "flood", "weather", "cyclone", "heatwave", "storm", "earthquake"]):
        return "https://images.unsplash.com/photo-1515694346937-94d85e41e6f0?auto=format&fit=crop&w=1200&q=80"

    # Education & Health
    if any(k in t for k in ["student", "exam", "neet", "ugc", "school", "college", "university", "cbse", "degree"]):
        return "https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["hospital", "doctor", "health", "virus", "vaccine", "disease", "medical", "patient"]):
        return "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=1200&q=80"

    # Sports
    if any(k in t for k in ["cricket", "match", "bcci", "ipl", "rohit", "virat", "stadium", "score", "wickets"]):
        return "https://images.unsplash.com/photo-1531415074968-036ba1b575da?auto=format&fit=crop&w=1200&q=80"
    if any(k in t for k in ["football", "soccer", "olympic", "tennis", "race", "hockey", "athlete"]):
        return "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1200&q=80"

    # Cinema & Entertainment
    if any(k in t for k in ["movie", "film", "actor", "actress", "bollywood", "cinema", "ott", "box office"]):
        return "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=1200&q=80"

    # Generic Breaking News Photo
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

# RSS feeds from major trusted Indian news publishers
RSS_FEEDS = [
    "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "https://feeds.feedburner.com/NDTV-LatestNews",
    "https://www.hindustantimes.com/feeds/rss/top-news/rssfeed.xml"
]

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
date_str = datetime.now().strftime("%Y-%m-%d")
os.makedirs("_posts", exist_ok=True)

processed_topics = set()
posts_generated = 0
MAX_POSTS_PER_RUN = 2

for feed_url in RSS_FEEDS:
    if posts_generated >= MAX_POSTS_PER_RUN:
        break
        
    try:
        req = urllib.request.Request(feed_url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req).read()
        root = ET.fromstring(response)
        items = root.findall('.//item')
        
        for item in items:
            if posts_generated >= MAX_POSTS_PER_RUN:
                break
                
            title_node = item.find('title')
            if title_node is None or not title_node.text:
                continue
                
            topic = title_node.text.strip()
            
            # Avoid duplicates or short headlines
            if topic in processed_topics or len(topic) < 15:
                continue
                
            processed_topics.add(topic)
            
            # Extract real news photo from RSS feed; fallback to 30+ category matcher if missing
            image_url = extract_image_from_rss(item)
            if not image_url:
                image_url = get_fallback_topic_image(topic)

            prompt = f"""
You are an expert journalist writing for 'India Daily Facts' (pishorkar.tech).
Write a high-quality, comprehensive, and engaging news post about this topic: "{topic}".

Follow this exact structure for the output:

CATEGORY: <Choose ONE from: Politics, Business, Technology, India, World, Sports, Science, Entertainment, Health>

## Quick Summary
* <Bullet point 1 summarizing headline>
* <Bullet point 2 summarizing key context>
* <Bullet point 3 summarizing current status>

## Detailed Analysis
Write an in-depth, well-structured, factual news report (500 to 600 words minimum). 
Use subheadings (###), short clear paragraphs, background context, and a neutral journalistic tone.

## Key Takeaways
* <Key insight or future implication 1>
* <Key insight or future implication 2>

Do NOT include Jekyll front matter (---) or title heading (#). Start directly with CATEGORY:
"""

            try:
                res = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                )
                content = res.text.strip()
                
                category = "India"
                if content.startswith("CATEGORY:"):
                    first_line, content = content.split("\n", 1)
                    category = first_line.replace("CATEGORY:", "").strip()
                    content = content.strip()
                
                # Sanitize headline for clean Markdown alt text and safe filenames
                safe_title_slug = re.sub(r'[^a-zA-Z0-9]', '-', topic).lower()
                safe_title_slug = re.sub(r'-+', '-', safe_title_slug).strip('-')
                safe_alt_text = re.sub(r'[^a-zA-Z0-9 ]', '', topic).strip()
                
                filename = f"_posts/{date_str}-{safe_title_slug}.md"
                
                if os.path.exists(filename):
                    continue

                # Inject image tag cleanly right after Quick Summary
                image_markdown = f"\n\n![{safe_alt_text}]({image_url})\n\n"
                if "## Detailed Analysis" in content:
                    content = content.replace("## Detailed Analysis", f"{image_markdown}## Detailed Analysis")
                else:
                    content = image_markdown + content

                clean_title = topic.replace('"', '\\"')
                
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("---\n")
                    f.write("layout: post\n")
                    f.write(f'title: "{clean_title}"\n')
                    f.write(f"categories: [{category}]\n")
                    f.write("---\n\n")
                    f.write(content)
                    
                print(f"Successfully generated: {filename}")
                posts_generated += 1
                
                # Ping IndexNow for instant search indexing
                published_post_url = f"https://pishorkar.tech/{category.lower()}/{datetime.now().strftime('%Y/%m/%d')}/{safe_title_slug}.html"
                ping_indexnow(published_post_url)
                
                time.sleep(5)

            except Exception as e:
                print(f"Failed to generate post for '{topic}': {e}")
                
    except Exception as feed_err:
        print(f"Failed to fetch RSS feed from {feed_url}: {feed_err}")
