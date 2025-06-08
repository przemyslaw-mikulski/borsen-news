# Example implementation using Hugging Face Inference API
import requests
import os

def translate_with_huggingface_mistral(text):
    """
    Use Hugging Face Inference API to access Mistral 7B
    Cost: ~$0.0002 per 1K tokens (very affordable)
    """
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        return text
    
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
            return result[0].get("generated_text", text).split("English:")[-1].strip()
        return text
    except Exception as e:
        print(f"Hugging Face Mistral translation failed: {e}")
        return text
