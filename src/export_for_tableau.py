"""
Run analytical queries against PostgreSQL and export each result to CSV.
Output files are written to data/processed/tableau_csvs/ for use in Tableau.
"""

import os
import csv
from pathlib import Path
from dotenv import load_dotenv
import psycopg

load_dotenv()

OUTPUT_DIR = Path("data/processed/tableau_csvs")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


# Each entry: (output_filename, SQL query)
# Filenames match the dashboard structure for easy reference in Tableau.
QUERIES = [
    # Dashboard 1: Overview
    ("q1_1_kpis.csv", """
        SELECT
            COUNT(*) AS total_trials,
            COUNT(*) FILTER (WHERE overall_status = 'COMPLETED') AS completed_trials,
            COUNT(*) FILTER (WHERE overall_status IN ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING')) AS active_trials,
            COUNT(*) FILTER (WHERE overall_status = 'TERMINATED') AS terminated_trials,
            ROUND(AVG(enrollment_count) FILTER (WHERE enrollment_count BETWEEN 1 AND 10000)) AS avg_enrollment
        FROM trials
        WHERE start_date >= '2010-01-01';
    """),

    ("q1_2_trials_over_time.csv", """
        SELECT
            EXTRACT(YEAR FROM start_date)::INTEGER AS start_year,
            phase,
            COUNT(*) AS trial_count
        FROM trials
        WHERE start_date >= '2010-01-01'
          AND start_date < '2026-01-01'
        GROUP BY start_year, phase
        ORDER BY start_year, phase;
    """),

    ("q1_3_status_breakdown.csv", """
        SELECT
            overall_status,
            COUNT(*) AS trial_count,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS percentage
        FROM trials
        WHERE start_date >= '2010-01-01'
        GROUP BY overall_status
        ORDER BY trial_count DESC;
    """),

    # Dashboard 2: Sponsors
    ("q2_1_class_completion_rates.csv", """
        SELECT
            s.sponsor_class,
            COUNT(DISTINCT t.nct_id) AS total_trials,
            COUNT(DISTINCT t.nct_id) FILTER (WHERE t.overall_status = 'COMPLETED') AS completed_trials,
            COUNT(DISTINCT t.nct_id) FILTER (WHERE t.overall_status = 'TERMINATED') AS terminated_trials,
            ROUND(
                100.0 * COUNT(DISTINCT t.nct_id) FILTER (WHERE t.overall_status = 'COMPLETED')
                / NULLIF(COUNT(DISTINCT t.nct_id) FILTER (WHERE t.overall_status IN ('COMPLETED', 'TERMINATED')), 0),
                1
            ) AS completion_rate_pct
        FROM trials t
        JOIN trial_sponsors ts ON t.nct_id = ts.nct_id
        JOIN sponsors s ON ts.sponsor_id = s.sponsor_id
        WHERE ts.lead_or_collaborator = 'LEAD'
          AND t.start_date >= '2010-01-01'
          AND s.sponsor_class IS NOT NULL
        GROUP BY s.sponsor_class
        ORDER BY total_trials DESC;
    """),

    ("q2_2_top_20_sponsors.csv", """
        SELECT
            s.sponsor_name,
            s.sponsor_class,
            COUNT(DISTINCT t.nct_id) AS total_trials,
            COUNT(DISTINCT t.nct_id) FILTER (WHERE t.overall_status = 'COMPLETED') AS completed_trials,
            COUNT(DISTINCT t.nct_id) FILTER (WHERE t.overall_status = 'TERMINATED') AS terminated_trials,
            ROUND(
                100.0 * COUNT(DISTINCT t.nct_id) FILTER (WHERE t.overall_status = 'COMPLETED')
                / NULLIF(COUNT(DISTINCT t.nct_id) FILTER (WHERE t.overall_status IN ('COMPLETED', 'TERMINATED')), 0),
                1
            ) AS completion_rate_pct
        FROM sponsors s
        JOIN trial_sponsors ts ON s.sponsor_id = ts.sponsor_id
        JOIN trials t ON ts.nct_id = t.nct_id
        WHERE ts.lead_or_collaborator = 'LEAD'
          AND t.start_date >= '2010-01-01'
        GROUP BY s.sponsor_name, s.sponsor_class
        HAVING COUNT(DISTINCT t.nct_id) >= 20
        ORDER BY total_trials DESC
        LIMIT 20;
    """),

    ("q2_3_duration_by_class.csv", """
        SELECT
            s.sponsor_class,
            COUNT(*) AS completed_trial_count,
            ROUND(AVG(t.completion_date - t.start_date), 0) AS avg_duration_days,
            ROUND(AVG(t.completion_date - t.start_date) / 365.0, 1) AS avg_duration_years
        FROM trials t
        JOIN trial_sponsors ts ON t.nct_id = ts.nct_id
        JOIN sponsors s ON ts.sponsor_id = s.sponsor_id
        WHERE ts.lead_or_collaborator = 'LEAD'
          AND t.overall_status = 'COMPLETED'
          AND t.start_date >= '2010-01-01'
          AND t.completion_date IS NOT NULL
          AND t.completion_date > t.start_date
          AND s.sponsor_class IS NOT NULL
        GROUP BY s.sponsor_class
        ORDER BY completed_trial_count DESC;
    """),

    # Dashboard 3: Conditions
    ("q3_1_top_25_conditions.csv", """
        SELECT
            c.condition_name,
            COUNT(DISTINCT tc.nct_id) AS trial_count,
            COUNT(DISTINCT tc.nct_id) FILTER (WHERE t.phase = 'PHASE3') AS phase3_count,
            COUNT(DISTINCT tc.nct_id) FILTER (WHERE t.overall_status = 'COMPLETED') AS completed_count
        FROM conditions c
        JOIN trial_conditions tc ON c.condition_id = tc.condition_id
        JOIN trials t ON tc.nct_id = t.nct_id
        WHERE t.start_date >= '2010-01-01'
        GROUP BY c.condition_name
        ORDER BY trial_count DESC
        LIMIT 25;
    """),

    ("q3_2_intervention_types.csv", """
        SELECT
            COALESCE(primary_intervention_type, 'UNKNOWN') AS intervention_type,
            COUNT(*) AS trial_count,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS percentage
        FROM trials
        WHERE start_date >= '2010-01-01'
        GROUP BY primary_intervention_type
        ORDER BY trial_count DESC;
    """),

    ("q3_3_intervention_over_time.csv", """
        SELECT
            EXTRACT(YEAR FROM start_date)::INTEGER AS start_year,
            COUNT(*) FILTER (WHERE primary_intervention_type = 'DRUG') AS drug_trials,
            COUNT(*) FILTER (WHERE primary_intervention_type = 'BIOLOGICAL') AS biological_trials,
            COUNT(*) FILTER (WHERE primary_intervention_type = 'RADIATION') AS radiation_trials,
            COUNT(*) FILTER (WHERE primary_intervention_type = 'PROCEDURE') AS procedure_trials,
            COUNT(*) AS total_trials
        FROM trials
        WHERE start_date >= '2010-01-01'
          AND start_date < '2026-01-01'
        GROUP BY start_year
        ORDER BY start_year;
    """),

    # Dashboard 4: Geography
    ("q4_1_trials_by_country.csv", """
        SELECT
            l.country,
            COUNT(DISTINCT l.nct_id) AS trial_count,
            COUNT(*) AS site_count
        FROM locations l
        JOIN trials t ON l.nct_id = t.nct_id
        WHERE t.start_date >= '2010-01-01'
          AND l.country IS NOT NULL
        GROUP BY l.country
        ORDER BY trial_count DESC;
    """),

    ("q4_2_trials_by_us_state.csv", """
        SELECT
            l.state,
            COUNT(DISTINCT l.nct_id) AS trial_count,
            COUNT(*) AS site_count
        FROM locations l
        JOIN trials t ON l.nct_id = t.nct_id
        WHERE t.start_date >= '2010-01-01'
          AND l.country = 'United States'
          AND l.state IS NOT NULL
        GROUP BY l.state
        ORDER BY trial_count DESC;
    """),

    ("q4_3_geographic_reach_by_class.csv", """
        SELECT
            s.sponsor_class,
            COUNT(DISTINCT l.country) AS countries_reached,
            COUNT(DISTINCT l.nct_id) AS trials_with_locations,
            ROUND(
                COUNT(DISTINCT l.nct_id || '-' || l.country)::NUMERIC
                / NULLIF(COUNT(DISTINCT l.nct_id), 0),
                2
            ) AS avg_countries_per_trial
        FROM locations l
        JOIN trials t ON l.nct_id = t.nct_id
        JOIN trial_sponsors ts ON t.nct_id = ts.nct_id
        JOIN sponsors s ON ts.sponsor_id = s.sponsor_id
        WHERE t.start_date >= '2010-01-01'
          AND ts.lead_or_collaborator = 'LEAD'
          AND s.sponsor_class IS NOT NULL
        GROUP BY s.sponsor_class
        ORDER BY trials_with_locations DESC;
    """),
]


def export_query_to_csv(conn, query, output_path):
    """Run one query and write the results to a CSV with column headers."""
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        column_names = [desc[0] for desc in cur.description]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(column_names)
        writer.writerows(rows)
    
    return len(rows)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Exporting {len(QUERIES)} queries to {OUTPUT_DIR}/")
    print()
    
    with psycopg.connect(**DB_CONFIG) as conn:
        for filename, query in QUERIES:
            output_path = OUTPUT_DIR / filename
            try:
                row_count = export_query_to_csv(conn, query, output_path)
                print(f"  {filename:<40} {row_count:>6} rows")
            except Exception as e:
                print(f"  {filename:<40} FAILED: {e}")
    
    print()
    print("Export complete.")


if __name__ == "__main__":
    main()