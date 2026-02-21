import sys
import os
# Fix path to find src modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db_config import get_db_connection
from src.ingestor import scrape_job_text
import time

def backfill_descriptions():
    supabase = get_db_connection()
    
    # 1. Fetch all rows where job_description is NULL
    print("Fetching incomplete records...")
    response = supabase.table("applications").select("*").is_("job_description", "null").execute()
    rows = response.data
    
    if not rows:
        print("No empty records found! Your database is up to date.")
        return

    print(f"found {len(rows)} records to update.")

    # 2. Loop through and fix them
    for row in rows:
        job_id = row['id']
        url = row['job_url']
        company = row.get('company_name', 'Unknown Company')
        
        print(f"Re-scraping: {company}...")
        
        # Re-run the scraper
        try:
            # We use the existing scrape function from your ingestor
            new_description = scrape_job_text(url)
            
            if new_description:
                # 3. Update the specific row
                supabase.table("applications").update({
                    "job_description": new_description
                }).eq("id", job_id).execute()
                print(f"   ✅ Fixed!")
            else:
                print(f"   ⚠️ Failed to scrape (Link might be expired).")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Sleep briefly to avoid getting blocked by anti-bots
        time.sleep(2)

if __name__ == "__main__":
    backfill_descriptions()