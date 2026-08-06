import unittest
from unittest.mock import MagicMock
from backend.services.scraper_service import (
    ScraperService,
    SEOHTMLParser,
    calculate_seo_score
)
from backend.services.ai_service import AIService, _generate_dynamic_recommendations
from backend.services.keyword_service import KeywordService
from backend.services.rank_service import RankService, _fetch_serp_position
from backend.services.metrics_service import MetricsService, _calculate_real_domain_metrics

class TestPhase4Replacements(unittest.TestCase):

    def test_real_whois_lookup(self):
        """Verify WHOIS service parses real or fallback domain registrar details."""
        res = ScraperService.lookup_whois("google.com")
        self.assertEqual(res["domain"], "google.com")
        self.assertIn("registrar", res)
        self.assertIn("creation_date", res)
        self.assertIn("expiration_date", res)
        self.assertIsInstance(res["name_servers"], list)

    def test_real_robots_txt_fetch(self):
        """Verify robots.txt fetcher extracts rules or returns clean defaults."""
        res = ScraperService.fetch_robots_txt("google.com")
        self.assertEqual(res["domain"], "google.com")
        self.assertIn("status", res)
        self.assertIn("user_agent", res)
        self.assertIsInstance(res["disallow"], list)
        self.assertIn("sitemap", res)

    def test_real_sitemap_fetch(self):
        """Verify sitemap parser extracts URLs and last modified dates."""
        res = ScraperService.fetch_sitemap("google.com")
        self.assertEqual(res["domain"], "google.com")
        self.assertIn("total_urls", res)
        self.assertIsInstance(res["urls"], list)
        self.assertGreater(len(res["urls"]), 0)

    def test_seo_html_parser_and_score(self):
        """Verify HTML tag parser and dynamic SEO score calculation logic."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Best SEO Agent Automation Software - High Quality Audit Tools</title>
            <meta name="description" content="Automate technical SEO audits, keyword research, rank tracking, and lead discovery with the ultimate production platform.">
            <link rel="canonical" href="https://seoagent.app/">
            <meta property="og:title" content="SEO Agent">
        </head>
        <body>
            <h1>Production SEO Platform</h1>
            <img src="/logo.png" alt="Company Logo">
            <img src="/banner.png">
            <a href="mailto:contact@seoagent.app">Contact Us</a>
        </body>
        </html>
        """
        parser = SEOHTMLParser()
        parser.feed(html)

        self.assertEqual(parser.title, "Best SEO Agent Automation Software - High Quality Audit Tools")
        self.assertIn("Automate technical SEO", parser.meta_description)
        self.assertEqual(parser.h1_tags, ["Production SEO Platform"])
        self.assertEqual(parser.images_count, 2)
        self.assertEqual(parser.images_without_alt, 1)
        self.assertIn("contact@seoagent.app", parser.emails)

        score = calculate_seo_score(
            title=parser.title,
            meta_description=parser.meta_description,
            h1_tags=parser.h1_tags,
            canonical_url=parser.canonical_url,
            images_count=parser.images_count,
            images_without_alt=parser.images_without_alt,
            has_opengraph=parser.has_opengraph,
            is_https=True
        )
        self.assertTrue(70 <= score <= 100)

    def test_dynamic_ai_recommendations(self):
        """Verify AI service generates tailored, dynamic recommendations based on audit flaws."""
        mock_audit = MagicMock()
        mock_audit.id = 101
        mock_audit.score = 45
        mock_audit.title = ""
        mock_audit.title_length = 0
        mock_audit.images_without_alt = 5
        mock_audit.meta_description = ""
        mock_audit.h1_tags = []
        mock_audit.canonical_url = None

        rec_data = _generate_dynamic_recommendations(mock_audit)
        self.assertIn(rec_data["provider"], ["gemini-3.6-flash", "rule-engine"])
        self.assertIn("45/100", rec_data["summary"])
        
        titles = [r["title"] for r in rec_data["recommendations"]]
        self.assertIn("Missing Title Tag", titles)
        self.assertIn("Fix Missing Image Alt Text", titles)
        self.assertIn("Add Meta Description Tag", titles)

    def test_dynamic_keyword_generation(self):
        """Verify KeywordService generates seed-specific variations with calculated volume & difficulty."""
        kws1 = KeywordService.get_keyword_ideas("seo audit", limit=5)
        kws2 = KeywordService.get_keyword_ideas("python fast api", limit=5)

        self.assertEqual(len(kws1), 5)
        self.assertEqual(len(kws2), 5)
        
        self.assertIn("seo audit", kws1[0]["kw"])
        self.assertIn("python fast api", kws2[0]["kw"])
        self.assertNotEqual(kws1[0]["volume"], kws2[0]["volume"])

    def test_real_rank_tracking(self):
        """Verify rank tracking fetches or computes SERP positions."""
        res = _fetch_serp_position("google search", "google.com")
        self.assertEqual(res["domain"], "google.com")
        self.assertIn("position", res)
        self.assertGreaterEqual(res["position"], 1)

    def test_dynamic_domain_metrics(self):
        """Verify MetricsService computes real domain age, authority, and traffic estimates."""
        m1 = _calculate_real_domain_metrics("google.com")
        m2 = _calculate_real_domain_metrics("example.com")

        self.assertEqual(m1["domain"], "google.com")
        self.assertGreater(m1["domain_authority"], 0)
        self.assertGreater(m1["organic_traffic_monthly"], 0)
        self.assertGreater(m1["domain_age_days"], 0)


if __name__ == "__main__":
    unittest.main()
