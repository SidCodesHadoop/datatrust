# Data Beat

## Problem

Healthcare planning relies on facility data that often appears complete but contains contradictions, sparse fields, and unreliable claims.

## Solution

Data Beat is a Data Readiness Desk that:

- Profiles dataset quality
- Detects contradictions
- Identifies suspicious claims
- Prioritizes records for review
- Persists reviewer decisions

## Architecture

Databricks Delta Tables
→ Quality Rules
→ Readiness Scoring
→ Review Queue
→ Human Decisions

## Tables Produced

- facility_profile
- facility_quality_issues
- facility_readiness_score
- facility_review_queue
- facility_review_decisions

## Tech Stack

- Databricks
- Delta Lake
- Streamlit
- Python
- SQL



## Live App
https://data-trust-desk-7474654569577474.aws.databricksapps.com
