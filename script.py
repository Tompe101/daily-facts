import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
import time
from datetime import datetime
from google import genai

def get_topic_image(title):
    t = title.lower()
    if "rahul" in t or "gandhi" in t:
        return "https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?auto=format&fit=crop&w=1200&q=80"
    elif "modi" in t or "pmo" in t or "prime minister" in t:
        return "https://images.unsplash.com/photo-1541872703-74c5e44368f9?auto=format&fit=crop&w=1200&q=80"
    elif any(k in t for k in ["court", "supreme court", "judge", "justice", "law", "bail"]):
        return "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=1200&q=80"
    elif any(k in t for k in ["student", "exam", "neet", "ugc", "school", "college", "protest"]):
        return "https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1200&q=80"
    elif any(k in t for k in ["parliament", "mps", "lok sabha", "rajya sabha", "election", "bjp", "congress"]):
        return "https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?auto=format&fit=crop&w=1200&q=80"
    elif any(k in t for k in ["cricket", "match", "bcci", "ipl", "rohit", "virat", "stadium"]):
        return "https://images.unsplash.com/photo-1531415074968-036ba1b575da?auto=format&fit=crop&w=1200&q=80"
    elif any(k in t for k in ["isro", "space", "rocket", "satellite", "nasa", "moon"]):
        return "https://images.unsplash.com/photo-1517976487192-5754f72128f2?auto=format&fit=crop&w=1200&q=80"
    elif any(k in t for k in ["sensex", "nifty", "stock", "market", "rupee", "bank", "rbi", "economy"]):
        return "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80"
    elif any(k in t for k in ["police", "cbi", "ed", "crime", "arrest", "investigation"]):
        return "https://images.unsplash.com/photo-1582139329536-e7284fece509?auto=format&fit=crop&w=1200&q=80"
    elif any(k in t for k in ["rain", "monsoon", "flood", "weather", "cyclone"]):
        return "https://images.unsplash.com/photo-1515694346937-94d85e41e6f0?auto=format&fit=crop&w=1200&q=80"
    elif any(k in t for k in ["tech", "ai", "google", "apple", "mobile", "cyber"]):
        return "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80"
    return "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?auto=format&fit=crop&w=1200&q=80"

def ping_indexnow(post_url):
    """Pings IndexNow API so search engines index the new page within minutes."""
    try:
        api_url = f"https://api.indexnow.org/indexnow?url={urllib.parse.quote(post_url)}&key=pishorkartechkey123"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        urllib.request.urlopen(req)
        print(f"IndexNow Ping Sent for: {post_url}")
    except Exception as e:
        print(f"IndexNow ping failed: {e}")

# Fetch RSS Feed
url = "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req).read()
root = ET.fromstring(response)

items = root.findall('.//item')[:2]
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
date_str = datetime.now().strftime("%Y-%m-%d")
os.makedirs("_posts", exist_ok=True)

for item in items:
    topic = item.find('title').text.strip()
    image_url = get_topic_image(topic)

    prompt = f"""
You are an expert journalist writing for 'India Daily Facts' (pishorkar.tech).
Write a high-quality, comprehensive, and engaging blog post about this trending news topic: "{topic}".

Follow this exact structure for the output:

1. The very first line MUST be: "CATEGORY: <CategoryName>" 
   (Choose ONE category from: Politics, Business, Technology, India, World, Sports, Science).

2. Create a section header: "## Quick Summary" 
   Write 3 clear bullet points summarizing the main headline for quick reading.

3. Embed the featured image using this exact Markdown tag:
   ![{topic}]({image_url})

4. Create a section header: "## Detailed Analysis"
   Write an in-depth, well-structured, factual news report (500 to 600 words minimum). 
   Use subheadings (###), short clear paragraphs, background context, and neutral tone.

5. Create a section header: "## Key Takeaways"
   List 2-3 key insights or implications of this event moving forward.

Note: Do not include Jekyll front matter (---) in your text output; start directly with "CATEGORY: ...".
"""

    try:
        res = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        content = res.text.strip()
        
        category = "General"
        if content.startswith("CATEGORY:"):
            first_line, content = content.split("\n", 1)
            category = first_line.replace("CATEGORY:", "").strip()
            content = content.strip()
        
        safe_title = re.sub(r'[^a-zA-Z0-9]', '-', topic).lower()
        safe_title = re.sub(r'-+', '-', safe_title).strip('-')
        filename = f"_posts/{date_str}-{safe_title}.md"
        clean_title = topic.replace('"', '\\"')
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write("layout: post\n")
            f.write(f'title: "{clean_title}"\n')
            f.write(f"categories: [{category}]\n")
            f.write("---\n\n")
            f.write(content)
            
        print(f"Successfully generated: {filename}")
        
        # Ping IndexNow with the new post link
        published_post_url = f"https://pishorkar.tech/{category.lower()}/{datetime.now().strftime('%Y/%m/%d')}/{safe_title}.html"
        ping_indexnow(published_post_url)

    except Exception as e:
        print(f"Failed to generate post for '{topic}': {e}")
        
    time.sleep(5)
