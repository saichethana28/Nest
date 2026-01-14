"""Update OWASP project health scores.

Calculates and updates project health scores based on defined health
requirements and applies a penalty when a project is marked as
level-non-compliant.
"""

from django.core.management.base import BaseCommand

from apps.owasp.models.project_health_metrics import ProjectHealthMetrics
from apps.owasp.models.project_health_requirements import (
    ProjectHealthRequirements,
)


class Command(BaseCommand):
    """Command to update OWASP project health scores."""

    help = "Update OWASP project health scores."

    LEVEL_NON_COMPLIANCE_PENALTY = 10.0

    @staticmethod
    def _safe_int(value) -> int:
        """Safely convert a nullable value to an integer.

        Args:
            value: A numeric or nullable value.

        Returns:
            int: Converted integer value or 0 if conversion fails.

        """
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def handle(self, *args, **options):
        """Execute the health score update process.

        Iterates through project health metrics with missing scores,
        evaluates them against level-specific requirements, applies
        scoring logic, and persists updated scores in bulk.

        Returns:
            None

        """
        forward_fields = {
            "age_days": 6.0,
            "contributors_count": 6.0,
            "forks_count": 6.0,
            "is_funding_requirements_compliant": 5.0,
            "is_leader_requirements_compliant": 5.0,
            "open_pull_requests_count": 6.0,
            "recent_releases_count": 6.0,
            "stars_count": 6.0,
            "total_pull_requests_count": 6.0,
            "total_releases_count": 6.0,
        }

        backward_fields = {
            "last_commit_days": 6.0,
            "last_pull_request_days": 6.0,
            "last_release_days": 6.0,
            "open_issues_count": 6.0,
            "owasp_page_last_update_days": 6.0,
            "unanswered_issues_count": 6.0,
            "unassigned_issues_count": 6.0,
        }

        requirements_by_level = {req.level: req for req in ProjectHealthRequirements.objects.all()}

        metrics_to_update = []

        for metric in ProjectHealthMetrics.objects.filter(score__isnull=True).select_related(
            "project"
        ):
            requirements = requirements_by_level.get(metric.project.level)

            if not requirements:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {metric.project.name}: "
                        f"No requirements for level {metric.project.level}"
                    )
                )
                continue

            self.stdout.write(
                self.style.NOTICE(f"Updating score for project: {metric.project.name}")
            )

            score = 0.0

            for field, weight in forward_fields.items():
                if self._safe_int(getattr(metric, field, None)) >= self._safe_int(
                    getattr(requirements, field, None)
                ):
                    score += weight

            for field, weight in backward_fields.items():
                if self._safe_int(getattr(metric, field, None)) <= self._safe_int(
                    getattr(requirements, field, None)
                ):
                    score += weight

            if metric.level_non_compliant:
                score -= self.LEVEL_NON_COMPLIANCE_PENALTY

            metric.score = max(0.0, min(100.0, score))
            metrics_to_update.append(metric)

        if metrics_to_update:
            ProjectHealthMetrics.bulk_save(
                metrics_to_update,
                fields=["score"],
            )

        self.stdout.write(self.style.SUCCESS("Updated project health scores successfully."))
