import os
import re
import httpx

DUB_API_KEY = os.getenv("DUB_API_KEY")
DUB_DOMAIN = os.getenv("DUB_DOMAIN")


def sanitize_key(key: str) -> str:
    """
    Sanitize a string to be used as a dub.co link key.
    - Removes file extension
    - Replaces spaces and special chars with hyphens
    - Converts to lowercase
    - Limits length
    """
    # Remove file extension
    key = os.path.splitext(key)[0]
    # Replace spaces and special chars with hyphens
    key = re.sub(r'[^a-zA-Z0-9-]', '-', key)
    # Replace multiple hyphens with single
    key = re.sub(r'-+', '-', key)
    # Remove leading/trailing hyphens
    key = key.strip('-')
    # Lowercase
    key = key.lower()
    # Limit length (dub.co has limits)
    key = key[:50]
    return key


async def create_short_link(url: str, key: str = None) -> dict | None:
    """
    Create a short link using dub.co API.
    
    Args:
        url: The URL to shorten
        key: Optional custom key for the short link
    
    Returns:
        Dict with shortLink, id, and key, or None if creation failed
    """
    if not DUB_API_KEY or not DUB_DOMAIN:
        return None
    
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "url": url,
                "domain": DUB_DOMAIN,
            }
            if key:
                payload["key"] = sanitize_key(key)
            
            response = await client.post(
                "https://api.dub.co/links",
                headers={
                    "Authorization": f"Bearer {DUB_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10.0,
            )
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                return {
                    "shortLink": data.get("shortLink"),
                    "id": data.get("id"),
                    "key": data.get("key"),
                }
            else:
                print(f"dub.co error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"dub.co error: {e}")
            return None


async def update_short_link(link_id: str, new_key: str) -> dict | None:
    """
    Update a short link's key using dub.co API.
    
    Args:
        link_id: The dub.co link ID
        new_key: The new key for the short link
    
    Returns:
        Dict with shortLink and key, or None if update failed
    """
    if not DUB_API_KEY or not DUB_DOMAIN:
        return None
    
    sanitized_key = sanitize_key(new_key)
    if not sanitized_key:
        return None
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.patch(
                f"https://api.dub.co/links/{link_id}",
                headers={
                    "Authorization": f"Bearer {DUB_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "key": sanitized_key,
                },
                timeout=10.0,
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "shortLink": data.get("shortLink"),
                    "key": data.get("key"),
                }
            else:
                print(f"dub.co update error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"dub.co update error: {e}")
            return None


async def delete_short_link(link_id: str) -> bool:
    """
    Delete a short link from dub.co.
    
    Args:
        link_id: The dub.co link ID
    
    Returns:
        True if deleted successfully, False otherwise
    """
    if not DUB_API_KEY or not link_id:
        return True  # Nothing to delete
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(
                f"https://api.dub.co/links/{link_id}",
                headers={
                    "Authorization": f"Bearer {DUB_API_KEY}",
                },
                timeout=10.0,
            )
            
            if response.status_code == 200 or response.status_code == 204:
                return True
            else:
                print(f"dub.co delete error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"dub.co delete error: {e}")
            return False
