import os
from unittest import result
from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, field_validator
from langchain_core.prompts import ChatPromptTemplate
from src.db_config import get_db_connection
from datetime import datetime, timedelta, date
from typing import Literal
from firecrawl import FirecrawlApp
from bs4 import BeautifulSoup

# Load Environment Variables
load_dotenv()
if not os.environ.get("GOOGLE_API_KEY"):
    raise ValueError("Missing GOOGLE_API_KEY in .env file")
if not os.environ.get("FIRECRAWL_API_KEY"):
    raise ValueError("Missing FIRECRAWL_API_KEY in .env file")

# Define the schema
class JobData(BaseModel):
    company_name: str = Field(description="The name of the company hiring")
    role_location: str = Field(description="City, State format (e.g. 'Austin, TX). If Remote, put 'Remote'.")
    industry: str = Field(description="The industry of the company (e.g., 'Semiconductor', 'Streaming', 'Fintech'). Infer this from the Company Name if not explicitly stated")
    role_title: str = Field(description="The exact job title")
    job_posting_date: str = Field(description="The date posted. If relative (e.g. '3 days ago'), calculate the date. If not found, return 'Unknown'.")
    job_summary: str = Field(description="A brief 3-sentence summary of the role")
    key_skills: list[str] = Field(description="List of top 5 technical skills required")

    # NEW FIELD: Function/Category
    job_function: Literal["Product", "Machine Learning", "Analytics", "Strategy", "Engineering", "Other"] = Field(
        description="Classify the role based on the description. 'Product' focuses on metrics/A/B testing. 'ML' focuses on modeling/deployment. 'Engineering' focuses on pipelines."
    )
    job_description: str = Field(description="The full job description text extracted from the posting (focus on responsibilities and requirements)")
    job_salary: str = Field(description="The salary range if mentioned, else 'Not Specified'")

    deadline:str = Field(description="The explicit application deadline mentioned in text (YYYY-MM-DD). " \
    "Return None if not found.",
        default=None)


    # VALIDATOR: Force Location Format (Python side cleaning)
    @field_validator('role_location')
    def clean_location(cls, v):
        # Basic cleanup: Remove "United States" or "USA" to keep it short
        clean = v.replace("United States", "").replace("USA", "").strip()
        # Remove trailing commas
        if clean.endswith(","):
            clean = clean[:-1]
        return clean

# The Scraper Function
# def scrape_job_text(url: str):
#     """Fetches raw text from a URL."""
#     print(f"Scraping: {url}...")
#     try:
#         # We add a fake user-agent so websites think we are a browser, not a bot
#         loader = WebBaseLoader(
#             url, 
#             header_template={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
#         )
#         docs = loader.load()
#         # Return the content (sliced to 10k chars to save money/tokens)
#         return docs[0].page_content[:10000]
#     except Exception as e:
#         print(f"Scraping Failed: {e}")
#         return None

def scrape_job_text(url: str):
    """Fetches raw text using Firecrawl."""
    print(f"🕵️‍♀️ Scraping with Firecrawl: {url}...")
    
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        print("❌ Missing FIRECRAWL_API_KEY")
        return None
        
    app = FirecrawlApp(api_key=api_key)
    
    """
    Hybrid Scraper:
    1. Fetches Raw HTML to find hidden JSON-LD (Date/Salary).
    2. Cleans the rest into simple text for the AI.
    """
    
    try:
        print(f"🕵️‍♀️ DEBUG: Requesting Raw HTML for {url}...")
        scrape_result = app.scrape(url, formats = ['rawHtml', 'markdown']) 
        # ^ Note: I added 'markdown' just in case you need a fallback

        # ---------------------------------------------------------
        # ✅ V2 OBJECT COMPATIBLE EXTRACTION
        # ---------------------------------------------------------
        raw_html = ""

        # Check if it's the v2 Document Object (What you have)
        if hasattr(scrape_result, 'rawHtml') or hasattr(scrape_result, 'raw_html'):
            # Try Snake Case first (standard for Python SDKs)
            raw_html = getattr(scrape_result, 'raw_html', None)
            
            # If empty, try Camel Case (standard for API JSON)
            if not raw_html:
                raw_html = getattr(scrape_result, 'rawHtml', None)

        # Fallback for dictionaries (just in case version changes)
        elif isinstance(scrape_result, dict):
            raw_html = scrape_result.get('rawHtml') or scrape_result.get('raw_html')

        # 2. PARSE: Use BeautifulSoup to read the HTML
        soup = BeautifulSoup(raw_html, 'html.parser')
        
        # --- A. SNIPER MODE: Find Hidden Metadata (Date/Salary) ---
        extracted_meta = []
        
        # Look for JSON-LD (Standard for Google Jobs/LinkedIn)
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                # Sometimes it's a list, grab the first job posting
                if isinstance(data, list): 
                    data = next((item for item in data if item.get('@type') == 'JobPosting'), data[0])
                
                if isinstance(data, dict):
                    if 'datePosted' in data:
                        extracted_meta.append(f"HARD_FACT_DATE_POSTED: {data['datePosted']}")
                    if 'baseSalary' in data:
                        extracted_meta.append(f"HARD_FACT_SALARY: {data.get('baseSalary')}")
            except:
                continue

        # --- B. CLEANING MODE: Strip Junk for the AI ---
        # Remove scripts, styles, navbars, footers to save tokens
        for element in soup(["script", "style", "nav", "footer", "header", "form"]):
            element.decompose()

        # Get clean text
        clean_text = soup.get_text(separator="\n")
        
        # Limit text length to prevent token overflow (e.g. 20k chars)
        final_content = clean_text[:20000]

        # 3. COMBINE: Metadata + Content
        final_output = f"""
        --- HIDDEN METADATA FOUND IN HTML ---
        {chr(10).join(extracted_meta)}
        
        --- JOB DESCRIPTION CONTENT ---
        {final_content}
        """
        
        return final_output

    except Exception as e:
        print(f"❌ Scraping Failed: {e}")
        return None
    
