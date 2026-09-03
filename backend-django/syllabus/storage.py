import os
from supabase import create_client, Client

_supabase_client = None


def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        _supabase_client = create_client(url, key)
    return _supabase_client


BUCKET_NAME = 'materials'


def upload_file(storage_path: str, file_bytes: bytes, content_type: str = 'application/octet-stream'):
    """Uploads file bytes to Supabase Storage bucket 'materials'."""
    client = get_supabase_client()
    return client.storage.from_(BUCKET_NAME).upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": content_type}
    )


def get_signed_url(storage_path: str, expires_in: int = 3600) -> str:
    """Generates a time-limited signed download URL for the specified storage path."""
    client = get_supabase_client()
    res = client.storage.from_(BUCKET_NAME).create_signed_url(
        path=storage_path,
        expires_in=expires_in
    )
    if isinstance(res, dict) and 'signedUrl' in res:
        return res['signedUrl']
    elif hasattr(res, 'signed_url') and res.signed_url:
        return res.signed_url
    elif isinstance(res, dict) and 'signedURL' in res:
        return res['signedURL']
    return str(res)


def delete_file(storage_path: str):
    """Deletes the specified file object from Supabase Storage bucket 'materials'."""
    client = get_supabase_client()
    return client.storage.from_(BUCKET_NAME).remove([storage_path])
