"""
Supabase Storage Client Service

Fetches raw file bytes from the Supabase Storage bucket 'materials' using the service-role key.
Bucket 'materials' has 0 storage policies, making access app-controlled via SUPABASE_SERVICE_ROLE_KEY.
"""

import httpx
from app.core.config import settings


class StorageFetchError(Exception):
    """Raised when fetching a material file from Supabase Storage fails."""
    pass


async def fetch_storage_file(storage_path: str) -> bytes:
    """
    Fetches raw bytes of a file stored in Supabase Storage bucket 'materials'.

    Args:
        storage_path: The file path within the 'materials' bucket.

    Returns:
        Raw file bytes.

    Raises:
        StorageFetchError: If configuration is missing, the file is not found (404),
                           access is denied, or a network/HTTP error occurs.
    """
    if not storage_path or not storage_path.strip():
        raise StorageFetchError("storage_path cannot be empty.")

    supabase_url = settings.SUPABASE_URL
    service_key = settings.SUPABASE_SERVICE_ROLE_KEY

    if not supabase_url or not service_key:
        raise StorageFetchError(
            "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not configured in settings."
        )

    # Supabase Storage REST API endpoint for downloading authenticated objects
    clean_path = storage_path.lstrip("/")
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/authenticated/materials/{clean_path}"

    headers = {
        "Authorization": f"Bearer {service_key}",
        "apiKey": service_key,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 404:
                raise StorageFetchError(
                    f"File not found in Supabase Storage bucket 'materials': {storage_path}"
                )
            elif response.status_code != 200:
                raise StorageFetchError(
                    f"Supabase Storage download failed (HTTP {response.status_code}): {response.text}"
                )

            return response.content

    except StorageFetchError:
        raise
    except Exception as e:
        raise StorageFetchError(f"Failed to fetch file from Supabase Storage: {e}") from e
