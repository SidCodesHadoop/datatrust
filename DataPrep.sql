-- =====================================================
-- ENHANCED DATA READINESS DESK TABLES
-- Requirement: Cite underlying text, communicate uncertainty, persist user actions
-- =====================================================

-- 1. CREATE/REPLACE TABLES (safe rebuild)

-- 2. ENHANCED QUALITY ISSUES TABLE (with confidence & evidence)
CREATE OR REPLACE TABLE datatrustlayer.facility_quality_issues_enhanced AS
SELECT 
    i.unique_id,
    i.issue_type,
    i.severity,
    -- Add confidence score (0-100) to communicate uncertainty
    CASE 
        WHEN i.issue_type = 'MISSING_NAME' THEN 100  -- High confidence
        WHEN i.issue_type = 'MISSING_LOCATION' THEN 100
        WHEN i.issue_type LIKE '%EXTREME%' THEN 65  -- Medium confidence (outlier detection)
        WHEN i.issue_type LIKE '%CONTRADICTION%' THEN 85  -- High confidence
        WHEN i.issue_type LIKE '%SPARSE%' THEN 90
        ELSE 70
    END as confidence_score,
    -- Add description with evidence
    CASE i.issue_type
        WHEN 'MISSING_NAME' THEN 'Facility name is missing. Cannot identify facility without a name.'
        WHEN 'MISSING_LOCATION' THEN 'Country information is missing. Cannot validate facility location.'
        WHEN 'SPARSE_CORE_CAPACITY_INFO' THEN 'Both capacity and doctor count are missing. Cannot assess facility size.'
        WHEN 'INVALID_LATITUDE' THEN CONCAT('Latitude value out of valid range (-90 to 90). Actual: ', CAST(f.latitude AS STRING))
        WHEN 'INVALID_LONGITUDE' THEN CONCAT('Longitude value out of valid range (-180 to 180). Actual: ', CAST(f.longitude AS STRING))
        WHEN 'EXTREME_CAPACITY_OUTLIER' THEN CONCAT('Capacity (', f.capacity, ') is unusually high compared to similar facilities.')
        WHEN 'HOSPITAL_NO_CAPACITY' THEN 'Facility type is Hospital but capacity is missing.'
        ELSE i.issue_type
    END as description,
    -- Reference to source fields (for citation)
    CASE i.issue_type
        WHEN 'MISSING_NAME' THEN 'name'
        WHEN 'MISSING_LOCATION' THEN 'address_country'
        WHEN 'SPARSE_CORE_CAPACITY_INFO' THEN 'capacity,numberDoctors'
        WHEN 'INVALID_LATITUDE' THEN 'latitude'
        WHEN 'INVALID_LONGITUDE' THEN 'longitude'
        WHEN 'EXTREME_CAPACITY_OUTLIER' THEN 'capacity'
        WHEN 'HOSPITAL_NO_CAPACITY' THEN 'capacity,organization_type'
        ELSE 'various'
    END as source_fields,
    CURRENT_TIMESTAMP() as detected_at
FROM datatrustlayer.facility_quality_issues i
LEFT JOIN datatrustlayer.facilities f ON i.unique_id = f.unique_id;

-- 3. EVIDENCE TABLE (citation for claims/scores)
CREATE OR REPLACE TABLE datatrustlayer.facility_evidence AS
SELECT 
    f.unique_id,
    f.name as facility_name,
    -- Key fields with actual values for citation
    STRUCT(
        f.capacity as capacity_value,
        f.numberDoctors as doctors_value,
        f.yearEstablished as year_established,
        f.organization_type as org_type,
        f.address_country as country,
        f.address_city as city,
        f.description as description_text,
        f.source as data_source,
        f.source_urls as source_urls
    ) as evidence,
    -- Completeness metrics (for "sparse fields" detection)
    STRUCT(
        CASE WHEN f.name IS NOT NULL THEN 1 ELSE 0 END as has_name,
        CASE WHEN f.capacity IS NOT NULL AND f.capacity != 'null' THEN 1 ELSE 0 END as has_capacity,
        CASE WHEN f.numberDoctors IS NOT NULL AND f.numberDoctors != 'null' THEN 1 ELSE 0 END as has_doctors,
        CASE WHEN f.address_country IS NOT NULL THEN 1 ELSE 0 END as has_location,
        CASE WHEN f.description IS NOT NULL AND LENGTH(f.description) > 50 THEN 1 ELSE 0 END as has_description,
        CASE WHEN f.email IS NOT NULL OR f.officialPhone IS NOT NULL THEN 1 ELSE 0 END as has_contact
    ) as completeness,
    -- Data quality flags (for "contradictions" detection)
    STRUCT(
        CASE WHEN f.latitude IS NOT NULL AND (f.latitude < -90 OR f.latitude > 90) THEN 1 ELSE 0 END as invalid_latitude,
        CASE WHEN f.longitude IS NOT NULL AND (f.longitude < -180 OR f.longitude > 180) THEN 1 ELSE 0 END as invalid_longitude,
        CASE WHEN f.organization_type = 'Hospital' AND (f.capacity IS NULL OR f.capacity = 'null') THEN 1 ELSE 0 END as hospital_no_capacity,
        CASE WHEN TRY_CAST(f.capacity as INT) = 0 AND TRY_CAST(f.numberDoctors as INT) > 50 THEN 1 ELSE 0 END as low_capacity_high_staff
    ) as quality_flags,
    CURRENT_TIMESTAMP() as captured_at
