"""
Børsen RSS Feed Article Fetcher and Translator.

This module provides functionality to:
- Fetch articles from Børsen RSS feeds
- Scrape full article content from web pages
- Translate Danish content to English using various APIs
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Constants
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

# Scraping constants
MIN_TEXT_LENGTH = 30
MIN_CONTENT_PARAGRAPHS = 2
MIN_PARAGRAPH_LENGTH = 50
CHUNK_SIZE = 3000
REQUEST_TIMEOUT = 30
SCRAPING_DELAY = 1.0
TRANSLATION_DELAY = 0.5

# Content filtering keywords
UNWANTED_CONTENT_KEYWORDS = [
    "advertisement", "cookie", "gdpr", "subscribe", "reklame",
    "pro indhold", "læs mere og bli", "nyhedsbreve", "menu"
]

# Browser headers for web scraping
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


def fetch_articles() -> pd.DataFrame:
    """
    Fetch articles from RSS feeds with automatic content scraping.
    
    Returns:
        DataFrame containing article data with scraped content
    """
    articles = []
    cutoff_time = datetime.now() - timedelta(hours=24)
    
    for feed_url in RSS_FEEDS:
        try:
            parsed_feed = feedparser.parse(feed_url)
            articles.extend(_process_feed_entries(parsed_feed, feed_url, cutoff_time))
        except Exception as e:
            print(f"Error processing feed {feed_url}: {e}")
            continue
    
    if not articles:
        return pd.DataFrame()
    
    # Create DataFrame and remove duplicates
    df = pd.DataFrame(articles)
    df = df.drop_duplicates(subset=["title", "summary", "link"], keep="last")
    
    # Scrape content for each article
    _scrape_article_content(df)
    
    return df


def _process_feed_entries(
    parsed_feed: feedparser.FeedParserDict, 
    feed_url: str, 
    cutoff_time: datetime
) -> List[Dict[str, Any]]:
    """Process entries from a single RSS feed."""
    articles = []
    
    for entry in parsed_feed.entries:
        published_date = pd.to_datetime(
            entry.get("published", ""), errors="coerce"
        )
        
        if pd.notna(published_date):
            # Convert timezone-aware datetime to naive for comparison
            if published_date.tz is not None:
                published_date = published_date.tz_convert(None)
            
            if published_date >= cutoff_time:
                article_link = entry.get("link", "")
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "link": article_link,
                    "published": published_date,
                    "feed": feed_url,
                    "content": "",
                    "word_count": 0,
                    "url": article_link,
                    "scraped_at": pd.to_datetime(datetime.now())
                })
    
    return articles


def _scrape_article_content(df: pd.DataFrame) -> None:
    """Scrape full content for all articles in the DataFrame."""
    if len(df) == 0:
        return
    
    print(f"Scraping full content for {len(df)} articles...")
    
    for idx, row in df.iterrows():
        try:
            print(f"Scraping article {idx + 1}/{len(df)}: {row['title'][:50]}...")
            article_data = scrape_full_article(row["link"])
            
            if "error" not in article_data:
                df.at[idx, "content"] = article_data.get("content", "")
                df.at[idx, "word_count"] = article_data.get("word_count", 0)
                scraped_at_value = article_data.get(
                    "scraped_at", datetime.now().isoformat()
                )
                df.at[idx, "scraped_at"] = pd.to_datetime(scraped_at_value)
            else:
                print(f"Failed to scrape: {article_data['error']}")
            
            time.sleep(SCRAPING_DELAY)
            
        except Exception as e:
            print(f"Error scraping article {idx + 1}: {e}")
            continue


def scrape_full_article(url: str) -> Dict[str, Any]:
    """
    Scrape the full article content from a given URL.
    
    Args:
        url: The URL of the article to scrape
        
    Returns:
        Dictionary containing title, content, and metadata
    """
    try:
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "lxml")
        _remove_unwanted_elements(soup)
        
        article_content = _find_article_content(soup)
        if not article_content:
            return {
                "title": "",
                "content": "",
                "error": "Could not find article content",
                "url": url
            }
        
        title = _extract_title(soup)
        content = _extract_content(article_content)
        
        return {
            "title": title,
            "content": content,
            "word_count": len(content.split()) if content else 0,
            "url": url,
            "scraped_at": datetime.now().isoformat()
        }
        
    except requests.RequestException as e:
        return {
            "title": "",
            "content": "",
            "error": f"Network error: {str(e)}",
            "url": url
        }
    except Exception as e:
        return {
            "title": "",
            "content": "",
            "error": f"Scraping error: {str(e)}",
            "url": url
        }


def _remove_unwanted_elements(soup: BeautifulSoup) -> None:
    """Remove script, style and other unwanted elements from soup."""
    unwanted_tags = ["script", "style", "nav", "footer", "header", "aside"]
    for tag in soup(unwanted_tags):
        tag.decompose()


def _find_article_content(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """Find the main article content element."""
    article_selectors = [
        "article",
        ".article-content",
        ".content",
        ".post-content",
        ".entry-content",
        ".article-body",
        ".story-content",
        "main",
        ".main-content"
    ]
    
    for selector in article_selectors:
        content_elem = soup.select_one(selector)
        if content_elem:
            return content_elem
    
    # Fallback to body if no specific article content found
    return soup.find("body")


def _extract_title(soup: BeautifulSoup) -> str:
    """Extract article title from soup."""
    title_selectors = ["h1", ".headline", ".title", ".article-title"]
    
    for selector in title_selectors:
        title_elem = soup.select_one(selector)
        if title_elem:
            return title_elem.get_text().strip()
    
    return ""


def _extract_content(article_content: BeautifulSoup) -> str:
    """Extract main content text from article content element."""
    paragraphs = article_content.find_all(["p"])
    content_text = []
    
    for paragraph in paragraphs:
        text = paragraph.get_text().strip()
        if _is_valid_content_text(text):
            content_text.append(text)
    
    # If we didn't find enough content, try broader search
    if len(content_text) < MIN_CONTENT_PARAGRAPHS:
        content_text = _extract_content_fallback(article_content)
    
    full_content = "\n\n".join(content_text)
    return " ".join(full_content.split())  # Clean up whitespace


def _is_valid_content_text(text: str) -> bool:
    """Check if text is valid article content."""
    if len(text) <= MIN_TEXT_LENGTH:
        return False
    
    return not any(
        keyword in text.lower() for keyword in UNWANTED_CONTENT_KEYWORDS
    )


def _extract_content_fallback(article_content: BeautifulSoup) -> List[str]:
    """Fallback method to extract content when paragraphs method fails."""
    main_text = article_content.get_text()
    text_parts = [
        part.strip() for part in main_text.split("\n") 
        if len(part.strip()) > MIN_PARAGRAPH_LENGTH
    ]
    
    return [
        part for part in text_parts 
        if not any(keyword in part.lower() for keyword in UNWANTED_CONTENT_KEYWORDS)
    ]


def translate_text(text: str, method: str = "none") -> str:
    """
    Translate text using the specified method.
    
    Args:
        text: Text to translate
        method: Translation method ("deepl", "openai", "mistral7b", "togetherai")
        
    Returns:
        Translated text or original text if translation fails
    """
    if method == "deepl":
        return _translate_with_deepl(text)
    elif method == "openai":
        return _translate_with_openai(text)
    elif method == "mistral7b":
        return _translate_with_mistral(text)
    elif method == "togetherai":
        return translate_with_together_ai(text)
    else:
        return "[No translation - Original Danish text]"


def _translate_with_deepl(text: str) -> str:
    """Translate text using DeepL API."""
    api_key = os.getenv("DEEPL_API_KEY")
    if not api_key:
        return text
    
    try:
        response = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={"text": text, "target_lang": "EN"},
            headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()["translations"][0]["text"]
    except Exception as e:
        print(f"DeepL translation failed: {e}")
        return text


def _translate_with_openai(text: str) -> str:
    """Translate text using OpenAI API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return text
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Translate from Danish to English"},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI translation failed: {e}")
        return text


