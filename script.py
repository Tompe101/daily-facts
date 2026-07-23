import os
import urllib.request
import xml.etree.ElementTree as ET
import re
import time
from datetime import datetime
from google import genai

# 1. Fetch the RSS feed from Times of India
url = "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req).read()
root = ET.fromstring(response)

# 2. Get top 2 articles per run (runs twice daily = 4 articles daily)
items = root.findall('.//item')[:2]

# Initialize Gemini Client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
date_str = datetime.now().strftime("%Y-%m-%d")
os.makedirs("_posts", exist_ok=True)

for item in items:
    topic = item.find('title').text.strip()
    
    # --- EXTRACT REAL NEWS IMAGE FROM RSS FEED ---
    image_url = None
    
    # Check 1: <enclosure> tag in RSS
    enclosure = item.find('enclosure')
    if enclosure is not None and enclosure.attrib.get('url'):
        image_url = enclosure.attrib.get('url')
        
    # Check 2: <img> tag embedded inside <description>
    if not image_url:
        desc_node = item.find('description')
        if desc_node is not None and desc_node.text:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc_node.text)
            if img_match:
                image_url = img_match.group(1)
                
    # Check 3: Clean, neutral editorial image fallback (no random Flickr photos!)
    if not image_url:
        image_url = "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?q=80&w=1200&auto=format&fit=crop"

    # Prompt Gemini to auto-categorize and structure the full length article
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
        
        # Parse the Category from the first line
        category = "General"
        if content.startswith("CATEGORY:"):
            first_line, content = content.split("\n", 1)
            category = first_line.replace("CATEGORY:", "").strip()
            content = content.strip()
        
        # Create a safe file slug (YEAR-MONTH-DAY-title.md)
        safe_title = re.sub(r'[^a-zA-Z0-9]', '-', topic).lower()
        safe_title = re.sub(r'-+', '-', safe_title).strip('-')
        filename = f"_posts/{date_str}-{safe_title}.md"
        
        # Escape quotes in title for YAML front matter
        clean_title = topic.replace('"', '\\"')
        
        # Save the structured post with Front Matter
        with open(filename, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write("layout: post\n")
            f.write(f'title: "{clean_title}"\n')
            f.write(f"categories: [{category}]\n")
            f.write("---\n\n")
            f.write(content)
            
        print(f"Successfully generated: {filename} under category [{category}]")
        
    except Exception as e:
        print(f"Failed to generate post for '{topic}': {e}")
        
    # Respect API rate limits between requests
    time.sleep(5)
