"""
processing.py
-------------
Pandas-based cleaning, filtering, and ranking of raw scraped listing data.
"""

import re
import pandas as pd


# ---------------------------------------------------------------------------
# Raw value parsers
# ---------------------------------------------------------------------------

def _parse_price(val: str) -> float | None:
    """Extract a numeric price from a string like '1.500 €/mes' or '1500€'."""
    if not val or pd.isna(val):
        return None
    cleaned = re.sub(r"[€\s]", "", str(val))       # Remove € and spaces
    cleaned = cleaned.replace(".", "").replace(",", ".")  # 1.500 → 1500
    match = re.search(r"[\d]+(?:\.\d+)?", cleaned)
    try:
        return float(match.group()) if match else None
    except (AttributeError, ValueError):
        return None


def _parse_m2(val: str) -> float | None:
    """Extract square metres from a string like '120 m²'."""
    if not val or pd.isna(val):
        return None
    match = re.search(r"(\d+)", str(val))
    return float(match.group(1)) if match else None


def _parse_rooms(val: str) -> float | None:
    """Extract room count from a string like '3 hab.'."""
    if not val or pd.isna(val):
        return None
    match = re.search(r"(\d+)", str(val))
    return float(match.group(1)) if match else None


def _parse_restrooms(val: str) -> float | None:
    """Extract restroom count from a string like '2 baños'. Returns None for N/A."""
    if not val or val == "N/A" or pd.isna(val):
        return None
    match = re.search(r"(\d+)", str(val))
    return float(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_and_rank(
    raw: list[dict],
    max_price: int,
    min_rooms: int,
    min_restrooms: int,
) -> pd.DataFrame:
    """
    Clean, filter, compute metrics, and rank scraped listing data.

    Args:
        raw:           List of raw dicts returned by the scraper.
        max_price:     Maximum monthly rent (€) — hard filter.
        min_rooms:     Minimum number of bedrooms — hard filter.
        min_restrooms: Minimum number of bathrooms (skipped when data is N/A).

    Returns:
        A display-ready DataFrame ranked by Price/m² (ascending), max 15 rows.
        Columns: Rank, Zone, Price (€), m², Rooms, Restrooms, €/m², Link.
    """
    if not raw:
        return pd.DataFrame()

    df = pd.DataFrame(raw)

    # --- Parse numeric columns ---
    df["price_num"]     = df["price_raw"].apply(_parse_price)
    df["m2_num"]        = df["m2_raw"].apply(_parse_m2)
    df["rooms_num"]     = df["rooms_raw"].apply(_parse_rooms)
    df["restrooms_num"] = df["restrooms_raw"].apply(_parse_restrooms)

    # --- Drop rows with missing critical fields ---
    df = df.dropna(subset=["price_num", "m2_num", "rooms_num"])
    df = df[df["m2_num"] > 0]

    # --- Compute Price per m² ---
    df["price_per_m2"] = (df["price_num"] / df["m2_num"]).round(2)

    # --- Fallback hard filters (safety net for sponsored/rogue listings) ---
    df = df[df["price_num"] <= max_price]
    df = df[df["rooms_num"] >= min_rooms]

    # Restroom filter: only applied to rows where restroom data is present.
    # Listings with missing restroom info are kept (we don't penalise missing data).
    if min_restrooms > 0:
        mask_known    = df["restrooms_num"].notna()
        mask_ok       = df["restrooms_num"].fillna(0) >= min_restrooms
        # Keep rows where restrooms unknown OR restrooms meet threshold
        df = df[~mask_known | mask_ok]

    if df.empty:
        return pd.DataFrame()

    # --- Rank ---
    df = df.sort_values("price_per_m2").head(15).reset_index(drop=True)
    df.index += 1  # Rank is 1-indexed

    # --- Build display-ready DataFrame ---
    def fmt_restrooms(val):
        return f"{val:.0f}" if pd.notna(val) else "N/A"

    display = pd.DataFrame({
        "Rank":        df.index,
        "Zone":        df["zone"],
        "Price (€)":   df["price_num"].apply(lambda x: f"{x:,.0f} €"),
        "m²":          df["m2_num"].apply(lambda x: f"{x:.0f}"),
        "Rooms":       df["rooms_num"].apply(lambda x: f"{x:.0f}"),
        "Restrooms":   df["restrooms_num"].apply(fmt_restrooms),
        "€/m²":        df["price_per_m2"].apply(lambda x: f"{x:.2f}"),
        "Link":        df["link"],
    })

    return display
