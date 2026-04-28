"""
utils.py
--------
Helper utilities: zone slug conversion, URL construction, and shared constants.
"""

import re
import unicodedata

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Zone slug conversion
# ---------------------------------------------------------------------------

def zone_to_slug(name: str) -> str:
    """
    Convert a human-readable neighborhood name to an Idealista URL slug.

    Examples:
        "Villaverde Alto"   → "villaverde-alto"
        "Boadilla del Monte" → "boadilla-del-monte"
        "Carabanchel"        → "carabanchel"
    """
    # 1. Remove accents via unicode normalization
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    # 2. Lowercase, strip whitespace
    name = name.strip().lower()
    # 3. Replace spaces and underscores with hyphens
    name = re.sub(r"[\s_]+", "-", name)
    # 4. Remove any characters that aren't alphanumeric, hyphens, or forward slashes
    name = re.sub(r"[^a-z0-9-/]", "", name)
    # 5. Collapse multiple consecutive hyphens or slashes
    name = re.sub(r"-+", "-", name)
    name = re.sub(r"/+", "/", name)
    return name.strip("-").strip("/")


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------

def _rooms_url_filter(min_rooms: int) -> str:
    """Map a minimum room count to the appropriate Idealista URL filter token."""
    if min_rooms <= 1:
        return "de-un-dormitorio,de-dos-dormitorios,de-tres-dormitorios,de-cuatro-cinco-habitaciones-o-mas"
    elif min_rooms == 2:
        return "de-dos-dormitorios,de-tres-dormitorios,de-cuatro-cinco-habitaciones-o-mas"
    elif min_rooms == 3:
        return "de-tres-dormitorios,de-cuatro-cinco-habitaciones-o-mas"
    else:  # 4+
        return "de-cuatro-cinco-habitaciones-o-mas"


def build_search_url(
    zone_slug: str,
    max_price: int,
    min_rooms: int,
    page: int = 1,
) -> str:
    """
    Build the full Idealista search URL for a given zone path and filter set.

    Args:
        zone_slug:     Path segment (e.g. "madrid/latina/aluche" or "madrid-madrid").
        max_price:     Maximum monthly rent in euros.
        min_rooms:     Minimum number of bedrooms.
        page:          Result page number (1-indexed).

    Returns:
        A fully constructed Idealista search URL string.
    """
    slug = zone_to_slug(zone_slug)
    base = f"https://www.idealista.com/alquiler-viviendas/{slug}/"

    # Build filter chain
    filters = [f"precio-hasta_{max_price}", _rooms_url_filter(min_rooms)]
    filter_str = ",".join(f for f in filters if f)

    if page == 1:
        return f"{base}con-{filter_str}/"
    else:
        return f"{base}con-{filter_str}/pagina-{page}.htm"
