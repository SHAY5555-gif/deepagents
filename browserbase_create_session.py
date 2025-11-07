#!/usr/bin/env python
"""
BrowserBase Session Creator with EU Region as Default

Usage:
    python browserbase_create_session.py

This script creates BrowserBase sessions with eu-central-1 as the default region.
Set BROWSERBASE_REGION in .env to change the default.
"""
import requests
import os
from dotenv import load_dotenv
import sys

load_dotenv()

def create_session(region=None, **kwargs):
    """
    Create a BrowserBase session with configurable region.

    Args:
        region: Region to use. Defaults to BROWSERBASE_REGION env var or 'eu-central-1'
        **kwargs: Additional session parameters (timeout, keepAlive, etc.)

    Returns:
        dict: Session data including id, connectUrl, and region
    """
    api_key = os.getenv("BROWSERBASE_API_KEY")
    project_id = os.getenv("BROWSERBASE_PROJECT_ID")

    if not api_key or not project_id:
        raise ValueError("BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID must be set in .env")

    # Use provided region, or env var, or default to EU
    if region is None:
        region = os.getenv("BROWSERBASE_REGION", "eu-central-1")

    payload = {
        "projectId": project_id,
        "region": region,
        **kwargs
    }

    response = requests.post(
        "https://api.browserbase.com/v1/sessions",
        headers={
            "Content-Type": "application/json",
            "X-BB-API-Key": api_key
        },
        json=payload
    )

    if response.status_code != 201:
        raise Exception(f"Failed to create session: {response.status_code} - {response.text}")

    return response.json()


if __name__ == "__main__":
    print("Creating BrowserBase session...")
    print(f"Default region: {os.getenv('BROWSERBASE_REGION', 'eu-central-1')}")
    print()

    session = create_session()

    print("SUCCESS! Session created")
    print(f"  Session ID: {session['id']}")
    print(f"  Region: {session['region']}")
    print(f"  Status: {session['status']}")
    print(f"  Connect URL: {session['connectUrl'][:80]}...")
    print()
    print(f"Region: {session['region']} - {'EUROPE!' if 'eu' in session['region'] else 'Other'}")
