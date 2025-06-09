# Together AI Setup Guide

## 🚀 Quick Setup (2 minutes)

### 1. Get Your Together AI API Key
- Visit: https://api.together.xyz
- Sign up (free account)
- Go to API Keys section
- Create new key named "RSS News App"
- Copy the key

### 2. Add Key to Your Project
- Open `.env` file in your project
- Replace `your_together_ai_api_key_here` with your actual key
- Save the file

### 3. Test the Setup
```bash
python test_together_ai.py
```

### 4. Use in Your App
- Open your Streamlit app: http://localhost:8502
- Select "togetherai" as translation method
- Fetch and translate articles

## 💰 Cost Comparison

| Service | Monthly Cost | Your Usage |
|---------|-------------|------------|
| **Together AI** | **$0.18-0.36** | ✅ **Cheapest** |
| OpenAI GPT-3.5 | $0.45-1.35 | 3-4x more expensive |
| Hugging Face | $0.45-0.90 | 2-3x more expensive |
| DeepL | $6.99 | 20x more expensive |

## ✅ Benefits of Together AI

- **Lowest cost**: $0.20 per 1M tokens
- **High quality**: Mistral 7B model (7 billion parameters)
- **Fast responses**: Optimized for real-time translation
- **Pay-as-you-use**: No monthly minimums
- **Already implemented**: Ready to use in your app

## 🔧 Your Implementation

Your app already includes the complete Together AI integration:
- `translate_with_together_ai()` function with NewsHavn's proven approach
- Different prompts for titles vs content
- Temperature 0 for deterministic translations
- Proper error handling and fallbacks

## 📊 Expected Usage

With your current RSS setup:
- **29 fetches per day** (every 30 minutes)
- **~50-100 articles per day**
- **~15,000-30,000 tokens per day**
- **~450,000-900,000 tokens per month**
- **Together AI cost: $0.18-0.36 per month**

That's less than 40 cents per month for unlimited Danish-to-English translation!
