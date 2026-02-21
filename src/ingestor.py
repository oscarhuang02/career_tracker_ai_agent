import os
from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, field_validator
from langchain_core.prompts import ChatPromptTemplate
from src.db_config import get_db_connection
from datetime import date
from typing import Literal
from firecrawl import FirecrawlApp

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
    
    try:
        # Pass 'formats' directly, not inside 'params'
        scrape_result = app.scrape(url, formats=['markdown'])
        
        # The result might be an Object or a Dict depending on exact version
        if isinstance(scrape_result, dict):
            content = scrape_result.get('markdown', '') or scrape_result.get('data', {}).get('markdown', '')
        else:
            # If it's an object (v1.0+ standard)
            content = getattr(scrape_result, 'markdown', '')

        return content[:20000]
    
    except Exception as e:
        print(f"❌ Firecrawl Failed: {e}")
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
        3. **Date:** If "Posted 3 days ago", calculate the date from {today}. There has to be a data somewhere in the job description, need to extract it! If no date found, return "Unknown".

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

        JOB TEXT:
        {{text}}
        """
    )
    
    # Run the chain
    chain = prompt | structured_llm
    return chain.invoke({"text": raw_text})

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