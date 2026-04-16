-- Clinacal Trials Landscape Analyzer
-- Schema for oncology clinical trials data from ClinicalTrials.gov
-- -- 6 tables: 4 entity (trials, sponsors, conditions, locations) + 2 junction (trial_sponsors, trial_conditions)

-- Drop tables if they exist (useful for re-running during development)
DROP TABLE IF EXISTS trial_sponsors CASCADE;
DROP TABLE IF EXISTS trial_conditions CASCADE;
DROP TABLE IF EXISTS locations CASCADE;
DROP TABLE IF EXISTS trials CASCADE;
DROP TABLE IF EXISTS sponsors CASCADE;
DROP TABLE IF EXISTS conditions CASCADE;

-- Main trials table
CREATE TABLE trials (
    nct_id VARCHAR(20) PRIMARY KEY,
    brief_title TEXT,
    official_title TEXT,
    overall_status VARCHAR(50),
    phase VARCHAR(50),
    study_type VARCHAR(50),
    enrollment_count INTEGER,
    start_date DATE,
    completion_date DATE,
    primary_completion_date DATE,
    why_stopped TEXT,
    has_results BOOLEAN,
    primary_intervention_type VARCHAR(50),
    primary_intervention_name TEXT
);

-- Sponsors (deduplicated)
CREATE TABLE sponsors (
    sponsor_id SERIAL PRIMARY KEY,
    sponsor_name VARCHAR(500) UNIQUE NOT NULL,
    sponsor_class VARCHAR(50)
);

-- Conditions (deduplicated)
CREATE TABLE conditions (
    condition_id SERIAL PRIMARY KEY,
    condition_name VARCHAR(500) UNIQUE NOT NULL
);

-- Locations (one row per trial site)
CREATE TABLE locations (
    location_id SERIAL PRIMARY KEY,
    nct_id VARCHAR(20) REFERENCES trials(nct_id) ON DELETE CASCADE,
    facility_name TEXT,
    city VARCHAR(200),
    state VARCHAR(200),
    country VARCHAR(100),
    status VARCHAR(50)
);

-- Junction: trials to sponsors
CREATE TABLE trial_sponsors (
    nct_id VARCHAR(20) REFERENCES trials(nct_id) ON DELETE CASCADE,
    sponsor_id INTEGER REFERENCES sponsors(sponsor_id) ON DELETE CASCADE,
    lead_or_collaborator VARCHAR(20),
    PRIMARY KEY (nct_id, sponsor_id, lead_or_collaborator)
);

-- Junction: trials to conditions
CREATE TABLE trial_conditions (
    nct_id VARCHAR(20) REFERENCES trials(nct_id) ON DELETE CASCADE,
    condition_id INTEGER REFERENCES conditions(condition_id) ON DELETE CASCADE,
    PRIMARY KEY (nct_id, condition_id)
);

-- Indexes for faster querying on common filter/join columns
CREATE INDEX idx_trials_phase ON trials(phase);
CREATE INDEX idx_trials_status ON trials(overall_status);
CREATE INDEX idx_trials_start_date ON trials(start_date);
CREATE INDEX idx_locations_country ON locations(country);
CREATE INDEX idx_locations_nct_id ON locations(nct_id);
CREATE INDEX idx_trial_sponsors_nct_id ON trial_sponsors(nct_id);
CREATE INDEX idx_trial_conditions_nct_id ON trial_conditions(nct_id);
