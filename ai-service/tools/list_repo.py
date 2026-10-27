"""List files at a GitHub repo root (or given path).

Usage:  python list_repo.py <owner/repo> [path]
"""
import json
import sys
import urllib.request

repo = sys.argv[1]
path = sys.argv[2] if len(sys.argv) > 2 else ""
url = f"https://api.github.com/repos/{repo}/contents/{path}"
req = urllib.request.Request(url, headers={"User-Agent": "phishguard-project"})
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.load(resp)
if not isinstance(data, list):
    print("not a directory:", data)
    sys.exit(1)
for item in data:
    size = item.get("size", 0)
    print(f"{size:>12}  {item['type']:<5} {item['name']}")
