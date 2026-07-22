import os
from pytrends.request import TrendReq
from google import genai

# 1. Fetch the #1 Trending Topic from Google Trends using pytrends
# tz=330 sets the timezone to India (UTC +5:30)
pytrend = TrendReq(hl='en-IN', tz=330)
trending_df = pytrend.trending_searches(pn='india')

# .iloc[0, 0] extracts the absolute #1 most searched term of the day
topic = trending_df.iloc[0, 0] 

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
