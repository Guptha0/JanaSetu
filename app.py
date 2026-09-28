import streamlit as st
import requests
import pandas as pd

# Constants
API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="JanSetu: Policymaker Dashboard", layout="wide")

# Sidebar
st.sidebar.title("JanSetu")
st.sidebar.subheader("Policymaker Dashboard")
st.sidebar.caption("By Team Spark Sense")
st.sidebar.divider()

st.sidebar.markdown("### Filters & Actions")
# Adding a refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# Fetch Data from FastAPI Backend
@st.cache_data(ttl=10)
def fetch_summary():
    try:
        return requests.get(f"{API_BASE_URL}/analytics/summary").json()
    except Exception:
        return None

@st.cache_data(ttl=10)
def fetch_priorities():
    try:
        return requests.get(f"{API_BASE_URL}/analytics/priorities").json()
    except Exception:
        return []

@st.cache_data(ttl=10)
def fetch_grievances():
    try:
        return requests.get(f"{API_BASE_URL}/api/grievances").json()
    except Exception:
        return []

summary_data = fetch_summary()
priorities_data = fetch_priorities()
grievances_data = fetch_grievances()

if not summary_data or not grievances_data:
    st.error("Failed to connect to the FastAPI backend. Make sure it's running on http://127.0.0.1:8000")
    st.stop()

# --- Metrics Overview Section ---
st.title("📊 JanSetu Metrics Overview")

total_active = summary_data.get("total_grievances", 0)
critical_count = summary_data.get("by_urgency", {}).get("Critical (4-5)", 0)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Active Grievances", total_active)
col2.metric("Critical Hazards", critical_count)
col3.metric("Pending Resolution", total_active)  # All are pending for Day 3
col4.metric("Resolved", 0)  # Mock resolved metric

st.divider()

# --- High-Priority Action Table ---
st.subheader("🚨 High-Priority Infrastructure Hotspots")
st.markdown("Zones requiring immediate municipal intervention based on complaint density and AI urgency scores.")

if priorities_data:
    df_priorities = pd.DataFrame(priorities_data)
    # Rename columns for better readability for policymakers
    df_priorities = df_priorities.rename(columns={
        "location": "Location / Ward",
        "grievance_count": "Total Complaints",
        "total_urgency": "Cumulative Urgency",
        "priority_score": "Priority Score"
    })
    st.dataframe(df_priorities, use_container_width=True, hide_index=True)
else:
    st.info("No priority data available.")

st.divider()

# --- Live Citizen Feed ---
st.subheader("📰 Live Citizen Feed")

# Search and filter options
col_search, col_filter = st.columns([2, 1])
with col_search:
    search_query = st.text_input("Search Complaints (by keyword or location)")
with col_filter:
    categories = ["All"] + list(summary_data.get("by_category", {}).keys())
    selected_category = st.selectbox("Filter by Category", categories)

# Process Data for feed
filtered_grievances = grievances_data
if selected_category != "All":
    filtered_grievances = [g for g in filtered_grievances if g["category"] == selected_category]

if search_query:
    q = search_query.lower()
    filtered_grievances = [g for g in filtered_grievances if q in g["raw_text"].lower() or q in g["location"].lower()]

# Render the feed
for g in filtered_grievances:
    with st.container(border=True):
        col_title, col_badges = st.columns([3, 1])
        
        with col_title:
            st.markdown(f"**{g['citizen_name']}** • 📍 {g['location']}")
            st.write(f'"{g["raw_text"]}"')
            st.caption(f"🤖 **AI Summary:** {g.get('ai_summary', 'N/A')}")
            
        with col_badges:
            score = g['urgency_score']
            if score >= 4:
                color = "red"
                level = "High"
            elif score == 3:
                color = "orange"
                level = "Medium"
            else:
                color = "green"
                level = "Low"
                
            st.markdown(f"**Urgency:** :{color}[{level} ({score}/5)]")
            st.markdown(f"**Category:** `{g['category']}`")
