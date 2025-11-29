"""
Test BrowserBase Region - Create session in Europe (eu-central-1)
"""
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("BROWSERBASE_API_KEY")
PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

print("Creating BrowserBase session...")
print(f"Target Region: eu-central-1 (Frankfurt, Europe)")
print(f"API Key: {API_KEY[:20]}...")
print(f"Project ID: {PROJECT_ID}")
print()

# Create session with EU region
response = requests.post(
    "https://api.browserbase.com/v1/sessions",
    headers={
        "Content-Type": "application/json",
        "X-BB-API-Key": API_KEY
    },
    json={
        "projectId": PROJECT_ID,
        "region": "eu-central-1"  # Europe (Frankfurt)
    }
)

print(f"HTTP Status: {response.status_code}")
print()

if response.status_code == 201:
    session_data = response.json()
    print("SUCCESS! Session created in Europe!")
    print()
    print("Session Details:")
    print(f"  Session ID: {session_data.get('id')}")
    print(f"  Region: {session_data.get('region')} <- EUROPE!")
    print(f"  Status: {session_data.get('status')}")
    print(f"  Project ID: {session_data.get('projectId')}")
    print()
    print(f"Connect URL: {session_data.get('connectUrl')[:80]}...")
    print()
    print("The browser is now running in Frankfurt, Germany!")
else:
    print("ERROR!")
    print(f"Response: {response.text}")
