import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.db_config import get_db_connection

# 1. Load Environment
load_dotenv()

def analyze_latest_job():
    # 2. Get the latest job from Supabase
    supabase = get_db_connection()
    
    # We fetch the most recent application
    response = supabase.table("applications")\
        .select("*")\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()
    
    if not response.data:
        print("No jobs found in database. Run 'src.ingestor' first!")
        return

    job = response.data[0]
    print(f"Analyzing fit for: {job['role_title']} at {job['company_name']}...")

    # 3. Load Your Resume
    try:
        with open("data/resume_master.txt", "r") as f:
            my_resume = f.read()
    except FileNotFoundError:
        print("Error: 'data/resume_master.txt' not found. Please create it.")
        return

    # 4. The Brain (Gemini Pro)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # 5. The "Coach" Prompt
    template = """
    You are a strict technical recruiter. 
    
    CANDIDATE RESUME:
    {resume}
    
    TARGET JOB DESCRIPTION:
    {job_desc}

    TARGET JOB INDUSTRY:
    {industry}
    
    TASK:
    Compare the resume to the job description. Also takes into account of the industry.
    Think about the relevant experienced needed for the role in the particular industry.
    Suggestions to improve the resume should be specific and actionable.

    
    OUTPUT FORMAT:
    fit_score: [0-100]
    missing_keywords: [List of top 3 hard skills present in JD but missing in Resume]
    advice: [1 sentence on how to tailor the resume for this specific role]
    Recommendeded Changes to bullet points:
    - [List of 3 specific bullet points to add or modify in the resume to better fit the job and why these changes]

    Do not be polite. Be factual.
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | StrOutputParser()
    
    # 6. Run the Analysis
    print("Thinking...")
    result = chain.invoke({
        "resume": my_resume, 
        "job_desc": job['job_description'],
        "industry": job['industry']
    })
    
    print("\n" + "="*30)
    print("      REPORT      ")
    print("="*30)
    print(result)
    
    # 7. (Optional) Save the score back to the database
    # This involves parsing the string 'fit_score: 85', which we can do later if you want.

if __name__ == "__main__":
    analyze_latest_job()