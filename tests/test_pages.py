#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX = DOCS / "index.html"
ANALYTICS = DOCS / "analytics.js"
PUBLIC_URL = "https://pinion05.github.io/domestic-brand-sale-scan/"
WEBSITE_ID = "fd90ef5c-88a8-40f1-b569-4413d8bf3e08"
VERIFICATION = "tGZYSwkJ7uPLwhzvsriljxAWZhofG76Pes8K-niG_Y0"


class PageAnalyticsMarkupTest(unittest.TestCase):
    def setUp(self):
        self.html = INDEX.read_text(encoding="utf-8")

    def test_installs_privacy_respecting_umami_and_search_console_verification(self):
        self.assertIn('src="https://cloud.umami.is/script.js"', self.html)
        self.assertIn(f'data-website-id="{WEBSITE_ID}"', self.html)
        self.assertIn('data-domains="pinion05.github.io"', self.html)
        self.assertIn('data-do-not-track="true"', self.html)
        self.assertIn('data-performance="true"', self.html)
        self.assertIn(f'content="{VERIFICATION}"', self.html)

    def test_exposes_share_control_and_canonical_metadata(self):
        self.assertIn('id="share-report"', self.html)
        self.assertIn(f'<link rel="canonical" href="{PUBLIC_URL}">', self.html)
        self.assertIn(f'<meta property="og:url" content="{PUBLIC_URL}">', self.html)
        self.assertIn('<script src="./analytics.js"></script>', self.html)


class AnalyticsContractTest(unittest.TestCase):
    def run_node(self, body: str):
        script = f"const analytics = require({json.dumps(str(ANALYTICS))});\n{body}"
        result = subprocess.run(
            ["node", "-e", script],
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_share_url_uses_dated_utm_contract_and_discards_existing_query(self):
        value = self.run_node(
            "console.log(JSON.stringify(analytics.buildShareUrl("
            "'https://pinion05.github.io/domestic-brand-sale-scan/?utm_source=old#list', "
            "'2026-07-20')));"
        )
        self.assertEqual(
            "https://pinion05.github.io/domestic-brand-sale-scan/"
            "?utm_source=direct_share&utm_medium=referral&"
            "utm_campaign=daily_sale_20260720&utm_content=daily_report",
            value,
        )

    def test_search_event_never_contains_the_raw_query(self):
        event = self.run_node(
            "console.log(JSON.stringify(analytics.searchEvent({"
            "resultCount: 3, filter: 'exact', reportDate: '2026-07-20'"
            "})));"
        )
        self.assertEqual("search_used", event["name"])
        self.assertEqual(
            {"result_count": 3, "filter": "exact", "report_date": "2026-07-20"},
            event["properties"],
        )
        self.assertNotIn("query", event["properties"])

    def test_official_store_event_has_stable_non_sensitive_properties(self):
        event = self.run_node(
            "console.log(JSON.stringify(analytics.saleClickEvent({"
            "brand: '마뗑킴', tier: 'exact', max: 80, urgent: false"
            "}, 5, 'ledger', '2026-07-20')));"
        )
        self.assertEqual("official_store_click", event["name"])
        self.assertEqual(
            {
                "brand": "마뗑킴",
                "tier": "exact",
                "max_discount": 80,
                "urgent": "no",
                "position": 5,
                "section": "ledger",
                "report_date": "2026-07-20",
            },
            event["properties"],
        )

    def test_ends_today_click_uses_the_expiring_offer_discount(self):
        event = self.run_node(
            "console.log(JSON.stringify(analytics.saleClickEvent({"
            "brand: '마인드브릿지', tier: 'exact', max: 92, urgent: true, urgentMax: 89"
            "}, 1, 'ends_today', '2026-07-20')));"
        )
        self.assertEqual(89, event["properties"]["max_discount"])


class AnalyticsDocumentationTest(unittest.TestCase):
    def test_readme_documents_events_privacy_and_utm_contract(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for expected in (
            "official_store_click",
            "filter_select",
            "search_used",
            "share_click",
            "검색어 원문은 수집하지 않는다",
            "utm_campaign=daily_sale_YYYYMMDD",
        ):
            self.assertIn(expected, readme)


class SearchDiscoveryFilesTest(unittest.TestCase):
    def test_robots_points_to_the_project_sitemap(self):
        robots = (DOCS / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("User-agent: *", robots)
        self.assertIn("Allow: /", robots)
        self.assertIn(f"Sitemap: {PUBLIC_URL}sitemap.xml", robots)

    def test_sitemap_contains_the_canonical_page(self):
        sitemap = (DOCS / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn(f"<loc>{PUBLIC_URL}</loc>", sitemap)
        self.assertIn("<lastmod>2026-07-20</lastmod>", sitemap)


if __name__ == "__main__":
    unittest.main(verbosity=2)
