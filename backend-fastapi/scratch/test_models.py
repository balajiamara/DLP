import sys
import os
sys.path.insert(0, os.path.abspath("."))

from google import genai
from app.core.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)
print("=== Gemini API Models List ===")
for m in client.models.list():
    if "embed" in m.name.lower() or "text" in m.name.lower():
        print(f"Model Name: {m.name}, Supported Methods: getattr(m, 'supported_generation_methods', None)")
