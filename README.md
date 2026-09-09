WarSpotting Equipment Loss Dashboard

Automated data analytics pipeline for tracking documented Russian military equipment losses in the Russo-Ukrainian war using the WarSpotting API.

The project combines Python data collection, data validation, time-series analysis, visualization and GitHub Actions automation into a reproducible analytics pipeline.

Project Overview

The goal of this project is to build a reproducible pipeline that automatically collects WarSpotting data, validates the dataset, aggregates equipment losses by week and generates a dashboard showing the development of documented losses over time.

The project currently focuses on Russian equipment losses recorded from January 1, 2026 onward.

The main output is a weekly time-series dashboard containing:

total documented losses
losses recorded during the latest week
four-week average
weekly loss counts
cumulative documented losses
data integrity check

The project is designed as a portfolio example of an automated data analytics workflow rather than as an attempt to reproduce the WarSpotting website.

Dashboard

The dashboard presents weekly documented Russian equipment losses as bars, with cumulative documented losses shown as a secondary line.

The dashboard is automatically regenerated whenever the pipeline runs.

Current output:

dashboard.png

Data Source

Data is collected from the WarSpotting API.

WarSpotting API documentation

WarSpotting describes itself as a database of documented material losses during the Russian invasion of Ukraine. Its methodology relies on visual evidence from open sources rather than claims from official parties.

The API provides individual loss records containing information such as:

loss ID
equipment type
model
status
recorded date
location
unit, where known
additional tags

The API supports date-based queries and pagination. A maximum of 100 records can be returned per page, with additional pages available when more records exist for a given date. The API also limits request frequency to 10 requests per 10 seconds.

Data Scope

Current project scope:

Parameter	Value
Source	WarSpotting API
Belligerent	Russia
Data type	Documented equipment losses
Start date	2026-01-01
Update frequency	Daily
Refresh window	10 days
Aggregation	Weekly
Primary language	Python

The project currently analyzes Russian losses only.

Data Pipeline

The complete pipeline is:

WarSpotting API
       │
       ▼
API pagination
       │
       ▼
10-day refresh window
       │
       ▼
Raw data
       │
       ▼
Deduplication
       │
       ▼
Data validation
       │
       ▼
Weekly aggregation
       │
       ├── Weekly losses
       ├── Cumulative losses
       └── 4-week rolling average
       │
       ▼
Dashboard
       │
       ▼
GitHub repository
       ▲
       │
GitHub Actions
Automated Data Collection

The pipeline is implemented in dashboard.py.

On each run:

Existing raw data is loaded from warspotting_raw_2026.csv.
The most recent 10 days are downloaded again.
New dates since the previous run are downloaded.
API pagination is used when a day contains more than 100 records.
Refreshed data replaces the corresponding existing records.
Records are deduplicated using the WarSpotting loss id.
The complete dataset is validated.
Weekly statistics are calculated.
The dashboard is generated.
Updated files are committed back to GitHub.

The 10-day refresh window is intended to capture late updates and corrections to recent records.

Data Validation

The pipeline performs several automated quality checks before generating the dashboard.

Required fields

The dataset must contain:

id
type
model
status
lost_by
date
nearest_location
geo
unit
tags
Additional checks

The pipeline verifies:

dataset is not empty
IDs are not missing
IDs are unique
dates are valid
dates are not before the project start date
dates are not in the future
lost_by contains the expected value
equipment type is present

If a critical validation fails, the pipeline stops instead of generating an apparently valid dashboard from invalid data.

Weekly Analysis

Daily records are converted into Monday-based weekly periods.

For each week the pipeline calculates:

Weekly losses

Number of documented equipment-loss records assigned to that week.

Cumulative losses

Running total of documented losses:

Week 1
Week 1 + Week 2
Week 1 + Week 2 + Week 3
...
Four-week average

Mean number of documented losses across the latest four weekly periods.

This metric is used as a simple short-term trend indicator rather than as a forecasting model.

Dashboard Metrics
TOTAL LOSSES

Total number of unique WarSpotting loss records currently contained in the project's dataset.

This represents documented equipment losses, not an estimate of total real-world equipment losses.

THIS WEEK

Number of records assigned to the week containing the latest available data.

The latest week may be incomplete.

Therefore, the current week's value should not automatically be compared with completed previous weeks without considering the number of days represented.

4-WEEK AVG

Average weekly number of documented losses across the latest four weekly periods.

Because the latest period can be incomplete, this metric can also be affected by a partially completed week.