FROM datatrustlayer.facilities f;

-- 4. FIELD-LEVEL SCORES (track which fields contribute to readiness)
CREATE OR REPLACE TABLE datatrustlayer.facility_field_scores AS
SELECT 
    f.unique_id,
    -- Score each key field (0-100)
    CASE 
        WHEN f.name IS NOT NULL AND LENGTH(f.name) > 3 THEN 100
        WHEN f.name IS NOT NULL THEN 50
        ELSE 0
    END as name_score,
    CASE 
        WHEN f.capacity IS NOT NULL AND f.capacity != 'null' AND TRY_CAST(f.capacity as INT) > 0 THEN 100
        WHEN f.capacity IS NOT NULL THEN 30
        ELSE 0
    END as capacity_score,
    CASE 
        WHEN f.numberDoctors IS NOT NULL AND f.numberDoctors != 'null' AND TRY_CAST(f.numberDoctors as INT) > 0 THEN 100
        WHEN f.numberDoctors IS NOT NULL THEN 30
        ELSE 0
    END as doctors_score,
    CASE 
        WHEN f.address_country IS NOT NULL AND f.address_city IS NOT NULL THEN 100
        WHEN f.address_country IS NOT NULL THEN 60
        ELSE 0
    END as location_score,
    CASE 
        WHEN f.latitude IS NOT NULL AND f.longitude IS NOT NULL 
             AND f.latitude BETWEEN -90 AND 90 
             AND f.longitude BETWEEN -180 AND 180 THEN 100
        WHEN f.latitude IS NOT NULL OR f.longitude IS NOT NULL THEN 40
        ELSE 0
    END as coordinates_score,
    CASE 
        WHEN f.description IS NOT NULL AND LENGTH(f.description) > 100 THEN 100
        WHEN f.description IS NOT NULL AND LENGTH(f.description) > 20 THEN 60
        ELSE 0
    END as description_score,
    CASE 
        WHEN f.email IS NOT NULL AND f.officialPhone IS NOT NULL THEN 100
        WHEN f.email IS NOT NULL OR f.officialPhone IS NOT NULL THEN 60
        ELSE 0
    END as contact_score,
    -- Overall field completeness score
    ROUND((
        CASE WHEN f.name IS NOT NULL AND LENGTH(f.name) > 3 THEN 100 ELSE 0 END +
        CASE WHEN f.capacity IS NOT NULL AND f.capacity != 'null' THEN 100 ELSE 0 END +
        CASE WHEN f.numberDoctors IS NOT NULL AND f.numberDoctors != 'null' THEN 100 ELSE 0 END +
        CASE WHEN f.address_country IS NOT NULL THEN 100 ELSE 0 END +
        CASE WHEN f.latitude IS NOT NULL AND f.latitude BETWEEN -90 AND 90 THEN 100 ELSE 0 END +
        CASE WHEN f.description IS NOT NULL AND LENGTH(f.description) > 50 THEN 100 ELSE 0 END +
        CASE WHEN f.email IS NOT NULL OR f.officialPhone IS NOT NULL THEN 100 ELSE 0 END
    ) / 7, 0) as overall_field_score,
    CURRENT_TIMESTAMP() as calculated_at
FROM datatrustlayer.facilities f;