# The parser function
def parse_job_details(raw_text: str):
    """Uses LLM to extract structured data from messy text."""
    print("Parsing job details from text...")   
    # Initialize the Model
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # Bind the schema (This is the Magic Move: 'Structured Output')
    structured_llm = llm.with_structured_output(JobData)

    # We add 'Today's Date' to the prompt so the AI can calculate "3 days ago"
    today = date.today().strftime("%Y-%m-%d")
    
    # Create the extraction prompt
    prompt = ChatPromptTemplate.from_template(
        f"""
        You are a career assistant. Today is {today}.
        
        TASK 1: Extract details (Company, Title, Skills). Extract job details from the text below.
        
        CRITICAL INSTRUCTIONS:
        1. **Location:** Standardize to "City, State" (e.g., "San Jose, CA"). If it says "San Jose, California, US", convert it. If the state name is full name, convert to abbreviation.
        2. **Industry:** If the text doesn't say the industry, USE YOUR OWN KNOWLEDGE about the company. 
           - Example: If Company is "NVIDIA", Industry = "Semiconductors".
           - Example: If Company is "Disney", Industry = "Entertainment".

        TASK 2: CLASSIFY the job function into exactly one of these categories:
        - "Engineering" (Pipelines, Infrastructure, Spark, SQL heavy)
        - "Product" (A/B Testing, Metrics, SQL, Product Strategy)
        - "Machine Learning" (Modeling, PyTorch, Deployment, Algorithms)
        - "Analytics" (Dashboards, Tableau, Reporting)
        - "Strategy" (Business Strategy, Market Analysis)
        - "Other" (If it doesn't fit)

        TASK 3: EXTRACT job description:
        - Provide the original job description from the text, focusing on responsibilities and requirements.
        - Separate the job description accordingly to the subtitles in the posting if any.
        - If it does not have any subtitlesjust extract the main body of the job description, organize it into paragraphs

        TASK 4 EXTRACT Date and Salary using the following logic: 
        1. Date: Look for "HARD_FACT_DATE_POSTED" at the top. If it exists, USE THAT DATE. 
            - If not found, look for text like "Posted 3 days ago" in the description.
            - If "Posted 3 days ago", calculate the date from {today}. There has to be a data somewhere in the job description, 
            need to extract it! If no date found, return "Unknown".
        2. Salary: Look for "HARD_FACT_SALARY". If it exists, parse it.
             - If not found, look for salary ranges in the text.
        3. Deadline (URGENCY): Look for phrases like "Applications close on...", "Deadline:", or "Expires on". 
             - If found, format as YYYY-MM-DD.
             - If NOT found, return None (do not guess).
            
        JOB TEXT:
        {{text}}
        """
    )
    
    # Run the chain
    chain = prompt | structured_llm
    result = chain.invoke({"text": raw_text}) # 1. Capture the result first

    if not result.deadline:
            try:
                # 1. Parse the Posting Date (AI should return YYYY-MM-DD)
                posted_dt = datetime.strptime(result.job_posting_date, "%Y-%m-%d")
                
                # 2. Add 14 Days (Your "Urgency Window")
                # You can change '14' to '7' or '30' depending on how fast you want to move
                calculated_deadline = posted_dt + timedelta(days=5)
                
                # 3. Update the result object
                result.deadline = calculated_deadline.strftime("%Y-%m-%d")
                print(f"⚡ No explicit deadline found. Auto-set to {result.deadline} (+5 days).")
                
            except (ValueError, TypeError):
                # Fallback: If "job_posting_date" is weird or missing, use Today + 14 Days
                fallback = datetime.now() + timedelta(days=5)
                result.deadline = fallback.strftime("%Y-%m-%d")
                print(f"⚠️ Date parsing failed. Defaulting deadline to {result.deadline}.")

    return result

# The main ingestor function
def ingest_job(url: str):
    """Runs the full pipeline: Scrape -> Parse -> Save to DB."""
    
    # Step A: Scrape
    raw_text = scrape_job_text(url)
    if not raw_text:
        return
    
    # Step B: Parse
    job_data = parse_job_details(raw_text)
    print(f"Extracted: {job_data.role_title} at {job_data.company_name}")
    

    # Print the classification to verify it works
    print(f"Extracted: {job_data.role_title} at {job_data.company_name}")
    print(f"Category: {job_data.job_function}")  # <--- SEE THE CLASSIFICATION

    # Step C: Save to Supabase
    supabase = get_db_connection()

    
    
    # Prepare the row for insertion
    row = {
        "job_url": url,
        "company_name": job_data.company_name,
        "role_location": job_data.role_location,
        "role_title": job_data.role_title,
        "industry": job_data.industry,
        "job_posting_date": job_data.job_posting_date,
        "job_description": job_data.job_description,
        "job_function": job_data.job_function, 
        "job_salary": job_data.job_salary,
        "status": "Yet to Apply",
        # We'll store summary/skills in a JSONB column or just print them for now
        # (You can add more columns to Supabase later if you want these distinct)
    }
    
    try:
        response = supabase.table("applications").insert(row).execute()
        print("Saved to Database!")
        return response
    except Exception as e:
        print(f"Database Error: {e}")

# Simple test to verify the ingestor
if __name__ == "__main__":
    # Test with a real job link (Replace this with a LIVE link you want to track)
    test_url = input("Paste a job URL to track: ")
    ingest_job(test_url)