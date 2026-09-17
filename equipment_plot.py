# ============================================================
# WARSPOTTING — ACLED-STYLE EQUIPMENT LOSS CHART
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

BASE_OPACITY = 0.42
SELECTED_OPACITY = 1.0

# Opacity of all other weeks when one week is selected.
# This recreates the stronger fading from the earlier version.
SELECTED_OTHER_OPACITY = 0.16


# ============================================================
# CATEGORY COLORS
# ============================================================
#
# Colors matched to the ACLED screenshot.
#
# ============================================================

CATEGORY_COLORS = {
    "Tanks": "#54A24B",
    "Infantry fighting vehicles": "#4C78A8",
    "Infantry mobility vehicles": "#9D755D",
    "Command posts, communication": "#EDC949",
    "Anti-tank systems": "#8CD17D",
    "Anti-aircraft systems": "#BAB0AC",
    "Towed artillery": "#59A14F",
    "Self-propelled artillery": "#E45756",
    "Rocket and missile artillery": "#FF9DA6",
    "Radars, jammers": "#AF7AA1",
    "Engineering": "#B279A2",
    "Ambulances, medical vehicles": "#5DA5DA",
    "Transport": "#F58518",
    "Airplanes": "#E15759",
    "Helicopters": "#F28E2B",
    "Drones": "#72B7B2",
    "Vessels": "#B6992D",
    "Other": "#76B7B2",
}


# ============================================================
# LOAD DATA
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
        "lost_by",
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

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    if df["date"].isna().any():

        raise ValueError(
            "Invalid dates found in raw dataset."
        )

    if df["type"].isna().any():

        raise ValueError(
            "Missing equipment categories found."
        )

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

    data["week"] = (
        data["date"]
        - pd.to_timedelta(
            data["date"].dt.weekday,
            unit="D"
        )
    )

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

def validate_weekly_data(
    raw_df,
    weekly_df
):

    print()
    print("=" * 60)
    print("WEEKLY DATA VALIDATION")
    print("=" * 60)

    raw_total = len(raw_df)

    weekly_total = (
        weekly_df["losses"].sum()
    )

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

    categories = (
        weekly_df["type"].nunique()
    )

    if categories == 0:

        raise ValueError(
            "No equipment categories found."
        )

    print(
        f"Equipment categories: {categories}"
    )

    print()
    print("VALIDATION STATUS: OK")


# ============================================================
# CATEGORY ORDER
# ============================================================

def get_category_order(df):

    totals = (
        df
        .groupby("type")["losses"]
        .sum()
        .sort_values(
            ascending=False
        )
    )

    return totals.index.tolist()


# ============================================================
# PREPARE WEEK DATA
# ============================================================

def prepare_week_data(weekly):

    week_data = {}

    for _, row in weekly.iterrows():

        week = row["week"].strftime(
            "%Y-%m-%d"
        )

        category = row["type"]

        losses = int(
            row["losses"]
        )

        if week not in week_data:

            week_data[week] = []

        week_data[week].append(
            {
                "type": category,
                "losses": losses,
            }
        )

    for week in week_data:

        week_data[week].sort(
            key=lambda item:
                item["losses"],
            reverse=True
        )

    return week_data


# ============================================================
# CREATE CHART
# ============================================================

