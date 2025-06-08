# Example implementation using Together AI
import requests
import os

def translate_with_together_mistral(text):
    """
    Use Together AI to access Mistral 7B
    Cost: ~$0.0002 per 1K tokens
    """
    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        return text
    
    url = "https://api.together.xyz/inference"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "mistralai/Mistral-7B-Instruct-v0.1",
        "prompt": f"Translate the following Danish text to English. Only return the translation:\n\n{text}",
        "max_tokens": 200,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        result = response.json()
        return result["output"]["choices"][0]["text"].strip()
    except Exception as e:
        print(f"Together AI Mistral translation failed: {e}")
        return text
