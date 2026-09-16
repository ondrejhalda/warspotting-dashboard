# ============================================================
# WARSPOTTING — ACLED-STYLE EQUIPMENT LOSS CHART
# ============================================================

# Purpose:
#   Create an interactive weekly stacked bar chart
#   of Russian equipment losses.
#
# Source:
#   warspotting_raw.csv
#
# Logic:
#   - one bar = one week
#   - total height = total documented losses
#   - each segment = WarSpotting equipment category
#   - hover = sorted breakdown of categories for the selected week
#   - hover = highlight the week under the mouse
#   - click = lock the selected week
#   - legend = shows weekly equipment counts after selection
#
# Output:
#   equipment_weekly.html
#
# This is an analytical prototype.
# It does not modify the main data pipeline.
# ============================================================


from pathlib import Path
import json

import pandas as pd
import plotly.graph_objects as go


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = Path("warspotting_raw.csv")
OUTPUT_FILE = Path("equipment_weekly.html")


# ============================================================
# LOAD RAW DATA
# ============================================================

def load_data():

    print("=" * 60)
    print("LOADING WARSPOTTING RAW DATA")
    print("=" * 60)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    print(
        f"Raw records loaded: {len(df):,}"
    )

    required_columns = [
        "id",
        "date",
        "type",
        "lost_by"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    # --------------------------------------------------------
    # Convert date
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    if df["date"].isna().any():
        raise ValueError(
            "Invalid dates found in raw dataset."
        )

    # --------------------------------------------------------
    # Check equipment category
    # --------------------------------------------------------

    if df["type"].isna().any():
        raise ValueError(
            "Missing equipment categories found."
        )

    # --------------------------------------------------------
    # Make sure we are analysing Russian losses
    # --------------------------------------------------------

    unexpected_lost_by = (
        df["lost_by"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    unexpected_lost_by = [
        value
        for value in unexpected_lost_by
        if value != "Russia"
    ]

    if unexpected_lost_by:
        raise ValueError(
            "Unexpected lost_by values: "
            f"{unexpected_lost_by}"
        )

    return df


# ============================================================
# CREATE WEEKLY DATASET
# ============================================================

def create_weekly_dataset(df):

    print()
    print("=" * 60)
    print("CREATING WEEKLY EQUIPMENT DATA")
    print("=" * 60)

    data = df.copy()

    # --------------------------------------------------------
    # Monday-based week
    # --------------------------------------------------------

    data["week"] = (
        data["date"]
        - pd.to_timedelta(
            data["date"].dt.weekday,
            unit="D"
        )
    )

    # --------------------------------------------------------
    # Aggregate by week and WarSpotting equipment type
    # --------------------------------------------------------

    weekly = (
        data
        .groupby(
            ["week", "type"],
            as_index=False
        )
        .size()
        .rename(
            columns={
                "size": "losses"
            }
        )
        .sort_values(
            by=["week", "type"]
        )
        .reset_index(drop=True)
    )

    print(
        f"Weekly rows: {len(weekly):,}"
    )

    print(
        f"Equipment categories: "
        f"{weekly['type'].nunique()}"
    )

    return weekly


# ============================================================
# VALIDATION
# ============================================================

def validate_weekly_data(raw_df, weekly_df):

    print()
    print("=" * 60)
    print("WEEKLY DATA VALIDATION")
    print("=" * 60)

    # --------------------------------------------------------
    # 1. Overall total
    # --------------------------------------------------------

    raw_total = len(raw_df)

    weekly_total = weekly_df["losses"].sum()

    print(
        f"Raw records: {raw_total:,}"
    )

    print(
        f"Weekly aggregated records: "
        f"{weekly_total:,}"
    )

    if raw_total != weekly_total:

        raise ValueError(
            "Weekly aggregation does not match "
            "raw dataset: "
            f"raw={raw_total:,}, "
            f"weekly={weekly_total:,}"
        )

    print(
        "Raw vs weekly total: OK"
    )

    # --------------------------------------------------------
    # 2. Duplicate week/category combinations
    # --------------------------------------------------------

    duplicates = (
        weekly_df
        .duplicated(
            subset=["week", "type"]
        )
        .sum()
    )

    if duplicates > 0:

        raise ValueError(
            "Duplicate week/category combinations: "
            f"{duplicates}"
        )

    print(
        "Duplicate week/category combinations: 0"
    )

    # --------------------------------------------------------
    # 3. Negative values
    # --------------------------------------------------------

    negative_values = (
        weekly_df["losses"] < 0
    ).sum()

    if negative_values > 0:

        raise ValueError(
            f"Negative loss values: "
            f"{negative_values}"
        )

    print(
        "Negative loss values: 0"
    )

    # --------------------------------------------------------
    # 4. Categories
    # --------------------------------------------------------

    categories = weekly_df["type"].nunique()

    if categories == 0:

        raise ValueError(
            "No equipment categories found."
        )

    print(
        f"Equipment categories: {categories}"
    )

    print()
    print(
        "VALIDATION STATUS: OK"
    )


# ============================================================
# CATEGORY ORDER
# ============================================================

def get_category_order(df):

    # Order categories by their total number
    # of documented losses across the entire dataset.

    category_totals = (
        df
        .groupby("type")["losses"]
        .sum()
        .sort_values(
            ascending=False
        )
    )

    return category_totals.index.tolist()


# ============================================================
# COLOUR PALETTE
# ============================================================

def get_category_colors(categories):

    # Muted ACLED-inspired palette.

    palette = [
        "#4C78A8",
        "#F58518",
        "#54A24B",
        "#E45756",
        "#72B7B2",
        "#B279A2",
        "#FF9DA6",
        "#9D755D",
        "#BAB0AC",
        "#59A14F",
        "#EDC949",
        "#AF7AA1",
        "#76B7B2",
        "#F28E2B",
        "#E15759",
        "#5DA5DA",
        "#8CD17D",
        "#B6992D",
    ]

    return {
        category: palette[index % len(palette)]
        for index, category in enumerate(categories)
    }


# ============================================================
# CREATE ACLED-STYLE CHART
# ============================================================

def create_chart(weekly):

    print()
    print("=" * 60)
    print("CREATING INTERACTIVE CHART")
    print("=" * 60)

    categories = get_category_order(weekly)

    colors = get_category_colors(categories)

    fig = go.Figure()

    # --------------------------------------------------------
    # One stacked bar trace per equipment category
    # --------------------------------------------------------

    for category in categories:

        category_data = (
            weekly[
                weekly["type"] == category
            ]
            .sort_values("week")
        )

        base_color = colors[category]

        # ----------------------------------------------------
        # Convert HEX to RGB
        # ----------------------------------------------------

        rgb = tuple(
            int(
                base_color[i:i + 2],
                16
            )
            for i in (1, 3, 5)
        )

        # ----------------------------------------------------
        # Faded ACLED-style colour
        # ----------------------------------------------------

        faded_color = (
            f"rgba("
            f"{rgb[0]},"
            f"{rgb[1]},"
            f"{rgb[2]},"
            f"0.40)"
        )

        faded_colors = [
            faded_color
            for _ in range(
                len(category_data)
            )
        ]

        fig.add_trace(
            go.Bar(
                x=category_data["week"],
                y=category_data["losses"],
                name=category,

                marker={
                    "color": faded_colors,
                    "line": {
                        "color": (
                            "rgba("
                            "255,255,255,0.55)"
                        ),
                        "width": 0.5,
                    },
                },

                hovertemplate=(
                    "<extra></extra>"
                ),
            )
        )

    # --------------------------------------------------------
    # Layout
    # --------------------------------------------------------

    fig.update_layout(

        title={
            "text": (
                "Russian Equipment Losses — Weekly"
            ),
            "x": 0.5,
            "xanchor": "center",
        },

        barmode="stack",

        hovermode="closest",

        xaxis={
            "title": "Date",
            "tickformat": "%m/%d/%y",
            "dtick": "M2",
        },

        yaxis={
            "title": "Documented losses",
            "rangemode": "tozero",
        },

        # Native Plotly legend is replaced
        # by the custom ACLED-style legend.

        showlegend=False,

        height=750,

        margin={
            "l": 70,
            "r": 310,
            "t": 90,
            "b": 70,
        },

        plot_bgcolor="#E5ECF6",
        paper_bgcolor="white",
    )

    # ========================================================
    # CUSTOM JAVASCRIPT
    # ========================================================

    post_script = r"""
    (function() {

        const gd =
            document.getElementById('{plot_id}');

        const categoryNames =
            __CATEGORY_NAMES__;

        const categoryColors =
            __CATEGORY_COLORS__;

        const weeklyData =
            __WEEKLY_DATA__;

        let selectedWeek = null;
        let hoveredWeek = null;


        // ====================================================
        // FORMAT WEEK
        // ====================================================

        function formatWeek(dateString) {

            const d =
                new Date(
                    dateString + "T00:00:00"
                );

            const day =
                String(
                    d.getDate()
                ).padStart(2, "0");

            const month =
                String(
                    d.getMonth() + 1
                ).padStart(2, "0");

            const year =
                String(
                    d.getFullYear()
                ).slice(-2);

            return (
                "Week of "
                + day
                + "/"
                + month
                + "/"
                + year
            );
        }


        // ====================================================
        // BUILD WEEKLY LOOKUP
        // ====================================================

        const weekLookup = {};

        weeklyData.forEach(
            function(row) {

                if (!weekLookup[row.week]) {
                    weekLookup[row.week] = [];
                }

                weekLookup[row.week].push({

                    type: row.type,

                    losses:
                        Number(
                            row.losses
                        )
                });
            }
        );


        // ----------------------------------------------------
        // Sort every week by number of losses
        // ----------------------------------------------------

        Object.keys(
            weekLookup
        ).forEach(
            function(week) {

                weekLookup[week].sort(
                    function(a, b) {

                        return (
                            b.losses
                            -
                            a.losses
                        );
                    }
                );
            }
        );


        // ====================================================
        // CUSTOM LEGEND
        // ====================================================

        const legend =
            document.createElement("div");

        legend.id =
            "equipment-legend";

        legend.style.position =
            "absolute";

        legend.style.right =
            "18px";

        legend.style.top =
            "78px";

        legend.style.width =
            "275px";

        legend.style.background =
            "rgba(255,255,255,0.97)";

        legend.style.border =
            "1px solid #D0D0D0";

        legend.style.boxSizing =
            "border-box";

        legend.style.fontFamily =
            "Arial, sans-serif";

        legend.style.fontSize =
            "13px";

        legend.style.color =
            "#222";

        legend.style.zIndex =
            "20";

        legend.style.boxShadow =
            "0 1px 3px rgba(0,0,0,0.10)";


        // ----------------------------------------------------
        // Header
        // ----------------------------------------------------

        const header =
            document.createElement("div");

        header.textContent =
            "Equipment";

        header.style.background =
            "#28547A";

        header.style.color =
            "white";

        header.style.fontWeight =
            "bold";

        header.style.padding =
            "7px 10px";

        header.style.fontSize =
            "14px";

        legend.appendChild(header);


        // ----------------------------------------------------
        // Legend content
        // ----------------------------------------------------

        const content =
            document.createElement("div");

        content.id =
            "equipment-legend-content";

        content.style.padding =
            "8px 10px 9px 10px";

        content.style.maxHeight =
            "560px";

        content.style.overflowY =
            "auto";

        legend.appendChild(content);


        gd.parentElement.style.position =
            "relative";

        gd.parentElement.appendChild(
            legend
        );


        // ====================================================
        // CREATE DEFAULT LEGEND ROW
        // ====================================================

        function createDefaultRow(
            category
        ) {

            const row =
                document.createElement("div");

            row.style.display =
                "flex";

            row.style.alignItems =
                "center";

            row.style.marginBottom =
                "5px";

            row.style.lineHeight =
                "16px";


            const square =
                document.createElement("span");

            square.style.width =
                "10px";

            square.style.height =
                "10px";

            square.style.background =
                categoryColors[category];

            square.style.display =
                "inline-block";

            square.style.marginRight =
                "8px";

            square.style.flex =
                "0 0 auto";


            const label =
                document.createElement("span");

            label.textContent =
                category;


            row.appendChild(square);

            row.appendChild(label);

            return row;
        }


        // ====================================================
        // UPDATE LEGEND
        // ====================================================

        function updateLegend(week) {

            content.innerHTML = "";


            // ------------------------------------------------
            // Default state
            // ------------------------------------------------

            if (!week) {

                categoryNames.forEach(
                    function(category) {

                        content.appendChild(
                            createDefaultRow(
                                category
                            )
                        );
                    }
                );

                return;
            }


            // ------------------------------------------------
            // Selected week
            // ------------------------------------------------

            const rows =
                weekLookup[week] || [];


            const total =
                rows.reduce(
                    function(sum, row) {

                        return (
                            sum
                            +
                            row.losses
                        );
                    },
                    0
                );


            // ------------------------------------------------
            // Week header
            // ------------------------------------------------

            const weekLabel =
                document.createElement("div");

            weekLabel.textContent =
                formatWeek(week);

            weekLabel.style.fontWeight =
                "bold";

            weekLabel.style.marginBottom =
                "7px";

            weekLabel.style.paddingBottom =
                "5px";

            weekLabel.style.borderBottom =
                "1px solid #D0D0D0";

            content.appendChild(
                weekLabel
            );


            // ------------------------------------------------
            // Categories
            // ------------------------------------------------

            rows.forEach(
                function(item) {

                    const row =
                        document.createElement("div");

                    row.style.display =
                        "flex";

                    row.style.alignItems =
                        "center";

                    row.style.marginBottom =
                        "5px";

                    row.style.lineHeight =
                        "16px";


                    const square =
                        document.createElement("span");

                    square.style.width =
                        "10px";

                    square.style.height =
                        "10px";

                    square.style.background =
                        categoryColors[item.type];

                    square.style.display =
                        "inline-block";

                    square.style.marginRight =
                        "8px";

                    square.style.flex =
                        "0 0 auto";


                    const label =
                        document.createElement("span");

                    label.textContent =
                        item.type;

                    label.style.flex =
                        "1";


                    const value =
                        document.createElement("span");

                    value.textContent =
                        item.losses;

                    value.style.fontWeight =
                        "bold";

                    value.style.marginLeft =
                        "8px";


                    row.appendChild(
                        square
                    );

                    row.appendChild(
                        label
                    );

                    row.appendChild(
                        value
                    );

                    content.appendChild(
                        row
                    );
                }
            );


            // ------------------------------------------------
            // Separator
            // ------------------------------------------------

            const separator =
                document.createElement("div");

            separator.style.borderTop =
                "1px solid #D0D0D0";

            separator.style.margin =
                "7px 0 6px 0";

            content.appendChild(
                separator
            );


            // ------------------------------------------------
            // Total
            // ------------------------------------------------

            const totalRow =
                document.createElement("div");

            totalRow.style.display =
                "flex";

            totalRow.style.fontWeight =
                "bold";

            totalRow.style.lineHeight =
                "18px";


            const totalLabel =
                document.createElement("span");

            totalLabel.textContent =
                "Total";

            totalLabel.style.flex =
                "1";


            const totalValue =
                document.createElement("span");

            totalValue.textContent =
                total;


            totalRow.appendChild(
                totalLabel
            );

            totalRow.appendChild(
                totalValue
            );

            content.appendChild(
                totalRow
            );
        }


        updateLegend(null);


        // ====================================================
        // CUSTOM TOOLTIP
        // ====================================================

        const tooltip =
            document.createElement("div");

        tooltip.id =
            "equipment-tooltip";

        tooltip.style.position =
            "fixed";

        tooltip.style.display =
            "none";

        tooltip.style.background =
            "rgba(255,255,255,0.98)";

        tooltip.style.border =
            "1px solid #777";

        tooltip.style.padding =
            "8px 10px";

        tooltip.style.fontFamily =
            "Arial, sans-serif";

        tooltip.style.fontSize =
            "12px";

        tooltip.style.color =
            "#222";

        tooltip.style.zIndex =
            "1000";

        tooltip.style.boxShadow =
            "0 1px 4px rgba(0,0,0,0.20)";

        tooltip.style.pointerEvents =
            "none";

        tooltip.style.minWidth =
            "210px";

        document.body.appendChild(
            tooltip
        );


        // ====================================================
        // SHOW TOOLTIP
        // ====================================================

        function showTooltip(
            week,
            event
        ) {

            const rows =
                weekLookup[week] || [];

            let total = 0;

            let html =
                "<div style='" +
                "font-weight:bold;" +
                "margin-bottom:7px;'>" +

                formatWeek(week) +

                "</div>";


            rows.forEach(
                function(item) {

                    total +=
                        item.losses;


                    html +=
                        "<div style='" +
                        "display:flex;" +
                        "align-items:center;" +
                        "margin-bottom:4px;'>" +

                        "<span style='" +
                        "width:10px;" +
                        "height:10px;" +
                        "background:" +
                        categoryColors[
                            item.type
                        ] +
                        ";display:inline-block;" +
                        "margin-right:7px;" +
                        "flex:0 0 auto;'>" +

                        "</span>" +

                        "<span style='" +
                        "flex:1;'>" +

                        item.type +

                        "</span>" +

                        "<span style='" +
                        "font-weight:bold;" +
                        "margin-left:10px;'>" +

                        item.losses +

                        "</span>" +

                        "</div>";
                }
            );


            html +=
                "<div style='" +
                "border-top:1px solid #ccc;" +
                "margin-top:6px;" +
                "padding-top:6px;" +
                "display:flex;" +
                "font-weight:bold;'>" +

                "<span style='flex:1;'>" +
                "Total" +
                "</span>" +

                "<span>" +
                total +
                "</span>" +

                "</div>";


            tooltip.innerHTML =
                html;

            tooltip.style.display =
                "block";


            // ------------------------------------------------
            // Position tooltip
            // ------------------------------------------------

            let x =
                event.clientX + 14;

            let y =
                event.clientY + 14;


            const tooltipWidth =
                tooltip.offsetWidth;

            const tooltipHeight =
                tooltip.offsetHeight;


            if (
                x + tooltipWidth
                >
                window.innerWidth - 10
            ) {

                x =
                    event.clientX
                    -
                    tooltipWidth
                    -
                    14;
            }


            if (
                y + tooltipHeight
                >
                window.innerHeight - 10
            ) {

                y =
                    event.clientY
                    -
                    tooltipHeight
                    -
                    14;
            }


            tooltip.style.left =
                x + "px";

            tooltip.style.top =
                y + "px";
        }


        // ====================================================
        // HIDE TOOLTIP
        // ====================================================

        function hideTooltip() {

            tooltip.style.display =
                "none";
        }


        // ====================================================
        // GET RGB
        // ====================================================

        function hexToRgb(
            hex
        ) {

            const clean =
                hex.replace(
                    "#",
                    ""
                );

            return [
                parseInt(
                    clean.substring(
                        0,
                        2
                    ),
                    16
                ),
                parseInt(
                    clean.substring(
                        2,
                        4
                    ),
                    16
                ),
                parseInt(
                    clean.substring(
                        4,
                        6
                    ),
                    16
                )
            ];
        }


        // ====================================================
        // APPLY VISUAL HIGHLIGHT
        // ====================================================

        function applyHighlight(
            activeWeek
        ) {

            gd.data.forEach(
                function(trace, traceIndex) {

                    const baseColor =
                        categoryColors[
                            trace.name
                        ];

                    const rgb =
                        hexToRgb(
                            baseColor
                        );


                    const normalColor =
                        "rgba(" +
                        rgb[0] +
                        "," +
                        rgb[1] +
                        "," +
                        rgb[2] +
                        ",0.40)";


                    const fadedColor =
                        "rgba(" +
                        rgb[0] +
                        "," +
                        rgb[1] +
                        "," +
                        rgb[2] +
                        ",0.15)";


                    const highlightedColor =
                        "rgba(" +
                        rgb[0] +
                        "," +
                        rgb[1] +
                        "," +
                        rgb[2] +
                        ",1.0)";


                    const newColors =
                        trace.x.map(
                            function(x) {

                                const xString =
                                    String(x)
                                        .slice(
                                            0,
                                            10
                                        );


                                // --------------------------------
                                // Nothing selected / hovered
                                // --------------------------------

                                if (!activeWeek) {

                                    return normalColor;
                                }


                                // --------------------------------
                                // Active week
                                // --------------------------------

                                if (
                                    xString ===
                                    activeWeek
                                ) {

                                    return highlightedColor;
                                }


                                // --------------------------------
                                // Everything else
                                // --------------------------------

                                return fadedColor;
                            }
                        );


                    Plotly.restyle(
                        gd,
                        {
                            "marker.color": [
                                newColors
                            ]
                        },
                        [traceIndex]
                    );
                }
            );
        }


        // ====================================================
        // DETERMINE ACTIVE WEEK
        // ====================================================

        function getActiveWeek() {

            if (hoveredWeek) {
                return hoveredWeek;
            }

            if (selectedWeek) {
                return selectedWeek;
            }

            return null;
        }


        // ====================================================
        // HOVER
        // ====================================================

        gd.on(
            "plotly_hover",
            function(data) {

                if (
                    !data.points
                    ||
                    !data.points.length
                ) {

                    return;
                }


                const week =
                    String(
                        data.points[0].x
                    ).slice(
                        0,
                        10
                    );


                hoveredWeek =
                    week;


                // Highlight the week
                // currently under mouse.

                applyHighlight(
                    getActiveWeek()
                );


                // Show tooltip.

                showTooltip(
                    week,
                    data.event
                );
            }
        );


        // ====================================================
        // UNHOVER
        // ====================================================

        gd.on(
            "plotly_unhover",
            function() {

                hoveredWeek =
                    null;


                // If a week was clicked,
                // return to the selected week.
                //
                // Otherwise return all weeks
                // to the faded state.

                applyHighlight(
                    getActiveWeek()
                );


                hideTooltip();
            }
        );


        // ====================================================
        // CLICK
        // ====================================================

        gd.on(
            "plotly_click",
            function(data) {

                if (
                    !data.points
                    ||
                    !data.points.length
                ) {

                    return;
                }


                const week =
                    String(
                        data.points[0].x
                    ).slice(
                        0,
                        10
                    );


                // ------------------------------------------------
                // Clicking the currently selected week
                // removes the selection.
                // ------------------------------------------------

                if (
                    selectedWeek === week
                ) {

                    selectedWeek =
                        null;

                } else {

                    selectedWeek =
                        week;
                }


                // ------------------------------------------------
                // Legend follows the selected week.
                // ------------------------------------------------

                updateLegend(
                    selectedWeek
                );


                // ------------------------------------------------
                // While mouse is still over the bar,
                // hover should remain visually dominant.
                // ------------------------------------------------

                applyHighlight(
                    getActiveWeek()
                );
            }
        );


        // ====================================================
        // CLICK OUTSIDE THE GRAPH
        // ====================================================

        document.addEventListener(
            "click",
            function(event) {

                if (
                    event.target === gd
                    ||
                    gd.contains(
                        event.target
                    )
                    ||
                    legend.contains(
                        event.target
                    )
                ) {

                    return;
                }


                selectedWeek =
                    null;

                hoveredWeek =
                    null;


                updateLegend(
                    null
                );


                applyHighlight(
                    null
                );
            }
        );

    })();
    """


    # ========================================================
    # INSERT PYTHON DATA INTO JAVASCRIPT
    # ========================================================

    category_names_json = json.dumps(
        categories
    )


    weekly_json = (
        weekly[
            [
                "week",
                "type",
                "losses"
            ]
        ]
        .assign(
            week=lambda x:
                x["week"].dt.strftime(
                    "%Y-%m-%d"
                )
        )
        .to_dict(
            "records"
        )
    )


    post_script = post_script.replace(
        "__CATEGORY_NAMES__",
        category_names_json
    )


    post_script = post_script.replace(
        "__CATEGORY_COLORS__",
        json.dumps(colors)
    )


    post_script = post_script.replace(
        "__WEEKLY_DATA__",
        json.dumps(weekly_json)
    )


    return fig, post_script


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("WARSPOTTING ACLED-STYLE ANALYSIS")
    print("=" * 60)

    print()


    # --------------------------------------------------------
    # 1. Load raw data
    # --------------------------------------------------------

    raw_df = load_data()


    # --------------------------------------------------------
    # 2. Create weekly equipment aggregation
    # --------------------------------------------------------

    weekly_df = create_weekly_dataset(
        raw_df
    )


    # --------------------------------------------------------
    # 3. Validate aggregation
    # --------------------------------------------------------

    validate_weekly_data(
        raw_df,
        weekly_df
    )


    # --------------------------------------------------------
    # 4. Create chart
    # --------------------------------------------------------

    fig, post_script = create_chart(
        weekly_df
    )


    # --------------------------------------------------------
    # 5. Save HTML
    # --------------------------------------------------------

    fig.write_html(
        OUTPUT_FILE,
        include_plotlyjs=True,
        post_script=post_script
    )


    print()

    print(
        f"Interactive chart saved: "
        f"{OUTPUT_FILE}"
    )


    print()

    print("=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