def create_chart(weekly):

    print()
    print("=" * 60)
    print("CREATING INTERACTIVE CHART")
    print("=" * 60)

    categories = get_category_order(
        weekly
    )

    missing_colors = [
        category
        for category in categories
        if category not in CATEGORY_COLORS
    ]

    if missing_colors:

        raise ValueError(
            "Missing colors for categories: "
            f"{missing_colors}"
        )

    fig = go.Figure()


    # ========================================================
    # STACKED BAR TRACES
    # ========================================================

    for category in categories:

        category_data = (
            weekly[
                weekly["type"] == category
            ]
            .sort_values("week")
            .copy()
        )

        x_values = (
            category_data["week"]
            .dt.strftime(
                "%Y-%m-%d"
            )
            .tolist()
        )

        y_values = (
            category_data["losses"]
            .astype(int)
            .tolist()
        )

        fig.add_trace(
            go.Bar(

                x=x_values,

                y=y_values,

                name=category,

                marker={
                    "color":
                        CATEGORY_COLORS[
                            category
                        ],

                    "opacity":
                        BASE_OPACITY,

                    "line": {
                        "color":
                            "rgba(255,255,255,0.55)",

                        "width": 0.5,
                    },
                },

                hovertemplate=
                    "<extra></extra>",
            )
        )


    # ========================================================
    # JAVASCRIPT DATA
    # ========================================================

    week_data = prepare_week_data(
        weekly
    )

    category_colors_json = json.dumps(
        {
            category:
                CATEGORY_COLORS[category]
            for category in categories
        },
        ensure_ascii=False,
    )

    week_data_json = json.dumps(
        week_data,
        ensure_ascii=False,
    )

    categories_json = json.dumps(
        categories,
        ensure_ascii=False,
    )


    # ========================================================
    # JAVASCRIPT
    # ========================================================

    post_script = r"""
(function() {

    const gd =
        document.getElementById('{plot_id}');


    // ========================================================
    // DATA
    // ========================================================

    const weekData =
        WEEK_DATA_PLACEHOLDER;

    const categoryColors =
        CATEGORY_COLORS_PLACEHOLDER;

    const categories =
        CATEGORIES_PLACEHOLDER;

    const baseOpacity =
        BASE_OPACITY_PLACEHOLDER;

    const selectedOpacity =
        SELECTED_OPACITY_PLACEHOLDER;

    const selectedOtherOpacity =
        SELECTED_OTHER_OPACITY_PLACEHOLDER;


    // ========================================================
    // STATE
    // ========================================================

    let selectedWeek = null;

    let hoverWeek = null;

    let plotlyBarClickHandled = false;


    // ========================================================
    // CONTAINER
    // ========================================================

    const wrapper =
        gd.parentElement;

    wrapper.style.position =
        'relative';


    // ========================================================
    // EQUIPMENT PANEL
    // ========================================================

    const panel =
        document.createElement('div');

    panel.id =
        'equipment-panel';

    panel.style.position =
        'absolute';

    panel.style.top =
        '90px';

    panel.style.right =
        '10px';

    panel.style.width =
        '245px';

    panel.style.background =
        '#ffffff';

    panel.style.border =
        '1px solid #c7cdd4';

    panel.style.boxShadow =
        '0 1px 4px rgba(0,0,0,0.12)';

    panel.style.fontFamily =
        'Arial, sans-serif';

    panel.style.fontSize =
        '13px';

    panel.style.color =
        '#222';

    panel.style.zIndex =
        '20';

    wrapper.appendChild(panel);


    // ========================================================
    // CUSTOM TOOLTIP
    // ========================================================

    const tooltip =
        document.createElement('div');

    tooltip.id =
        'equipment-tooltip';

    tooltip.style.position =
        'fixed';

    tooltip.style.display =
        'none';

    tooltip.style.background =
        '#ffffff';

    tooltip.style.border =
        '1px solid #777';

    tooltip.style.boxShadow =
        '0 1px 4px rgba(0,0,0,0.20)';

    tooltip.style.padding =
        '8px 10px';

    tooltip.style.fontFamily =
        'Arial, sans-serif';

    tooltip.style.fontSize =
        '12px';

    tooltip.style.color =
        '#222';

    tooltip.style.zIndex =
        '9999';

    tooltip.style.pointerEvents =
        'none';

    tooltip.style.minWidth =
        '210px';

    document.body.appendChild(
        tooltip
    );


    // ========================================================
    // DATE FORMAT
    // ========================================================

    function formatWeek(week) {

        const parts =
            week.split('-');

        if (parts.length !== 3) {
            return week;
        }

        return (
            parts[2] +
            '/' +
            parts[1] +
            '/' +
            parts[0].slice(2)
        );
    }


    // ========================================================
    // NUMBER FORMAT
    // ========================================================

    function formatNumber(value) {

        return value.toLocaleString(
            'en-US'
        );
    }


    // ========================================================
    // GET WEEK ITEMS
    // ========================================================

    function getWeekItems(week) {

        if (!weekData[week]) {
            return [];
        }

        return [
            ...weekData[week]
        ].sort(
            (a, b) =>
                b.losses - a.losses
        );
    }


    // ========================================================
    // GET WEEK TOTAL
    // ========================================================

    function getWeekTotal(week) {

        return getWeekItems(week)
            .reduce(
                (sum, item) =>
                    sum + item.losses,
                0
            );
    }


    // ========================================================
    // RENDER EQUIPMENT PANEL
    // ========================================================

    function renderPanel(week) {

        panel.innerHTML = '';


        // ----------------------------------------------------
        // Header
        // ----------------------------------------------------

        const header =
            document.createElement(
                'div'
            );

        header.style.background =
            '#28547A';

        header.style.color =
            '#ffffff';

        header.style.fontWeight =
            'bold';

        header.style.padding =
            '8px 10px';

        header.style.fontSize =
            '14px';


        if (week) {

            header.textContent =
                'Equipment — ' +
                formatWeek(week);

        } else {

            header.textContent =
                'Equipment';
        }


        panel.appendChild(
            header
        );


        // ----------------------------------------------------
        // Body
        // ----------------------------------------------------

        const body =
            document.createElement(
                'div'
            );

        body.style.padding =
            '8px 10px 10px 10px';

        panel.appendChild(
            body
        );


        // ----------------------------------------------------
        // No selected week
        // ----------------------------------------------------

        if (!week) {

            categories.forEach(
                function(category) {

                    const row =
                        document.createElement(
                            'div'
                        );

                    row.style.display =
                        'flex';

                    row.style.alignItems =
                        'center';

                    row.style.marginBottom =
                        '5px';


                    const square =
                        document.createElement(
                            'span'
                        );

                    square.style.width =
                        '10px';

                    square.style.height =
                        '10px';

                    square.style.background =
                        categoryColors[
                            category
                        ];

                    square.style.display =
                        'inline-block';

                    square.style.marginRight =
                        '7px';

                    square.style.flexShrink =
                        '0';


                    const name =
                        document.createElement(
                            'span'
                        );

                    name.textContent =
                        category;


                    row.appendChild(
                        square
                    );

                    row.appendChild(
                        name
                    );

                    body.appendChild(
                        row
                    );
                }
            );

            return;
        }


        // ----------------------------------------------------
        // Selected week
        // ----------------------------------------------------

        const items =
            getWeekItems(week);


        items.forEach(
            function(item) {

                const row =
                    document.createElement(
                        'div'
                    );

                row.style.display =
                    'flex';

                row.style.alignItems =
                    'center';

                row.style.marginBottom =
                    '5px';


                const square =
                    document.createElement(
                        'span'
                    );

                square.style.width =
                    '10px';

                square.style.height =
                    '10px';

                square.style.background =
                    categoryColors[
                        item.type
                    ];

                square.style.display =
                    'inline-block';

                square.style.marginRight =
                    '7px';

                square.style.flexShrink =
                    '0';


                const name =
                    document.createElement(
                        'span'
                    );

                name.textContent =
                    item.type;

                name.style.flex =
                    '1';


                const value =
                    document.createElement(
                        'span'
                    );

                value.textContent =
                    formatNumber(
                        item.losses
                    );

                value.style.fontWeight =
                    'bold';

                value.style.marginLeft =
                    '8px';


                row.appendChild(
                    square
                );

                row.appendChild(
                    name
                );

                row.appendChild(
                    value
                );

                body.appendChild(
                    row
                );
            }
        );


        // ----------------------------------------------------
        // Total
        // ----------------------------------------------------

        const separator =
            document.createElement(
                'div'
            );

        separator.style.borderTop =
            '1px solid #d5d9de';

        separator.style.margin =
            '8px 0 7px 0';

        body.appendChild(
            separator
        );


        const totalRow =
            document.createElement(
                'div'
            );

        totalRow.style.display =
            'flex';

        totalRow.style.fontWeight =
            'bold';


        const totalLabel =
            document.createElement(
                'span'
            );

        totalLabel.style.flex =
            '1';

        totalLabel.textContent =
            'Total';


        const totalValue =
            document.createElement(
                'span'
            );

        totalValue.textContent =
            formatNumber(
                getWeekTotal(week)
            );


        totalRow.appendChild(
            totalLabel
        );

        totalRow.appendChild(
            totalValue
        );

        body.appendChild(
            totalRow
        );
    }


    // ========================================================
    // INITIAL PANEL
    // ========================================================

    renderPanel(null);


    // ========================================================
    // HIGHLIGHT SELECTED WEEK
    // ========================================================
    //
    // IMPORTANT:
    //
    // When no week is selected:
    //     all bars = BASE_OPACITY
    //
    // When a week is selected:
    //     selected week = SELECTED_OPACITY
    //     all other weeks = SELECTED_OTHER_OPACITY
    //
    // This function is called ONLY after a click.
    //
    // ========================================================

    function highlightWeek(week) {

        const update = {
            'marker.opacity': []
        };


        for (
            let traceIndex = 0;
            traceIndex < gd.data.length;
            traceIndex++
        ) {

            const trace =
                gd.data[traceIndex];

            const opacities = [];


            for (
                let pointIndex = 0;
                pointIndex < trace.x.length;
                pointIndex++
            ) {

                const pointWeek =
                    String(
                        trace.x[pointIndex]
                    ).slice(0, 10);


                if (!week) {

                    // No selection.
                    opacities.push(
                        baseOpacity
                    );

                } else if (
                    pointWeek === week
                ) {

                    // Selected week.
                    opacities.push(
                        selectedOpacity
                    );

                } else {

                    // Everything else becomes
                    // more faded.
                    opacities.push(
                        selectedOtherOpacity
                    );
                }
            }


            update[
                'marker.opacity'
            ].push(
                opacities
            );
        }


        Plotly.restyle(
            gd,
            update
        );
    }


    // ========================================================
    // HOVER
    // ========================================================
    //
    // Hover ONLY changes the tooltip.
    //
    // No opacity changes here.
    //
    // The Plotly spike line is handled automatically
    // by the x-axis configuration below.
    //
    // ========================================================

    gd.on(
        'plotly_hover',
        function(eventData) {

            if (
                !eventData ||
                !eventData.points ||
                !eventData.points.length
            ) {
                return;
            }


            const point =
                eventData.points[0];


            hoverWeek =
                String(
                    point.x
                ).slice(0, 10);


            const items =
                getWeekItems(
                    hoverWeek
                );


            if (!items.length) {
                return;
            }


            let html = '';


            html +=
                '<div style="' +
                'font-weight:bold;' +
                'font-size:12px;' +
                'margin-bottom:8px;' +
                '">' +
                'Week of ' +
                formatWeek(
                    hoverWeek
                ) +
                '</div>';


            items.forEach(
                function(item) {

                    html +=
                        '<div style="' +
                        'display:flex;' +
                        'align-items:center;' +
                        'margin-bottom:4px;' +
                        '">';


                    html +=
                        '<span style="' +
                        'width:10px;' +
                        'height:10px;' +
                        'background:' +
                        categoryColors[
                            item.type
                        ] +
                        ';' +
                        'display:inline-block;' +
                        'margin-right:7px;' +
                        'flex-shrink:0;' +
                        '"></span>';


                    html +=
                        '<span style="flex:1;">' +
                        item.type +
                        '</span>';


                    html +=
                        '<span style="' +
                        'font-weight:bold;' +
                        'margin-left:12px;' +
                        '">' +
                        formatNumber(
                            item.losses
                        ) +
                        '</span>';


                    html +=
                        '</div>';
                }
            );


            // ------------------------------------------------
            // Total
            // ------------------------------------------------

            html +=
                '<div style="' +
                'border-top:1px solid #d5d9de;' +
                'margin-top:7px;' +
                'padding-top:6px;' +
                'display:flex;' +
                'font-weight:bold;' +
                '">';


            html +=
                '<span style="flex:1;">' +
                'Total' +
                '</span>';


            html +=
                '<span>' +
                formatNumber(
                    getWeekTotal(
                        hoverWeek
                    )
                ) +
                '</span>';


            html +=
                '</div>';


            tooltip.innerHTML =
                html;

            tooltip.style.display =
                'block';


            // ------------------------------------------------
            // Position tooltip
            // ------------------------------------------------

            let x = 0;
            let y = 0;


            if (
                eventData.event &&
                typeof eventData.event.clientX ===
                    'number'
            ) {

                x =
                    eventData.event.clientX +
                    15;

                y =
                    eventData.event.clientY +
                    15;

            } else {

                const rect =
                    gd.getBoundingClientRect();

                x =
                    rect.left + 20;

                y =
                    rect.top + 20;
            }


            const tooltipWidth =
                tooltip.offsetWidth;

            const tooltipHeight =
                tooltip.offsetHeight;


            if (
                x + tooltipWidth >
                window.innerWidth - 10
            ) {

                x =
                    window.innerWidth -
                    tooltipWidth -
                    10;
            }


            if (
                y + tooltipHeight >
                window.innerHeight - 10
            ) {

                y =
                    window.innerHeight -
                    tooltipHeight -
                    10;
            }


            tooltip.style.left =
                Math.max(
                    10,
                    x
                ) + 'px';


            tooltip.style.top =
                Math.max(
                    10,
                    y
                ) + 'px';
        }
    );


    // ========================================================
    // HOVER OUT
    // ========================================================

    gd.on(
        'plotly_unhover',
        function() {

            hoverWeek = null;

            tooltip.style.display =
                'none';

        }
    );


    // ========================================================
    // CLICK ON BAR
    // ========================================================

    gd.on(
        'plotly_click',
        function(eventData) {

            if (
                !eventData ||
                !eventData.points ||
                !eventData.points.length
            ) {
                return;
            }


            plotlyBarClickHandled = true;


            const point =
                eventData.points[0];


            const clickedWeek =
                String(
                    point.x
                ).slice(0, 10);


            // ------------------------------------------------
            // Click selected week again = unlock
            // ------------------------------------------------

            if (
                selectedWeek ===
                clickedWeek
            ) {

                selectedWeek = null;

                highlightWeek(null);

                renderPanel(null);

                return;
            }


            // ------------------------------------------------
            // Select another week
            // ------------------------------------------------

            selectedWeek =
                clickedWeek;


            highlightWeek(
                selectedWeek
            );


            renderPanel(
                selectedWeek
            );
        }
    );


    // ========================================================
    // CLICK EMPTY AREA OF CHART
    // ========================================================

    gd.addEventListener(
        'click',
        function(event) {

            setTimeout(
                function() {

                    if (
                        plotlyBarClickHandled
                    ) {

                        plotlyBarClickHandled =
                            false;

                        return;
                    }


                    if (selectedWeek) {

                        selectedWeek = null;

                        highlightWeek(null);

                        renderPanel(null);
                    }

                },
                0
            );
        }
    );


    // ========================================================
    // CLICK OUTSIDE CHART
    // ========================================================

    document.addEventListener(
        'click',
        function(event) {

            if (!selectedWeek) {
                return;
            }


            const clickedInsideChart =
                gd.contains(
                    event.target
                );


            const clickedInsidePanel =
                panel.contains(
                    event.target
                );


            if (
                !clickedInsideChart &&
                !clickedInsidePanel
            ) {

                selectedWeek = null;

                highlightWeek(null);

                renderPanel(null);
            }
        }
    );


})();
"""

    # ========================================================
    # INSERT DATA INTO JAVASCRIPT
    # ========================================================

    post_script = (
        post_script

        .replace(
            "WEEK_DATA_PLACEHOLDER",
            week_data_json
        )

        .replace(
            "CATEGORY_COLORS_PLACEHOLDER",
            category_colors_json
        )

        .replace(
            "CATEGORIES_PLACEHOLDER",
            categories_json
        )

        .replace(
            "BASE_OPACITY_PLACEHOLDER",
            str(BASE_OPACITY)
        )

        .replace(
            "SELECTED_OPACITY_PLACEHOLDER",
            str(SELECTED_OPACITY)
        )

        .replace(
            "SELECTED_OTHER_OPACITY_PLACEHOLDER",
            str(SELECTED_OTHER_OPACITY)
        )
    )


    # ========================================================
    # LAYOUT
    # ========================================================

    fig.update_layout(

        title={
            "text":
                "Russian Equipment Losses — Weekly",

            "x":
                0.5,

            "xanchor":
                "center",
        },


        barmode="stack",


        # Keep hover behaviour unchanged.
        hovermode="closest",


        xaxis={

            "title":
                "Date",

            "tickformat":
                "%m/%d/%y",

            "dtick":
                "M2",

            "type":
                "date",

            # =================================================
            # ACLED-STYLE VERTICAL HOVER LINE
            # =================================================
            #
            # Dotted vertical line follows mouse position.
            # This does not restyle the bars.
            #
            "showspikes":
                True,

            "spikemode":
                "across",

            "spikesnap":
                "cursor",

            "spikethickness":
                1,

            "spikedash":
                "dot",

            "spikecolor":
                "rgba(80,80,80,0.65)",
        },


        yaxis={
            "title":
                "Documented losses",

            "rangemode":
                "tozero",
        },


        showlegend=False,


        height=750,


        margin={
            "l": 70,
            "r": 290,
            "t": 90,
            "b": 70,
        },


        hoverlabel={
            "bgcolor":
                "rgba(255,255,255,0)",

            "bordercolor":
                "rgba(255,255,255,0)",

            "font": {
                "color":
                    "rgba(0,0,0,0)",
            },
        },


        plot_bgcolor=
            "#eaf1f8",

        paper_bgcolor=
            "#ffffff",


        font={
            "family":
                "Arial, sans-serif",
        },
    )


    # ========================================================
    # ADD SELECTED-WEEK VERTICAL LINE
    # ========================================================
    #
    # The actual line is controlled by JavaScript after click.
    # The initial layout contains no selected line.
    #
    # ========================================================

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
    # Load raw data
    # --------------------------------------------------------

    raw_df = load_data()


    # --------------------------------------------------------
    # Weekly aggregation
    # --------------------------------------------------------

    weekly_df = create_weekly_dataset(
        raw_df
    )


    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    validate_weekly_data(
        raw_df,
        weekly_df
    )


    # --------------------------------------------------------
    # Create chart
    # --------------------------------------------------------

    fig, post_script = create_chart(
        weekly_df
    )


    # ========================================================
    # ADD SOLID SELECTED LINE LOGIC
    # ========================================================
    #
    # This is inserted into the existing JavaScript.
    #
    # It changes ONLY when a week is clicked.
    #
    # ========================================================

    selected_line_js = r"""
    
    // ========================================================
    // SELECTED WEEK SOLID LINE
    // ========================================================

    function updateSelectedLine(week) {

        if (!week) {

            Plotly.relayout(
                gd,
                {
                    shapes: []
                }
            );

            return;
        }


        Plotly.relayout(
            gd,
            {
                shapes: [
                    {
                        type: 'line',

                        x0: week,

                        x1: week,

                        y0: 0,

                        y1: 1,

                        yref: 'paper',

                        line: {
                            color:
                                'rgba(60,60,60,0.90)',

                            width: 2,

                            dash: 'solid'
                        }
                    }
                ]
            }
        );
    }

    """

    # --------------------------------------------------------
    # Insert function before click handling.
    # --------------------------------------------------------

    post_script = post_script.replace(
        """
    // ========================================================
    // CLICK ON BAR
    // ========================================================
    """,
        selected_line_js
        + """
    // ========================================================
    // CLICK ON BAR
    // ========================================================
    """
    )


    # --------------------------------------------------------
    # Update selected line when selecting a week.
    # --------------------------------------------------------

    post_script = post_script.replace(
        """
                selectedWeek = null;

                highlightWeek(null);

                renderPanel(null);

                return;
        """,
        """
                selectedWeek = null;

                highlightWeek(null);


                renderPanel(null);

                return;
        """,
        1
    )


    post_script = post_script.replace(
        """
            selectedWeek =
                clickedWeek;


            highlightWeek(
                selectedWeek
            );


            renderPanel(
                selectedWeek
            );
        """,
        """
            selectedWeek =
                clickedWeek;


            highlightWeek(
                selectedWeek
            );




            renderPanel(
                selectedWeek
            );
        """,
        1
    )


    # --------------------------------------------------------
    # Empty chart click.
    # --------------------------------------------------------

    post_script = post_script.replace(
        """
                        selectedWeek = null;

                        highlightWeek(null);

                        renderPanel(null);
        """,
        """
                        selectedWeek = null;

                        highlightWeek(null);


                        renderPanel(null);
        """,
        1
    )


    # --------------------------------------------------------
    # Outside click.
    # --------------------------------------------------------

    post_script = post_script.replace(
        """
                selectedWeek = null;

                highlightWeek(null);

                renderPanel(null);
            }
        }
    );


})();
""",
        """
                selectedWeek = null;

                highlightWeek(null);


                renderPanel(null);
            }
        }
    );


})();
""",
        1
    )


    # ========================================================
    # SAVE HTML
    # ========================================================

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
