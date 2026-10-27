"""What lexicon phrases does github.com's real page text trigger?"""
from __future__ import annotations
from app.acquisition import fetcher
from app.features import page_text
from app.ml import social_lexicon

for url in ["https://github.com", "https://www.python.org"]:
    fr = fetcher.fetch_html(url)
    txt = page_text.extract_visible_text(fr.html) if fr.ok else ""
    ta = page_text.analyze_text(txt, source="webpage")
    print(f"\n=== {url}  (fetched ok={fr.ok}, text len={len(txt)})")
    print(f"  category_scores: {ta.category_scores}")
    for m in ta.phrase_matches[:15]:
        print(f"    [{m.category} w={m.weight}] '{m.phrase}'")
