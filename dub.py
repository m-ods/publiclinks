import os
import httpx

DUB_API_KEY = os.getenv("DUB_API_KEY")
DUB_DOMAIN = os.getenv("DUB_DOMAIN")


async def create_short_link(url: str) -> str | None:
    """
    Create a short link using dub.co API.
    
    Args:
        url: The URL to shorten
    
    Returns:
        The short URL, or None if creation failed
    """
    if not DUB_API_KEY or not DUB_DOMAIN:
        return None
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.dub.co/links",
                headers={
                    "Authorization": f"Bearer {DUB_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "domain": DUB_DOMAIN,
                },
                timeout=10.0,
            )
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                return data.get("shortLink")
            else:
                print(f"dub.co error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"dub.co error: {e}")
            return None


async def delete_short_link(short_url: str) -> bool:
    """
    Delete a short link from dub.co.
    
    Note: This requires the link ID, which we'd need to store.
    For now, we'll skip deletion of dub links.
    """
    # TODO: Store link IDs if we want to delete dub links
    return True
