"""
Shared visual identity for the app -- fonts, CSS, and the signature
"ledger strip" component reused across pages.

Dark theme design tokens:

    App background   #0B1120  (near-black navy)
    Sidebar          #0B1120  (same, so it reads as one surface, not two)
    Card bg          #151E32  (raised slate)
    Border           #1F2A44
    Text             #E5E7EB
    Muted text       #8B94A7
    Accent (primary) #14B8A6  (teal)
    Auto-approved    #22C55E  (green)
    Human review     #F59E0B  (amber)
    Exception        #EF4444  (red)

Typography: Space Grotesk for headings, Inter for body, JetBrains Mono
for IDs/amounts/UTRs -- this is a ledger, numbers should line up in a
monospace grid.
"""

import streamlit as st

COLORS = {
    "bg": "#0B1120",
    "sidebar": "#0B1120",
    "card": "#151E32",
    "border": "#1F2A44",
    "text": "#E5E7EB",
    "muted": "#8B94A7",
    "accent": "#14B8A6",
    "auto_approved": "#22C55E",
    "human_review": "#F59E0B",
    "exception": "#EF4444",
}


def inject_theme() -> None:
    """Call once per page, right after st.set_page_config()."""
    st.markdown(f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

    <style>
        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
            color: {COLORS['text']};
        }}

        h1, h2, h3 {{
            font-family: 'Space Grotesk', sans-serif !important;
            font-weight: 600 !important;
            letter-spacing: -0.01em;
        }}

        [data-testid="stMetricValue"], code, .mono {{
            font-family: 'JetBrains Mono', monospace !important;
        }}

        /* --- sidebar shell --- */
        [data-testid="stSidebar"] {{
            background-color: {COLORS['sidebar']};
            border-right: 1px solid {COLORS['border']};
        }}

        /* --- nav menu: give links breathing room, rounded hover, active highlight --- */
        [data-testid="stSidebarNav"] {{
            padding-top: 4px;
        }}
        section[data-testid="stSidebar"] a {{
            border-radius: 8px !important;
            margin: 2px 8px !important;
            padding: 10px 12px !important;
            font-weight: 500 !important;
            color: {COLORS['muted']} !important;
            transition: background-color 0.15s ease, color 0.15s ease;
        }}
        section[data-testid="stSidebar"] a:hover {{
            background-color: {COLORS['card']} !important;
            color: {COLORS['text']} !important;
        }}
        section[data-testid="stSidebar"] a[aria-current="page"] {{
            background-color: {COLORS['accent']}22 !important;
            color: {COLORS['accent']} !important;
            border-left: 3px solid {COLORS['accent']};
        }}
        /* section label above the nav links (e.g. "MENU") */
        [data-testid="stSidebarNav"] span {{
            color: {COLORS['muted']} !important;
            text-transform: uppercase;
            font-size: 0.72rem !important;
            letter-spacing: 0.08em;
            font-weight: 600 !important;
        }}

        /* --- card-style containers --- */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {COLORS['card']};
            border-radius: 12px;
            border: 1px solid {COLORS['border']};
        }}

        /* --- buttons --- */
        .stButton > button {{
            border-radius: 8px;
            font-weight: 500;
            border: 1px solid {COLORS['border']};
            color: {COLORS['text']};
        }}
        .stButton > button[kind="primary"] {{
            background-color: {COLORS['accent']};
            border: none;
            color: #06251F;
        }}

        [data-testid="stMetricLabel"] {{
            color: {COLORS['muted']} !important;
            font-size: 0.85rem;
        }}

        /* --- overall page rhythm: the cramped feeling comes from too little
           breathing room around the main block and inside cards --- */
        .block-container {{
            padding-top: 2.2rem;
            padding-bottom: 3rem;
            max-width: 1100px;
        }}

        /* space between stacked top-level elements (headers, cards, etc.) */
        [data-testid="stVerticalBlock"] > div {{
            margin-bottom: 4px;
        }}

        h1 {{ margin-bottom: 4px !important; }}
        h2, h3 {{ margin-bottom: 14px !important; margin-top: 4px !important; }}

        /* card padding + internal spacing */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {COLORS['card']};
            border-radius: 12px;
            border: 1px solid {COLORS['border']};
            padding: 22px 26px;
            margin-bottom: 4px;
        }}

        /* gap between columns so metrics/cards don't touch */
        [data-testid="stHorizontalBlock"] {{
            gap: 1.25rem;
        }}

        /* buttons: consistent spacing, no flush edges */
        .stButton > button {{
            border-radius: 8px;
            font-weight: 500;
            border: 1px solid {COLORS['border']};
            color: {COLORS['text']};
            padding: 0.5rem 1.1rem;
        }}
        .stButton > button[kind="primary"] {{
            background-color: {COLORS['accent']};
            border: none;
            color: #06251F;
        }}
        .stButton > button:hover {{
            border-color: {COLORS['accent']};
            color: {COLORS['accent']};
        }}

        /* --- extend dark styling to elements the base theme misses --- */
        [data-testid="stExpander"] {{
            background-color: {COLORS['card']};
            border: 1px solid {COLORS['border']};
            border-radius: 10px;
            margin-bottom: 8px;
        }}
        [data-testid="stExpander"] summary {{
            padding: 10px 14px !important;
        }}

        [data-testid="stDataFrame"] {{
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            overflow: hidden;
        }}

        div[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {{
            background-color: {COLORS['bg']} !important;
            border-color: {COLORS['border']} !important;
            color: {COLORS['text']} !important;
        }}

        [data-testid="stFileUploaderDropzone"] {{
            background-color: {COLORS['bg']};
            border: 1px dashed {COLORS['border']};
            border-radius: 10px;
        }}

        /* alerts (info/success/warning/error) get card-consistent radius */
        [data-testid="stAlert"] {{
            border-radius: 10px;
        }}

        /* status widget (used during the live reconciliation run) */
        [data-testid="stStatusWidget"] {{
            background-color: {COLORS['card']};
            border: 1px solid {COLORS['border']};
            border-radius: 10px;
        }}

        hr {{
            border-color: {COLORS['border']};
            margin: 20px 0;
        }}
    </style>
    """, unsafe_allow_html=True)


def ledger_strip(auto_approved: int, human_review: int, exception: int, height: int = 28) -> None:
    """
    The signature visual: a horizontal proportional bar showing the three
    reconciliation buckets as colored segments -- literally a ledger,
    rendered as one.
    """
    total = max(auto_approved + human_review + exception, 1)
    pct_auto = auto_approved / total * 100
    pct_review = human_review / total * 100
    pct_exception = exception / total * 100

    st.markdown(f"""
    <div style="display:flex; width:100%; height:{height}px; border-radius:8px; overflow:hidden; margin-bottom:8px;">
        <div style="width:{pct_auto}%; background-color:{COLORS['auto_approved']};"></div>
        <div style="width:{pct_review}%; background-color:{COLORS['human_review']};"></div>
        <div style="width:{pct_exception}%; background-color:{COLORS['exception']};"></div>
    </div>
    <div style="display:flex; gap:20px; font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:{COLORS['muted']};">
        <span><span style="color:{COLORS['auto_approved']};">&#9679;</span> Auto-approved &nbsp;{auto_approved}</span>
        <span><span style="color:{COLORS['human_review']};">&#9679;</span> Human review &nbsp;{human_review}</span>
        <span><span style="color:{COLORS['exception']};">&#9679;</span> Exception &nbsp;{exception}</span>
    </div>
    """, unsafe_allow_html=True)


def status_badge(status: str) -> str:
    color_map = {
        "auto_approved": COLORS["auto_approved"],
        "human_review": COLORS["human_review"],
        "exception": COLORS["exception"],
    }
    color = color_map.get(status, COLORS["muted"])
    label = status.replace("_", " ").title()
    return f'<span style="background-color:{color}22; color:{color}; padding:2px 10px; border-radius:999px; font-size:0.8rem; font-weight:500;">{label}</span>'