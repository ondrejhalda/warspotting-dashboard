# ============================================================
# WARSPOTTING — ACLED-STYLE EQUIPMENT LOSS CHART
# ============================================================

from pathlib import Path
from datetime import datetime, timezone
import json

import pandas as pd
import plotly.graph_objects as go


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = Path("warspotting_raw.csv")
OUTPUT_FILE = Path("equipment_weekly.html")
QUALITY_FILE = Path("data_quality.json")
WEEKLY_EQUIPMENT_FILE = Path("weekly_equipment_losses.csv")

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

    lost_by_clean = (
        df["lost_by"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    valid_lost_by = (
        lost_by_clean == "Russia"
    )

    excluded_lost_by = (
        ~valid_lost_by
    )

    excluded_ids = []

    if excluded_lost_by.any():

        excluded_ids = (
            df.loc[
                excluded_lost_by,
                "id"
            ]
            .astype(str)
            .tolist()
        )

        print(
            "WARNING: Excluded records with "
            "missing or invalid lost_by: "
            f"{excluded_lost_by.sum()}"
        )

        print(
            "Excluded record IDs: "
            f"{excluded_ids}"
        )

    df = df.loc[
        valid_lost_by
    ].copy()

    excluded_count = int(excluded_lost_by.sum())

    print(
        f"Analytical records after lost_by filter: "
        f"{len(df):,}"
    )

    quality = {
        "raw_records": int(len(df) + excluded_count),
        "analytical_records": int(len(df)),
        "excluded_lost_by": excluded_count,
        "excluded_ids": excluded_ids,
    }

    return df, quality


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
    analysis_df,
    weekly_df
):

    print()
    print("=" * 60)
    print("WEEKLY DATA VALIDATION")
    print("=" * 60)

    analysis_total = len(analysis_df)

    weekly_total = (
        weekly_df["losses"].sum()
    )

    print(
        f"Analytical records: {analysis_total:,}"
    )

    print(
        f"Weekly aggregated records: "
        f"{weekly_total:,}"
    )

    if analysis_total != weekly_total:

        raise ValueError(
            "Weekly aggregation does not match "
            "analytical dataset: "
            f"analytical={analysis_total:,}, "
            f"weekly={weekly_total:,}"
        )

    print(
        "Analytical vs weekly total: OK"
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

def create_chart(weekly, quality_data):

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

        print(
            "WARNING: New equipment categories "
            "without a defined color: "
            f"{missing_colors}"
        )

        fallback_colors = [
            "#9E9E9E",
            "#B0B0B0",
            "#8C8C8C",
            "#C0C0C0",
        ]

        for index, category in enumerate(
            missing_colors
        ):

            CATEGORY_COLORS[category] = (
                fallback_colors[
                    index % len(fallback_colors)
                ]
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


    quality_data_json = json.dumps(
        quality_data,
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

    // Category filter state.
    // "__ALL__" keeps the original full-chart behaviour.
    let selectedCategory = "__ALL__";

    let plotlyBarClickHandled = false;


    // ========================================================
    // CONTAINER
    // ========================================================

    const wrapper =
        gd.parentElement;

    wrapper.style.position =
        'relative';


    // ========================================================
    // DATA QUALITY PANEL
    // ========================================================

    const qualityData =
        QUALITY_DATA_PLACEHOLDER;

    const qualityPanel =
        document.createElement('div');

    qualityPanel.id =
        'data-quality-panel';

    qualityPanel.style.position =
        'absolute';

    // Keep the panel below the Plotly modebar.
    qualityPanel.style.top =
        '48px';

    qualityPanel.style.right =
        '10px';

    qualityPanel.style.width =
        '245px';

    qualityPanel.style.background =
        '#ffffff';

    qualityPanel.style.border =
        '1px solid #c7cdd4';

    qualityPanel.style.boxShadow =
        '0 1px 4px rgba(0,0,0,0.12)';

    qualityPanel.style.fontFamily =
        'Arial, sans-serif';

    qualityPanel.style.fontSize =
        '12px';

    qualityPanel.style.color =
        '#222';

    qualityPanel.style.zIndex =
        '21';

    // Keep the quality panel compact so it never overlaps
    // the equipment panel below it. Extra details can scroll.
    qualityPanel.style.maxHeight =
        '220px';

    qualityPanel.style.overflowY =
        'auto';

    wrapper.appendChild(qualityPanel);


    function renderQualityPanel() {

        qualityPanel.innerHTML = '';

        const header =
            document.createElement('div');

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

        header.textContent =
            'Data quality';

        qualityPanel.appendChild(header);

        const body =
            document.createElement('div');

        body.style.padding =
            '8px 10px 10px 10px';

        qualityPanel.appendChild(body);

        const statusRow =
            document.createElement('div');

        statusRow.style.display =
            'flex';

        statusRow.style.alignItems =
            'center';

        statusRow.style.marginBottom =
            '8px';

        const statusDot =
            document.createElement('span');

        statusDot.style.width =
            '10px';

        statusDot.style.height =
            '10px';

        statusDot.style.borderRadius =
            '50%';

        statusDot.style.display =
            'inline-block';

        statusDot.style.marginRight =
            '7px';

        statusDot.style.background =
            qualityData.validation_status === 'OK'
                ? '#2e7d32'
                : '#f0a000';

        const statusText =
            document.createElement('span');

        statusText.style.fontWeight =
            'bold';

        statusText.textContent =
            qualityData.validation_status;

        statusRow.appendChild(statusDot);
        statusRow.appendChild(statusText);
        body.appendChild(statusRow);

        const rows = [
            ['Last update (UTC)', qualityData.last_update],
            ['Raw records', formatNumber(qualityData.raw_records)],
            ['Analytical records', formatNumber(qualityData.analytical_records)],
            ['Excluded records', formatNumber(qualityData.excluded_lost_by)],
            ['Equipment categories', formatNumber(qualityData.equipment_categories)],
            ['Weekly rows', formatNumber(qualityData.weekly_rows)],
            ['Validation', qualityData.validation_detail]
        ];

        rows.forEach(function(item) {

            const row =
                document.createElement('div');

            row.style.display =
                'flex';

            row.style.marginBottom =
                '5px';

            const label =
                document.createElement('span');

            label.textContent =
                item[0];

            label.style.flex =
                '1';

            label.style.marginRight =
                '8px';

            const value =
                document.createElement('span');

            value.textContent =
                item[1];

            value.style.fontWeight =
                'bold';

            value.style.textAlign =
                'right';

            row.appendChild(label);
            row.appendChild(value);
            body.appendChild(row);
        });

        if (qualityData.new_equipment_categories.length) {

            const separator =
                document.createElement('div');

            separator.style.borderTop =
                '1px solid #d5d9de';

            separator.style.margin =
                '8px 0 7px 0';

            body.appendChild(separator);

            const label =
                document.createElement('div');

            label.style.fontWeight =
                'bold';

            label.style.marginBottom =
                '4px';

            label.textContent =
                'New equipment categories';

            body.appendChild(label);

            const list =
                document.createElement('div');

            list.textContent =
                qualityData.new_equipment_categories.join(', ');

            list.style.lineHeight =
                '1.35';

            body.appendChild(list);
        }

        if (qualityData.excluded_ids.length) {

            const separator =
                document.createElement('div');

            separator.style.borderTop =
                '1px solid #d5d9de';

            separator.style.margin =
                '8px 0 7px 0';

            body.appendChild(separator);

            const details =
                document.createElement('details');

            const summary =
                document.createElement('summary');

            summary.textContent =
                'Excluded record IDs';

            summary.style.cursor =
                'pointer';

            details.appendChild(summary);

            const ids =
                document.createElement('div');

            ids.textContent =
                qualityData.excluded_ids.join(', ');

            ids.style.marginTop =
                '5px';

            ids.style.lineHeight =
                '1.35';

            details.appendChild(ids);
            body.appendChild(details);
        }
    }

    renderQualityPanel();


    // ========================================================
    // EQUIPMENT CATEGORY FILTER
    // ========================================================

    const filterPanel =
        document.createElement('div');

    filterPanel.id =
        'equipment-filter-panel';

    filterPanel.style.position =
        'absolute';

    filterPanel.style.top =
        '48px';

    filterPanel.style.left =
        '10px';

    filterPanel.style.background =
        '#ffffff';

    filterPanel.style.border =
        '1px solid #c7cdd4';

    filterPanel.style.boxShadow =
        '0 1px 4px rgba(0,0,0,0.12)';

    filterPanel.style.padding =
        '8px 10px';

    filterPanel.style.fontFamily =
        'Arial, sans-serif';

    filterPanel.style.fontSize =
        '12px';

    filterPanel.style.color =
        '#222';

    filterPanel.style.zIndex =
        '22';

    const filterLabel =
        document.createElement('label');

    filterLabel.textContent =
        'Equipment category';

    filterLabel.style.fontWeight =
        'bold';

    filterLabel.style.display =
        'block';

    filterLabel.style.marginBottom =
        '5px';

    filterPanel.appendChild(filterLabel);

    const filterSelect =
        document.createElement('select');

    filterSelect.id =
        'equipment-category-filter';

    filterSelect.style.width =
        '190px';

    filterSelect.style.padding =
        '3px 5px';

    filterSelect.style.fontFamily =
        'Arial, sans-serif';

    filterSelect.style.fontSize =
        '12px';

    const allOption =
        document.createElement('option');

    allOption.value =
        '__ALL__';

    allOption.textContent =
        'All equipment';

    filterSelect.appendChild(allOption);

    categories.forEach(
        function(category) {

            const option =
                document.createElement('option');

            option.value =
                category;

            option.textContent =
                category;

            filterSelect.appendChild(option);
        }
    );

    filterPanel.appendChild(filterSelect);

    wrapper.appendChild(filterPanel);


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
        '260px';

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


    // Return only the equipment categories currently selected
    // in the filter. "__ALL__" keeps the original behaviour.
    function getVisibleWeekItems(week) {

        const items =
            getWeekItems(week);

        if (selectedCategory === "__ALL__") {
            return items;
        }

        return items.filter(
            function(item) {
                return item.type === selectedCategory;
            }
        );
    }


    function getVisibleCategories() {

        if (selectedCategory === "__ALL__") {
            return categories;
        }

        return [selectedCategory];
    }


    // ========================================================
    // GET WEEK TOTAL
    // ========================================================

    function getWeekTotal(week) {

        return getVisibleWeekItems(week)
            .reduce(
                (sum, item) =>
                    sum + item.losses,
                0
            );
    }


    // ========================================================
    // APPLY CATEGORY FILTER
    // ========================================================

    function applyCategoryFilter() {

        const visibility =
            categories.map(
                function(category) {
                    return (
                        selectedCategory === "__ALL__" ||
                        category === selectedCategory
                    );
                }
            );

        Plotly.restyle(
            gd,
            { visible: visibility }
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

            getVisibleCategories().forEach(
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
            getVisibleWeekItems(week);


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
    // FILTER CHANGE
    // ========================================================

    filterSelect.addEventListener(
        'change',
        function() {

            selectedCategory =
                filterSelect.value;

            // Changing the filter starts a fresh view.
            // This prevents a selected week from becoming stale.
            selectedWeek = null;

            hoverWeek = null;

            tooltip.style.display =
                'none';

            highlightWeek(null);

            applyCategoryFilter();

            renderPanel(null);
        }
    );


    // ========================================================
    // INITIAL FILTER
    // ========================================================

    applyCategoryFilter();


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
                getVisibleWeekItems(
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

            const clickedInsideQualityPanel =
                qualityPanel.contains(
                    event.target
                );


            if (
                !clickedInsideChart &&
                !clickedInsidePanel &&
                !clickedInsideQualityPanel
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
            "QUALITY_DATA_PLACEHOLDER",
            quality_data_json
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

    raw_df, quality = load_data()


    # --------------------------------------------------------
    # Weekly aggregation
    # --------------------------------------------------------

    weekly_df = create_weekly_dataset(
        raw_df
    )


    # --------------------------------------------------------
    # Detect new equipment categories before the chart
    # assigns fallback colours.
    # --------------------------------------------------------

    new_equipment_categories = sorted(
        set(weekly_df["type"].unique())
        - set(CATEGORY_COLORS)
    )


    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    validate_weekly_data(
        raw_df,
        weekly_df
    )


    # --------------------------------------------------------
    # Quality metadata for JSON + Plotly panel
    # --------------------------------------------------------

    quality.update({
        "last_update": datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "equipment_categories": int(weekly_df["type"].nunique()),
        "weekly_rows": int(len(weekly_df)),
        "new_equipment_categories": new_equipment_categories,
        "validation_status": (
            "WARNING"
            if quality["excluded_lost_by"] or new_equipment_categories
            else "OK"
        ),
        "validation_detail": (
            "OK"
            if not quality["excluded_lost_by"] and not new_equipment_categories
            else "OK with exclusions"
            if quality["excluded_lost_by"] and not new_equipment_categories
            else "OK with new categories"
            if not quality["excluded_lost_by"] and new_equipment_categories
            else "OK with exclusions + new categories"
        ),
    })


    # --------------------------------------------------------
    # Create chart
    # --------------------------------------------------------

    fig, post_script = create_chart(
        weekly_df,
        quality
    )


    # --------------------------------------------------------
    # Save the current weekly analytical dataset.
    #
    # This is a derived dataset generated from the same
    # validated raw data used for the Plotly chart.
    # --------------------------------------------------------

    weekly_df.to_csv(
        WEEKLY_EQUIPMENT_FILE,
        index=False
    )

    print(
        f"Weekly equipment data saved: "
        f"{WEEKLY_EQUIPMENT_FILE}"
    )


    # --------------------------------------------------------
    # Save data-quality metadata for Streamlit and other UI.
    # --------------------------------------------------------

    QUALITY_FILE.write_text(
        json.dumps(quality, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"Data quality file saved: {QUALITY_FILE}"
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
