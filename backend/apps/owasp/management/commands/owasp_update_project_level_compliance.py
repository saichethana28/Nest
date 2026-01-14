"""Management command to update project level compliance."""

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now

from apps.owasp.models.project_health_metrics import ProjectHealthMetrics
from apps.owasp.utils.project_level import map_level, normalize_project_name


class Command(BaseCommand):
    """Update project level compliance using canonical OWASP source of truth."""

    help = "Update project level compliance using canonical OWASP source of truth."

    def handle(self, *args, **options):
        """Handle command execution."""
        url = (
            "https://raw.githubusercontent.com/"
            "OWASP/owasp.github.io/main/_data/project_levels.json"
        )

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            official_data = response.json()
        except (requests.RequestException, ValueError) as exc:
            self.stderr.write(self.style.ERROR(f"Failed to fetch official levels: {exc}"))
            return

        by_repo, by_name = {}, {}
        for item in official_data:
            level = item.get("level")
            if repo := item.get("repo"):
                by_repo[repo.lower().strip()] = level
            if name := item.get("name"):
                by_name[normalize_project_name(name)] = level

        current_time = now()
        updated_metrics = []

        metrics_qs = ProjectHealthMetrics.objects.select_related("project").all()

        for metric in metrics_qs:
            project = metric.project

            repo_slug = ""
            if project.owasp_url:
                repo_slug = project.owasp_url.rstrip("/").split("/")[-1].lower()

            raw_level = by_repo.get(repo_slug) or by_name.get(normalize_project_name(project.name))

            if raw_level is None:
                continue

            expected_level = map_level(raw_level)
            if expected_level is None:
                continue

            metric.level_non_compliant = project.level != expected_level
            metric.last_level_check = current_time
            updated_metrics.append(metric)

        if updated_metrics:
            with transaction.atomic():
                ProjectHealthMetrics.bulk_save(
                    updated_metrics,
                    fields=["level_non_compliant", "last_level_check"],
                )

            self.stdout.write(self.style.SUCCESS(f"Processed {len(updated_metrics)} updates."))
