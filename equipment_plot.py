from pathlib import Path
import json

import pandas as pd
import plotly.graph_objects as go


# ============================================================
# CONFIG
# ============================================================

INPUT_FILE = Path("weekly_equipment_losses.csv")
OUTPUT_FILE = Path("equipment_weekly.html")

BASE_OPACITY = 0.42
SELECTED_OPACITY = 1.0
SELECTED_OTHER_OPACITY = 0.16


# ============================================================
# CATEGORY COLORS
# ============================================================

CATEGORY_COLORS = {
    "Tanks": "#54A24B",
    "Infantry fighting vehicles": "#4C78A8",
    "Infantry mobility vehicles": "#9D755D",
    "Command posts, communication": "#EDC949",
    "Anti-tank systems": "#8CD17D",
    "Anti-aircraft systems": "#BAB0AC",
    "Towed artillery": "#777777",
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

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Input file not found: {INPUT_FILE}"
    )


df = pd.read_csv(INPUT_FILE)

required_columns = {
    "week",
    "type",
    "losses",
}

missing_columns = required_columns - set(df.columns)

if missing_columns:
    raise ValueError(
        f"Missing columns: {sorted(missing_columns)}"
    )


df["week"] = pd.to_datetime(df["week"])

df["type"] = df["type"].astype(str)

df["losses"] = pd.to_numeric(
    df["losses"],
    errors="coerce"
).fillna(0)


# ============================================================
# SORTING
# ============================================================

weeks = sorted(
    df["week"].drop_duplicates()
)

categories = list(CATEGORY_COLORS.keys())

# Add any unexpected categories to the end.
extra_categories = [
    category
    for category in sorted(df["type"].unique())
    if category not in categories
]

categories.extend(extra_categories)


# ============================================================
# CREATE COMPLETE MATRIX
# ============================================================

pivot = (
    df
    .pivot_table(
        index="week",
        columns="type",
        values="losses",
        aggfunc="sum",
        fill_value=0,
    )
    .reindex(
        index=weeks,
        columns=categories,
        fill_value=0,
    )
)


# ============================================================
# CATEGORY COLORS FOR UNKNOWN CATEGORIES
# ============================================================

fallback_colors = [
    "#999999",
    "#888888",
    "#AAAAAA",
    "#666666",
    "#BBBBBB",
]

for i, category in enumerate(extra_categories):
    CATEGORY_COLORS[category] = fallback_colors[
        i % len(fallback_colors)
    ]


# ============================================================
# TOTALS
# ============================================================

weekly_totals = pivot.sum(axis=1)


# ============================================================
# PLOT
# ============================================================

fig = go.Figure()


for category in categories:

    values = pivot[category].tolist()

    color = CATEGORY_COLORS[category]

    fig.add_trace(
        go.Bar(
            name=category,

            x=weeks,

            y=values,

            marker=dict(
                color=color,
                opacity=BASE_OPACITY,
            ),

            hoverinfo="skip",

            customdata=[
                category
                for _ in weeks
            ],
        )
    )


# ============================================================
# LAYOUT
# ============================================================

fig.update_layout(

    barmode="stack",

    bargap=0.08,

    height=700,

    margin=dict(
        l=70,
        r=320,
        t=60,
        b=70,
    ),

    paper_bgcolor="white",

    plot_bgcolor="white",

    showlegend=False,

    hovermode="x",

    xaxis=dict(

        type="date",

        title="",

        showgrid=False,

        zeroline=False,

        showline=True,

        linecolor="#BBBBBB",

        linewidth=1,

        tickformat="%b\n%Y",

        ticks="outside",

        ticklen=5,

        showspikes=True,

        spikemode="across",

        spikesnap="cursor",

        spikethickness=1,

        spikedash="dot",

        spikecolor="rgba(80,80,80,0.65)",
    ),

    yaxis=dict(

        title="Documented equipment losses",

        showgrid=True,

        gridcolor="rgba(0,0,0,0.08)",

        zeroline=False,

        showline=False,

    ),

    hoverlabel=dict(
        bgcolor="white",
        bordercolor="#777777",
        font=dict(
            color="#222222",
            size=13,
        ),
        align="left",
    ),
)


# ============================================================
# CUSTOM EQUIPMENT PANEL
# ============================================================

panel_items = []

