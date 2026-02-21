import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load env
load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    print("No API Key found in .env")
    exit()

print(f"Testing API Key: {api_key[:5]}...")

# Configure the SDK
genai.configure(api_key=api_key)

print("\n Fetching available models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f" - {m.name}")
except Exception as e:
    print(f"Error fetching models: {e}")