-- 5. ENHANCED REVIEW DECISIONS TABLE (persist user actions)
CREATE TABLE IF NOT EXISTS datatrustlayer.facility_review_decisions (
    decision_id STRING,  -- Unique decision ID
    unique_id STRING,  -- Facility ID
    decision STRING,  -- APPROVE, NEEDS_INVESTIGATION, REJECT, SHORTLIST
    reviewer STRING,  -- User who made decision
    comments STRING,  -- Reviewer notes
    evidence_cited STRING,  -- Which fields/evidence influenced decision
    confidence_override INT,  -- User can override confidence (0-100)
    priority STRING,  -- HIGH, MEDIUM, LOW (for follow-up)
    tags ARRAY<STRING>,  -- User-defined tags for categorization
    timestamp TIMESTAMP,  -- When decision was made
    previous_decision STRING,  -- Track changes
    decision_version INT  -- Version number for audit trail
);

-- 6. AUDIT TRAIL TABLE (track all changes)
CREATE TABLE IF NOT EXISTS datatrustlayer.facility_review_audit (
    audit_id STRING,
    unique_id STRING,
    action_type STRING,  -- VIEW, REVIEW, APPROVE, REJECT, EDIT, etc.
    action_by STRING,  -- User
    action_details STRING,  -- JSON or text describing what changed
    timestamp TIMESTAMP
);

-- 7. ENHANCED REVIEW QUEUE (with citations and uncertainty)
CREATE OR REPLACE TABLE datatrustlayer.facility_review_queue_enhanced AS
SELECT 
    q.unique_id,
    f.name as facility_name,
    f.organization_type,
    f.address_city,
    f.address_stateOrRegion as region,
    q.readiness_score,
    q.readiness_category,
    q.impact_score,
    q.issue_count,
    -- Add average confidence for all issues (uncertainty metric)
    COALESCE(AVG(ie.confidence_score), 100) as avg_issue_confidence,
    -- Add field score
    fs.overall_field_score,
    -- Evidence snippet for quick review
    STRUCT(
        f.capacity as capacity,
        f.numberDoctors as doctors,
        f.description as description_preview,
        f.source as data_source
    ) as evidence_preview,
    -- Top 3 issues with confidence
    COLLECT_LIST(
        STRUCT(
            ie.issue_type,
            ie.severity,
            ie.confidence_score,
            ie.description,
            ie.source_fields
        )
    ) as top_issues,
    -- Decision status (from review decisions table)
    COALESCE(rd.decision, 'PENDING') as review_status,
    rd.reviewer as reviewed_by,
    rd.timestamp as reviewed_at,
    CURRENT_TIMESTAMP() as queue_generated_at
FROM datatrustlayer.facility_review_queue q
LEFT JOIN datatrustlayer.facilities f ON q.unique_id = f.unique_id
LEFT JOIN datatrustlayer.facility_quality_issues_enhanced ie ON q.unique_id = ie.unique_id
LEFT JOIN datatrustlayer.facility_field_scores fs ON q.unique_id = fs.unique_id
LEFT JOIN (
    -- Get latest decision per facility
    SELECT unique_id, decision, reviewer, timestamp,
           ROW_NUMBER() OVER (PARTITION BY unique_id ORDER BY timestamp DESC) as rn
    FROM datatrustlayer.facility_review_decisions
) rd ON q.unique_id = rd.unique_id AND rd.rn = 1
GROUP BY 
    q.unique_id, f.name, f.organization_type, f.address_city, f.address_stateOrRegion,
    q.readiness_score, q.readiness_category, q.impact_score, q.issue_count,
    fs.overall_field_score, f.capacity, f.numberDoctors, f.description, f.source,
    rd.decision, rd.reviewer, rd.timestamp;

-- 8. SUMMARY STATISTICS FOR APP
SELECT 
    'facility_quality_issues_enhanced' as table_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT unique_id) as unique_facilities,
    ROUND(AVG(confidence_score), 1) as avg_confidence
FROM datatrustlayer.facility_quality_issues_enhanced
UNION ALL
SELECT 
    'facility_evidence' as table_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT unique_id) as unique_facilities,
    NULL as avg_confidence
FROM datatrustlayer.facility_evidence
UNION ALL
SELECT 
    'facility_field_scores' as table_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT unique_id) as unique_facilities,
    ROUND(AVG(overall_field_score), 1) as avg_confidence
FROM datatrustlayer.facility_field_scores
UNION ALL
SELECT 
    'facility_review_queue_enhanced' as table_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT unique_id) as unique_facilities,
    ROUND(AVG(avg_issue_confidence), 1) as avg_confidence
FROM datatrustlayer.facility_review_queue_enhanced;