for category in categories:

    panel_items.append(
        f"""
        <div class="equipment-item">
            <span
                class="equipment-color"
                style="background:{CATEGORY_COLORS[category]}"
            ></span>

            <span class="equipment-name">
                {category}
            </span>
        </div>
        """
    )


panel_html = f"""
<div
    id="equipment-panel"
    style="
        position:absolute;
        top:60px;
        right:20px;
        width:265px;
        background:white;
        border:1px solid #D0D0D0;
        box-shadow:0 2px 8px rgba(0,0,0,0.08);
        font-family:Arial,sans-serif;
        z-index:10;
    "
>

    <div
        style="
            background:#17365D;
            color:white;
            padding:11px 14px;
            font-size:16px;
            font-weight:bold;
        "
    >
        Equipment
    </div>

    <div
        id="equipment-content"
        style="
            padding:12px 14px;
            max-height:560px;
            overflow-y:auto;
        "
    >
        {''.join(panel_items)}
    </div>

</div>
"""


# ============================================================
# CUSTOM TOOLTIP
# ============================================================

tooltip_html = """
<div
    id="custom-tooltip"
    style="
        display:none;
        position:fixed;
        z-index:9999;
        background:white;
        border:1px solid #777;
        box-shadow:0 2px 8px rgba(0,0,0,0.18);
        padding:10px 12px;
        font-family:Arial,sans-serif;
        font-size:13px;
        pointer-events:none;
        min-width:220px;
    "
>
</div>
"""


# ============================================================
# DATA FOR JAVASCRIPT
# ============================================================

week_data = {}

for week in weeks:

    week_key = week.strftime("%Y-%m-%d")

    items = []

    for category in categories:

        value = int(
            pivot.loc[week, category]
        )

        if value > 0:

            items.append(
                {
                    "type": category,
                    "losses": value,
                    "color": CATEGORY_COLORS[category],
                }
            )

    items.sort(
        key=lambda item: item["losses"],
        reverse=True,
    )

    total = int(
        weekly_totals.loc[week]
    )

    week_data[week_key] = {
        "items": items,
        "total": total,
    }


week_data_json = json.dumps(
    week_data,
    ensure_ascii=False,
)


# ============================================================
# HTML
# ============================================================

html = fig.to_html(
    full_html=True,
    include_plotlyjs=True,
    config={
        "displayModeBar": False,
        "responsive": True,
    },
)


# ============================================================
# INSERT CUSTOM UI + JAVASCRIPT
# ============================================================

