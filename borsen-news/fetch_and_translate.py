import feedparser
import pandas as pd
import os
from openai import OpenAI
import requests
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

def translate_with_huggingface_mistral(text):
    """
    Use Hugging Face Inference API to access Mistral 7B
    Fallback for cloud environments where Ollama isn't available
    """
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        return "[Hugging Face API key not configured - Original Danish text]"
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Using Mistral 7B Instruct model
    model_url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
    
    payload = {
        "inputs": f"Translate the following Danish text to English. Only return the translation:\n\n{text}",
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.1
        }
    }
    
    try:
        response = requests.post(model_url, headers=headers, json=payload, timeout=30)
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0:
            generated_text = result[0].get("generated_text", "")
            # Extract just the translation part
            if "English:" in generated_text:
                return generated_text.split("English:")[-1].strip()
            elif "Translation:" in generated_text:
                return generated_text.split("Translation:")[-1].strip()
            else:
                # Return the part after the input prompt
                prompt_part = f"Translate the following Danish text to English. Only return the translation:\n\n{text}"
                if prompt_part in generated_text:
                    return generated_text.replace(prompt_part, "").strip()
                return generated_text.strip()
        
        return text
    except Exception as e:
        print(f"Hugging Face Mistral translation failed: {e}")
        return text

def translate_with_together_ai(text, is_title=False):
    """
    Use Together AI to access Mistral 7B for translation
    Exact implementation matching NewsHavn project approach
    """
    api_key = os.getenv("API_KEY")  # NewsHavn uses "API_KEY"
    if not api_key:
        return "[Together AI API key not configured - Original Danish text]"

    if not text or text.strip() == "":
        return ""

    # NewsHavn's exact API configuration
    api_url = "https://api.together.xyz/v1/chat/completions"
    model = "mistralai/Mistral-7B-Instruct-v0.2"  # NewsHavn uses v0.2
    temperature = 0  # NewsHavn uses 0 for deterministic translations

    # Different prompts and max_tokens for titles vs content
    if is_title:
        prompt = (
            "You are a highly skilled and concise professional translator. "
            "When you receive a sentence in Danish, your task is to translate "
            "it into English. VERY IMPORTANT: Do not output any notes, "
            "explanations, alternatives or comments after or before the "
            f"translation.\n\nDanish sentence: {text}\n\nEnglish translation:"
        )
        max_tokens = 50
    else:
        prompt = f"""You are a highly skilled professional translator.

Here are your instructions:
- When you receive an article in Danish, your critical task is to translate it into English.
- You do not output any html, but the actual text of the article.
- You do not add any notes or explanations.
- The article to translate will be inside the <article> tags.
- Once prompted, just output the English translation.
- Do not output the title of the article, only the content.
- Make sure the translation is well formatted and easy to read (no useless line breaks, no extra spaces, etc.)

<article>

{text}

</article>

Here is the best English translation of the article above:"""
        max_tokens = 8400

    # NewsHavn's exact payload structure
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "stop": ["</s>", "[/INST]"],  # NewsHavn's stop tokens
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.post(
            api_url, headers=headers, json=payload, timeout=30
        )
        response.raise_for_status()

        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            translation = result["choices"][0]["message"]["content"].strip()
            
            # NewsHavn's translation ratio check for titles
            if is_title:
                t_ratio = len(translation) / len(text) if len(text) > 0 else 0
                if t_ratio > 2.0:
                    # Limit to first line if ratio too high
                    translation = translation.split("\n")[0]
            
            return translation

        return text

    except requests.exceptions.RequestException as e:
        print(f"Together AI translation failed: {e}")
        return text
    except Exception as e:
        print(f"Together AI translation error: {e}")
        return text

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
            # Try local Ollama first (for local development)
            import ollama
            response = ollama.chat(model='mistral', messages=[
                {
                    'role': 'user',
                    'content': f'Translate the following Danish text to English. Only return the translation, no explanations:\n\n{text}'
                }
            ])
            return response['message']['content']
        except ImportError:
            # Fall back to Hugging Face Inference API (for cloud deployment)
            return translate_with_huggingface_mistral(text)
        except Exception as e:
            print(f"Local Mistral failed, trying Hugging Face: {e}")
            return translate_with_huggingface_mistral(text)
    elif method == "togetherai":
        return translate_with_together_ai(text)
    else:
        return "[No translation - Original Danish text]"
