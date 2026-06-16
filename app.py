from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import random
from typing import Union
import os
import uuid

import altair as alt
import pandas as pd
import streamlit as st
from databricks import sql
import plotly.express as px


st.set_page_config(
    page_title="Data Readiness Desk",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Profile, review, and improve your facility dataset before planning.",
    },
)


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Instrument+Serif&display=swap');

:root {
  --background: #f8fafc;
  --foreground: #1e293b;
  --card: #ffffff;
  --muted: #eef3f8;
  --muted-foreground: #64748b;
  --primary: #2563a7;
  --accent: #32b39a;
  --success: #22a66b;
  --warning: #d89d27;
  --destructive: #dc3d37;
  --border: #dce4ee;
  --sidebar: #1b2638;
  --sidebar-foreground: #eef3f8;
  --shadow-card: 0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px -12px rgba(15, 23, 42, 0.12);
}

html, body, [class*="css"] {
  font-family: "IBM Plex Sans", system-ui, sans-serif;
}

.block-container {
  padding-top: 1.4rem;
  padding-bottom: 3rem;
  max-width: 1400px;
}

[data-testid="stSidebar"] {
  background: var(--sidebar);
}

[data-testid="stSidebar"] * {
  color: var(--sidebar-foreground);
}

.brand-title {
  font-family: "Instrument Serif", Georgia, serif;
  font-size: 2.1rem;
  line-height: 1;
}

.mono {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  letter-spacing: .12em;
  text-transform: uppercase;
  font-size: .68rem;
  color: var(--muted-foreground);
}

.hero {
  border: 1px solid rgba(100, 181, 246, 0.3);
  border-radius: 14px;
  padding: 2rem;
  color: #1e293b;
  background:
    radial-gradient(circle at 1px 1px, rgba(255,255,255,.5) 1px, transparent 0) 0 0 / 22px 22px,
    linear-gradient(135deg, #e3f2fd 0%, #bbdefb 45%, #90caf9 100%);
  box-shadow: 0 24px 48px -18px rgba(100, 181, 246, .25);
}

.hero h1 {
  font-family: "Instrument Serif", Georgia, serif;
  font-size: clamp(2.1rem, 4.4vw, 4rem);
  line-height: 1.02;
  font-weight: 400;
  margin: .5rem 0 .8rem;
  color: #1565c0;
}

.hero p {
  color: rgba(30, 41, 59, 0.8);
  max-width: 780px;
}

.hero .mono {
  color: rgba(30, 41, 59, 0.6);
}

.metric-card, .soft-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--card);
  padding: 1.05rem;
  box-shadow: var(--shadow-card);
}

.metric-label {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  letter-spacing: .14em;
  text-transform: uppercase;
  font-size: .66rem;
  color: var(--muted-foreground);
}

.metric-value {
  font-family: "Instrument Serif", Georgia, serif;
  font-size: 2.55rem;
  line-height: 1.05;
  color: var(--foreground);
}

.metric-hint {
  font-size: .78rem;
  color: var(--muted-foreground);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: .18rem .55rem;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: .65rem;
  text-transform: uppercase;
  letter-spacing: .08em;
  font-weight: 600;
}

.confidence-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 6px;
  padding: .25rem .5rem;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: .68rem;
  font-weight: 600;
  margin-left: .5rem;
}

