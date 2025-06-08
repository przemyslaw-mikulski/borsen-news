# Example implementation using Replicate API
import replicate
import os

def translate_with_replicate_mistral(text):
    """
    Use Replicate API to access Mistral 7B
    Cost: ~$0.0001 per second (very affordable)
    """
    api_key = os.getenv("REPLICATE_API_TOKEN")
    if not api_key:
        return text
    
    try:
        output = replicate.run(
            "mistralai/mistral-7b-instruct-v0.1:83b6a56e7c828e667f21fd596c338fd4f0039b46bcfa18d973e8e70e455fda70",
            input={
                "prompt": f"Translate the following Danish text to English. Only return the translation:\n\n{text}",
                "max_new_tokens": 200,
                "temperature": 0.1
            }
        )
        return "".join(output).strip()
    except Exception as e:
        print(f"Replicate Mistral translation failed: {e}")
        return text
