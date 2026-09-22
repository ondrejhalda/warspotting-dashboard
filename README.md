**WarSpotting Dashboard**

Automated Python pipeline and interactive dashboard for documented Russian military equipment losses recorded by WarSpotting.

**Why I built this project**

This project started as a way to practice data-analysis tools and Python programming on a real, continuously changing dataset rather than a prepared training dataset.
It also provides a public example of my own work, problem-solving and development process.

**Project goal**

The main question is:
How does the intensity and composition of documented Russian equipment losses change over time?

The current version focuses on building the data pipeline and an interactive weekly dashboard. The next phase will expand the analytical and reporting layer.

**What the project does**

Collects Russian equipment-loss records from the WarSpotting API.
Maintains historical data from 24 February 2022 onward.
Updates recent records automatically.
Refreshes the latest 10 days to capture changes to recent records.
Uses unique WarSpotting IDs for deduplication and synchronization.
Validates the data before producing analytical outputs.
Periodically reconciles the local dataset against the current source.
Aggregates losses by week and equipment category.
Generates an interactive Plotly dashboard.
Publishes the results as HTML and supporting CSV/JSON outputs.
Runs automatically through GitHub Actions.

**Data workflow**

WarSpotting API
       ↓
Data ingestion
       ↓
Recent-data refresh
       ↓
Deduplication
       ↓
Source reconciliation
       ↓
Data validation
       ↓
Weekly aggregation
       ↓
Plotly dashboard
       ↓
GitHub Actions

**Data scope and methodology**

The analytical dataset currently contains records that:
have lost_by = Russia
fall within the project scope 24 February 2022 → present
have a unique WarSpotting loss ID
Weekly analysis uses Monday-based weeks.

The dashboard reports documented losses recorded by WarSpotting. It is not intended to represent a complete count of all real-world military losses.

**Data quality and synchronization**

Data quality is built into the pipeline.

Checks include:
required columns
missing and duplicate IDs
invalid dates
date scope
lost_by consistency
equipment categories
raw vs. aggregated record counts

During development, a real mismatch was found between the WarSpotting source and the local dataset. The investigation identified both missing source records and local-only records.

A full-source reconciliation was added to compare source and local IDs within the project scope.

The dashboard exposes the synchronization status:
Source records in project scope
Local records
Missing source IDs
Local-only IDs
Sync status

Critical pipeline failures stop the run. Validation and synchronization status are shown in the dashboard when output generation succeeds.

**Automation**

GitHub Actions handles the automated update.

Regular update
The daily process uses:
WarSpotting /recent
a rolling 10-day refresh
deduplication
validation
regeneration of analytical outputs and the dashboard

Periodic full reconciliation
A scheduled full-source reconciliation checks the complete source/local ID set. This captures historical changes that may not be visible in the normal recent-data update without downloading the full source on every run.
A full reconciliation can also be triggered manually.

**Dashboard**

The main output is equipment_weekly.html, an interactive Plotly dashboard with:
weekly stacked equipment-loss chart
equipment category filtering
week selection
weekly category breakdown in the tooltip
selected-week highlighting
Data Quality and source synchronization information
Technical data
Methodology and limitations

The project was also tested in Streamlit during development. The final public version uses standalone Plotly HTML because it preserved the full Plotly interaction and provided a more stable presentation.

**Development path**

The project evolved from a simple data import and visualization exercise into an automated analytical workflow.

Key stages:
Initial historical WarSpotting API import and pagination.
Building the raw historical dataset.
Creating incremental updates and recent-data refreshes.
Adding weekly equipment aggregation.
Developing the interactive Plotly dashboard and filters.
Adding week selection, hover details and reporting panels.
Building data-quality validation.
Investigating a real source-vs-local data mismatch.
Adding ID-based source reconciliation and safer synchronization.
Separating daily updates from periodic full reconciliation.
Finalizing the dashboard and GitHub Actions automation.

This project therefore includes both data analytics and substantial Python/data-engineering work.

**Technology stack**

Python
Pandas
Requests
Plotly
Matplotlib
HTML / JavaScript
GitHub Actions
CSV / JSON

**Current status**

The current version provides a working automated data pipeline, source synchronization checks, data-quality reporting and an interactive weekly dashboard.

Next phase
The project will now move further into analytical insights and reporting, including:
loss-intensity trends over time
changes in equipment composition
category-specific trends
unusual periods
additional analytical indicators
structured reporting of findings
Further code hardening and larger architectural refactoring are intentionally left for a later phase.

**Limitations**

This project analyses documented WarSpotting records, not a complete or independently verified census of all military losses.
Source data can be added, modified or revised over time, and some records contain incomplete metadata.
The dashboard should therefore be interpreted as exploratory analysis of documented OSINT data.

**Source**

WarSpotting
https://ukr.warspotting.net/

**This is an independent data-analysis and programming project based on publicly available OSINT data.**
