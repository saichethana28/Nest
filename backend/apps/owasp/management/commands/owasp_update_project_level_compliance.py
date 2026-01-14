"""A command to update OWASP project level compliance."""

import logging
import re

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.owasp.models.project_health_metrics import ProjectHealthMetrics

logger = logging.getLogger(__name__)

LEVELS_URL = (
    "https://raw.githubusercontent.com/OWASP/www-community/main/tab-data/project_levels.json"
)


def clean_name(name: str) -> str:
    """Normalize project names to ensure matches.

    Removes 'OWASP', whitespace, and special characters.
    """
    if not name:
        return ""
    name = name.lower().replace("owasp", "")
    return re.sub(r"[^a-z0-9]+", "", name)


class Command(BaseCommand):
    help = "Update project level compliance based on official OWASP data."

    LEVEL_MAP = {
        "4": "Flagship",
        "3.5": "Flagship",
        "3": "Production",
        "2": "Incubator",
        "1": "Lab",
        "0": "Other",
    }

    def handle(self, *args, **options) -> None:
        self.stdout.write("Fetching official OWASP project levels...")
        try:
            response = requests.get(LEVELS_URL, timeout=15)
            response.raise_for_status()
            official_data = response.json()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch levels: {e}"))
            logger.exception("Network error syncing project levels")
            return

        name_lookup = {}
        repo_lookup = {}
        for item in official_data:
            raw_lvl = str(item.get("level"))
            lvl_name = self.LEVEL_MAP.get(raw_lvl, "Other")
            name = item.get("name")
            repo = item.get("repo")

            if name:
                name_lookup[clean_name(name)] = lvl_name
            if repo:
                repo_lookup[repo.lower().strip()] = lvl_name

        updated_metrics = []
        metrics_qs = ProjectHealthMetrics.objects.select_related("project").iterator()

        for metric in metrics_qs:
            project = metric.project
            official_level = name_lookup.get(clean_name(project.name))
            if not official_level and project.owasp_url:
                slug = project.owasp_url.rstrip("/").split("/")[-1].lower()
                official_level = repo_lookup.get(slug)

            if official_level:
                is_compliant = str(project.level).lower() == official_level.lower()
                if metric.is_level_compliant != is_compliant:
                    metric.is_level_compliant = is_compliant
                    updated_metrics.append(metric)

        if updated_metrics:
            with transaction.atomic():
                ProjectHealthMetrics.bulk_save(updated_metrics, fields=["is_level_compliant"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully updated compliance for {len(updated_metrics)} projects."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("All projects are already in compliance."))
