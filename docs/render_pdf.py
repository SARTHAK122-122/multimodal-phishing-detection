"""Render docs/datasets-report.html to a print-ready A4 PDF.

Run with the project venv:
    ai-service\\.venv\\Scripts\\python.exe docs\\render_pdf.py
"""
import pathlib

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
HTML = HERE / "datasets-report.html"
PDF = HERE / "Datasets-Report.pdf"


def main() -> None:
    if not HTML.exists():
        raise SystemExit(f"missing {HTML}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(HTML.as_uri())
        page.pdf(
            path=str(PDF),
            format="A4",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            display_header_footer=True,
            header_template="<span></span>",
            footer_template=(
                '<div style="width:100%;font-size:7.5px;color:#8892a8;'
                "text-align:center;font-family:Segoe UI,Arial\">"
                "PhishGuard AI — Datasets &amp; Data Pipeline &nbsp;·&nbsp; "
                'Page <span class="pageNumber"></span> of <span class="totalPages"></span>'
                "</div>"
            ),
        )
        browser.close()
    print(f"OK  {PDF}  ({PDF.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
