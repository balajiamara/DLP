import sys
import os
sys.path.insert(0, os.path.abspath("."))

from google import genai
from google.genai import types
from app.core.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

for model_name in ["gemini-embedding-001", "models/gemini-embedding-001", "gemini-embedding-2"]:
    try:
        res = client.models.embed_content(
            model=model_name,
            contents=["Hello world test sentence"],
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        vec = res.embeddings[0].values
        print(f"SUCCESS with model '{model_name}': returned vector dimension = {len(vec)}")
        break
    except Exception as e:
        print(f"FAILED model '{model_name}': {e}")
