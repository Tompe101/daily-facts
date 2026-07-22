import os
import urllib.request
import xml.etree.ElementTree as ET
import re
import time
from datetime import datetime
from google import genai

# 1. Fetch the RSS feed
url = "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req).read()
root = ET.fromstring(response)

# 2. Get the TOP 2 articles from the feed
items = root.findall('.//item')[:2]

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
date_str = datetime.now().strftime("%Y-%m-%d")
os.makedirs("_posts", exist_ok=True)

# 3. Loop through each of the 2 articles
for item in items:
    topic = item.find('title').text
    
    # Generate the article
    prompt = f"Write a neutral, unbiased 300-word factual article on this trending news topic: {topic}. Output in Markdown format. Do not take sides."
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        # Create a safe file name
        safe_title = re.sub(r'[^a-zA-Z0-9]', '-', topic).lower()
        safe_title = re.sub(r'-+', '-', safe_title).strip('-')
        filename = f"_posts/{date_str}-{safe_title}.md"
        
        # Save the file
        with open(filename, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write("layout: post\n")
            f.write(f"title: \"{topic}\"\n")
            f.write("---\n\n")
            f.write(response.text)
            
    except Exception as e:
        print(f"Failed to generate {topic}: {e}")
        
    # Pause for 5 seconds to respect Gemini's free-tier rate limits
    time.sleep(5)
