from pathlib import Path

from django.conf import settings
from django.test import TestCase


class PublicPagesSmokeTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_login_page_loads(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)


class ProtectedReportsSmokeTests(TestCase):
    def test_summary_requires_login(self):
        response = self.client.get("/reports/summary/")
        self.assertIn(response.status_code, [302, 403])

        if response.status_code == 302:
            self.assertIn("/accounts/login/", response["Location"])

    def test_analytics_requires_login(self):
        response = self.client.get("/reports/analytics/")
        self.assertIn(response.status_code, [302, 403])

        if response.status_code == 302:
            self.assertIn("/accounts/login/", response["Location"])


class TemplateRegressionTests(TestCase):
    def test_analytics_template_has_quick_filters(self):
        template_path = Path(settings.BASE_DIR) / "templates" / "reports" / "analytics.html"
        html = template_path.read_text(encoding="utf-8")

        self.assertIn("analyticsFilterForm", html)
        self.assertIn("quick-filters", html)
        self.assertIn('data-range="today"', html)
        self.assertIn('data-range="7"', html)
        self.assertIn('data-range="30"', html)
        self.assertIn('data-range="180"', html)

    def test_tx_preview_template_has_cancel_button(self):
        template_path = Path(settings.BASE_DIR) / "templates" / "reports" / "tx_preview.html"
        html = template_path.read_text(encoding="utf-8")

        self.assertIn("cancelTxForm", html)
        self.assertIn("data-cancel-url", html)
        self.assertIn("/transactions/api/tx/{{ tx.id }}/cancel/", html)
        self.assertIn("btn danger", html)
        self.assertIn("tx-status-badge", html)
