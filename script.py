import os
import urllib.request
import xml.etree.ElementTree as ET
import re
from datetime import datetime
from google import genai

# 1. Fetch the top trending news from Times of India (Bot-friendly)
url = "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req).read()
root = ET.fromstring(response)
topic = root.find('.//item/title').text

# 2. Ask Gemini AI to write a factual, unbiased article
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
prompt = f"Write a neutral, unbiased 300-word factual article on this trending news topic: {topic}. Output in Markdown format. Do not take sides."

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt,
)

# 3. Create the Jekyll-friendly file name (e.g., 2026-07-22-topic-name.md)
date_str = datetime.now().strftime("%Y-%m-%d")
# Make the topic safe for a file name by replacing spaces with hyphens
safe_title = re.sub(r'[^a-zA-Z0-9]', '-', topic).lower()
safe_title = re.sub(r'-+', '-', safe_title).strip('-')

filename = f"_posts/{date_str}-{safe_title}.md"

# 4. Ensure the _posts folder exists
os.makedirs("_posts", exist_ok=True)

# 5. Save the daily fact as a new post
with open(filename, "w", encoding="utf-8") as f:
    f.write("---\n")
    f.write("layout: post\n")  # 'post' layout tells Jekyll this is a blog article
    f.write(f"title: \"{topic}\"\n")
    f.write("---\n\n")
    f.write(response.text)
