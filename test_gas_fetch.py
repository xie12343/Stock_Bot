import requests
import json

GAS_URL = "https://script.google.com/macros/s/AKfycbxLks0Ad8OidLHTfaRtztMCm9yH8_kQjNjIRYwD1XWwgjjnNq_kMKP0fWokErMhNZ0wqA/exec"

try:
    # Try fetching with and without parameters
    print(f"Fetching from: {GAS_URL}")
    response = requests.get(GAS_URL, timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Content: {response.text[:1000]}")
    else:
        print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
