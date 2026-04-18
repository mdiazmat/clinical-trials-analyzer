"""
Load parsed trial data from data/raw/*.json into the PostgreSQL database.
Handles deduplication of sponsors and conditions, and junction table inserts.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

from .parsers import (
    parse_trial,
    parse_sponsors,
    parse_conditions,
    parse_locations,
)

load_dotenv()

RAW_DATA_DIR = Path("data/raw")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


def get_connection():
    return psycopg.connect(**DB_CONFIG)


def truncate_all_tables(conn):
    """Clear all tables before loading. Useful during development."""
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE TABLE trial_sponsors, trial_conditions, locations,
                           trials, sponsors, sponsors, conditions
            RESTART IDENTITY CASCADE;
        """)
    conn.commit()
    print("Cleared all tables.")


def insert_trial(cur, trial):
    """Insert one trial record. Skips if nct_id is None."""
    if not trial["nct_id"]:
        return False
    
    cur.execute("""
        INSERT INTO trials (
            nct_id, brief_title, official_title, overall_status, phase,
            study_type, enrollment_count, start_date, completion_date,
            primary_completion_date, why_stopped, has_results,
            primary_intervention_type, primary_intervention_name
        ) VALUES (
            %(nct_id)s, %(brief_title)s, %(official_title)s, %(overall_status)s,
            %(phase)s, %(study_type)s, %(enrollment_count)s, %(start_date)s,
            %(completion_date)s, %(primary_completion_date)s, %(why_stopped)s,
            %(has_results)s, %(primary_intervention_type)s, %(primary_intervention_name)s
        )
        ON CONFLICT (nct_id) DO NOTHING;
    """, trial)
    return True


def get_or_create_sponsor(cur, sponsor_name, sponsor_class, sponsor_cache):
    """
    Look up a sponsor by name. If not in DB, insert and return new ID.
    Uses an in-memory cache to avoid repeat DB lookups for the same name.
    """
    if sponsor_name in sponsor_cache:
        return sponsor_cache[sponsor_name]
    
    cur.execute("""
        INSERT INTO sponsors (sponsor_name, sponsor_class)
        VALUES (%s, %s)
        ON CONFLICT (sponsor_name) DO UPDATE
            SET sponsor_class = EXCLUDED.sponsor_class
        RETURNING sponsor_id;
    """, (sponsor_name, sponsor_class))
    
    sponsor_id = cur.fetchone()[0]
    sponsor_cache[sponsor_name] = sponsor_id
    return sponsor_id


def get_or_create_condition(cur, condition_name, condition_cache):
    """Same pattern as sponsors but for conditions."""
    if condition_name in condition_cache:
        return condition_cache[condition_name]
    
    cur.execute("""
        INSERT INTO conditions (condition_name)
        VALUES (%s)
        ON CONFLICT (condition_name) DO NOTHING
        RETURNING condition_id;
    """, (condition_name,))
    
    result = cur.fetchone()
    if result is None:
        # ON CONFLICT DO NOTHING returned no row, so fetch the existing ID
        cur.execute("SELECT condition_id FROM conditions WHERE condition_name = %s",
                    (condition_name,))
        result = cur.fetchone()
    
    condition_id = result[0]
    condition_cache[condition_name] = condition_id
    return condition_id


def insert_trial_sponsors(cur, nct_id, sponsors, sponsor_cache):
    """Link a trial to all its sponsors via the junction table."""
    for s in sponsors:
        if not s["sponsor_name"]:
            continue
        sponsor_id = get_or_create_sponsor(
            cur, s["sponsor_name"], s["sponsor_class"], sponsor_cache
        )
        cur.execute("""
            INSERT INTO trial_sponsors (nct_id, sponsor_id, lead_or_collaborator)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (nct_id, sponsor_id, s["lead_or_collaborator"]))


def insert_trial_conditions(cur, nct_id, conditions, condition_cache):
    """Link a trial to all its conditions via the junction table."""
    for condition_name in conditions:
        if not condition_name:
            continue
        condition_id = get_or_create_condition(cur, condition_name, condition_cache)
        cur.execute("""
            INSERT INTO trial_conditions (nct_id, condition_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (nct_id, condition_id))


def insert_locations(cur, nct_id, locations):
    """Insert all locations for one trial."""
    for loc in locations:
        cur.execute("""
            INSERT INTO locations (nct_id, facility_name, city, state, country, status)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (nct_id, loc["facility_name"], loc["city"], loc["state"],
              loc["country"], loc["status"]))


def process_study(cur, study, sponsor_cache, condition_cache):
    """Parse and insert one study and all its related data."""
    trial = parse_trial(study)
    inserted = insert_trial(cur, trial)
    if not inserted:
        return False
    
    nct_id = trial["nct_id"]
    
    sponsors = parse_sponsors(study)
    insert_trial_sponsors(cur, nct_id, sponsors, sponsor_cache)
    
    conditions = parse_conditions(study)
    insert_trial_conditions(cur, nct_id, conditions, condition_cache)
    
    locations = parse_locations(study)
    insert_locations(cur, nct_id, locations)
    
    return True


def load_all_pages():
    """Main loop: process every JSON file in data/raw/."""
    page_files = sorted(RAW_DATA_DIR.glob("page_*.json"))
    print(f"Found {len(page_files)} page files to load.")
    
    sponsor_cache = {}
    condition_cache = {}
    
    total_loaded = 0
    total_skipped = 0
    
    with get_connection() as conn:
        truncate_all_tables(conn)
        
        with conn.cursor() as cur:
            for page_file in page_files:
                with open(page_file, "r", encoding="utf-8") as f:
                    studies = json.load(f)
                
                page_loaded = 0
                page_skipped = 0
                for study in studies:
                    try:
                        if process_study(cur, study, sponsor_cache, condition_cache):
                            page_loaded += 1
                        else:
                            page_skipped += 1
                    except Exception as e:
                        page_skipped += 1
                        print(f"  Error on study {study.get('protocolSection', {}).get('identificationModule', {}).get('nctId', 'unknown')}: {e}")
                
                conn.commit()  # commit after each page
                total_loaded += page_loaded
                total_skipped += page_skipped
                print(f"{page_file.name}: loaded {page_loaded}, skipped {page_skipped} (running total loaded: {total_loaded})")
    
    print(f"\nLoad complete.")
    print(f"  Total loaded: {total_loaded}")
    print(f"  Total skipped: {total_skipped}")
    print(f"  Unique sponsors: {len(sponsor_cache)}")
    print(f"  Unique conditions: {len(condition_cache)}")


if __name__ == "__main__":
    load_all_pages()