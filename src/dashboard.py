import streamlit as st
import pandas as pd
from src.db_config import get_db_connection
from src.ingestor import ingest_job
# from src.monitor import check_emails # Commented out until you set up Gmail
from src.analyst import analyze_latest_job
import os
import sys

# Force Python to find the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

st.set_page_config(page_title="Career Tracer AI Agent", page_icon="🚀", layout="wide")

# TITLE
st.title("Career Tracker AI Agent")
st.markdown("Automated Job Tracking | Status Monitoring")

# SIDEBAR: Actions
with st.sidebar:
    st.header("Actions")
    
    # 1. Add New Job
    new_url = st.text_input("Paste Job URL:")
    if st.button("Track Job"):
        if new_url:
            with st.spinner("Scraping & Parsing..."):
                ingest_job(new_url)
            st.success("Job Added!")
            st.rerun()

    st.divider()

    # # 2. Analyze Fit
    # if st.button("🧠 Analyze Latest Fit"):
    #     with st.spinner("Consulting Gemini..."):
    #         analyze_latest_job()
    #     st.success("Analysis Complete!")
    #     st.rerun()

# MAIN DASHBOARD
supabase = get_db_connection()
response = supabase.table("applications").select("*").order("created_at", desc=True).execute()
data = response.data

if data:
    df = pd.DataFrame(data)
    
    # METRICS ROW
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Applied", len(df))
    col2.metric("Interviews", len(df[df['status'] == 'Interview']))
    col3.metric("Rejections", len(df[df['status'] == 'Rejected']))
    
    yield_rate = (len(df[df['status'] == 'Interview']) / len(df)) * 100 if len(df) > 0 else 0
    col4.metric("Yield Rate", f"{yield_rate:.1f}%")

    # ---------------------------------------------------------
    # INTERACTIVE TABLE
    # ---------------------------------------------------------
    st.subheader("Application Pipeline")
    st.info("💡 Tip: Click on 'Status' to update it. Changes save automatically.")

    edited_df = st.data_editor(
        df,
        key="job_editor", # Critical for tracking changes
        column_config={
            "status": st.column_config.SelectboxColumn(
                "Status",
                width="medium",
                options=[
                    "Applied",
                    "Interview",
                    "Rejected",
                    "Offer",
                    "Ghosted",
                    "Yet to Apply"
                ],
                required=True,
            ),
            "created_at": st.column_config.TextColumn("Posted", width = 'small'),
            "job_url": st.column_config.LinkColumn("Link", display_text="View Job"),
            "job_posting_date": st.column_config.TextColumn("Posted", width = 'medium'),
            "job_description": st.column_config.TextColumn("Job Description", width='wide'),
        },
        # Organize the columns neatly
        column_order=[
            "created_at",
            "company_name", 
            "role_title", 
            "status", 
            "role_location", 
            "job_function", 
            "job_posting_date", 
            "job_url",
            "job_description",
            "job_salary"
        ],
        # Prevent editing of columns that should remain static
        disabled=["created_at", "company_name", "role_title", "role_location", "job_url", "job_function"],
        width='stretch',
        hide_index=True,
    )

    # ---------------------------------------------------------
    # AUTO-SAVE LOGIC
    # ---------------------------------------------------------
    if st.session_state["job_editor"]["edited_rows"]:
        updates = st.session_state["job_editor"]["edited_rows"]
        
        for idx, changes in updates.items():
            # 1. Get the real DB ID (Streamlit index matches DataFrame index)
            row_id = df.loc[idx, "id"]
            
            # 2. Update Supabase
            try:
                supabase.table("applications").update(changes).eq("id", int(row_id)).execute()
                st.toast(f"✅ Updated status for {df.loc[idx, 'company_name']}")
            except Exception as e:
                st.error(f"Error updating DB: {e}")
        
        # 3. Rerun to refresh the table with new data
        st.rerun()

else:
    st.info("No applications tracked yet. Paste a URL in the sidebar!")



            # "fit_score": st.column_config.ProgressColumn(
            #     "Fit Score",
            #     format="%d",
            #     min_value=0,
            #     max_value=100,
            # ),