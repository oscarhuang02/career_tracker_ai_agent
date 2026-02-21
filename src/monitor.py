import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from src.db_config import get_db_connection

# Scopes: Read-only access to Gmail
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    """Authenticates with Gmail API."""
    creds = None
    # Token file stores your login so you don't log in every time
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Opens a browser window to log you in
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the token for next time
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

def check_emails():
    print("📧 Scanning Inbox for Career Updates...")
    service = get_gmail_service()
    supabase = get_db_connection()

    # 1. Fetch 'Applied' jobs from DB to know what Company Names to look for
    jobs = supabase.table("applications").select("id, company_name").eq("status", "Applied").execute().data
    
    if not jobs:
        print("✅ No pending applications to check.")
        return

    # 2. Scan recent emails (Last 10 messages to be safe)
    results = service.users().messages().list(userId='me', maxResults=20).execute()
    messages = results.get('messages', [])

    for msg in messages:
        txt = service.users().messages().get(userId='me', id=msg['id']).execute()
        snippet = txt.get('snippet', '').lower()
        headers = txt['payload']['headers']
        subject = next(h['value'] for h in headers if h['name'] == 'Subject').lower()
        sender = next(h['value'] for h in headers if h['name'] == 'From').lower()

        # 3. Match Emails to Companies
        for job in jobs:
            company = job['company_name'].lower()
            
            # Simple Logic: If Company Name is in Subject/Sender AND keyword matches
            if company in subject or company in sender:
                new_status = None
                
                # REJECTION DETECTION
                if any(x in snippet for x in ["unfortunately", "not moving forward", "other candidates"]):
                    new_status = "Rejected"
                    print(f"❌ Rejection found for {job['company_name']}")

                # INTERVIEW DETECTION
                elif any(x in snippet for x in ["schedule", "availability", "interview", "phone screen"]):
                    new_status = "Interview"
                    print(f"🎉 Interview found for {job['company_name']}!")

                # UPDATE DB
                if new_status:
                    supabase.table("applications").update({"status": new_status}).eq("id", job['id']).execute()

if __name__ == "__main__":
    check_emails()