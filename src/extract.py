"""
Extract Phase 2/3 oncology clinical trials from ClinicalTrials.gov API.
Saves raw JSON responses to data/raw/ in batches.
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime

# Configuration
BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
OUTPUT_DIR = Path("data/raw")
PAGE_SIZE = 1000  # max allowed by API
REQUEST_DELAY = 0.5  # seconds between requests 
MAX_RETRIES = 3

# Query parameters: Phase 2 or Phase 3 cancer trials, started 2015 or later
QUERY_PARAMS = {
    "query.cond": "cancer",
    "filter.advanced": "AREA[Phase]PHASE2 OR AREA[Phase]PHASE3",
    "pageSize": PAGE_SIZE,
    "format": "json",
    "countTotal": "true"
}

def fetch_page(params, retries=MAX_RETRIES):
    """
    Fetch a single page from the API with retry logic.
    Returns parsed JSON response or raises an exception on final failure.
    """
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                wait = 2 ** attempt  # exponential backoff: 2s, 4s, 8s
                print(f"  Waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                raise

def extract_all_trials():
    """
    Split the results across multiple pages through all matching trials and save raw JSON to disk.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # First request to get total count and first page
    params = QUERY_PARAMS.copy()
    print("Fetching page 1...")
    data = fetch_page(params)
    
    total_count = data.get("totalCount", 0)
    studies = data.get("studies", [])
    next_page_token = data.get("nextPageToken")
    
    print(f"Total trials matching query: {total_count}")
    print(f"Page 1 returned {len(studies)} studies")
    
    # Save page 1
    page_num = 1
    save_page(studies, page_num)
    
    # Loop through remaining pages
    while next_page_token:
        page_num += 1
        params = QUERY_PARAMS.copy()
        params["pageToken"] = next_page_token
        
        print(f"Fetching page {page_num}...")
        time.sleep(REQUEST_DELAY)
        
        data = fetch_page(params)
        studies = data.get("studies", [])
        next_page_token = data.get("nextPageToken")
        
        if studies:
            save_page(studies, page_num)
            print(f"  Saved {len(studies)} studies (running total: ~{page_num * PAGE_SIZE})")
        else:
            print("  Empty page, stopping.")
            break
    
    print(f"\nExtraction complete. Total pages saved: {page_num}")


def save_page(studies, page_num):
    """Save a single page of studies to a JSON file."""
    filename = OUTPUT_DIR / f"page_{page_num:04d}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(studies, f, indent=2)

if __name__ == "__main__":
    start_time = datetime.now()
    print(f"Extraction started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        extract_all_trials()
    except Exception as e:
        print(f"\nExtraction failed: {e}")
        raise
    
    elapsed = datetime.now() - start_time
    print(f"Elapsed time: {elapsed}")