from urllib.parse import urlparse, urljoin

def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def make_absolute_url(base_url: str, relative_url: str) -> str:
    if not relative_url:
        return ""
    if relative_url.startswith("data:image") or relative_url.startswith("blob:"):
        return ""
    return urljoin(base_url, relative_url)
