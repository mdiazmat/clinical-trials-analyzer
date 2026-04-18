-- Clinical Trials Landscape Analyzer: Analytical Queries
-- These queries support the four-dashboard Tableau deliverable:
--   1. Overview
--   2. Sponsor analysis
--   3. Conditions deep-dive
--   4. Geographic distribution
--
-- All queries run against the 6-table schema defined in schema.sql.
-- Focus period: post-2010 trials where data coverage is robust.


-- Dashboard 1: Overview
-- Q1.1 Headline KPIs
-- Single-row result with the big #'s for the overview dashboard tiles.
SELECT
    COUNT(*) AS total_trials,
    COUNT(*) FILTER (WHERE overall_status = 'COMPLETED') AS completed_trials,
    COUNT(*) FILTER (WHERE overall_status IN ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING')) AS active_trials,
    COUNT(*) FILTER (WHERE overall_status = 'TERMINATED') AS terminated_trials,
    ROUND(AVG(enrollment_count) FILTER (WHERE enrollment_count BETWEEN 1 AND 10000)) AS avg_enrollment
FROM trials
WHERE start_date >= '2010-01-01';

-- Q1.2: Trials over time (for trend line chart)
-- Yearly trial starts from 2010 onward, broken down by phase. 

SELECT
    EXTRACT(YEAR FROM start_date)::INTEGER AS start_year,
    phase,
    COUNT(*) AS trial_count
FROM trials
WHERE start_date >= '2010-01-01'
  AND start_date < '2026-01-01'
GROUP BY start_year, phase
ORDER BY start_year, phase;

-- Q1.3: Status breakdown (for pie or donut chart)
SELECT
    overall_status,
    COUNT(*) AS trial_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS percentage
FROM trials
WHERE start_date >= '2010-01-01'
GROUP BY overall_status
ORDER BY trial_count DESC;


-- Dashboard 2: Sponsor Analysis
-- Q2.1: INdustry vs academic trial volume and completion rate
-- Shows whether industry or academic sponsor have higher completion rates.
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

-- Q2.2: Top 20 sponsors by trial volume iwth completion rates
-- Used for the main sponsor leaderboard view
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

-- Q2.3: Average trial duration by sponsor class (completed trials only)
-- Dates subtract to integer days in Postgres, so no EXTRACT needed.
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


-- Dashboard 3: Conditions Deep-Dive
-- Q3.1: Top 25 conditions by trial count
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

-- Q3.2: Intervention type breakdown
-- Shows the mix of drug vs biological vs radiation vs other trials.
SELECT
    COALESCE(primary_intervention_type, 'UNKNOWN') AS intervention_type,
    COUNT(*) AS trial_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS percentage
FROM trials
WHERE start_date >= '2010-01-01'
GROUP BY primary_intervention_type
ORDER BY trial_count DESC;


-- Q3.3: Biological therapy growth over time
-- Tracks the shift toward immunotherapy/biologics, which is a major trend in oncology.
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


-- Dashboard 4: Geographic Distribution
-- Q4.1: Trial sites by country
-- Used for the world map. Counts UNIQUE trials per country (not sites).
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

-- Q4.2: US states breakdown for the US-only map drill-down
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

-- Q4.3: Geographic reach per sponsor class
-- Shows whether industry trials are more geographically distributed than academic.
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