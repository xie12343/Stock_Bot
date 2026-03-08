import requests
import json

base_url = "https://script.google.com/macros/s/AKfycbxLks0Ad8OidLHTfaRtztMCm9yH8_kQjNjIRYwD1XWwgjjnNq_kMKP0fWokErMhNZ0wqA/exec"

params_to_try = [
    {},
    {"sheet": "etf"},
    {"type": "etf"},
    {"action": "get_etf"},
    {"name": "etf.csv"}
]

for p in params_to_try:
    try:
        print(f"Trying params: {p}")
        response = requests.get(base_url, params=p, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Content length: {len(response.text)}")
            print(f"Preview: {response.text[:200]}")
            if "portfolio_value" in response.text:
                print("Found portfolio_value")
        else:
            print(f"Response: {response.text[:100]}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)
