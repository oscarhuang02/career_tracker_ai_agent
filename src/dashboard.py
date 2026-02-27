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
    
    # "errors='coerce'" turns "Unknown" strings into NaT (Empty/Blank), which fixes the crash.
    df['job_posting_date'] = pd.to_datetime(df['job_posting_date'], errors='coerce')
    df['deadline'] = pd.to_datetime(df['deadline'], errors='coerce')
    
    # Get Today (normalized to midnight so 'days_left' is an integer)
    today = pd.to_datetime("today").normalize()
    
    # Logic: If deadline is Missing (NaN), use Today + 5 Days
    # We create a temporary 'effective_deadline' column for the math
    df['effective_deadline'] = df['deadline'].fillna(today + pd.Timedelta(days=5))
    
    # Calculate Days Left
    df['days_left'] = (df['effective_deadline'] - today).dt.days

    # Formatter Function
    def format_deadline(row):
        days = int(row['days_left'])
        # Show the date stored in effective_deadline (either real or default)
        date_str = row['effective_deadline'].strftime('%Y-%m-%d')
        
        if days < 0:
            return f"Expired ({date_str})"
        else:
            return f"Due in {days} days ({date_str})"

    df['formatted_deadline'] = df.apply(format_deadline, axis=1)

    # METRICS ROW
    col1, col2, col3, col4, col5= st.columns(5)
    col1.metric("Total Applied", len(df[df['status'] == 'Applied']))
    col2.metric("Yet to Apply", len(df[df['status'] == 'Yet to Apply']))
    col3.metric("Interviews", len(df[df['status'] == 'Interview']))
    col4.metric("Rejections", len(df[df['status'] == 'Rejected']))
    
    yield_rate = (len(df[df['status'] == 'Interview']) / len(df)) * 100 if len(df) > 0 else 0
    col5.metric("Yield Rate", f"{yield_rate:.1f}%")

    # ---------------------------------------------------------
    # INTERACTIVE TABLE
    # ---------------------------------------------------------
    st.subheader("Application Pipeline")
    st.info("💡 Tip: Click on 'Status' to update it. Changes save automatically.")

    edited_df = st.data_editor(
        df,
        key="job_editor",
        column_config={
            "status": st.column_config.SelectboxColumn(
                "Status",
                width="medium",
                options=[
                    "Yet to Apply", "Applied", "Interview", 
                    "Rejected", "Offer", "Ghosted"
                ],
                required=True,
            ),
            "created_at": st.column_config.TextColumn("Added On", width='small'),
            "job_url": st.column_config.LinkColumn("Link", display_text="View Job"),
            "job_posting_date": st.column_config.DateColumn("Posted", width='small'),
            
            # NEW: formatted_deadline Configuration
            "formatted_deadline": st.column_config.TextColumn(
                "Deadline", 
                width="medium"
            ),
            
            "job_description": st.column_config.TextColumn("Job Description", width='large'),
        },
        # Organize the columns (Inserted formatted_deadline after job_posting_date)
        column_order=[
            "created_at",
            "company_name", 
            "role_title", 
            "status", 
            "job_posting_date",
            "formatted_deadline", 
            "role_location", 
            "job_function", 
            "job_url",
            "job_salary"
        ],
        # Disable editing for calculated fields
        disabled=[
            "created_at", "company_name", "role_title", 
            "role_location", "job_url", "job_function", 
            "formatted_deadline", "job_posting_date"
        ],
        use_container_width=True,
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