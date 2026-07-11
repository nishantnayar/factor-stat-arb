"""
CSS Configuration for Trading System Streamlit UI
Design system consistent with nishantnayar.vercel.app
  - Playfair Display: page titles & section headings
  - DM Sans: body, labels, UI text
  - DM Mono: ALL financial numbers (prices, P&L, volumes, %)
  - Paper-white background, ink text, flat cards with subtle borders
"""

# Color palette - matches portfolio site with trader-specific additions
COLORS = {
    # Base palette (portfolio site)
    "ink": "#1a1a1a",                   # Primary text
    "ink_mid": "#6b6b6b",               # Secondary text
    "ink_light": "#9e9e9e",             # Tertiary / muted text
    "paper": "#FAFAF8",                 # Page background (warm white)
    "paper_warm": "#F5F4F0",            # Card hover / secondary bg
    "border": "rgba(26,26,26,0.08)",    # Subtle ink border (10% opacity)
    "accent": "#1a1a1a",                # Accent - same as ink

    # Trader-specific (deviation from portfolio site - required for trading)
    "profit": "#2A7A4B",                # Positive P&L - green
    "loss": "#C0392B",                  # Negative P&L - red
    "market_open": "#2A7A4B",           # Market open status
    "market_closed": "#C0392B",         # Market closed status
    "market_prepost": "#D97706",        # Pre/after-hours - amber
    "neutral": "#6b6b6b",               # Flat / no change
}

# Typography - direct match to portfolio site
FONTS = {
    "display": "'Playfair Display', Georgia, 'Times New Roman', serif",
    "body": "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    "mono": "'DM Mono', 'Fira Code', 'Monaco', 'Consolas', monospace",
}

# Spacing
SPACING = {
    "xs": "0.25rem",
    "small": "0.5rem",
    "medium": "1rem",
    "large": "1.5rem",
    "xlarge": "2rem",
    "xxlarge": "3rem",
}

# Border radius - portfolio site uses rounded-sm (4px)
BORDER_RADIUS = {
    "small": "2px",
    "medium": "4px",
    "large": "6px",
    "xlarge": "8px",
}

# Flat design - minimal shadows (portfolio site uses none; we allow one subtle level)
SHADOWS = {
    "none": "none",
    "subtle": "0 1px 3px rgba(26,26,26,0.06)",
}

# Transitions
ANIMATIONS = {
    "fast": "0.15s",
    "normal": "0.2s",
    "slow": "0.3s",
}


def generate_css_variables() -> str:
    """Generate CSS custom properties from configuration."""
    lines = [":root {"]

    for name, value in COLORS.items():
        lines.append(f"  --color-{name}: {value};")

    for name, value in FONTS.items():
        lines.append(f"  --font-{name}: {value};")

    for name, value in SPACING.items():
        lines.append(f"  --space-{name}: {value};")

    for name, value in BORDER_RADIUS.items():
        lines.append(f"  --radius-{name}: {value};")

    for name, value in SHADOWS.items():
        lines.append(f"  --shadow-{name}: {value};")

    for name, value in ANIMATIONS.items():
        lines.append(f"  --duration-{name}: {value};")

    lines.append("}")
    return "\n".join(lines) + "\n"


def get_theme_css() -> str:
    """Return theme-level CSS rules using the design variables."""
    return """
    /* -- Typography ------------------------------------------- */
    .main h1, .main h2 {
        font-family: var(--font-display) !important;
        font-weight: 500;
        color: var(--color-ink);
        letter-spacing: -0.01em;
    }
    .main h1 {
        font-size: 1.9rem;
        border-bottom: 1px solid var(--color-border);
        padding-bottom: 0.6rem;
        margin-bottom: 1.5rem;
    }
    .main h2 {
        font-size: 1.3rem;
        margin-top: 1.8rem;
        margin-bottom: 0.8rem;
    }
    .main h3, .main p, .main label, .stMarkdown {
        font-family: var(--font-body) !important;
        color: var(--color-ink);
    }
    .main h3 {
        font-size: 1rem;
        font-weight: 500;
        color: var(--color-ink_mid);
        text-transform: uppercase;
        letter-spacing: 0.07em;
        margin-top: 1.2rem;
        margin-bottom: 0.4rem;
    }

    /* -- Metric values use DM Mono ----------------------------- */
    [data-testid="stMetricValue"],
    [data-testid="stMetricDelta"] {
        font-family: var(--font-mono) !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
        color: var(--color-ink) !important;
    }

    /* -- Cards ------------------------------------------------- */
    .card {
        background: #ffffff;
        border: 1px solid var(--color-border);
        border-radius: var(--radius-medium);
        padding: var(--space-large);
        margin: var(--space-small) 0;
        transition: background var(--duration-normal) ease;
    }
    .card:hover {
        background: var(--color-paper_warm);
    }

    /* -- Market status banner ---------------------------------- */
    .market-banner {
        border-radius: var(--radius-medium);
        padding: 0.6rem 1.2rem;
        font-family: var(--font-body);
        font-size: 0.85rem;
        font-weight: 500;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 1.2rem;
    }
    .market-banner .market-time {
        font-family: var(--font-mono);
        font-size: 0.8rem;
        opacity: 0.85;
    }
    .market-open-banner {
        background: rgba(42,122,75,0.08);
        border: 1px solid rgba(42,122,75,0.2);
        color: var(--color-market_open);
    }
    .market-closed-banner {
        background: rgba(192,57,43,0.07);
        border: 1px solid rgba(192,57,43,0.18);
        color: var(--color-market_closed);
    }
    .market-prepost-banner {
        background: rgba(217,119,6,0.07);
        border: 1px solid rgba(217,119,6,0.18);
        color: var(--color-market_prepost);
    }

    /* -- P&L color helpers ------------------------------------- */
    .pnl-positive { color: var(--color-profit) !important; font-family: var(--font-mono); }
    .pnl-negative { color: var(--color-loss) !important;   font-family: var(--font-mono); }
    .pnl-neutral  { color: var(--color-neutral) !important; font-family: var(--font-mono); }

    /* -- Dataframe / table numbers ----------------------------- */
    .dataframe td, .dataframe th {
        font-family: var(--font-mono) !important;
        font-size: 0.82rem;
    }
    .dataframe th {
        font-family: var(--font-body) !important;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-size: 0.72rem;
        color: var(--color-ink_mid);
        background: var(--color-paper_warm) !important;
    }

    /* -- Metric container -------------------------------------- */
    .metric-container {
        background: #ffffff;
        border: 1px solid var(--color-border);
        border-radius: var(--radius-medium);
        padding: var(--space-medium);
        transition: background var(--duration-normal) ease;
    }
    .metric-container:hover {
        background: var(--color-paper_warm);
    }
    """


__all__ = [
    "COLORS", "FONTS", "SPACING", "BORDER_RADIUS", "SHADOWS", "ANIMATIONS",
    "generate_css_variables", "get_theme_css",
]
