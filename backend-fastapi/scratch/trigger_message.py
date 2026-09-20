import sys
import os
import requests
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import jwt
import uuid
from app.core.config import settings

DJANGO_URL = "http://127.0.0.1:8000"

def get_token_for_user(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "token_type": "access",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm="HS256")

def send_message(conv_id: int, body: str, sender_id: int = 2):
    token = get_token_for_user(sender_id)
    url = f"{DJANGO_URL}/api/conversations/{conv_id}/messages/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, json={"body": body}, headers=headers, timeout=10.0)
    print(f"Status: {resp.status_code}, Response: {resp.text}")
    return resp

if __name__ == "__main__":
    conv_id = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    body = sys.argv[2] if len(sys.argv) > 2 else f"Real-time test message from Session A at {time.strftime('%X')}!"
    sender_id = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    send_message(conv_id, body, sender_id)
