## Career Tracker AI Agent 🚀
A smart, automated job application tracker. Instead of manually copy-pasting company names, salaries, and job descriptions into a spreadsheet, you just give this tool a link to a job posting. The AI reads the page, pulls out all the important details, and organizes them into a clean, interactive dashboard.

### How It Works (Step-by-Step)
This project runs a pipeline that turns a messy webpage into structured data:

You Provide a Link: You enter the URL of a job posting (like a LinkedIn or Greenhouse link).

The Scraper Reads the Page: The app uses Firecrawl to grab the raw website code. It uses Python to quickly hunt down hidden facts (like the exact date it was posted or hidden salary numbers) and strips away the junk (like website menus and buttons).

The AI Extracts the Facts: We pass the clean text to Google's Gemini AI. The AI acts like a recruiter, reading the description to find the Company Name, Role, Industry, and core requirements.

Smart Deadlines are Calculated: If the job doesn't have a strict deadline, the app automatically gives you a "5-Day Default" deadline so you remember to apply.

Data is Saved safely: Everything is instantly stored in a Supabase database.

You Manage Your Pipeline: You open the Streamlit dashboard. Here, you can view all your saved jobs, see how many days you have left to apply, and change your status (e.g., from "Yet to Apply" to "Interview").

### Built With
Frontend: Streamlit (For the interactive dashboard and tables)

AI: Google Gemini Flash & LangChain (For reading and extracting text)

Scraping: Firecrawl & BeautifulSoup4 (For reading websites)

Database: Supabase (PostgreSQL)

Language: Python

### How to Run This Project Locally
1. Activate your virtual environment
Make sure you are in the project folder, then run:

Bash
source venv/bin/activate
2. Install the required libraries

Bash
pip install -r requirements.txt
3. Set up your secret keys
Create a file named .env in the main folder and add your API keys:

Ini, TOML
SUPABASE_URL="your_supabase_url"
SUPABASE_KEY="your_supabase_key"
GEMINI_API_KEY="your_gemini_key"
FIRECRAWL_API_KEY="your_firecrawl_key"
4. Start the Dashboard

Bash
streamlit run src/dashboard.py
