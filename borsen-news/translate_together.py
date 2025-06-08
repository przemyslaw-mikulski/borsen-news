"""
Together AI implementation for Mistral 7B translation.

Exact implementation based on NewsHavn project approach.
"""
import json
import os

import requests


def translate_with_together_ai(text: str, is_title: bool = False) -> str:
    """Use Together AI to access Mistral 7B for translation.
    
    Exact implementation matching NewsHavn project.
    
    Args:
        text: The Danish text to translate
        is_title: Whether this is a title (uses different prompt/tokens)
        
    Returns:
        Translated English text or error message
    """
    # NewsHavn uses "API_KEY" not "TOGETHER_API_KEY"
    api_key = os.getenv("API_KEY")
    if not api_key:
        return "[Together AI API key not configured - Original Danish text]"

    if not text or text.strip() == "":
        return ""

    # NewsHavn's exact API configuration
    api_url = "https://api.together.xyz/v1/chat/completions"
    model = "mistralai/Mistral-7B-Instruct-v0.2"  # NewsHavn uses v0.2
    temperature = 0  # NewsHavn uses 0 for deterministic translations

    # Different prompts and max_tokens for titles vs content (NewsHavn approach)
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


# Test function
if __name__ == "__main__":
    test_text = "Dette er en test af Together AI oversættelse."
    result = translate_with_together_ai(test_text)
    print(f"Original: {test_text}")
    print(f"Translated: {result}")
