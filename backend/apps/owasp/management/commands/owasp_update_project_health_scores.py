"""A command to update OWASP project health metrics scores."""

from django.core.management.base import BaseCommand

from apps.owasp.models.project_health_metrics import ProjectHealthMetrics
from apps.owasp.models.project_health_requirements import ProjectHealthRequirements


class Command(BaseCommand):
    """Command to update project health scores."""

    help = "Update OWASP project health scores."

    LEVEL_NON_COMPLIANCE_PENALTY = 10.0

    def handle(self, *args, **options):
        """Handle the command execution.

        Args:
            *args: Variable length argument list.
            **options: Arbitrary keyword arguments.

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

        project_health_metrics = []
        project_health_requirements = {
            phr.level: phr for phr in ProjectHealthRequirements.objects.all()
        }
        for metric in ProjectHealthMetrics.objects.filter(
            score__isnull=True,
        ).select_related(
            "project",
        ):
            requirements = project_health_requirements.get(metric.project.level)
            if not requirements:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {metric.project.name}: No requirements found "
                        f"for level {metric.project.level}"
                    )
                )
                continue

            self.stdout.write(
                self.style.NOTICE(f"Updating score for project: {metric.project.name}")
            )

            score = 0.0
            for field, weight in forward_fields.items():
                if int(getattr(metric, field)) >= int(getattr(requirements, field)):
                    score += weight

            for field, weight in backward_fields.items():
                if int(getattr(metric, field)) <= int(getattr(requirements, field)):
                    score += weight

            if requirements.is_level_compliant and not metric.is_level_compliant:
                score -= self.LEVEL_NON_COMPLIANCE_PENALTY

            metric.score = max(0.0, min(100.0, float(score)))
            project_health_metrics.append(metric)

        ProjectHealthMetrics.bulk_save(
            project_health_metrics,
            fields=[
                "score",
            ],
        )
        self.stdout.write(self.style.SUCCESS("Updated project health scores successfully."))
