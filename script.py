import os
import urllib.request
import xml.etree.ElementTree as ET
from google import genai

# 1. Fetch the #1 Trending Topic from Google Trends India
url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req).read()
root = ET.fromstring(response)
topic = root.find('.//item/title').text

# 2. Ask Gemini AI to write a factual, unbiased article
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
prompt = f"Write a neutral, unbiased 300-word factual article on this trending topic: {topic}. Output in Markdown format. Do not take sides."

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt,
)

# 3. Save it as the main page of your website (index.md)
with open("index.md", "w", encoding="utf-8") as f:
    f.write(f"# Daily Fact: {topic}\n\n")
    f.write(response.text)