def _translate_with_mistral(text: str) -> str:
    """Translate text using Mistral (local or cloud)."""
    try:
        # Try local Ollama first
        import ollama
        response = ollama.chat(
            model="mistral",
            messages=[{
                "role": "user",
                "content": (
                    f"Translate the following Danish text to English. "
                    f"Only return the translation, no explanations:\n\n{text}"
                )
            }]
        )
        return response["message"]["content"]
    except ImportError:
        return translate_with_huggingface_mistral(text)
    except Exception as e:
        print(f"Local Mistral failed, trying Hugging Face: {e}")
        return translate_with_huggingface_mistral(text)


def translate_with_huggingface_mistral(text: str) -> str:
    """Translate text using Hugging Face Mistral API."""
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        return "[Hugging Face API key not configured - Original Danish text]"
    
    headers = {"Authorization": f"Bearer {api_key}"}
    model_url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
    
    payload = {
        "inputs": f"Translate the following Danish text to English. Only return the translation:\n\n{text}",
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.1
        }
    }
    
    try:
        response = requests.post(
            model_url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
        )
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0:
            generated_text = result[0].get("generated_text", "")
            return _extract_translation_from_generated_text(generated_text, text)
        
        return text
    except Exception as e:
        print(f"Hugging Face Mistral translation failed: {e}")
        return text


