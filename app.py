"""
app.py
------
Streamlit dashboard for the Idealista Rental Scraper & Analyzer.
Run with: streamlit run app.py
"""

import logging
import io

import streamlit as st
import pandas as pd

from scraper import run_all_zones
from processing import process_and_rank

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Page config & global CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Idealista Rental Analyzer",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* ---- Google Font ---- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ---- Page background ---- */
    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 60%, #16213e 100%);
        color: #e8e8f0;
    }

    /* ---- Hero header ---- */
    .hero {
        text-align: center;
        padding: 2.5rem 1rem 1rem;
    }
    .hero h1 {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(90deg, #a78bfa, #60a5fa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.4rem;
    }
    .hero p {
        color: #94a3b8;
        font-size: 1.05rem;
    }

    /* ---- Sidebar ---- */
    [data-testid="stSidebar"] {
        background: #12122a;
        border-right: 1px solid #2d2d4e;
    }
    [data-testid="stSidebar"] h2 {
        color: #a78bfa;
        font-size: 1rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 1rem;
    }

    /* ---- Metric cards ---- */
    .metric-row {
        display: flex;
        gap: 1rem;
        margin: 1.5rem 0;
        flex-wrap: wrap;
    }
    .metric-card {
        flex: 1;
        min-width: 130px;
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(167,139,250,0.25);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        text-align: center;
    }
    .metric-card .value {
        font-size: 1.9rem;
        font-weight: 700;
        color: #a78bfa;
    }
    .metric-card .label {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-top: 0.2rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    /* ---- Result table styling ---- */
    .stDataFrame {
        border: 1px solid rgba(167,139,250,0.2) !important;
        border-radius: 10px !important;
        overflow: hidden !important;
    }

    /* ---- Rank badge column ---- */
    .rank-badge {
        display: inline-block;
        background: linear-gradient(90deg, #7c3aed, #4f46e5);
        color: white;
        border-radius: 6px;
        padding: 2px 8px;
        font-weight: 600;
    }

    /* ---- Section labels ---- */
    .section-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: #a78bfa;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.4rem;
    }

    /* ---- Warning / info boxes ---- */
    .info-box {
        background: rgba(96, 165, 250, 0.08);
        border-left: 3px solid #60a5fa;
        border-radius: 6px;
        padding: 0.7rem 1rem;
        font-size: 0.88rem;
        color: #93c5fd;
        margin: 0.8rem 0;
    }

    /* ---- Button styling ---- */
    div.stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #7c3aed, #4f46e5);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.7rem 1.5rem;
        font-size: 1.05rem;
        font-weight: 600;
        cursor: pointer;
        transition: opacity 0.2s ease, transform 0.1s ease;
    }
    div.stButton > button:hover {
        opacity: 0.88;
        transform: translateY(-1px);
    }

    /* ---- Expander ---- */
    .streamlit-expanderHeader {
        color: #a78bfa !important;
        font-weight: 600 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Hero header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="hero">
        <h1>🏠 Idealista Rental Analyzer</h1>
        <p>Find the best rental deals in Madrid — ranked by price per m², automatically.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

# ---------------------------------------------------------------------------
# Sidebar — Search parameters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## ⚙️ Search Parameters")
    st.markdown(
        '<p style="color:#94a3b8; font-size:0.85rem;">These values are sent directly in the Idealista URL and used as hard post-scrape filters.</p>',
        unsafe_allow_html=True,
    )

    max_price = st.number_input(
        "💶 Max Price (€/month)",
        min_value=300,
        max_value=10_000,
        value=2400,
        step=50,
        help="Listings above this price are excluded.",
    )
    min_rooms = st.number_input(
        "🛏️ Min Bedrooms",
        min_value=1,
        max_value=10,
        value=3,
        step=1,
        help="Minimum number of bedrooms.",
    )
    min_restrooms = st.number_input(
        "🚿 Min Restrooms",
        min_value=0,
        max_value=5,
        value=1,
        step=1,
        help="Minimum bathrooms/toilets. Set 0 to disable this filter.",
    )

    st.divider()

    st.markdown("## 🔧 Advanced")
    headless_mode = st.toggle(
        "Headless browser",
        value=False,
        help="Disable if Idealista is blocking you — runs the browser visibly instead.",
    )
    top_n = st.slider(
        "Default results shown",
        min_value=1,
        max_value=15,
        value=5,
        help="Number of top results shown by default (up to 15 available).",
    )

# ---------------------------------------------------------------------------
# Main area — Zone input
# ---------------------------------------------------------------------------

col_input, col_tip = st.columns([3, 2])

with col_input:
    st.markdown('<p class="section-label">📍 Neighborhoods to search</p>', unsafe_allow_html=True)
    input_method = st.radio(
        "Input method",
        ["✏️ Manual text", "📄 Upload CSV"],
        horizontal=True,
        label_visibility="collapsed",
    )

zonas: list[str] = []

if input_method == "✏️ Manual text":
    with col_input:
        raw_text = st.text_area(
            "Enter neighborhood paths (one per line or comma-separated):",
            placeholder="boadilla-del-monte/el-olivar-de-mirabal\nalcorcon/centro\nalcorcon-madrid", 
            height=130,
            label_visibility="collapsed",
        )
        if raw_text.strip():
            # Support both comma-separated and newline-separated input
            raw_text = raw_text.replace("\n", ",")
            zonas = [z.strip() for z in raw_text.split(",") if z.strip()]

else:
    with col_input:
        uploaded_file = st.file_uploader(
            "CSV file with a 'zona' column:",
            type=["csv"],
            label_visibility="collapsed",
        )
        if uploaded_file is not None:
            try:
                df_csv = pd.read_csv(uploaded_file)
                # Ensure missing values are treated as empty strings
                df_csv = df_csv.fillna("")
                
                if "zona" in df_csv.columns:
                    zonas = df_csv["zona"].dropna().astype(str).tolist()
                elif "ciudad" in df_csv.columns and "distrito" in df_csv.columns and "barrio" in df_csv.columns:
                    # Combine columns into a slug: ciudad/distrito/barrio
                    combined = df_csv.apply(
                        lambda row: "/".join([
                            str(row["ciudad"]), 
                            str(row["distrito"]), 
                            str(row["barrio"])
                        ]).strip("/"),
                        axis=1
                    )
                    zonas = [z for z in combined.tolist() if z]
                else:
                    st.error("❌ CSV must have a **'zona'** column containing the Idealista path.")
                
                if zonas:
                    st.success(f"✅ Loaded {len(zonas)} zone(s) from CSV.")
            except Exception as e:
                st.error(f"Failed to parse CSV: {e}")

with col_tip:
    st.markdown(
        """
        <div class="info-box">
        <b>💡 Tip:</b> Use the <b>exact path</b> from the Idealista URL:
        <br>• <code>madrid/latina/aluche</code>
        <br>• <code>boadilla-del-monte-madrid</code>
        <br>• <code>alcorcon/centro</code>
        <br><br>If using CSV, ensure it has a <b>'zona'</b> column with these paths.
        </div>
        """,
        unsafe_allow_html=True,
    )

# Show preview of parsed zones
if zonas:
    st.markdown(
        f'<p style="color:#6ee7b7; font-size:0.9rem; margin-top:0.3rem;">🟢 Will search {len(zonas)} zone(s): '
        + ", ".join(f"<b>{z}</b>" for z in zonas)
        + "</p>",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Search trigger
# ---------------------------------------------------------------------------

search_clicked = st.button("🔍 Search & Analyze", disabled=(not zonas))

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

if search_clicked and zonas:
    progress_placeholder = st.empty()
    status_text = st.empty()

    status_text.markdown(
        '<p style="color:#a78bfa;">⏳ Launching browser and scraping Idealista…</p>',
        unsafe_allow_html=True,
    )

    def on_progress(zone, page_num, n_collected):
        status_text.markdown(
            f'<p style="color:#a78bfa;">⏳ Zone <b>{zone}</b> — page {page_num}, {n_collected} listing(s) collected so far…</p>',
            unsafe_allow_html=True,
        )

    captcha_placeholder = st.empty()

    def on_status(message):
        if "CAPTCHA" in message.upper():
            captcha_placeholder.warning(
                f"⚠️ **{message}**\n\n"
                "Switch to the Chromium browser window and solve the slider CAPTCHA. "
                "The scraper will resume automatically once solved."
            )
        else:
            captcha_placeholder.info(message)

    # Run scraper
    raw_data = run_all_zones(
        zone_names=zonas,
        max_price=int(max_price),
        min_rooms=int(min_rooms),
        max_listings=15,
        headless=headless_mode,
        progress_callback=on_progress,
        status_callback=on_status,
    )

    captcha_placeholder.empty()
    status_text.empty()

    if not raw_data:
        st.error(
            "❌ No listings were collected. Possible causes:\n"
            "- Zone slug didn't match any Idealista URL — check the path in your browser.\n"
            "- Idealista served a CAPTCHA — **disable headless mode** in the sidebar, "
            "then solve the slider in the browser window when prompted.\n"
            "- Your IP may be temporarily rate-limited. Wait a few minutes and try again."
        )
        st.stop()

    # Process & rank
    df = process_and_rank(
        raw=raw_data,
        max_price=int(max_price),
        min_rooms=int(min_rooms),
        min_restrooms=int(min_restrooms),
    )

    if df.empty:
        st.warning(
            "⚠️ Data was collected but no listings passed the filter criteria. "
            "Try relaxing Max Price, Min Rooms, or Min Restrooms."
        )
        st.stop()

    # --- Summary metrics ---
    best_ppm2   = df["€/m²"].iloc[0] if not df.empty else "—"
    best_price  = df["Price (€)"].iloc[0] if not df.empty else "—"
    zones_found = df["Zone"].nunique()

    st.markdown(
        f"""
        <div class="metric-row">
            <div class="metric-card">
                <div class="value">{len(df)}</div>
                <div class="label">Listings found</div>
            </div>
            <div class="metric-card">
                <div class="value">{zones_found}</div>
                <div class="label">Zones with results</div>
            </div>
            <div class="metric-card">
                <div class="value">{best_ppm2} €</div>
                <div class="label">Best €/m²</div>
            </div>
            <div class="metric-card">
                <div class="value">{best_price}</div>
                <div class="label">Cheapest listing</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Build clickable link column ---
    def make_clickable(url: str) -> str:
        if url:
            return f'<a href="{url}" target="_blank" style="color:#a78bfa;">🔗 View</a>'
        return "—"

    # Render top N results
    st.markdown(f'<p class="section-label">🏆 Top {min(top_n, len(df))} Results</p>', unsafe_allow_html=True)
    display_top = df.head(top_n).copy()
    display_top["Link"] = display_top["Link"].apply(make_clickable)

    st.write(
        display_top.to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )

    # --- Show more ---
    if len(df) > top_n:
        with st.expander(f"📋 Show more results — up to Top 15 ({len(df) - top_n} more)"):
            display_more = df.iloc[top_n:].copy()
            display_more["Link"] = display_more["Link"].apply(make_clickable)
            st.write(
                display_more.to_html(escape=False, index=False),
                unsafe_allow_html=True,
            )

    # --- Download ---
    st.markdown("<br>", unsafe_allow_html=True)
    csv_export = df.copy()
    csv_export["Link"] = raw_data  # raw URLs for the export
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="⬇️ Download results as CSV",
        data=csv_buffer.getvalue(),
        file_name="idealista_results.csv",
        mime="text/csv",
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(
    '<p style="text-align:center; color:#334155; font-size:0.8rem;">'
    "Idealista Rental Analyzer · Data scraped in real time · For personal use only"
    "</p>",
    unsafe_allow_html=True,
)
