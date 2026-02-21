import os
from dotenv import load_dotenv
from supabase import create_client, Client 

# load environment variables from .env file
load_dotenv()

# create supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")

# initialize supabase client
supabase: Client = create_client(supabase_url, supabase_key)

def get_db_connection():
    """Returns the authenticated supabase client."""
    print("Database connection established.")
    return supabase

# simple test to verify connection
if __name__ == "__main__":
    db = get_db_connection()
    response = db.table("applications").select("*").execute()
    print(f"Connection Test: Found {len(response.data)} applications.")