def _extract_translation_from_generated_text(generated_text: str, original_text: str) -> str:
    """Extract translation from Hugging Face generated text."""
    if "English:" in generated_text:
        return generated_text.split("English:")[-1].strip()
    elif "Translation:" in generated_text:
        return generated_text.split("Translation:")[-1].strip()
    else:
        prompt_part = f"Translate the following Danish text to English. Only return the translation:\n\n{original_text}"
        if prompt_part in generated_text:
            return generated_text.replace(prompt_part, "").strip()
        return generated_text.strip()


def translate_with_together_ai(text: str, is_title: bool = False) -> str:
    """
    Translate text using Together AI API.
    
    Args:
        text: Text to translate
        is_title: Whether the text is a title (affects prompt and token limit)
        
    Returns:
        Translated text
    """
    api_key = os.getenv("API_KEY")
    if not api_key:
        return "[API key not configured - Original Danish text]"

    if not text or text.strip() == "":
        return ""

    api_url = "https://api.together.xyz/v1/chat/completions"
    model = "mistralai/Mistral-7B-Instruct-v0.2"
    
    prompt, max_tokens = _get_translation_prompt_and_tokens(text, is_title)
    
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "stop": ["</s>", "[/INST]"],
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.post(
            api_url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            translation = result["choices"][0]["message"]["content"].strip()
            
            # Check translation ratio for titles
            if is_title:
                translation_ratio = len(translation) / len(text) if len(text) > 0 else 0
                if translation_ratio > 2.0:
                    translation = translation.split("\n")[0]
            
            return translation

        return text

    except requests.exceptions.RequestException as e:
        print(f"Translation API failed: {e}")
        return text
    except Exception as e:
        print(f"Translation error: {e}")
        return text


def _get_translation_prompt_and_tokens(text: str, is_title: bool) -> tuple[str, int]:
    """Get appropriate prompt and token limit for translation."""
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
    
    return prompt, max_tokens


def translate_full_article(article_data: Dict[str, Any], method: str = "togetherai") -> Dict[str, Any]:
    """
    Translate the full article content.
    
    Args:
        article_data: Article data from scrape_full_article
        method: Translation method to use
        
    Returns:
        Article data with translated content
    """
    if "error" in article_data:
        return article_data
    
    try:
        # Translate title if available
        translated_title = ""
        if article_data["title"]:
            translated_title = translate_with_together_ai(
                article_data["title"], is_title=True
            )
        
        # Translate content
        content = article_data["content"]
        if not content:
            return {
                **article_data,
                "translated_title": translated_title,
                "translated_content": "",
                "error": "No content to translate"
            }
        
        translated_content = _translate_content_in_chunks(content, method)
        
        return {
            **article_data,
            "translated_title": translated_title,
            "translated_content": translated_content,
            "translation_method": method,
        }
        
    except Exception as e:
        return {
            **article_data,
            "translated_title": "",
            "translated_content": "",
            "error": f"Translation error: {str(e)}"
        }


def _translate_content_in_chunks(content: str, method: str) -> str:
    """Translate content in chunks to avoid API limits."""
    chunks = _split_content_into_chunks(content)
    translated_chunks = []
    
    for i, chunk in enumerate(chunks):
        print(f"Translating chunk {i+1}/{len(chunks)}...")
        translated_chunk = translate_text(chunk, method)
        translated_chunks.append(translated_chunk)
        
        # Add delay between requests
        if i < len(chunks) - 1:
            time.sleep(TRANSLATION_DELAY)
    
    return "\n\n".join(translated_chunks)


def _split_content_into_chunks(content: str) -> List[str]:
    """Split content into chunks of appropriate size for translation."""
    chunks = []
    words = content.split()
    current_chunk = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1  # +1 for space
        
        if current_length + word_length > CHUNK_SIZE and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)
            current_length += word_length
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks
