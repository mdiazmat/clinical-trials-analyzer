"""
Parsing helpers for ClinicalTrials.gov study JSON.
Each function extracts a specific piece of data from a study record
and handles missing fields gracefully.
"""

from datetime import datetime


def parse_date(date_str):
    """
    Convert API date strings to Python date objects.
    Handles both full dates (2023-06-15) and partial dates (2023-06).
    Partial dates are assumed to be the 1st of the month.
    Returns None if date is missing or unparseable.
    """
    if not date_str:
        return None
    
    # Try full date first
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        pass
    
    # Try year-month, assume day 1
    try:
        return datetime.strptime(date_str, "%Y-%m").date()
    except ValueError:
        pass
    
    # Try year only, assume Jan 1
    try:
        return datetime.strptime(date_str, "%Y").date()
    except ValueError:
        return None


def pick_highest_phase(phases_list):
    """
    Studies can list multiple phases (e.g., ['PHASE1', 'PHASE2']).
    We pick the highest phase for the single 'phase' column.
    Returns None if the list is empty or missing.
    """
    if not phases_list:
        return None
    
    phase_order = ["PHASE4", "PHASE3", "PHASE2", "PHASE1", "EARLY_PHASE1", "NA"]
    for phase in phase_order:
        if phase in phases_list:
            return phase
    return phases_list[0]  # fallback: whatever is first


def normalize_sponsor_name(name):
    """
    Basic sponsor name normalization to reduce duplicates.
    Strips whitespace, removes trailing punctuation, consolidates case.
    This is intentionally light; aggressive normalization needs human review.
    """
    if not name:
        return None
    
    name = name.strip()
    # Remove trailing commas, periods, etc.
    name = name.rstrip(".,;")
    return name


def parse_trial(study):
    """
    Extract fields for the trials table from a single study.
    Returns a dict matching the trials table schema.
    """
    protocol = study.get("protocolSection", {})
    
    identification = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    interventions_module = protocol.get("armsInterventionsModule", {})
    
    # Intervention: just grab the first one for the "primary" field
    interventions = interventions_module.get("interventions", [])
    primary_intervention = interventions[0] if interventions else {}
    
    # has_results: the API includes a hasResults flag at the study level
    has_results = study.get("hasResults", False)
    
    return {
        "nct_id": identification.get("nctId"),
        "brief_title": identification.get("briefTitle"),
        "official_title": identification.get("officialTitle"),
        "overall_status": status.get("overallStatus"),
        "phase": pick_highest_phase(design.get("phases", [])),
        "study_type": design.get("studyType"),
        "enrollment_count": design.get("enrollmentInfo", {}).get("count"),
        "start_date": parse_date(status.get("startDateStruct", {}).get("date")),
        "completion_date": parse_date(status.get("completionDateStruct", {}).get("date")),
        "primary_completion_date": parse_date(status.get("primaryCompletionDateStruct", {}).get("date")),
        "why_stopped": status.get("whyStopped"),
        "has_results": has_results,
        "primary_intervention_type": primary_intervention.get("type"),
        "primary_intervention_name": primary_intervention.get("name"),
    }


def parse_sponsors(study):
    """
    Extract sponsors (lead + collaborators) from a study.
    Returns a list of dicts: {sponsor_name, sponsor_class, lead_or_collaborator}.
    """
    protocol = study.get("protocolSection", {})
    sponsors_module = protocol.get("sponsorCollaboratorsModule", {})
    
    sponsors = []
    
    lead = sponsors_module.get("leadSponsor")
    if lead and lead.get("name"):
        sponsors.append({
            "sponsor_name": normalize_sponsor_name(lead.get("name")),
            "sponsor_class": lead.get("class"),
            "lead_or_collaborator": "LEAD"
        })
    
    collaborators = sponsors_module.get("collaborators", [])
    for collab in collaborators:
        if collab.get("name"):
            sponsors.append({
                "sponsor_name": normalize_sponsor_name(collab.get("name")),
                "sponsor_class": collab.get("class"),
                "lead_or_collaborator": "COLLABORATOR"
            })
    
    return sponsors


def parse_conditions(study):
    """Extract the list of conditions for a study."""
    protocol = study.get("protocolSection", {})
    conditions_module = protocol.get("conditionsModule", {})
    return conditions_module.get("conditions", [])


def parse_locations(study):
    """
    Extract trial site locations.
    Returns a list of dicts matching the locations table schema.
    """
    protocol = study.get("protocolSection", {})
    locations_module = protocol.get("contactsLocationsModule", {})
    raw_locations = locations_module.get("locations", [])
    
    parsed = []
    for loc in raw_locations:
        parsed.append({
            "facility_name": loc.get("facility"),
            "city": loc.get("city"),
            "state": loc.get("state"),
            "country": loc.get("country"),
            "status": loc.get("status"),
        })
    return parsed