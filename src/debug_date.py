import sys
import os
# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.ingestor import scrape_job_text

url = input("Paste a URL where the date was 'Unknown': ")
raw_text = scrape_job_text(url)

print("\n--- RAW TEXT START ---")
print(raw_text[:5000])  # Print first 1000 chars (where dates usually live)
print("--- RAW TEXT END ---\n")

print("👀 LOOK ABOVE: Do you see the date (e.g. 'Posted 2 days ago')?")