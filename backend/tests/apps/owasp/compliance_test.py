"""Tests for OWASP project level compliance."""

from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command

from apps.owasp.models.project import Project
from apps.owasp.models.project_health_metrics import ProjectHealthMetrics
from apps.owasp.models.project_health_requirements import ProjectHealthRequirements


@pytest.mark.django_db
class TestCompliance:
    """Test suite for OWASP project level compliance and scoring penalty."""

    def setup_method(self) -> None:
        """Set up test data for compliance tracking."""
        self.project = Project.objects.create(
            name="Test Project",
            level="Flagship",
            owasp_url="https://owasp.org/www-project-test",
            is_active=True,
        )

        self.req = ProjectHealthRequirements.objects.create(
            level="Flagship", is_level_compliant=True, age_days=0, stars_count=0, forks_count=0
        )

        self.metrics = ProjectHealthMetrics.objects.create(
            project=self.project,
            is_level_compliant=True,
            score=100.0,
            age_days=100,
            stars_count=100,
            forks_count=100,
        )

    @patch("requests.get")
    def test_compliance_detection(self, mock_get) -> None:
        mock_get.return_value = Mock(status_code=200)
        mock_get.return_value.json.return_value = [
            {"name": "Test Project", "level": "1", "repo": "www-project-test"}
        ]
        call_command("owasp_update_project_level_compliance")
        self.metrics.refresh_from_db()
        assert self.metrics.is_level_compliant is False

    def test_score_penalty_application(self) -> None:
        """Ensure score calculation applies the penalty when non-compliant."""
        self.metrics.is_level_compliant = False
        self.metrics.score = None
        self.metrics.save()

        call_command("owasp_update_project_health_scores")

        self.metrics.refresh_from_db()
        assert float(self.metrics.score) < 100.0
        assert float(self.metrics.score) >= 0.0
