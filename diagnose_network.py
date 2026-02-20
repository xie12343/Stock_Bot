import requests

domains = [
    "https://script.google.com",
    "https://notify-api.line.me",
    "https://google.com"
]

for url in domains:
    try:
        print(f"探查 {url}...", end=" ")
        res = requests.get(url, timeout=3)
        print(f"✅ 成功 (Code: {res.status_code})")
    except Exception as e:
        print(f"❌ 失敗 ({type(e).__name__})")
