import os
import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# استخدام نموذج مجاني سريع ومستقر
DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct"

def send_message(user_message, system_prompt="You are a helpful assistant."):
    api_key = os.getenv('OPENROUTER_API_KEY')

    if not api_key or api_key == 'paste-your-key-here':
        return "⚠️ No API key found. Add your OpenRouter key to the .env file and restart the app."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8080"
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message}
    ]

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json={"model": DEFAULT_MODEL, "messages": messages},
            timeout=25
        )
        result = response.json()

        if 'error' in result:
            return f"⚠️ OpenRouter error: {result['error'].get('message', 'Unknown error')}"

        if 'choices' not in result:
            return f"⚠️ Unexpected response: {result}"

        return result['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ Connection error: {str(e)}"