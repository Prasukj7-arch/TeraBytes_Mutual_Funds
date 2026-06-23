"""Plotly theme configuration for the Mutual Fund Analytics dashboard.

Defines colour palettes, a custom dark template, and helper functions
that ensure every chart produced by the platform has a consistent,
premium look.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio


# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------

COLORS: dict[str, str] = {
    "primary": "#6366F1",       # indigo
    "secondary": "#8B5CF6",     # purple
    "accent": "#06B6D4",        # cyan
    "success": "#10B981",       # emerald
    "danger": "#EF4444",        # red
    "warning": "#F59E0B",       # amber
    "info": "#3B82F6",          # blue
    "background": "#0F172A",    # slate 900
    "surface": "#1E293B",       # slate 800
    "surface_light": "#334155", # slate 700
    "text": "#F8FAFC",          # slate 50
    "text_muted": "#94A3B8",    # slate 400
    "border": "#475569",        # slate 600
}

CATEGORY_COLORS: dict[str, str] = {
    "Large Cap": "#6366F1",
    "Mid Cap": "#8B5CF6",
    "Small Cap": "#A78BFA",
    "Multi Cap": "#06B6D4",
    "Flexi Cap": "#22D3EE",
    "ELSS": "#10B981",
    "Sectoral": "#F59E0B",
    "Thematic": "#FB923C",
    "Index Fund": "#3B82F6",
    "Debt": "#14B8A6",
    "Hybrid": "#EC4899",
    "Liquid": "#64748B",
    "Gilt": "#84CC16",
    "International": "#E879F9",
    "Balanced Advantage": "#F472B6",
    "Contra": "#FACC15",
    "Value": "#2DD4BF",
    "Focused": "#818CF8",
    "Dividend Yield": "#34D399",
    "Other": "#94A3B8",
}

GRADIENT_COLORS: list[str] = [
    "#6366F1",
    "#818CF8",
    "#A78BFA",
    "#8B5CF6",
    "#7C3AED",
    "#6D28D9",
    "#5B21B6",
    "#4C1D95",
    "#06B6D4",
    "#0891B2",
]


# ---------------------------------------------------------------------------
# Custom Plotly template
# ---------------------------------------------------------------------------

_layout = go.Layout(
    font=dict(family="Inter, system-ui, sans-serif", color=COLORS["text"], size=12),
    paper_bgcolor=COLORS["background"],
    plot_bgcolor=COLORS["background"],
    title=dict(
        font=dict(size=16, color=COLORS["text"]),
        x=0.0,
        xanchor="left",
        yanchor="top",
        pad=dict(l=0, t=0),
    ),
    xaxis=dict(
        gridcolor=COLORS["surface_light"],
        gridwidth=1,
        linecolor=COLORS["border"],
        linewidth=1,
        zerolinecolor=COLORS["surface_light"],
        zerolinewidth=1,
        tickfont=dict(color=COLORS["text_muted"], size=11),
        title_font=dict(color=COLORS["text_muted"], size=12),
    ),
    yaxis=dict(
        gridcolor=COLORS["surface_light"],
        gridwidth=1,
        linecolor=COLORS["border"],
        linewidth=1,
        zerolinecolor=COLORS["surface_light"],
        zerolinewidth=1,
        tickfont=dict(color=COLORS["text_muted"], size=11),
        title_font=dict(color=COLORS["text_muted"], size=12),
    ),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text_muted"], size=11),
        borderwidth=0,
    ),
    margin=dict(l=60, r=20, t=50, b=50),
    hoverlabel=dict(
        bgcolor=COLORS["surface"],
        font_size=12,
        font_color=COLORS["text"],
        bordercolor=COLORS["border"],
    ),
    colorway=[
        COLORS["primary"],
        COLORS["accent"],
        COLORS["success"],
        COLORS["warning"],
        COLORS["danger"],
        COLORS["secondary"],
        COLORS["info"],
        "#EC4899",
        "#84CC16",
        "#F97316",
    ],
)

PLOTLY_TEMPLATE = go.layout.Template(layout=_layout)
PLOTLY_TEMPLATE.layout.annotationdefaults = dict(
    font=dict(color=COLORS["text_muted"], size=11)
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def apply_theme() -> None:
    """Register and set the custom dark template as the Plotly default."""
    pio.templates["mf_dark"] = PLOTLY_TEMPLATE
    pio.templates.default = "mf_dark"


def get_chart_layout(**overrides: object) -> dict:
    """Return a standard layout dict with dark background and proper margins.

    Any keyword argument is merged on top of the defaults, allowing
    per-chart overrides (e.g. ``height``, ``xaxis_title``).

    Returns:
        Dictionary suitable for ``fig.update_layout(**result)``.
    """
    base: dict = dict(
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font=dict(family="Inter, system-ui, sans-serif", color=COLORS["text"]),
        margin=dict(l=60, r=20, t=50, b=50),
        hoverlabel=dict(
            bgcolor=COLORS["surface"],
            font_size=12,
            font_color=COLORS["text"],
            bordercolor=COLORS["border"],
        ),
        showlegend=True,
        legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
    )
    base.update(overrides)
    return base


def style_figure(
    fig: go.Figure,
    title: str | None = None,
    height: int = 400,
) -> go.Figure:
    """Apply the dark theme to an existing Plotly figure.

    Args:
        fig: A ``go.Figure`` instance.
        title: Optional chart title.
        height: Desired figure height in pixels.

    Returns:
        The same figure, mutated in place (also returned for chaining).
    """
    layout_updates = get_chart_layout(height=height)
    if title is not None:
        layout_updates["title"] = dict(
            text=title,
            font=dict(size=16, color=COLORS["text"]),
            x=0.0,
            xanchor="left",
        )
    fig.update_layout(**layout_updates)
    fig.update_layout(template=PLOTLY_TEMPLATE)
    return fig