insertion = f"""

<style>

html, body {{
    margin:0;
    padding:0;
    background:white;
}}

.equipment-item {{
    display:flex;
    align-items:center;
    margin-bottom:8px;
    line-height:1.2;
}}

.equipment-color {{
    width:12px;
    height:12px;
    min-width:12px;
    margin-right:8px;
    display:inline-block;
}}

.equipment-name {{
    font-size:13px;
    color:#333;
}}

.equipment-value {{
    margin-left:auto;
    font-weight:bold;
    color:#222;
}}

.equipment-total {{
    border-top:1px solid #CCCCCC;
    margin-top:10px;
    padding-top:10px;
    display:flex;
    justify-content:space-between;
    font-weight:bold;
    font-size:14px;
}}

</style>

{panel_html}

{tooltip_html}


<script>

document.addEventListener(
    "DOMContentLoaded",
    function() {{

        const gd =
            document.querySelector(
                ".plotly-graph-div"
            );

        const panel =
            document.getElementById(
                "equipment-panel"
            );

        const panelContent =
            document.getElementById(
                "equipment-content"
            );

        const tooltip =
            document.getElementById(
                "custom-tooltip"
            );


        const weekData =
            {week_data_json};


        let selectedWeek = null;

        let hoveredWeek = null;


        // ====================================================
        // GET WEEK DATA
        // ====================================================

        function getWeekItems(week) {{

            if (!weekData[week]) {{
                return [];
            }}

            return weekData[week].items
                .slice()
                .sort(
                    (a, b) =>
                        b.losses - a.losses
                );
        }}


        // ====================================================
        // RENDER EQUIPMENT PANEL
        // ====================================================

        function renderPanel(week) {{

            if (!week) {{

                panelContent.innerHTML =
                    {json.dumps("".join(panel_items))};

                return;
            }}


            const data =
                weekData[week];


            if (!data) {{
                return;
            }}


            const items =
                getWeekItems(week);


            let html = "";


            items.forEach(
                function(item) {{

                    html += `
                        <div class="equipment-item">

                            <span
                                class="equipment-color"
                                style="background:${{item.color}}"
                            ></span>

                            <span class="equipment-name">
                                ${{item.type}}
                            </span>

                            <span class="equipment-value">
                                ${{item.losses}}
                            </span>

                        </div>
                    `;
                }
            );


            html += `
                <div class="equipment-total">
                    <span>Total</span>
                    <span>${{data.total}}</span>
                </div>
            `;


            panelContent.innerHTML =
                html;
        }}


        // ====================================================
        // HIGHLIGHT SELECTED WEEK
        // ====================================================

        function highlightWeek(week) {{

            const opacityValues = [];


            for (
                let traceIndex = 0;
                traceIndex < gd.data.length;
                traceIndex++
            ) {{

                const trace =
                    gd.data[traceIndex];


                const values =
                    [];


                for (
                    let i = 0;
                    i < trace.x.length;
                    i++
                ) {{

                    const currentWeek =
                        String(
                            trace.x[i]
                        ).slice(0, 10);


                    if (!week) {{

                        values.push(
                            {BASE_OPACITY}
                        );

                    }} else if (
                        currentWeek === week
                    ) {{

                        values.push(
                            {SELECTED_OPACITY}
                        );

                    }} else {{

                        values.push(
                            {SELECTED_OTHER_OPACITY}
                        );
                    }}
                }}


                opacityValues.push(
                    values
                );
            }}


            Plotly.restyle(
                gd,
                {
                    "marker.opacity":
                        opacityValues
                }
            );
        }}


        // ====================================================
        // SELECTED WEEK LINE
        // ====================================================

        function updateSelectedLine(week) {{

            if (!week) {{

                Plotly.relayout(
                    gd,
                    {{
                        shapes: []
                    }}
                );

                return;
            }}


            const selectedDate =
                new Date(
                    week + "T00:00:00"
                );


            Plotly.relayout(
                gd,
                {{
                    shapes: [
                        {{
                            type: "line",

                            x0: selectedDate,

                            x1: selectedDate,

                            y0: 0,

                            y1: 1,

                            yref: "paper",

                            line: {{
                                color:
                                    "rgba(60,60,60,0.90)",

                                width: 2,

                                dash: "solid"
                            }}
                        }}
                    ]
                }}
            );
        }}


        // ====================================================
        // TOOLTIP
        // ====================================================

        function showTooltip(
            week,
            clientX,
            clientY
        ) {{

            const data =
                weekData[week];


            if (!data) {{
                return;
            }}


            const items =
                getWeekItems(week);


            let html = `
                <div
                    style="
                        font-weight:bold;
                        margin-bottom:8px;
                        font-size:14px;
                    "
                >
                    ${{week}}
                </div>
            `;


            items.forEach(
                function(item) {{

                    html += `
                        <div
                            style="
                                display:flex;
                                align-items:center;
                                margin-bottom:5px;
                            "
                        >

                            <span
                                style="
                                    width:10px;
                                    height:10px;
                                    background:${{item.color}};
                                    display:inline-block;
                                    margin-right:7px;
                                "
                            ></span>

                            <span>
                                ${{item.type}}
                            </span>

                            <span
                                style="
                                    margin-left:auto;
                                    padding-left:15px;
                                    font-weight:bold;
                                "
                            >
                                ${{item.losses}}
                            </span>

                        </div>
                    `;
                }
            );


            html += `
                <div
                    style="
                        border-top:1px solid #CCCCCC;
                        margin-top:7px;
                        padding-top:7px;
                        display:flex;
                        justify-content:space-between;
                        font-weight:bold;
                    "
                >
                    <span>Total</span>
                    <span>${{data.total}}</span>
                </div>
            `;


            tooltip.innerHTML =
                html;


            tooltip.style.display =
                "block";


            let left =
                clientX + 15;


            let top =
                clientY + 15;


            const rect =
                tooltip.getBoundingClientRect();


            if (
                left + rect.width >
                window.innerWidth - 10
            ) {{

                left =
                    clientX -
                    rect.width -
                    15;
            }}


            if (
                top + rect.height >
                window.innerHeight - 10
            ) {{

                top =
                    clientY -
                    rect.height -
                    15;
            }}


            tooltip.style.left =
                left + "px";


            tooltip.style.top =
                top + "px";
        }}


        function hideTooltip() {{

            tooltip.style.display =
                "none";
        }}


        // ====================================================
        // PLOTLY HOVER
        // ====================================================

        gd.on(
            "plotly_hover",
            function(eventData) {{

                if (
                    !eventData ||
                    !eventData.points ||
                    !eventData.points.length
                ) {{
                    return;
                }}


                const point =
                    eventData.points[0];


                const week =
                    String(point.x)
                    .slice(0, 10);


                hoveredWeek =
                    week;


                if (
                    eventData.event
                ) {{

                    showTooltip(
                        week,
                        eventData.event.clientX,
                        eventData.event.clientY
                    );
                }}
            }}
        );


        // ====================================================
        // PLOTLY UNHOVER
        // ====================================================

        gd.on(
            "plotly_unhover",
            function() {{

                hoveredWeek = null;

                hideTooltip();
            }}
        );


        // ====================================================
        // BAR CLICK
        // ====================================================

        gd.on(
            "plotly_click",
            function(eventData) {{

                if (
                    !eventData ||
                    !eventData.points ||
                    !eventData.points.length
                ) {{
                    return;
                }}


                const point =
                    eventData.points[0];


                const clickedWeek =
                    String(point.x)
                    .slice(0, 10);


                // --------------------------------------------
                // CLICK SELECTED WEEK AGAIN -> UNLOCK
                // --------------------------------------------

                if (
                    selectedWeek ===
                    clickedWeek
                ) {{

                    selectedWeek =
                        null;

                    highlightWeek(
                        null
                    );

                    updateSelectedLine(
                        null
                    );

                    renderPanel(
                        null
                    );

                    return;
                }}


                // --------------------------------------------
                // SELECT NEW WEEK
                // --------------------------------------------

                selectedWeek =
                    clickedWeek;


                highlightWeek(
                    selectedWeek
                );


                updateSelectedLine(
                    selectedWeek
                );


                renderPanel(
                    selectedWeek
                );
            }}
        );


        // ====================================================
        // EMPTY AREA CLICK
        // ====================================================

        gd.addEventListener(
            "click",
            function(event) {{

                const barPoint =
                    event.target.closest(
                        ".point"
                    );


                // Clicking a bar is handled
                // by plotly_click.
                if (barPoint) {{
                    return;
                }}


                if (!selectedWeek) {{
                    return;
                }}


                selectedWeek =
                    null;


                highlightWeek(
                    null
                );


                updateSelectedLine(
                    null
                );


                renderPanel(
                    null
                );
            }},
            true
        );


        // ====================================================
        // CLICK OUTSIDE CHART
        // ====================================================

        document.addEventListener(
            "click",
            function(event) {{

                if (!selectedWeek) {{
                    return;
                }}


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
                ) {{

                    selectedWeek =
                        null;


                    highlightWeek(
                        null
                    );


                    updateSelectedLine(
                        null
                    );


                    renderPanel(
                        null
                    );
                }}
            }
        );


        // ====================================================
        // TOOLTIP FOLLOWS CURSOR
        // ====================================================

        gd.addEventListener(
            "mousemove",
            function(event) {{

                if (
                    tooltip.style.display !==
                    "block"
                ) {{
                    return;
                }}


                if (!hoveredWeek) {{
                    return;
                }}


                const rect =
                    tooltip.getBoundingClientRect();


                let left =
                    event.clientX + 15;


                let top =
                    event.clientY + 15;


                if (
                    left + rect.width >
                    window.innerWidth - 10
                ) {{

                    left =
                        event.clientX -
                        rect.width -
                        15;
                }}


                if (
                    top + rect.height >
                    window.innerHeight - 10
                ) {{

                    top =
                        event.clientY -
                        rect.height -
                        15;
                }}


                tooltip.style.left =
                    left + "px";


                tooltip.style.top =
                    top + "px";
            }}
        );


    }}
);

</script>
"""


# ============================================================
# INSERT BEFORE </body>
# ============================================================

html = html.replace(
    "</body>",
    insertion + "\n</body>"
)


# ============================================================
# SAVE
# ============================================================

OUTPUT_FILE.write_text(
    html,
    encoding="utf-8"
)


print(
    f"Equipment plot saved to {OUTPUT_FILE}"
)

print(
    f"Weeks: {len(weeks)}"
)

print(
    f"Categories: {len(categories)}"
)

print(
    f"Records represented: {int(weekly_totals.sum())}"
)