.confidence-high { background: rgba(34,166,107,.15); color: #22a66b; border: 1px solid rgba(34,166,107,.3); }
.confidence-medium { background: rgba(216,157,39,.15); color: #d89d27; border: 1px solid rgba(216,157,39,.3); }
.confidence-low { background: rgba(220,61,55,.15); color: #dc3d37; border: 1px solid rgba(220,61,55,.3); }

.evidence-box {
  background: var(--muted);
  border-left: 3px solid var(--primary);
  padding: .75rem;
  margin: .5rem 0;
  border-radius: 6px;
  font-size: .85rem;
}

.citation {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: .7rem;
  color: var(--muted-foreground);
  margin-top: .3rem;
}

.ready { color: var(--success); background: rgba(34,166,107,.10); border: 1px solid rgba(34,166,107,.32); }
.review { color: var(--warning); background: rgba(216,157,39,.12); border: 1px solid rgba(216,157,39,.34); }
.not-ready { color: var(--destructive); background: rgba(220,61,55,.10); border: 1px solid rgba(220,61,55,.32); }

h1, h2, h3 {
  color: var(--foreground);
}
</style>
"""


@dataclass
class FacilityReadiness:
    unique_id: str
    facility_name: str
    facility_type: str
    region: str
    city: str
    readiness_score: int
    readiness_category: str
    impact_score: int
    beds: int
    last_updated: str


def execute_query(query: str) -> pd.DataFrame:
    """Execute SQL query using Databricks SQL connector"""
    with sql.connect(
        server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN")
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            # Fetch results and column names
            result = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(result, columns=columns)


def execute_insert(query: str, params: dict = None) -> None:
    """Execute INSERT/UPDATE query using Databricks SQL connector"""
    with sql.connect(
        server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN")
    ) as connection:
        with connection.cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_real_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load data from Unity Catalog enhanced tables in datatrustlayer schema"""
    
    # Load enhanced review queue with confidence scores and evidence
    queue_query = """
    SELECT 
        q.unique_id,
        q.facility_name,
        q.organization_type as facility_type,
        COALESCE(f.address_city, 'Unknown') as city,
        COALESCE(f.address_stateOrRegion, 'Unknown') as region,
        q.readiness_score,
        q.readiness_category,
        q.impact_score,
        q.issue_count,
        q.avg_issue_confidence,
        q.overall_field_score,
        q.review_status,
        q.reviewed_by,
        CAST(q.evidence_preview.capacity as STRING) as capacity,
        CAST(q.evidence_preview.doctors as STRING) as doctors,
        CAST(q.evidence_preview.description_preview as STRING) as description_preview,
        CAST(q.evidence_preview.data_source as STRING) as data_source,
        COALESCE(f.recency_of_page_update, '2024-01-01') as last_updated,
        f.latitude,
        f.longitude
    FROM datatrustlayer.facility_review_queue_enhanced q
    LEFT JOIN datatrustlayer.facilities f ON q.unique_id = f.unique_id
    WHERE q.readiness_category != 'READY'
    """
    
    # Also get READY facilities
    ready_query = """
    SELECT 
        s.unique_id,
        f.name as facility_name,
        f.organization_type as facility_type,
        COALESCE(f.address_city, 'Unknown') as city,
        COALESCE(f.address_stateOrRegion, 'Unknown') as region,
        s.readiness_score,
        s.readiness_category,
        s.impact_score,
        0 as issue_count,
        100.0 as avg_issue_confidence,
        100.0 as overall_field_score,
        'APPROVED' as review_status,
        NULL as reviewed_by,
        CAST(f.capacity as STRING) as capacity,
        CAST(f.numberDoctors as STRING) as doctors,
        f.description as description_preview,
        f.source as data_source,
        COALESCE(f.recency_of_page_update, '2024-01-01') as last_updated,
        f.latitude,
        f.longitude
    FROM datatrustlayer.facility_readiness_score s
    LEFT JOIN datatrustlayer.facilities f ON s.unique_id = f.unique_id
    WHERE s.readiness_category = 'READY'
    """
    
    # Execute queries
    queue_df = execute_query(queue_query)
    ready_df = execute_query(ready_query)
    facilities_df = pd.concat([queue_df, ready_df], ignore_index=True)
    
    # Fill missing values and clean up
    facilities_df['facility_name'] = facilities_df['facility_name'].fillna('Unknown Facility')
    facilities_df['facility_type'] = facilities_df['facility_type'].fillna('Unknown')
    facilities_df['last_updated'] = facilities_df['last_updated'].astype(str)
    facilities_df['issue_count'] = facilities_df['issue_count'].fillna(0).astype(int)
    facilities_df['avg_issue_confidence'] = facilities_df['avg_issue_confidence'].fillna(100.0)
    facilities_df['overall_field_score'] = facilities_df['overall_field_score'].fillna(100.0)
    
    # Convert capacity to int for beds column
    facilities_df['beds'] = facilities_df['capacity'].apply(
        lambda x: int(x) if x and str(x).isdigit() else 0
    )
    
    # Load column profile
    columns_query = """
        SELECT 
            column as column_name,
            'string' as data_type,
            null_pct,
            distinct_count,
            total_rows
        FROM datatrustlayer.facility_profile
    """
    columns_df = execute_query(columns_query)
    
    # Load enhanced issues with confidence and evidence
    issues_query = """
    SELECT 
        CONCAT('ISS-', ROW_NUMBER() OVER (ORDER BY i.unique_id)) as issue_id,
        i.unique_id,
        COALESCE(f.name, 'Unknown Facility') as facility_name,
        i.issue_type,
        i.severity,
        i.confidence_score,
        i.description,
        i.source_fields as column,
        CAST(i.detected_at as STRING) as detected_at
    FROM datatrustlayer.facility_quality_issues_enhanced i
    LEFT JOIN datatrustlayer.facilities f ON i.unique_id = f.unique_id
    ORDER BY i.confidence_score ASC, i.severity DESC
    """
    issues = execute_query(issues_query)
    
    # Load field scores for detailed breakdown
    field_scores_query = """
    SELECT 
        unique_id,
        name_score,
        capacity_score,
        doctors_score,
        location_score,
        coordinates_score,
        description_score,
        contact_score,
        overall_field_score
    FROM datatrustlayer.facility_field_scores
    """
    field_scores = execute_query(field_scores_query)
    
    return facilities_df, columns_df, issues, field_scores


def confidence_badge(confidence: float) -> str:
    """Generate HTML badge for confidence score"""
    if confidence >= 85:
        css_class = "confidence-high"
        icon = "🟢"
    elif confidence >= 70:
        css_class = "confidence-medium"
        icon = "🟡"
    else:
        css_class = "confidence-low"
        icon = "🔴"
    
    return f'<span class="{css_class} confidence-badge">{icon} {int(confidence)}% confidence</span>'


def status_html(category: str) -> str:
    label_map = {"READY": "Ready", "REVIEW": "Review", "NOT_READY": "Not Ready"}
    class_map = {"READY": "ready", "REVIEW": "review", "NOT_READY": "not-ready"}
    return f'<span class="status-pill {class_map[category]}">{label_map[category]}</span>'


def metric_card(label: str, value: Union[int, str], hint: str, color: str = "var(--primary)") -> None:
    st.markdown(
        f"""
        <div class="metric-card" style="border-bottom: 3px solid {color};">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_color(score: int) -> str:
    if score > 78:
        return "#22a66b"
    if score > 45:
        return "#d89d27"
    return "#dc3d37"


def overview(facilities: pd.DataFrame, columns_df: pd.DataFrame, issues: pd.DataFrame) -> None:
    total = len(facilities)
    ready = int((facilities["readiness_category"] == "READY").sum())
    review = int((facilities["readiness_category"] == "REVIEW").sum())
    not_ready = int((facilities["readiness_category"] == "NOT_READY").sum())
    trust = round((ready / total) * 100) if total > 0 else 0
    
    # Calculate average confidence across all issues
    avg_confidence = round(issues["confidence_score"].mean()) if len(issues) > 0 else 100

    st.markdown(
        f"""
        <section class="hero">
          <div class="mono" style="color: rgba(30,41,59,.6);">Today's question</div>
          <h1>What needs to be fixed before this dataset can be trusted for planning?</h1>
          <p>{not_ready} facilities are blocking trust. {review} more need a second look.
          Start with the prioritized review queue; decisions are persisted for downstream planning models.</p>
          <div style="margin-top: 1rem; font-family: IBM Plex Mono, monospace; font-size: .78rem; color: rgba(30,41,59,.85);">
            Trust score: <strong style="font-size: 1.45rem; color: #1565c0;">{trust}%</strong>
            &nbsp;&nbsp; {len(issues)} open issues
            &nbsp;&nbsp; {int((columns_df["null_pct"] > 20).sum())} sparse columns
            &nbsp;&nbsp; Avg issue confidence: <strong>{avg_confidence}%</strong>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Total Facilities", total, "in dataset")
    with col2:
        metric_card("Ready", ready, f"{round((ready / total) * 100) if total > 0 else 0}% of dataset", "var(--success)")
    with col3:
        metric_card("Review", review, "needs verification", "var(--warning)")
    with col4:
        metric_card("Not Ready", not_ready, "blocking trust", "var(--destructive)")

    st.write("")
    chart_col, table_col = st.columns([1, 1.35])
    dist = pd.DataFrame(
        [
            {"name": "Ready", "value": ready, "color": "#22a66b"},
            {"name": "Review", "value": review, "color": "#d89d27"},
            {"name": "Not Ready", "value": not_ready, "color": "#dc3d37"},
        ]
    )

    with chart_col:
        st.subheader("Readiness Distribution")
        chart = (
            alt.Chart(dist)
            .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
            .encode(
                x=alt.X("name:N", title=None),
                y=alt.Y("value:Q", title=None),
                color=alt.Color("name:N", scale=alt.Scale(range=dist["color"].tolist()), legend=None),
                tooltip=["name", "value"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)

    with table_col:
        st.subheader("High-Risk Facilities")
        high_risk = facilities.sort_values("readiness_score").head(8).copy()
        high_risk["status"] = high_risk["readiness_category"].map(
            {"READY": "Ready", "REVIEW": "Review", "NOT_READY": "Not Ready"}
        )
        st.dataframe(
            high_risk[["facility_name", "unique_id", "city", "region", "readiness_score", "status"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "facility_name": "Facility",
                "unique_id": "ID",
                "city": "City",
                "region": "Region",
                "readiness_score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=100, format="%d"
                ),
                "status": "Status",
            },
        )


def profiling(columns_df: pd.DataFrame) -> None:
    sorted_columns = columns_df.sort_values("null_pct", ascending=False)
    sparse = int((columns_df["null_pct"] >= 20).sum())
    clean = int((columns_df["null_pct"] < 5).sum())

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Columns Profiled", len(columns_df), "across facility table")
    with col2:
        metric_card("Sparse Columns", sparse, "> 20% null", "var(--warning)")
    with col3:
        metric_card("Clean Columns", clean, "< 5% null", "var(--success)")

    st.write("")
    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Column Completeness")
        st.dataframe(
            sorted_columns,
            use_container_width=True,
            hide_index=True,
            column_config={
                "column_name": "Column",
                "data_type": "Type",
                "distinct_count": "Distinct",
                "total_rows": "Rows",
                "null_pct": st.column_config.ProgressColumn("Null %", min_value=0, max_value=100, format="%.1f%%"),
            },
        )

    with right:
        st.subheader("Worst Offenders")
        worst = sorted_columns.head(8)
        chart = (
            alt.Chart(worst)
            .mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6, color="#2563a7")
            .encode(
                x=alt.X("null_pct:Q", title="Null %", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("column_name:N", title=None, sort="-x"),
                tooltip=["column_name", alt.Tooltip("null_pct:Q", format=".1f")],
            )
            .properties(height=360)
        )
        st.altair_chart(chart, use_container_width=True)


def issues_view(issues: pd.DataFrame) -> None:
    if len(issues) == 0:
        st.info("No issues detected in the dataset.")
        return
    
    # Show confidence distribution
    st.subheader("Issue Confidence Distribution")
    col1, col2, col3 = st.columns(3)
    high_conf = len(issues[issues["confidence_score"] >= 85])
    med_conf = len(issues[(issues["confidence_score"] >= 70) & (issues["confidence_score"] < 85)])
    low_conf = len(issues[issues["confidence_score"] < 70])
    
    with col1:
        metric_card("High Confidence", high_conf, "≥ 85% certain", "var(--success)")
    with col2:
        metric_card("Medium Confidence", med_conf, "70-85% certain", "var(--warning)")
    with col3:
        metric_card("Low Confidence", low_conf, "< 70% uncertain", "var(--destructive)")
    
    st.write("")
        
    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    counts = issues["severity"].value_counts().to_dict()
    cols = st.columns(4)
    for col, severity in zip(cols, severities):
        with col:
            metric_card(
                severity,
                int(counts.get(severity, 0)),
                f"{(counts.get(severity, 0) / len(issues) * 100):.0f}% of open issues" if len(issues) > 0 else "0%",
                {
                    "LOW": "var(--muted-foreground)",
                    "MEDIUM": "var(--warning)",
                    "HIGH": "var(--primary)",
                    "CRITICAL": "var(--destructive)",
                }[severity],
            )

    selected_severities = st.multiselect("Severity", severities, default=severities)
    issue_type_options = sorted(issues["issue_type"].unique().tolist())
    selected_types = st.multiselect("Issue types", issue_type_options, default=issue_type_options)
    filtered = issues[
        issues["severity"].isin(selected_severities) & issues["issue_type"].isin(selected_types)
    ]

    left, right = st.columns(2)
    with left:
        st.subheader("Issue Breakdown")
        by_type = issues.groupby("issue_type", as_index=False).size().sort_values("size", ascending=False)
        chart = (
            alt.Chart(by_type)
            .mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6, color="#32b39a")
            .encode(
                x=alt.X("size:Q", title=None),
                y=alt.Y("issue_type:N", title=None, sort="-x"),
                tooltip=["issue_type", "size"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)

    with right:
        st.subheader("Severity Breakdown")
        by_severity = pd.DataFrame({"severity": severities})
        by_severity["count"] = by_severity["severity"].map(counts).fillna(0).astype(int)
        chart = (
            alt.Chart(by_severity)
            .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
            .encode(
                x=alt.X("severity:N", title=None, sort=severities),
                y=alt.Y("count:Q", title=None),
                color=alt.Color(
                    "severity:N",
                    scale=alt.Scale(domain=severities, range=["#64748b", "#d89d27", "#2563a7", "#dc3d37"]),
                    legend=None,
                ),
                tooltip=["severity", "count"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)

    st.subheader(f"Issue List ({len(filtered)} of {len(issues)})")
    
    # Display issues with confidence badges
    display_issues = filtered.head(25).copy()
    st.dataframe(
        display_issues[["issue_id", "issue_type", "facility_name", "unique_id", "column", "severity", "confidence_score", "description"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "confidence_score": st.column_config.ProgressColumn(
                "Confidence",
                min_value=0,
                max_value=100,
                format="%d%%"
            ),
        }
    )


def map_view(facilities: pd.DataFrame) -> None:
    """Interactive map showing facilities that need attention"""
    
    # Separate facilities with and without coordinates
    map_data = facilities[
        (facilities['latitude'].notna()) & 
        (facilities['longitude'].notna()) &
        (facilities['latitude'] != 0) &
        (facilities['longitude'] != 0)
    ].copy()
    
    no_coords_data = facilities[
        (facilities['latitude'].isna()) | 
        (facilities['longitude'].isna()) |
        (facilities['latitude'] == 0) |
        (facilities['longitude'] == 0)
    ].copy()
    
    # Show data quality warning
    st.markdown("### Interactive Map - Facilities by Readiness Status")
    
    if len(no_coords_data) > 0:
        no_coords_ready = len(no_coords_data[no_coords_data['readiness_category'] == 'READY'])
        no_coords_review = len(no_coords_data[no_coords_data['readiness_category'] == 'REVIEW'])
        no_coords_not_ready = len(no_coords_data[no_coords_data['readiness_category'] == 'NOT_READY'])
        
        st.warning(
            f"⚠️ **Data Quality Issue**: {len(no_coords_data)} facilities are missing coordinate data "
            f"({no_coords_not_ready} Not Ready, {no_coords_review} Review, {no_coords_ready} Ready). "
            f"These facilities cannot be displayed on the map."
        )
    
    if len(map_data) == 0:
        st.error("No facilities with valid coordinates found.")
        st.subheader("Facilities Without Coordinates")
        st.dataframe(
            no_coords_data[["facility_name", "unique_id", "city", "region", "readiness_category", "readiness_score"]],
            use_container_width=True,
            hide_index=True
        )
        return
    
    st.caption("🟢 Ready  •  🟡 Review  •  🔴 Not Ready")
    
    # Filters
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # State/Region filter
        all_regions = sorted(map_data['region'].unique().tolist())
        selected_regions = st.multiselect(
            "Filter by State/Region",
            options=all_regions,
            default=all_regions[:5] if len(all_regions) > 5 else all_regions,
            help="Select states/regions to display"
        )
    
    with col2:
        # City filter (dynamic based on selected regions)
        filtered_by_region = map_data[map_data['region'].isin(selected_regions)] if selected_regions else map_data
        all_cities = sorted(filtered_by_region['city'].unique().tolist())
        selected_cities = st.multiselect(
            "Filter by City",
            options=all_cities,
            default=[],
            help="Leave empty to show all cities"
        )
    
    with col3:
        # Status filter
        status_options = ["READY", "REVIEW", "NOT_READY"]
        selected_statuses = st.multiselect(
            "Filter by Status",
            options=status_options,
            default=status_options,  # Changed to show all by default
            format_func=lambda x: x.replace("_", " ").title()
        )
    
    # Apply filters
    filtered_data = map_data[map_data['region'].isin(selected_regions)] if selected_regions else map_data
    if selected_cities:
        filtered_data = filtered_data[filtered_data['city'].isin(selected_cities)]
    if selected_statuses:
        filtered_data = filtered_data[filtered_data['readiness_category'].isin(selected_statuses)]
    
    if len(filtered_data) == 0:
        st.info("No facilities match the selected filters.")
        return
    
    # Summary metrics
    st.write("")
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        metric_card("Facilities Shown", len(filtered_data), f"of {len(map_data)} with coords")
    with col_b:
        ready_count = len(filtered_data[filtered_data['readiness_category'] == 'READY'])
        metric_card("Ready", ready_count, f"{(ready_count/len(filtered_data)*100):.0f}% shown" if len(filtered_data) > 0 else "0%", "var(--success)")
    with col_c:
        review_count = len(filtered_data[filtered_data['readiness_category'] == 'REVIEW'])
        metric_card("Review", review_count, "need attention", "var(--warning)")
    with col_d:
        not_ready_count = len(filtered_data[filtered_data['readiness_category'] == 'NOT_READY'])
        metric_card("Not Ready", not_ready_count, "critical", "var(--destructive)")
    
    st.write("")
    
    # Map color mapping
    color_map = {
        "READY": "#22a66b",
        "REVIEW": "#d89d27",
        "NOT_READY": "#dc3d37"
    }
    
    filtered_data['color'] = filtered_data['readiness_category'].map(color_map)
    filtered_data['status_label'] = filtered_data['readiness_category'].map(
        {"READY": "Ready", "REVIEW": "Review", "NOT_READY": "Not Ready"}
    )
    
    # Create hover text
    filtered_data['hover_text'] = (
        "<b>" + filtered_data['facility_name'] + "</b><br>" +
        filtered_data['city'] + ", " + filtered_data['region'] + "<br>" +
        "Status: " + filtered_data['status_label'] + "<br>" +
        "Score: " + filtered_data['readiness_score'].astype(str) + "/100<br>" +
        "Beds: " + filtered_data['beds'].astype(str) + "<br>" +
        "Issues: " + filtered_data['issue_count'].astype(str)
    )
    
    # Create plotly map
    fig = px.scatter_mapbox(
        filtered_data,
        lat='latitude',
        lon='longitude',
        color='status_label',
        color_discrete_map={
            "Ready": "#22a66b",
            "Review": "#d89d27",
            "Not Ready": "#dc3d37"
        },
        hover_name='facility_name',
        hover_data={
            'city': True,
            'region': True,
            'readiness_score': True,
            'beds': True,
            'issue_count': True,
            'latitude': False,
            'longitude': False,
            'status_label': False
        },
        zoom=3,
        height=700,
        size_max=15
    )
    
    # Update layout
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend=dict(
            title="Status",
            orientation="h",
            yanchor="bottom",
            y=0.02,
            xanchor="left",
            x=0.02,
            bgcolor="rgba(255,255,255,0.9)"
        )
    )
    
    # Auto-zoom to filtered data if specific filters applied
    if selected_cities or (selected_regions and len(selected_regions) <= 2):
        center_lat = filtered_data['latitude'].mean()
        center_lon = filtered_data['longitude'].mean()
        
        # Calculate zoom level based on data spread
        lat_range = filtered_data['latitude'].max() - filtered_data['latitude'].min()
        lon_range = filtered_data['longitude'].max() - filtered_data['longitude'].min()
        max_range = max(lat_range, lon_range)
        
        if max_range < 0.5:
            zoom = 11
        elif max_range < 2:
            zoom = 9
        elif max_range < 5:
            zoom = 7
        else:
            zoom = 5
        
        fig.update_layout(
            mapbox=dict(
                center=dict(lat=center_lat, lon=center_lon),
                zoom=zoom
            )
        )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Facilities table below map
    st.subheader("Facility List (With Coordinates)")
    display_cols = ['facility_name', 'city', 'region', 'readiness_score', 'status_label', 'beds', 'issue_count']
    st.dataframe(
        filtered_data[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "facility_name": "Facility",
            "city": "City",
            "region": "State/Region",
            "readiness_score": st.column_config.ProgressColumn(
                "Score",
                min_value=0,
                max_value=100,
                format="%d"
            ),
            "status_label": "Status",
            "beds": "Beds",
            "issue_count": "Issues"
        }
    )
    
    # Show facilities without coordinates
    if len(no_coords_data) > 0:
        st.write("")
        st.subheader(f"Facilities Without Coordinates ({len(no_coords_data)})")
        st.caption("These facilities need coordinate data to be mapped")
        
        # Filter no_coords_data by status
        if selected_statuses:
            no_coords_filtered = no_coords_data[no_coords_data['readiness_category'].isin(selected_statuses)]
        else:
            no_coords_filtered = no_coords_data
        
        if len(no_coords_filtered) > 0:
            no_coords_filtered['status_label'] = no_coords_filtered['readiness_category'].map(
                {"READY": "Ready", "REVIEW": "Review", "NOT_READY": "Not Ready"}
            )
            
            st.dataframe(
                no_coords_filtered[['facility_name', 'unique_id', 'city', 'region', 'readiness_score', 'status_label', 'issue_count']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "facility_name": "Facility",
                    "unique_id": "ID",
                    "city": "City",
                    "region": "State/Region",
                    "readiness_score": st.column_config.ProgressColumn(
                        "Score",
                        min_value=0,
                        max_value=100,
                        format="%d"
                    ),
                    "status_label": "Status",
                    "issue_count": "Issues"
                }
            )
        else:
            st.info("No facilities without coordinates match the selected status filters.")


def build_review_queue(facilities: pd.DataFrame, issues: pd.DataFrame) -> pd.DataFrame:
    queue = facilities[facilities["readiness_category"] != "READY"].copy()
    return queue.sort_values("readiness_score")


def save_decision_to_db(unique_id: str, decision: str, comments: str, evidence_cited: str, 
                        confidence_override: int = None, priority: str = "MEDIUM", 
                        reviewer: str = "analyst") -> None:
    """Persist review decision to facility_review_decisions table (simple schema)"""
    
    # Helper function to escape SQL strings
    def escape_sql_string(s: str) -> str:
        if s is None:
            return ''
        # Escape single quotes and backslashes
        return str(s).replace("\\", "\\\\").replace("'", "''")
    
    # Escape all string inputs
    unique_id_safe = escape_sql_string(unique_id)
    decision_safe = escape_sql_string(decision)
    reviewer_safe = escape_sql_string(reviewer)
    
    # Combine all context into comments field since table schema is simple
    combined_comments = comments if comments else ""
    if evidence_cited:
        combined_comments += f" | Evidence: {evidence_cited}"
    if priority and priority != "MEDIUM":
        combined_comments += f" | Priority: {priority}"
    if confidence_override:
        combined_comments += f" | Confidence Override: {confidence_override}%"
    
    comments_safe = escape_sql_string(combined_comments)
    
    # Insert new decision - matching actual table schema: unique_id, decision, comments, reviewer, timestamp
    insert_query = f"""
    INSERT INTO datatrustlayer.facility_review_decisions
    VALUES (
        '{unique_id_safe}',
        '{decision_safe}',
        '{comments_safe}',
        '{reviewer_safe}',
        CURRENT_TIMESTAMP()
    )
    """
    
    execute_insert(insert_query)


def review_queue_view(facilities: pd.DataFrame, issues: pd.DataFrame, field_scores: pd.DataFrame) -> None:
    queue = build_review_queue(facilities, issues)
    
    if len(queue) == 0:
        st.info("No facilities in the review queue. All facilities are ready!")
        return
        
    if "decisions" not in st.session_state:
        st.session_state.decisions = []

    left, right = st.columns([.85, 1.5])
    with left:
        st.subheader("Prioritized Queue")
        query_text = st.text_input("Search facility or ID")
        visible = queue
        if query_text:
            mask = queue["facility_name"].str.contains(query_text, case=False, na=False) | queue["unique_id"].str.contains(
                query_text, case=False, na=False
            )
            visible = queue[mask]

        if len(visible) == 0:
            st.warning("No facilities match your search.")
            return

        selected_id = st.radio(
            f"{len(visible)} flagged · sorted by lowest readiness",
            visible["unique_id"].tolist(),
            format_func=lambda value: (
                f"{queue.loc[queue['unique_id'] == value, 'facility_name'].iloc[0]} · "
                f"{queue.loc[queue['unique_id'] == value, 'readiness_score'].iloc[0]}"
            ),
        )

    record = queue[queue["unique_id"] == selected_id].iloc[0]
    record_issues = issues[issues["unique_id"] == selected_id].head(5)
    record_fields = field_scores[field_scores["unique_id"] == selected_id]

    with right:
        st.markdown(
            f"""
            <div class="soft-card">
              <div class="mono">{record["unique_id"]} · {record["facility_type"]}</div>
              <h2 style="font-family: Instrument Serif, Georgia, serif; font-weight: 400; margin: .3rem 0 0;">
                {record["facility_name"]}
              </h2>
              <div style="color: var(--muted-foreground); margin-top: .3rem;">
                {record["city"]}, {record["region"]} · {record["beds"]} beds · updated {record["last_updated"]}
              </div>
              <div style="margin-top: .8rem;">{status_html(record["readiness_category"])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        a, b, c = st.columns(3)
        with a:
            metric_card("Readiness", int(record["readiness_score"]), "/ 100", score_color(int(record["readiness_score"])))
        with b:
            metric_card("Impact", int(record["impact_score"]), "/ 100", "var(--accent)")
        with c:
            metric_card("Open Issues", int(record["issue_count"]), "for this facility", "var(--warning)")
        
        # Show confidence and field score
        st.write("")
        d, e = st.columns(2)
        with d:
            avg_conf = record.get("avg_issue_confidence", 100)
            st.markdown(
                f'<div style="text-align: center;">Avg Issue Confidence{confidence_badge(avg_conf)}</div>',
                unsafe_allow_html=True
            )
        with e:
            field_score = record.get("overall_field_score", 100)
            st.markdown(
                f'<div style="text-align: center;">Field Completeness: <strong>{int(field_score)}%</strong></div>',
                unsafe_allow_html=True
            )

        # Field-level breakdown
        if not record_fields.empty:
            st.subheader("Field-Level Breakdown")
            field_data = record_fields.iloc[0]
            field_names = ["name", "capacity", "doctors", "location", "coordinates", "description", "contact"]
            field_values = [
                field_data.get(f"{fn}_score", 0) for fn in field_names
            ]
            
            field_df = pd.DataFrame({
                "Field": [fn.title() for fn in field_names],
                "Score": field_values
            })
            
            chart = (
                alt.Chart(field_df)
                .mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
                .encode(
                    x=alt.X("Score:Q", title="Score", scale=alt.Scale(domain=[0, 100])),
                    y=alt.Y("Field:N", title=None, sort="-x"),
                    color=alt.Color(
                        "Score:Q",
                        scale=alt.Scale(domain=[0, 50, 100], range=["#dc3d37", "#d89d27", "#22a66b"]),
                        legend=None
                    ),
                    tooltip=["Field", "Score"],
                )
                .properties(height=240)
            )
            st.altair_chart(chart, use_container_width=True)

        # Evidence preview
        st.subheader("Evidence Preview")
        if record.get("description_preview"):
            st.markdown(
                f"""
                <div class="evidence-box">
                  <strong>Description:</strong> {record["description_preview"][:200]}...
                  <div class="citation">Source: {record.get("data_source", "unknown")} | Fields: capacity={record.get("capacity", "N/A")}, doctors={record.get("doctors", "N/A")}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.subheader("Detected Issues")
        if record_issues.empty:
            st.info("No open issues; this record is clean.")
        else:
            # Display issues with confidence indicators
            for idx, issue in record_issues.iterrows():
                conf_badge = confidence_badge(issue['confidence_score'])
                st.markdown(
                    f"""
                    <div style="border-left: 3px solid {'#22a66b' if issue['confidence_score'] >= 85 else '#d89d27' if issue['confidence_score'] >= 70 else '#dc3d37'}; 
                                padding: .5rem; margin: .5rem 0; background: var(--muted); border-radius: 4px;">
                      <strong>{issue['issue_type']}</strong> · <span style="color: var(--muted-foreground);">{issue['severity']}</span>{conf_badge}
                      <div style="margin-top: .3rem; font-size: .85rem;">{issue['description']}</div>
                      <div class="citation">Field: {issue['column']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        st.subheader("Review Decision")
        decision = st.radio(
            "Decision",
            ["APPROVE", "NEEDS_INVESTIGATION", "REJECT", "SHORTLIST"],
            format_func=lambda value: value.replace("_", " ").title(),
            horizontal=True,
        )
        
        col1, col2 = st.columns(2)
        with col1:
            priority = st.selectbox("Priority", ["HIGH", "MEDIUM", "LOW"], index=1)
        with col2:
            confidence_override = st.number_input("Confidence Override (optional)", min_value=0, max_value=100, value=None, step=5)
        
        comments = st.text_area("Reviewer notes", placeholder="Document evidence, source links, or follow-up actions...")
        evidence_fields = st.text_input("Evidence fields cited", placeholder="e.g., capacity, name, description")
        
        if st.button("Submit decision", type="primary"):
            try:
                # Save to database
                save_decision_to_db(
                    unique_id=selected_id,
                    decision=decision,
                    comments=comments,
                    evidence_cited=evidence_fields,
                    confidence_override=confidence_override,
                    priority=priority
                )
                
                # Also save to session state for display
                st.session_state.decisions.insert(
                    0,
                    {
                        "id": selected_id,
                        "decision": decision,
                        "priority": priority,
                        "comments": comments,
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                    },
                )
                
                # Clear cache to refresh data
                st.cache_data.clear()
                
                st.success(f"✅ Saved {decision.replace('_', ' ').title()} for {selected_id} to database!")
                st.info("Decision persisted to `datatrustlayer.facility_review_decisions` and audit trail logged.")
            except Exception as e:
                st.error(f"Failed to save decision: {str(e)}")

        if st.session_state.decisions:
            st.caption("Recently saved (this session)")
            st.dataframe(pd.DataFrame(st.session_state.decisions[:4]), use_container_width=True, hide_index=True)


def not_found() -> None:
    st.markdown(
        """
        <div style="min-height: 70vh; display: grid; place-items: center; text-align: center;">
          <div>
            <div style="font-size: 5rem; font-weight: 700;">404</div>
            <h2>Page not found</h2>
            <p style="color: var(--muted-foreground);">The page you're looking for doesn't exist or has been moved.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def app() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    facilities, columns_df, issues, field_scores = load_real_data()

    with st.sidebar:
        st.markdown('<div class="brand-title">Readiness Desk</div>', unsafe_allow_html=True)
        st.markdown('<div class="mono" style="color: rgba(255,255,255,.58);">Data Trust Layer</div>', unsafe_allow_html=True)
        st.write("")
        page = st.radio(
            "Navigation",
            ["Overview", "Map", "Profiling", "Issues", "Review Queue"],
            label_visibility="collapsed",
        )
        st.write("")
        st.markdown("**Source**")
        st.code("datatrustlayer.facility_*_enhanced")
        st.caption("Databricks · Unity Catalog")
        st.write("")
        st.markdown("**Features**")
        st.caption("✓ Confidence scoring")
        st.caption("✓ Evidence citations")
        st.caption("✓ Persistent decisions")
        st.caption("✓ Field-level scores")
        st.caption("✓ Interactive map")

    route = st.query_params.get("page")
    if route and route.lower() not in {"overview", "map", "profiling", "issues", "review", "review-queue"}:
        not_found()
        return

    st.caption("Facility Dataset · Enhanced with Citations & Uncertainty")
    st.title(page)

    if page == "Overview":
        overview(facilities, columns_df, issues)
    elif page == "Map":
        map_view(facilities)
    elif page == "Profiling":
        profiling(columns_df)
    elif page == "Issues":
        issues_view(issues)
    elif page == "Review Queue":
        review_queue_view(facilities, issues, field_scores)


try:
    app()
except Exception as exc:
    st.error("This page didn't load")
    st.write("Something went wrong on our end. You can try refreshing or head back home.")
    with st.expander("Error details"):
        st.exception(exc)
