"""
Import calendar events from CSV or ICS files.

CSV columns (header required):
title,date,start_time,end_time,category,is_all_day
"""

import csv
import logging
from datetime import datetime, time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.calendar.models import PersonalSchedule

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import calendar events from CSV or ICS files into PersonalSchedule"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to CSV or ICS file")
        parser.add_argument("--user-id", type=str, help="User id to associate events", required=True)

    def handle(self, *args, **options):
        file_path = Path(options["file_path"])
        user_id = options["user_id"]

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        if file_path.suffix.lower() == ".csv":
            created = self._import_csv(file_path, user_id)
        elif file_path.suffix.lower() == ".ics":
            created = self._import_ics(file_path, user_id)
        else:
            raise CommandError("Unsupported file type. Use CSV or ICS.")

        self.stdout.write(self.style.SUCCESS(f"Imported {created} events"))

    def _import_csv(self, path: Path, user_id: str) -> int:
        created = 0
        with path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    date_obj = datetime.strptime(row["date"], "%Y-%m-%d").date()
                    start_time = (
                        datetime.strptime(row["start_time"], "%H:%M").time()
                        if row.get("start_time")
                        else None
                    )
                    end_time = (
                        datetime.strptime(row["end_time"], "%H:%M").time()
                        if row.get("end_time")
                        else None
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Skipping row %s: %s", row, exc)
                    continue

                PersonalSchedule.objects.create(
                    user_id=user_id,
                    title=row.get("title") or "Untitled",
                    date=date_obj,
                    start_time=start_time,
                    end_time=end_time,
                    category=row.get("category", "general"),
                    is_all_day=row.get("is_all_day", "").lower() in ["true", "1", "yes"],
                )
                created += 1
        return created

    def _import_ics(self, path: Path, user_id: str) -> int:
        """
        Minimal ICS parser (VEVENT only). Supports DTSTART/DTEND DATE or DATETIME.
        """
        created = 0
        current = {}

        def _flush():
            nonlocal created, current
            if not current:
                return
            dtstart = current.get("DTSTART")
            dtend = current.get("DTEND")
            date_obj = None
            start_t = None
            end_t = None

            def parse_dt(val):
                if "T" in val:
                    dt = datetime.strptime(val, "%Y%m%dT%H%M%S")
                    return dt.date(), dt.time()
                dt = datetime.strptime(val, "%Y%m%d")
                return dt.date(), None

            if dtstart:
                date_obj, start_t = parse_dt(dtstart)
            if dtend:
                _, end_t = parse_dt(dtend)

            PersonalSchedule.objects.create(
                user_id=user_id,
                title=current.get("SUMMARY", "Untitled"),
                date=date_obj,
                start_time=start_t,
                end_time=end_t,
                category="ics",
                is_all_day=start_t is None,
                location=current.get("LOCATION", ""),
                description=current.get("DESCRIPTION", ""),
            )
            created += 1
            current = {}

        with path.open() as f:
            for raw in f:
                line = raw.strip()
                if line == "BEGIN:VEVENT":
                    current = {}
                    continue
                if line == "END:VEVENT":
                    _flush()
                    continue
                if ":" in line:
                    key, val = line.split(":", 1)
                    current[key.split(";")[0]] = val
        return created
