"""Centralized Plotly chart factory for the Mutual Fund Analytics Platform.

Every public method creates a ``go.Figure``, applies the dark dashboard
theme via :func:`charts.theme.style_figure`, and returns the figure
ready for rendering in Streamlit.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from charts.theme import COLORS, CATEGORY_COLORS, style_figure, get_chart_layout


class ChartFactory:
    """Static factory that produces consistently-themed Plotly figures."""

    # ------------------------------------------------------------------
    # Line charts
    # ------------------------------------------------------------------

    @staticmethod
    def line_chart(
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str,
        color_col: str | None = None,
        height: int = 400,
    ) -> go.Figure:
        """Single or multi-series line chart.

        Args:
            df: Source data.
            x: Column for the x-axis.
            y: Column for the y-axis.
            title: Chart title.
            color_col: Optional column to split into coloured series.
            height: Figure height in pixels.

        Returns:
            Styled ``go.Figure``.
        """
        color_map = CATEGORY_COLORS if color_col else None
        fig = px.line(
            df,
            x=x,
            y=y,
            color=color_col,
            color_discrete_map=color_map,
        )
        fig.update_traces(line=dict(width=2))
        return style_figure(fig, title=title, height=height)

    @staticmethod
    def multi_line_chart(
        df: pd.DataFrame,
        x: str,
        y_columns: list[str],
        title: str,
        labels: list[str] | None = None,
        height: int = 400,
    ) -> go.Figure:
        """Overlay multiple y-columns as separate lines.

        Args:
            df: Source data.
            x: Column for the x-axis.
            y_columns: List of column names to plot.
            labels: Optional display names (same order as *y_columns*).
            height: Figure height in pixels.

        Returns:
            Styled ``go.Figure``.
        """
        palette = [
            COLORS["primary"],
            COLORS["accent"],
            COLORS["success"],
            COLORS["warning"],
            COLORS["danger"],
            COLORS["secondary"],
            COLORS["info"],
        ]
        fig = go.Figure()
        for idx, col in enumerate(y_columns):
            name = labels[idx] if labels and idx < len(labels) else col
            fig.add_trace(
                go.Scatter(
                    x=df[x],
                    y=df[col],
                    mode="lines",
                    name=name,
                    line=dict(width=2, color=palette[idx % len(palette)]),
                )
            )
        return style_figure(fig, title=title, height=height)

    # ------------------------------------------------------------------
    # Area chart
    # ------------------------------------------------------------------

    @staticmethod
    def area_chart(
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str,
        color_col: str | None = None,
        height: int = 400,
    ) -> go.Figure:
        """Filled area chart.

        Args:
            df: Source data.
            x: Column for the x-axis.
            y: Column for the y-axis.
            title: Chart title.
            color_col: Optional column for colour grouping.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        color_map = CATEGORY_COLORS if color_col else None
        fig = px.area(
            df,
            x=x,
            y=y,
            color=color_col,
            color_discrete_map=color_map,
        )
        fig.update_traces(line=dict(width=2))
        return style_figure(fig, title=title, height=height)

    # ------------------------------------------------------------------
    # Bar charts
    # ------------------------------------------------------------------

    @staticmethod
    def bar_chart(
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str,
        color_col: str | None = None,
        orientation: str = "v",
        height: int = 400,
    ) -> go.Figure:
        """Vertical or horizontal bar chart.

        Args:
            df: Source data.
            x: Column for the category axis.
            y: Column for the value axis.
            title: Chart title.
            color_col: Optional column for bar colouring.
            orientation: ``'v'`` for vertical, ``'h'`` for horizontal.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        color_map = CATEGORY_COLORS if color_col else None
        fig = px.bar(
            df,
            x=x,
            y=y,
            color=color_col,
            orientation=orientation,
            color_discrete_map=color_map,
        )
        if not color_col:
            fig.update_traces(marker_color=COLORS["primary"])
        return style_figure(fig, title=title, height=height)

    @staticmethod
    def grouped_bar_chart(
        df: pd.DataFrame,
        x: str,
        y_columns: list[str],
        title: str,
        height: int = 400,
    ) -> go.Figure:
        """Grouped bar chart with multiple y-columns side-by-side.

        Args:
            df: Source data.
            x: Column for the category axis.
            y_columns: Columns to group.
            title: Chart title.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        palette = [
            COLORS["primary"],
            COLORS["accent"],
            COLORS["success"],
            COLORS["warning"],
            COLORS["danger"],
            COLORS["secondary"],
        ]
        fig = go.Figure()
        for idx, col in enumerate(y_columns):
            fig.add_trace(
                go.Bar(
                    x=df[x],
                    y=df[col],
                    name=col,
                    marker_color=palette[idx % len(palette)],
                )
            )
        fig.update_layout(barmode="group")
        return style_figure(fig, title=title, height=height)

    @staticmethod
    def horizontal_bar_chart(
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str,
        color_col: str | None = None,
        height: int = 400,
    ) -> go.Figure:
        """Convenience wrapper for a horizontal bar chart.

        Args:
            df: Source data.
            x: Value column (horizontal length).
            y: Category column (vertical labels).
            title: Chart title.
            color_col: Optional colour column.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        color_map = CATEGORY_COLORS if color_col else None
        fig = px.bar(
            df,
            x=x,
            y=y,
            color=color_col,
            orientation="h",
            color_discrete_map=color_map,
        )
        if not color_col:
            fig.update_traces(marker_color=COLORS["primary"])
        return style_figure(fig, title=title, height=height)

    # ------------------------------------------------------------------
    # Pie / donut
    # ------------------------------------------------------------------

    @staticmethod
    def pie_chart(
        df: pd.DataFrame,
        names: str,
        values: str,
        title: str,
        hole: float = 0.4,
        height: int = 400,
    ) -> go.Figure:
        """Donut chart (pie chart with a hole).

        Args:
            df: Source data.
            names: Column for slice labels.
            values: Column for slice sizes.
            title: Chart title.
            hole: Size of the donut hole (0 → full pie).
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        # Build a colour list aligned to the names
        color_list = [
            CATEGORY_COLORS.get(name, COLORS["primary"])
            for name in df[names]
        ]
        fig = go.Figure(
            go.Pie(
                labels=df[names],
                values=df[values],
                hole=hole,
                marker=dict(colors=color_list, line=dict(color=COLORS["background"], width=2)),
                textfont=dict(color=COLORS["text"], size=11),
                textinfo="percent+label",
                hoverinfo="label+value+percent",
            )
        )
        return style_figure(fig, title=title, height=height)

    # ------------------------------------------------------------------
    # Scatter / bubble
    # ------------------------------------------------------------------

    @staticmethod
    def scatter_chart(
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str,
        size_col: str | None = None,
        color_col: str | None = None,
        hover_name: str | None = None,
        height: int = 400,
    ) -> go.Figure:
        """Scatter plot with optional size and colour encoding.

        Args:
            df: Source data.
            x: Column for the x-axis.
            y: Column for the y-axis.
            title: Chart title.
            size_col: Optional column for marker size.
            color_col: Optional column for marker colour.
            hover_name: Column shown on hover.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        color_map = CATEGORY_COLORS if color_col else None
        fig = px.scatter(
            df,
            x=x,
            y=y,
            size=size_col,
            color=color_col,
            hover_name=hover_name,
            color_discrete_map=color_map,
        )
        if not color_col:
            fig.update_traces(marker=dict(color=COLORS["primary"], opacity=0.8))
        return style_figure(fig, title=title, height=height)

    @staticmethod
    def bubble_chart(
        df: pd.DataFrame,
        x: str,
        y: str,
        size: str,
        title: str,
        color_col: str | None = None,
        hover_name: str | None = None,
        height: int = 400,
    ) -> go.Figure:
        """Bubble chart (scatter with mandatory size encoding).

        Args:
            df: Source data.
            x: Column for the x-axis.
            y: Column for the y-axis.
            size: Column for bubble size.
            title: Chart title.
            color_col: Optional column for colour grouping.
            hover_name: Column shown on hover.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        color_map = CATEGORY_COLORS if color_col else None
        fig = px.scatter(
            df,
            x=x,
            y=y,
            size=size,
            color=color_col,
            hover_name=hover_name,
            color_discrete_map=color_map,
            size_max=50,
        )
        if not color_col:
            fig.update_traces(marker=dict(color=COLORS["accent"], opacity=0.75))
        return style_figure(fig, title=title, height=height)

    # ------------------------------------------------------------------
    # Heatmap
    # ------------------------------------------------------------------

    @staticmethod
    def heatmap(
        df: pd.DataFrame,
        title: str,
        height: int = 400,
    ) -> go.Figure:
        """Correlation-style heatmap.

        Args:
            df: Square (or rectangular) DataFrame of values.
            title: Chart title.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        fig = go.Figure(
            go.Heatmap(
                z=df.values,
                x=df.columns.tolist(),
                y=df.index.tolist(),
                colorscale=[
                    [0.0, COLORS["danger"]],
                    [0.5, COLORS["background"]],
                    [1.0, COLORS["success"]],
                ],
                zmin=-1,
                zmax=1,
                text=df.round(2).values,
                texttemplate="%{text}",
                textfont=dict(size=11, color=COLORS["text"]),
                hovertemplate="x: %{x}<br>y: %{y}<br>value: %{z:.2f}<extra></extra>",
                colorbar=dict(
                    tickfont=dict(color=COLORS["text_muted"]),
                    title=dict(font=dict(color=COLORS["text_muted"])),
                ),
            )
        )
        return style_figure(fig, title=title, height=height)

    # ------------------------------------------------------------------
    # Treemap
    # ------------------------------------------------------------------

    @staticmethod
    def treemap(
        df: pd.DataFrame,
        path: list[str],
        values: str,
        title: str,
        color_col: str | None = None,
        height: int = 500,
    ) -> go.Figure:
        """Treemap chart for hierarchical data.

        Args:
            df: Source data.
            path: List of columns defining hierarchy levels.
            values: Column for tile sizing.
            title: Chart title.
            color_col: Optional column for colour encoding.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        fig = px.treemap(
            df,
            path=[px.Constant("All")] + path,
            values=values,
            color=color_col,
            color_discrete_map=CATEGORY_COLORS if color_col else None,
        )
        fig.update_traces(
            marker=dict(cornerradius=4),
            textfont=dict(color=COLORS["text"]),
            root_color=COLORS["background"],
        )
        return style_figure(fig, title=title, height=height)

    # ------------------------------------------------------------------
    # Radar chart
    # ------------------------------------------------------------------

    @staticmethod
    def radar_chart(
        categories: list[str],
        values: list[float],
        title: str,
        height: int = 400,
    ) -> go.Figure:
        """Radar / spider chart using Scatterpolar.

        Args:
            categories: Spoke labels.
            values: Values for each spoke.
            title: Chart title.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        # Close the polygon
        plot_categories = list(categories) + [categories[0]]
        plot_values = list(values) + [values[0]]
        fig = go.Figure(
            go.Scatterpolar(
                r=plot_values,
                theta=plot_categories,
                fill="toself",
                fillcolor=f"rgba(99, 102, 241, 0.25)",
                line=dict(color=COLORS["primary"], width=2),
                marker=dict(color=COLORS["primary"], size=6),
            )
        )
        fig.update_layout(
            polar=dict(
                bgcolor=COLORS["background"],
                radialaxis=dict(
                    visible=True,
                    gridcolor=COLORS["surface_light"],
                    linecolor=COLORS["border"],
                    tickfont=dict(color=COLORS["text_muted"], size=10),
                ),
                angularaxis=dict(
                    gridcolor=COLORS["surface_light"],
                    linecolor=COLORS["border"],
                    tickfont=dict(color=COLORS["text_muted"], size=11),
                ),
            )
        )
        return style_figure(fig, title=title, height=height)

    # ------------------------------------------------------------------
    # Histogram
    # ------------------------------------------------------------------

    @staticmethod
    def histogram(
        df: pd.DataFrame,
        x: str,
        title: str,
        nbins: int = 30,
        height: int = 400,
    ) -> go.Figure:
        """Histogram for distribution analysis.

        Args:
            df: Source data.
            x: Column to bin.
            title: Chart title.
            nbins: Number of bins.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        fig = px.histogram(df, x=x, nbins=nbins)
        fig.update_traces(marker_color=COLORS["primary"], marker_line_width=0)
        return style_figure(fig, title=title, height=height)

    # ------------------------------------------------------------------
    # Gauge chart
    # ------------------------------------------------------------------

    @staticmethod
    def gauge_chart(
        value: float,
        title: str,
        min_val: float = 0,
        max_val: float = 100,
        height: int = 300,
    ) -> go.Figure:
        """Gauge / speedometer chart for single KPI values.

        Args:
            value: Current value.
            title: Gauge title.
            min_val: Minimum of the gauge range.
            max_val: Maximum of the gauge range.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        range_span = max_val - min_val
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=value,
                title=dict(text=title, font=dict(size=14, color=COLORS["text"])),
                number=dict(font=dict(size=28, color=COLORS["text"])),
                gauge=dict(
                    axis=dict(
                        range=[min_val, max_val],
                        tickfont=dict(color=COLORS["text_muted"], size=10),
                        tickcolor=COLORS["border"],
                    ),
                    bar=dict(color=COLORS["primary"]),
                    bgcolor=COLORS["surface"],
                    borderwidth=1,
                    bordercolor=COLORS["border"],
                    steps=[
                        dict(
                            range=[min_val, min_val + range_span * 0.33],
                            color=COLORS["success"],
                        ),
                        dict(
                            range=[min_val + range_span * 0.33, min_val + range_span * 0.66],
                            color=COLORS["warning"],
                        ),
                        dict(
                            range=[min_val + range_span * 0.66, max_val],
                            color=COLORS["danger"],
                        ),
                    ],
                    threshold=dict(
                        line=dict(color=COLORS["text"], width=3),
                        thickness=0.8,
                        value=value,
                    ),
                ),
            )
        )
        return style_figure(fig, height=height)

    # ------------------------------------------------------------------
    # Sparkline
    # ------------------------------------------------------------------

    @staticmethod
    def sparkline(
        values: list[float] | pd.Series,
        height: int = 60,
        width: int = 150,
    ) -> go.Figure:
        """Minimal inline sparkline chart with no axes or labels.

        Args:
            values: Sequence of numeric values.
            height: Figure height in pixels.
            width: Figure width in pixels.

        Returns:
            Styled ``go.Figure``.
        """
        series = list(values)
        trend_color = COLORS["success"] if series[-1] >= series[0] else COLORS["danger"]
        fig = go.Figure(
            go.Scatter(
                y=series,
                mode="lines",
                line=dict(color=trend_color, width=1.5),
                fill="tozeroy",
                fillcolor=trend_color.replace(")", ", 0.15)").replace("rgb", "rgba")
                if trend_color.startswith("rgb")
                else f"rgba({int(trend_color[1:3], 16)}, {int(trend_color[3:5], 16)}, {int(trend_color[5:7], 16)}, 0.15)",
                hoverinfo="skip",
            )
        )
        fig.update_layout(
            width=width,
            height=height,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            showlegend=False,
        )
        return fig

    # ------------------------------------------------------------------
    # KPI card figure
    # ------------------------------------------------------------------

    @staticmethod
    def kpi_card_figure(
        value: float,
        delta: float | None = None,
        title: str = "",
        height: int = 120,
    ) -> go.Figure:
        """Number indicator suitable for embedding in a KPI card.

        Args:
            value: Primary numeric value.
            delta: Optional delta value shown as change indicator.
            title: Label above the number.
            height: Figure height.

        Returns:
            Styled ``go.Figure``.
        """
        indicator_kwargs: dict = dict(
            mode="number+delta" if delta is not None else "number",
            value=value,
            title=dict(
                text=title,
                font=dict(size=12, color=COLORS["text_muted"]),
            ),
            number=dict(font=dict(size=28, color=COLORS["text"])),
        )
        if delta is not None:
            indicator_kwargs["delta"] = dict(
                reference=value - delta,
                relative=False,
                increasing=dict(color=COLORS["success"]),
                decreasing=dict(color=COLORS["danger"]),
                font=dict(size=14),
            )
        fig = go.Figure(go.Indicator(**indicator_kwargs))
        fig.update_layout(
            height=height,
            margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig
