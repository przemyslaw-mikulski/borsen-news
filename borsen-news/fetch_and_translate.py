import feedparser
import pandas as pd
import os
from openai import OpenAI
import requests
import ollama
from datetime import datetime, timedelta

RSS_FEEDS = [
    "https://borsen.dk/rss",
    "https://borsen.dk/rss/breaking",
    "https://borsen.dk/rss/baeredygtig",
    "https://borsen.dk/rss/ejendomme",
    "https://borsen.dk/rss/finans",
    "https://borsen.dk/rss/investor",
    "https://borsen.dk/rss/ledelse",
    "https://borsen.dk/rss/longread",
    "https://borsen.dk/rss/markedsberetringen",
    "https://borsen.dk/rss/opinion",
    "https://borsen.dk/rss/pleasure",
    "https://borsen.dk/rss/politik",
    "https://borsen.dk/rss/tech",
    "https://borsen.dk/rss/utland",
    "https://borsen.dk/rss/virksomder",
    "https://borsen.dk/rss/okonomii"
]

def fetch_articles():
    items = []
    cutoff_time = datetime.now() - timedelta(hours=24)
    
    for url in RSS_FEEDS:
        parsed = feedparser.parse(url)
        for entry in parsed.entries:
            published_date = pd.to_datetime(entry.get("published", ""), errors="coerce")
            
            # Only include articles from the last 24 hours
            if pd.notna(published_date):
                # Convert timezone-aware datetime to naive for comparison
                if published_date.tz is not None:
                    published_date_naive = published_date.tz_convert(None)
                else:
                    published_date_naive = published_date
                
                if published_date_naive >= cutoff_time:
                    items.append({
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", ""),
                        "link": entry.get("link", ""),
                        "published": published_date,
                        "feed": url
                    })
    
    df = pd.DataFrame(items)
    # Deduplicate based on title, summary, and link
    df = df.drop_duplicates(subset=['title', 'summary', 'link'], keep='last')
    return df

def translate_text(text, method="none"):
    if method == "deepl":
        api_key = os.getenv("DEEPL_API_KEY")
        if not api_key:
            return text
        response = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={"text": text, "target_lang": "EN"},
            headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
            timeout=30
        )
        return response.json()["translations"][0]["text"]
    elif method == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return text
        
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Translate from Danish to English"},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content
    elif method == "mistral7b":
        try:
            response = ollama.chat(model='mistral', messages=[
                {
                    'role': 'user',
                    'content': f'Translate the following Danish text to English. Only return the translation, no explanations:\n\n{text}'
                }
            ])
            return response['message']['content']
        except Exception as e:
            print(f"Mistral translation failed: {e}")
            return text
    else:
        return text
