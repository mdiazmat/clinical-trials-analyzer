# Clinical Trials Landscape Analyzer

End-to-end data pipeline and Tableau dashboard analyzing 47,000+ Phase 2 and Phase 3 oncology clinical trials from ClinicalTrials.gov spanning six decades of research (1966-2030), with focused analysis of post-2010 trends.

## Project Status
In progress. 2-week build timeline.

## Tech Stack
- Python (requests, pandas, psycopg2)
- PostgreSQL
- Tableau Public
- ClinicalTrials.gov API v2

## Project Overview
This project extracts oncology trial data from the ClinicalTrials.gov API, loads it into a normalized PostgreSQL database, and visualizes trends in Tableau. The dashboard covers four views: overview metrics, sponsor analysis, condition deep-dives, and geographic distribution of trial sites.

The full dataset spans 1966 to 2030 (planned trial start dates), with detailed analysis focused on the post-2010 period where data coverage is most robust. This design choice allows the project to show both historical context and modern trends in oncology research.

## Data Notes
- Date coverage is uneven: pre-2010 trials are sparsely represented due to historical reporting requirements, so trend analysis focuses on post-2010
- Some future-dated trials (2025+) are planned but not yet started, and are excluded from completion-rate metrics
- Condition names are free-text in ClinicalTrials.gov, so the 17,800+ unique condition strings include variations of the same disease (e.g., "NSCLC" vs "Non-Small Cell Lung Cancer"). No deduplication was applied; this reflects the raw data
- Sponsor normalization was intentionally light (whitespace/punctuation only) to avoid making incorrect merges

## Dashboard
Tableau Public link coming soon.

## Database Schema
ER diagram coming soon. Six tables total: four entity tables (trials, sponsors, conditions, locations) and two junction tables (trial_sponsors, trial_conditions).

## Key Findings
To be added at project completion.

## Repo Structure

```
clinical-trials-analyzer/
├── sql/                  SQL schema and analytical queries
├── src/                  Python scripts for extraction and ETL
├── data/                 Raw and processed data (gitignored)
├── docs/                 ER diagram and dashboard screenshots
└── notebooks/            Exploratory analysis
```

## Setup
1. Clone the repo
2. Create a Python virtual environment and install requirements.txt
3. Set up PostgreSQL and run sql/schema.sql
4. Copy .env.example to .env and fill in your DB credentials
5. Run src/extract.py to pull data from the API
6. Run src/load.py to populate the database

## Data Source
ClinicalTrials.gov API v2: https://clinicaltrials.gov/api/v2/studies

## Author
Martha Diaz-Matamoros  
MS Data Science and Business Analytics, UNC Charlotte
