import feedparser
import pandas as pd
import os
from openai import OpenAI
import requests
from datetime import datetime, timedelta
import time
from bs4 import BeautifulSoup
import re

RSS_FEEDS = [
    "https://borsen.dk/rss",
    "https://borsen.dk/rss/breaking",
    "https://borsen.dk/rss/baeredygtig",
    "https://borsen.dk/rss/ejendomme",
    "https://borsen.dk/rss/finans",
    "https://borsen.dk/rss/investor",
    "https://borsen.dk/rss/ledelse",
    "https://borsen.dk/rss/longread",
    "https://borsen.dk/rss/markedsberetningen",
    "https://borsen.dk/rss/opinion",
    "https://borsen.dk/rss/pleasure",
    "https://borsen.dk/rss/politik",
    "https://borsen.dk/rss/tech",
    "https://borsen.dk/rss/utland",
    "https://borsen.dk/rss/virksomheder",
    "https://borsen.dk/rss/okonomi"
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
    
    # Add translated_summary column (will be filled by the Streamlit app)
    if not df.empty:
        df['translated_summary'] = None
        
    # Scrape full content for each article to extract NÆVNTE sections
    if not df.empty:
        scrape_article_content(df)
    
    return df


def scrape_article_content(df):
    """Scrape full content and extract NÆVNTE sections from articles."""
    if len(df) == 0:
        return
    
    print(f"Scraping content for {len(df)} articles...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for idx, row in df.iterrows():
        try:
            print(f"Scraping article {idx + 1}/{len(df)}: {row['title'][:50]}...")
            
            response = requests.get(row["link"], headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            text_content = soup.get_text()
            
            # Extract NÆVNTE sections
            naevnte_emner = extract_naevnte_section(text_content, "NÆVNTE EMNER:")
            naevnte_virksomheder = extract_naevnte_section(text_content, "NÆVNTE VIRKSOMHEDER:")
            
            # Store the extracted data
            df.at[idx, "content"] = text_content[:2000]  # Store first 2000 chars
            df.at[idx, "word_count"] = len(text_content.split())
            df.at[idx, "scraped_at"] = datetime.now()
            df.at[idx, "naevnte_emner"] = naevnte_emner
            df.at[idx, "naevnte_virksomheder"] = naevnte_virksomheder
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"Error scraping article {idx + 1}: {e}")
            # Set default values for failed scraping
            df.at[idx, "content"] = ""
            df.at[idx, "word_count"] = 0
            df.at[idx, "scraped_at"] = datetime.now()
            df.at[idx, "naevnte_emner"] = ""
            df.at[idx, "naevnte_virksomheder"] = ""
            continue


def extract_naevnte_section(text_content, section_name):
    """Extract content from NÆVNTE EMNER or NÆVNTE VIRKSOMHEDER sections."""
    try:
        lines = text_content.split('\n')
        section_found = False
        content_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Check if this line contains the section header
            if section_name.lower() in line.lower():
                section_found = True
                continue
                
            # If we found the section, collect the following lines
            if section_found:
                # Stop if we hit another section or empty lines
                if line == "" or "NÆVNTE" in line or len(line) > 100:
                    break
                if line and not line.startswith("http"):  # Skip URLs
                    content_lines.append(line)
        
        if content_lines:
            return ", ".join(content_lines)
        else:
            return ""
            
    except Exception as e:
        print(f"Error extracting {section_name}: {e}")
        return ""


def translate_with_huggingface_mistral(text):
    """
    Use Hugging Face Inference API to access Mistral 7B
    Fallback for cloud environments where Ollama isn't available
    """
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        return "[Hugging Face API key not configured - Original Danish text]"
    
    model_url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    payload = {
        "inputs": f"Translate the following Danish text to English. Only return the translation:\n\n{text}",
        "parameters": {
            "max_new_tokens": 512,
            "temperature": 0.1
        }
    }
    
    try:
        response = requests.post(model_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            generated_text = result[0].get("generated_text", "")
            
            # Clean up the response to extract just the translation
            if "English:" in generated_text:
                return generated_text.split("English:")[-1].strip()
            elif "Translation:" in generated_text:
                return generated_text.split("Translation:")[-1].strip()
            else:
                # Remove the original prompt if it appears in the response
                for prompt_part in ["Translate the following", "Danish text", text[:50]]:
                    if prompt_part in generated_text:
                        generated_text = generated_text.replace(prompt_part, "").strip()
                return generated_text
        else:
            return "[Translation failed - API response format error]"
    
    except Exception as e:
        return f"[Translation failed: {str(e)}]"


def translate_with_together_ai(text):
    """
    Translate text using Together AI's Mistral-7B model.
    Proven approach from NewsHavn integration.
    """
    api_key = os.getenv("API_KEY")  # Using API_KEY to match .env file
    if not api_key:
        return "[Together AI API key not configured - Original Danish text]"
    
    if not text or text.strip() == "":
        return ""
    
    # Different prompts and max_tokens for titles vs content
    if len(text) < 200:  # Likely a title
        system_prompt = (
            "When you receive a sentence in Danish, your task is to translate "
            "it into clear, natural English. Output only the English translation."
        )
        max_tokens = 100
    else:  # Article content
        system_prompt = (
            "Your task:\n"
            "- When you receive an article in Danish, your critical task is to translate it into English.\n"
            "- Preserve all meaning, context, and nuance.\n"
            "- Maintain professional tone appropriate for business/financial news.\n"
            "- Once prompted, just output the English translation."
        )
        max_tokens = 2000
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.together.xyz/v1",
        )
        
        result = client.chat.completions.create(
            model="mistralai/Mistral-7B-Instruct-v0.2",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=max_tokens,
            temperature=0
        )
        
        if result.choices:
            translation = result.choices[0].message.content.strip()
            
            # Quality check: if translation is much longer than original, 
            # it might include the prompt - take only the relevant part
            if len(translation) > len(text) * 2:
                lines = translation.split('\n')
                for line in lines:
                    if len(line.strip()) > 10 and not any(word in line.lower() for word in 
                                                         ['translate', 'danish', 'english', 'task']):
                        return line.strip()
                # Fallback: Limit to first line if ratio too high
                return translation.split('\n')[0]
            
            return translation
        else:
            return "[No translation generated]"
    
    except Exception as e:
        return f"[Translation error: {str(e)}]"


def translate_with_ollama_mistral(text):
    """
    Use local Ollama Mistral model for translation
    """
    try:
        import ollama
        
        response = ollama.chat(model='mistral', messages=[
            {
                'role': 'user',
                'content': f'Translate this Danish text to English: {text}'
            },
        ])
        
        return response['message']['content']
    except ImportError:
        return "[Ollama not available - install with: pip install ollama]"
    except Exception as e:
        return f"[Ollama translation failed: {str(e)}]"


def translate_text(text, method="none"):
    """Main translation function that routes to the appropriate method"""
    if method == "none" or not text or text.strip() == "":
        return text
    
    if method == "togetherai":
        return translate_with_together_ai(text)
    elif method == "huggingface":
        return translate_with_huggingface_mistral(text)
    elif method == "ollama":
        return translate_with_ollama_mistral(text)
    else:
        return text