DATA CHECK

Internal integrity check comparing:

sum of weekly losses
        =
total number of records

The dashboard displays:

DATA CHECK: OK

when the two values match.

Important Data Limitations

WarSpotting data should be interpreted with caution.

WarSpotting explicitly states that its database does not correspond to the actual amount of losses, although it aims to approach the real figure. Losses are added when sufficient visual evidence exists, and evidence can sometimes be misleading or of insufficient quality.

Therefore:

Documented losses ≠ total actual losses

The dataset should be interpreted as a measure of visually documented equipment losses, not as a complete census of battlefield losses.

Visual confirmation bias

Equipment without publicly available visual evidence may not appear in the database.

Consequently, changes in the number of documented losses can reflect both:

actual battlefield losses
availability of evidence and subsequent documentation
Recorded date vs. actual loss date

The date associated with a WarSpotting record should not automatically be interpreted as the exact date on which the equipment was lost.

WarSpotting notes that recorded dates can sometimes differ substantially from the actual loss date because they may be derived from evidence or situation reports.

Late discoveries

A loss may be discovered and added to the database after the event occurred. WarSpotting's API documentation specifically notes that recently added losses can include losses that actually occurred earlier.

This project therefore refreshes the most recent 10 days on every run.

However, this does not completely eliminate late-discovery bias. A record referring to an older event may be added outside the 10-day refresh window.

A future version of the pipeline could use the API's recently-added endpoint to identify such records independently of their recorded loss date.

Current-week effect

The latest week is often incomplete.

For example:

Completed week       23 losses
Completed week       28 losses
Current partial week  5 losses

The current week's lower value does not necessarily indicate a decrease in the underlying loss rate.

Technology Stack
Python

Used for:

API requests
data processing
validation
aggregation
visualization

Main libraries:

requests
pandas
matplotlib
GitHub

Used for:

source-code version control
raw data storage
generated outputs
project documentation
GitHub Actions

Used to automate the pipeline.

The workflow:

schedule
   ↓
Python environment
   ↓
install dependencies
   ↓
run dashboard.py
   ↓
generate outputs
   ↓
commit updated files
Repository Structure
warspotting-dashboard/
│
├── .github/
│   └── workflows/
│       └── update.yml
│
├── dashboard.py
├── requirements.txt
├── warspotting_raw_2026.csv
├── weekly_losses_2026.csv
├── dashboard.png
└── README.md
dashboard.py

Main data pipeline and dashboard generation script.

requirements.txt

Python dependencies required to run the pipeline.

warspotting_raw_2026.csv

Raw/processed WarSpotting records used by the project.

weekly_losses_2026.csv

Weekly analytical dataset generated by the pipeline.

dashboard.png

Generated dashboard visualization.

.github/workflows/update.yml

GitHub Actions workflow responsible for automated execution.

Automation

The pipeline is configured to run automatically using GitHub Actions.

It can also be triggered manually using:

Actions
→ Update WarSpotting Dashboard
→ Run workflow

The workflow uses the existing CSV as the baseline and incrementally updates it rather than downloading the entire dataset from scratch on every run.

Why This Project?

The project was designed to demonstrate a complete data analytics workflow:

Data acquisition
        ↓
Data engineering
        ↓
Data cleaning
        ↓
Data validation
        ↓
SQL/analytical thinking
        ↓
Time-series analysis
        ↓
Data visualization
        ↓
Automation

The emphasis is on building a reproducible analytical process, rather than producing a one-off visualization.

Future Development

Potential future extensions include:

equipment-category analysis
destroyed vs captured vs abandoned vs damaged
weekly trends by equipment type
comparison of equipment categories
monthly aggregation
anomaly detection
moving averages and trend analysis
geographic analysis
additional statistical analysis
interactive dashboard
database storage instead of CSV
improved handling of late-discovered records using the API's recently-added endpoint

These extensions will be added only after the core pipeline remains stable and reproducible.

Methodological Note

This project is an independent analysis of publicly available WarSpotting data.

The dashboard does not attempt to estimate total Russian military losses, battlefield strength, or military effectiveness.

Its primary purpose is to demonstrate how a continuously updated open-source dataset can be transformed into a reproducible analytical workflow.

The numbers shown by this project should therefore be interpreted as documented observations within the WarSpotting dataset, not as a complete measurement of real-world losses.

Source

WarSpotting — documented material losses in the Russo-Ukrainian war

WarSpotting

WarSpotting API documentation
