"""Search GitHub for public phishing URL datasets (repo search API, no auth).

Usage:  curl.exe -s "<search-url>" | python search_repos.py
Prints repo name, stars and description.
"""
import json
import sys

data = json.load(sys.stdin)
items = data.get("items", [])
if not items:
    print("no results:", data.get("message", ""))
for i in items:
    desc = (i.get("description") or "").replace("\n", " ")[:90]
    print(f"{i['stargazers_count']:>5}  {i['full_name']:<55} {desc}")
