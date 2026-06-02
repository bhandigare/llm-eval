# src/bot.py — OpenRouter client (OpenAI-compatible API)
from openai import OpenAI
from dotenv import load_dotenv
import os
load_dotenv()

SYSTEM_PROMPT = """You are a helpful customer support agent for ShopEasy.
Answer questions about orders, refunds, and shipping using only the
information provided. Be concise and professional.

Knowledge base:
- Return window: 30 days from purchase date
- Refund processing: 5-7 business days
- Standard shipping: 3-5 business days, free over $50
- Express shipping: 1-2 business days, $12.99
- Order tracking: use tracking link in confirmation email
- Contact support: support@shopeasy.com or 1-800-555-0199"""

# OpenRouter client — drop-in for openai.OpenAI()
def _get_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ["OPENROUTER_BASEURL"],
        api_key=os.environ["OPENROUTER_API_KEY"],
    )

# Optional: identify your app in OpenRouter dashboard
EXTRA_HEADERS = {
    "HTTP-Referer": "https://your-app.com",   # shown in usage logs
    "X-Title":      "ShopEasy Support Bot",    # shown in OpenRouter UI
}

def answer(question: str, context: str = "") -> str:
    client = _get_client()

    user_content = (
        f"Context: {context}\n\nQuestion: {question}"
        if context else question
    )

    resp = client.chat.completions.create(
        model=os.environ["OPENROUTER_MODEL"],   # OpenRouter model string
        max_tokens=300,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
        extra_headers=EXTRA_HEADERS,
    )
    return resp.choices[0].message.content.strip()

if __name__ == "__main__":
    print(answer("What is the refund window?"))
    print(answer("How long does express shipping take?"))