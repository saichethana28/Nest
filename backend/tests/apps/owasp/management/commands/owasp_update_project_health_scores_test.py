"""Update OWASP project health scores.

This command recalculates health scores for OWASP projects based on
their collected metrics and level-specific requirements.

In addition to the base scoring logic, a fixed penalty is applied
to projects whose locally stored level does not match the official
OWASP project level (i.e., level_non_compliant=True).

This command is designed to be run periodically after project sync
and level-compliance detection jobs.
"""

from django.core.management.base import BaseCommand

from apps.owasp.models.project_health_metrics import ProjectHealthMetrics
from apps.owasp.models.project_health_requirements import (
    ProjectHealthRequirements,
)


class Command(BaseCommand):
    """Management command to update OWASP project health scores.

    Scoring logic:
    - Forward metrics: higher values are better (>= requirement)
    - Backward metrics: lower values are better (<= requirement)
    - Each satisfied requirement contributes a fixed weight
    - Non-compliant project levels incur a penalty

    The final score is clamped to the range [0, 100].
    """

    help = "Update OWASP project health scores."

    LEVEL_NON_COMPLIANCE_PENALTY = 10.0

    def handle(self, *args, **options):
        """Execute the health score update process."""
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
            project = metric.project
            requirements = requirements_by_level.get(project.level)

            if not requirements:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {project.name}: No requirements found for level {project.level}"
                    )
                )
                continue

            self.stdout.write(self.style.NOTICE(f"Updating score for project: {project.name}"))

            score = 0.0

            for field, weight in forward_fields.items():
                if int(getattr(metric, field)) >= int(getattr(requirements, field)):
                    score += weight

            for field, weight in backward_fields.items():
                if int(getattr(metric, field)) <= int(getattr(requirements, field)):
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
