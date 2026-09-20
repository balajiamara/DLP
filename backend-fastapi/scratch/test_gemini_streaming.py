import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from google import genai
from google.genai import types
from app.core.config import settings

def test_gemini_streaming():
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        print("ERROR: No GEMINI_API_KEY found.")
        return

    client = genai.Client(api_key=api_key)
    print("Testing client.models.generate_content_stream with gemini-3.6-flash...")
    
    config = types.GenerateContentConfig(
        system_instruction="You are a helpful assistant. Keep your answer to 2-3 short sentences.",
        temperature=0.2,
    )
    
    prompt = "Explain in brief what an API is."
    start_time = time.perf_counter()
    
    try:
        response_stream = client.models.generate_content_stream(
            model="gemini-3.6-flash",
            contents=prompt,
            config=config,
        )
        
        chunk_count = 0
        chunks_collected = []
        
        for chunk in response_stream:
            chunk_count += 1
            chunk_elapsed = time.perf_counter() - start_time
            # Inspect chunk attributes
            chunk_text = chunk.text
            chunks_collected.append(chunk_text)
            print(f"[Chunk {chunk_count} @ {chunk_elapsed*1000:.1f}ms]: len={len(chunk_text or '')} | repr={repr(chunk_text)}")
            
        total_time = time.perf_counter() - start_time
        full_text = "".join(chunks_collected)
        
        print(f"\nStream finished: {chunk_count} chunks in {total_time*1000:.1f}ms.")
        print(f"Total reconstructed length: {len(full_text)} chars.")
        print(f"Full text:\n{full_text}")
        
        # Check if chunks are deltas or accumulated:
        # If chunk 2 starts with chunk 1, it's accumulated. If chunk 2 is just the next words, it's deltas.
        if len(chunks_collected) > 1:
            first = chunks_collected[0]
            second = chunks_collected[1]
            is_accumulated = second.startswith(first)
            print(f"\nDelta vs Accumulated check: chunks are {'ACCUMULATED' if is_accumulated else 'DELTAS (each chunk is new text)'}.")
        
    except Exception as exc:
        print(f"FAILED with error: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gemini_streaming()
