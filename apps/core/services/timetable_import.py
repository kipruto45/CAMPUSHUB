"""Utilities for importing academic structure from CUK timetable PDFs."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess

from apps.courses.models import Course, Unit
from apps.faculties.models import Department, Faculty


WEEKDAYS = (
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
)

UNIT_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9/ .-]*\d[A-Z0-9/ .-]*$")
ONLY_DIGITS_RE = re.compile(r"^\d+$")


@dataclass(frozen=True)
class FacultySpec:
    code: str
    name: str
    description: str


@dataclass(frozen=True)
class DepartmentSpec:
    code: str
    faculty_code: str
    name: str
    description: str


@dataclass(frozen=True)
class CourseSpec:
    code: str
    name: str
    department_code: str
    duration_years: int
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedTimetableRow:
    course_label: str
    course_code: str
    year_of_study: int
    semester: str
    unit_code: str
    unit_name: str
    source_line: str
    ssp_variant: bool = False


@dataclass
class TimetableImportReport:
    faculties_created: int = 0
    faculties_updated: int = 0
    departments_created: int = 0
    departments_updated: int = 0
    courses_created: int = 0
    courses_updated: int = 0
    units_created: int = 0
    units_updated: int = 0
    parsed_rows: int = 0
    clustered_units: int = 0
    skipped_rows: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


FACULTY_SPECS: dict[str, FacultySpec] = {
    "SOC": FacultySpec(
        code="SOC",
        name="School of Computing and Mathematics",
        description="School of Computing and Mathematics",
    ),
    "SBE": FacultySpec(
        code="SBE",
        name="School of Business and Economics",
        description="School of Business and Economics",
    ),
    "SCCD": FacultySpec(
        code="SCCD",
        name="School of Co-operative and Community Development",
        description="School of Co-operative and Community Development",
    ),
    "SESD": FacultySpec(
        code="SESD",
        name="School of Environment and Sustainable Development",
        description="School of Environment and Sustainable Development",
    ),
}

DEPARTMENT_SPECS: dict[str, DepartmentSpec] = {
    "CS": DepartmentSpec(
        code="CS",
        faculty_code="SOC",
        name="Computer Science",
        description="Department of Computer Science and Information Technology",
    ),
    "MDS": DepartmentSpec(
        code="MDS",
        faculty_code="SOC",
        name="Mathematics and Data Science",
        description="Department of Mathematics, Statistics and Data Science",
    ),
    "BE": DepartmentSpec(
        code="BE",
        faculty_code="SBE",
        name="Business and Economics",
        description="Department of Business and Economics programmes",
    ),
    "CCD": DepartmentSpec(
        code="CCD",
        faculty_code="SCCD",
        name="Co-operative and Community Development",
        description="Department of Co-operative and Community Development",
    ),
    "ESD": DepartmentSpec(
        code="ESD",
        faculty_code="SESD",
        name="Environment and Sustainable Development",
        description="Department of Environment and Sustainable Development",
    ),
}

COURSE_SPECS: dict[str, CourseSpec] = {
    "BAEM": CourseSpec(
        code="BAEM",
        name="Bachelor of Agricultural Economics and Marketing",
        department_code="CCD",
        duration_years=4,
    ),
    "BASD": CourseSpec(
        code="BASD",
        name="Bachelor of Science in Applied Statistics and Data Science",
        department_code="MDS",
        duration_years=4,
        aliases=("BSASDS",),
    ),
    "BASE": CourseSpec(
        code="BASE",
        name="Bachelor of Science in Applied Statistics and Economics",
        department_code="MDS",
        duration_years=4,
        aliases=("BSASE",),
    ),
    "BBF": CourseSpec(
        code="BBF",
        name="Bachelor of Banking and Finance",
        department_code="BE",
        duration_years=4,
    ),
    "BBIO": CourseSpec(
        code="BBIO",
        name="Bachelor of Science in Bioinformatics",
        department_code="MDS",
        duration_years=4,
    ),
    "BBIT": CourseSpec(
        code="BBIT",
        name="Bachelor of Business Information Technology",
        department_code="CS",
        duration_years=4,
    ),
    "BBM": CourseSpec(
        code="BBM",
        name="Bachelor of Business Management",
        department_code="BE",
        duration_years=4,
    ),
    "BCCD": CourseSpec(
        code="BCCD",
        name="Bachelor of Co-operative and Community Development",
        department_code="CCD",
        duration_years=4,
    ),
    "BCD": CourseSpec(
        code="BCD",
        name="Bachelor of Community Development",
        department_code="CCD",
        duration_years=4,
    ),
    "BCHM": CourseSpec(
        code="BCHM",
        name="Bachelor of Catering and Hospitality Management",
        department_code="BE",
        duration_years=4,
    ),
    "BCOB": CourseSpec(
        code="BCOB",
        name="Bachelor of Co-operative Business",
        department_code="CCD",
        duration_years=4,
        aliases=("BCB",),
    ),
    "BCOM": CourseSpec(
        code="BCOM",
        name="Bachelor of Commerce",
        department_code="BE",
        duration_years=4,
    ),
    "BCS": CourseSpec(
        code="BCS",
        name="Bachelor of Science in Computer Science",
        department_code="CS",
        duration_years=4,
        aliases=("BCSC",),
    ),
    "BDAT": CourseSpec(
        code="BDAT",
        name="Bachelor of Science in Data Science",
        department_code="MDS",
        duration_years=4,
        aliases=("BDSC",),
    ),
    "BDRM": CourseSpec(
        code="BDRM",
        name="Bachelor of Science in Disaster Risk Management and Sustainable Development",
        department_code="ESD",
        duration_years=4,
        aliases=("BSDRMSD",),
    ),
    "BDS": CourseSpec(
        code="BDS",
        name="Bachelor of Development Studies",
        department_code="CCD",
        duration_years=4,
    ),
    "BECO": CourseSpec(
        code="BECO",
        name="Bachelor of Science in Economics",
        department_code="BE",
        duration_years=4,
        aliases=("BECON",),
    ),
    "BEEP": CourseSpec(
        code="BEEP",
        name="Bachelor of Science in Environmental Economics and Policy",
        department_code="ESD",
        duration_years=4,
        aliases=("BSEEP",),
    ),
    "BELSI": CourseSpec(
        code="BELSI",
        name="Bachelor of Science in Environment, Lands and Sustainable Infrastructure",
        department_code="ESD",
        duration_years=4,
        aliases=("BSELSI",),
    ),
    "BEP": CourseSpec(
        code="BEP",
        name="Bachelor of Entrepreneurship",
        department_code="BE",
        duration_years=4,
    ),
    "BHRM": CourseSpec(
        code="BHRM",
        name="Bachelor of Human Resource Management",
        department_code="BE",
        duration_years=4,
    ),
    "BIT": CourseSpec(
        code="BIT",
        name="Bachelor of Science in Information Technology",
        department_code="CS",
        duration_years=4,
        aliases=("BCIT",),
    ),
    "BMIT": CourseSpec(
        code="BMIT",
        name="Bachelor of Science in Marketing, Innovation and Technology",
        department_code="BE",
        duration_years=4,
    ),
    "BNCS": CourseSpec(
        code="BNCS",
        name="Bachelor of Science in Network Engineering and Cyber Security",
        department_code="CS",
        duration_years=4,
        aliases=("BSNECS",),
    ),
    "BPRA": CourseSpec(
        code="BPRA",
        name="Bachelor of Public Relations and Advertising",
        department_code="BE",
        duration_years=4,
    ),
    "BPSM": CourseSpec(
        code="BPSM",
        name="Bachelor of Purchasing and Supplies Management",
        department_code="BE",
        duration_years=4,
    ),
    "BSA": CourseSpec(
        code="BSA",
        name="Bachelor of Science in Accountancy",
        department_code="BE",
        duration_years=4,
    ),
    "BSAS": CourseSpec(
        code="BSAS",
        name="Bachelor of Science in Actuarial Science",
        department_code="MDS",
        duration_years=4,
        aliases=("BACT",),
    ),
    "BSCAS": CourseSpec(
        code="BSCAS",
        name="Bachelor of Science in Applied Statistics",
        department_code="MDS",
        duration_years=4,
        aliases=("BSTA",),
    ),
    "BSET": CourseSpec(
        code="BSET",
        name="Bachelor of Science in Environmental Science and Technology",
        department_code="ESD",
        duration_years=4,
        aliases=("BSEST",),
    ),
    "BSIT": CourseSpec(
        code="BSIT",
        name="Bachelor of Statistics and Information Technology",
        department_code="MDS",
        duration_years=4,
    ),
    "BSSE": CourseSpec(
        code="BSSE",
        name="Bachelor of Science in Software Engineering",
        department_code="CS",
        duration_years=4,
    ),
    "BSc.AM": CourseSpec(
        code="BSc.AM",
        name="Bachelor of Science in Agribusiness Management",
        department_code="CCD",
        duration_years=4,
        aliases=("BSABM",),
    ),
    "BSc.Fin": CourseSpec(
        code="BSc.Fin",
        name="Bachelor of Science in Finance",
        department_code="BE",
        duration_years=4,
        aliases=("BFIN",),
    ),
    "BTM": CourseSpec(
        code="BTM",
        name="Bachelor of Tourism and Travel Management",
        department_code="BE",
        duration_years=4,
    ),
    "CBM": CourseSpec(
        code="CBM",
        name="Certificate in Business Management",
        department_code="BE",
        duration_years=1,
    ),
    "CPS": CourseSpec(
        code="CPS",
        name="Certificate in Purchasing and Supplies Management",
        department_code="BE",
        duration_years=1,
    ),
    "DAF": CourseSpec(
        code="DAF",
        name="Diploma in Accounting and Finance",
        department_code="BE",
        duration_years=2,
        aliases=("DACC",),
    ),
    "DBA": CourseSpec(
        code="DBA",
        name="Diploma in Business Administration",
        department_code="BE",
        duration_years=2,
    ),
    "DBF": CourseSpec(
        code="DBF",
        name="Diploma in Banking and Finance",
        department_code="BE",
        duration_years=2,
    ),
    "DBM": CourseSpec(
        code="DBM",
        name="Diploma in Business Management",
        department_code="BE",
        duration_years=2,
    ),
    "DCAM": CourseSpec(
        code="DCAM",
        name="Diploma in Housekeeping Management",
        department_code="BE",
        duration_years=2,
    ),
    "DCD": CourseSpec(
        code="DCD",
        name="Diploma in Community Development",
        department_code="CCD",
        duration_years=2,
    ),
    "DCHM": CourseSpec(
        code="DCHM",
        name="Diploma in Catering and Hotel Management",
        department_code="BE",
        duration_years=2,
    ),
    "DCM": CourseSpec(
        code="DCM",
        name="Diploma in Co-operative Management",
        department_code="CCD",
        duration_years=2,
    ),
    "DCP": CourseSpec(
        code="DCP",
        name="Diploma in Computer Programming",
        department_code="CS",
        duration_years=2,
    ),
    "DCS": CourseSpec(
        code="DCS",
        name="Diploma in Computer Science",
        department_code="CS",
        duration_years=2,
    ),
    "DCY": CourseSpec(
        code="DCY",
        name="Diploma in Cyber Security",
        department_code="CS",
        duration_years=2,
    ),
    "DHRM": CourseSpec(
        code="DHRM",
        name="Diploma in Human Resource Management",
        department_code="BE",
        duration_years=2,
    ),
    "DIT": CourseSpec(
        code="DIT",
        name="Diploma in Information Technology",
        department_code="CS",
        duration_years=2,
    ),
    "DPM": CourseSpec(
        code="DPM",
        name="Diploma in Project Management",
        department_code="BE",
        duration_years=2,
    ),
    "DPSM": CourseSpec(
        code="DPSM",
        name="Diploma in Purchasing and Supplies Management",
        department_code="BE",
        duration_years=2,
    ),
    "DSW": CourseSpec(
        code="DSW",
        name="Diploma in Social Work and Community Development",
        department_code="CCD",
        duration_years=2,
        aliases=("DCDSW",),
    ),
    "DTM": CourseSpec(
        code="DTM",
        name="Diploma in Tourism Management",
        department_code="BE",
        duration_years=2,
    ),
}


def clean_text(text: str) -> str:
    return " ".join(text.replace("\x0c", " ").split())


def normalize_course_label(label: str) -> str:
    normalized = clean_text(label)
    normalized = normalized.replace("YIS", "Y1S").replace("YI S", "Y1 S")
    normalized = re.sub(r"\bYI\b", "Y1", normalized)
    normalized = re.sub(r"([A-Za-z.]+)Y(\d)", r"\1 Y\2", normalized)
    normalized = normalized.replace(".S", " S")
    normalized = normalized.replace(" S1(SSP)", " S1 (SSP)")
    normalized = normalized.replace("S1(SSP)", "S1 (SSP)")
    return clean_text(normalized)


def looks_like_course_label(text: str) -> bool:
    normalized = normalize_course_label(text)
    if normalized in {"(SSP)", "S1 (SSP)", "S2 (SSP)", "SSP"}:
        return True
    return bool(
        re.search(r"(?:\bY\d\s*S\d\b|\bY\dS\d\b|\b\d\.\d\b)", normalized)
    )


def parse_course_label(label: str) -> tuple[str, int, str] | None:
    normalized = normalize_course_label(label)
    patterns = (
        re.compile(
            r"^(?P<code>.+?)\s+Y(?P<year>\d)\s*S(?P<semester>\d)(?:\s*\([^)]*\))?$"
        ),
        re.compile(
            r"^(?P<code>.+?)\s+Y(?P<year>\d)S(?P<semester>\d)(?:\s*\([^)]*\))?$"
        ),
        re.compile(
            r"^(?P<code>.+?)\s+(?P<year>\d)\.(?P<semester>\d)(?:\s*\([^)]*\))?$"
        ),
    )
    for pattern in patterns:
        match = pattern.match(normalized)
        if match:
            return (
                clean_text(match.group("code")),
                int(match.group("year")),
                str(int(match.group("semester"))),
            )
    return None


def _is_day_row(line: str) -> bool:
    return line.lstrip("\x0c").startswith(WEEKDAYS)


def _extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        completed = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "pdftotext is required to import timetable PDFs in this environment."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"pdftotext failed: {exc.stderr.strip()}") from exc
    return completed.stdout


def _resolve_unit_rows(text: str) -> list[ParsedTimetableRow]:
    rows: list[dict[str, str]] = []
    pending_course: list[str] = []
    pending_name: list[str] = []
    current: dict[str, str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n").rstrip("\r")
        stripped = clean_text(line)
        if (
            not stripped
            or "CUK is ISO" in stripped
            or stripped in {"UNDERGRADUATE", "POSTGRADUATE", "DIPLOMA", "CERTIFICATE"}
            or stripped.isdigit()
            or stripped.startswith("DAY ")
            or stripped.startswith("Prepared By")
            or stripped.startswith("University Timetabler")
            or stripped == "17.12.2025"
        ):
            continue

        if _is_day_row(line):
            if current:
                rows.append(current)

            parts = [
                clean_text(part)
                for part in re.split(r"\s{2,}", line.lstrip("\x0c").strip())
                if clean_text(part)
            ]
            rest = parts[3:]
            course_label = ""
            unit_code = ""
            unit_name = ""

            if rest:
                if looks_like_course_label(rest[0]) or not UNIT_CODE_RE.match(rest[0]):
                    course_label = normalize_course_label(rest.pop(0))
                elif pending_course:
                    course_label = normalize_course_label(" ".join(pending_course))
                    pending_course.clear()

            if not course_label and pending_course:
                course_label = normalize_course_label(" ".join(pending_course))
                pending_course.clear()

            if rest:
                if UNIT_CODE_RE.match(rest[0]):
                    unit_code = rest.pop(0)
                elif (
                    len(rest) >= 2
                    and not ONLY_DIGITS_RE.match(rest[0])
                    and ONLY_DIGITS_RE.match(rest[1])
                ):
                    unit_code = f"{rest.pop(0)} {rest.pop(0)}"
                elif (
                    len(rest) >= 2
                    and re.match(r"^[A-Z/]+$", rest[0])
                    and re.match(r"^[0-9A-Z/.-]+$", rest[1])
                ):
                    unit_code = f"{rest.pop(0)} {rest.pop(0)}"

            if rest and not ONLY_DIGITS_RE.match(rest[0]):
                unit_name = rest.pop(0)

            if pending_name and not unit_name:
                unit_name = clean_text(" ".join(pending_name))
                pending_name.clear()

            current = {
                "course_label": course_label,
                "unit_code": clean_text(unit_code),
                "unit_name": clean_text(unit_name),
                "source_line": stripped,
            }
            continue

        normalized = normalize_course_label(stripped)
        if looks_like_course_label(normalized):
            if current and (normalized.startswith("(") or "SSP" in normalized):
                current["course_label"] = clean_text(
                    f"{current['course_label']} {normalized}"
                )
            else:
                pending_course.append(normalized)
            continue

        if current and (not current["unit_name"] or len(current["unit_name"]) < 8):
            current["unit_name"] = clean_text(f"{current['unit_name']} {stripped}")
        else:
            pending_name.append(stripped)

    if current:
        rows.append(current)

    parsed_rows: list[ParsedTimetableRow] = []
    for row in rows:
        parsed_label = parse_course_label(row["course_label"])
        if not parsed_label or not row["unit_code"]:
            continue
        course_code, year_of_study, semester = parsed_label
        parsed_rows.append(
            ParsedTimetableRow(
                course_label=row["course_label"],
                course_code=course_code,
                year_of_study=year_of_study,
                semester=semester,
                unit_code=row["unit_code"],
                unit_name=row["unit_name"],
                source_line=row["source_line"],
                ssp_variant="SSP" in row["course_label"].upper(),
            )
        )
    return parsed_rows


def _choose_preferred_row(rows: list[ParsedTimetableRow]) -> ParsedTimetableRow:
    if len(rows) == 1:
        return rows[0]

    non_ssp_rows = [row for row in rows if not row.ssp_variant]
    candidates = non_ssp_rows or rows
    name_counts = Counter(row.unit_name for row in candidates)
    preferred_name = max(
        name_counts,
        key=lambda name: (name_counts[name], len(name)),
    )
    for row in candidates:
        if row.unit_name == preferred_name:
            return row
    return candidates[0]


def cluster_timetable_rows(rows: list[ParsedTimetableRow]) -> tuple[list[ParsedTimetableRow], list[str]]:
    grouped: dict[tuple[str, int, str, str], list[ParsedTimetableRow]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                row.course_code,
                row.year_of_study,
                row.semester,
                row.unit_code,
            )
        ].append(row)

    clustered: list[ParsedTimetableRow] = []
    warnings: list[str] = []

    for key, candidates in grouped.items():
        selected = _choose_preferred_row(candidates)
        names = {candidate.unit_name for candidate in candidates}
        if len(names) > 1:
            warnings.append(
                f"{selected.course_code} Y{selected.year_of_study}S{selected.semester} "
                f"{selected.unit_code}: multiple titles found {sorted(names)}. "
                f"Using '{selected.unit_name}'."
            )
        clustered.append(selected)

    clustered.sort(
        key=lambda row: (
            row.course_code,
            row.year_of_study,
            row.semester,
            row.unit_code,
        )
    )
    return clustered, warnings


def parse_timetable_pdf(pdf_path: str | Path) -> tuple[list[ParsedTimetableRow], list[str]]:
    path = Path(pdf_path)
    text = _extract_text_from_pdf(path)
    rows = _resolve_unit_rows(text)
    clustered_rows, warnings = cluster_timetable_rows(rows)
    return clustered_rows, warnings


def _upsert_faculty(spec: FacultySpec, report: TimetableImportReport) -> Faculty:
    faculty, created = Faculty.objects.get_or_create(
        code=spec.code,
        defaults={
            "name": spec.name,
            "description": spec.description,
            "is_active": True,
        },
    )
    changed = created
    if faculty.name != spec.name:
        faculty.name = spec.name
        changed = True
    if faculty.description != spec.description:
        faculty.description = spec.description
        changed = True
    if not faculty.is_active:
        faculty.is_active = True
        changed = True
    if changed and not created:
        faculty.save(update_fields=["name", "description", "is_active"])
        report.faculties_updated += 1
    elif created:
        report.faculties_created += 1
    return faculty


def _upsert_department(
    spec: DepartmentSpec,
    faculties_by_code: dict[str, Faculty],
    report: TimetableImportReport,
) -> Department:
    department, created = Department.objects.get_or_create(
        faculty=faculties_by_code[spec.faculty_code],
        code=spec.code,
        defaults={
            "name": spec.name,
            "description": spec.description,
            "is_active": True,
        },
    )
    changed = created
    if department.name != spec.name:
        department.name = spec.name
        changed = True
    if department.description != spec.description:
        department.description = spec.description
        changed = True
    if not department.is_active:
        department.is_active = True
        changed = True
    if changed and not created:
        department.save(update_fields=["name", "description", "is_active"])
        report.departments_updated += 1
    elif created:
        report.departments_created += 1
    return department


def _find_course_candidate(spec: CourseSpec) -> Course | None:
    lookup_codes = [spec.code, *spec.aliases]
    course = (
        Course.objects.filter(code=spec.code)
        .select_related("department__faculty")
        .first()
    )
    if course:
        return course
    return (
        Course.objects.filter(code__in=lookup_codes)
        .select_related("department__faculty")
        .order_by("id")
        .first()
    )


def _upsert_course(
    spec: CourseSpec,
    departments_by_code: dict[str, Department],
    report: TimetableImportReport,
) -> Course:
    course = _find_course_candidate(spec)
    created = False
    code_changed = False
    if course is None:
        course = Course(
            code=spec.code,
            department=departments_by_code[spec.department_code],
        )
        created = True

    changed = created
    if course.code != spec.code:
        course.code = spec.code
        course.slug = ""
        code_changed = True
        changed = True
    if course.name != spec.name:
        course.name = spec.name
        changed = True
    target_department = departments_by_code[spec.department_code]
    if course.department_id != target_department.id:
        course.department = target_department
        changed = True
    if course.duration_years != spec.duration_years:
        course.duration_years = spec.duration_years
        changed = True
    if not course.is_active:
        course.is_active = True
        changed = True

    if created:
        course.save()
        report.courses_created += 1
    elif changed:
        if code_changed:
            course.save()
        else:
            course.save(
                update_fields=[
                    "code",
                    "name",
                    "department",
                    "duration_years",
                    "is_active",
                ]
            )
        report.courses_updated += 1
    course._slug_needs_refresh = code_changed
    return course


def _upsert_unit(course: Course, row: ParsedTimetableRow, report: TimetableImportReport) -> Unit:
    unit, created = Unit.objects.get_or_create(
        course=course,
        code=row.unit_code,
        semester=row.semester,
        defaults={
            "name": row.unit_name,
            "year_of_study": row.year_of_study,
            "is_active": True,
        },
    )
    changed = created
    slug_needs_refresh = bool(getattr(course, "_slug_needs_refresh", False))
    if unit.name != row.unit_name:
        unit.name = row.unit_name
        changed = True
    if unit.year_of_study != row.year_of_study:
        unit.year_of_study = row.year_of_study
        changed = True
    if not unit.is_active:
        unit.is_active = True
        changed = True
    if slug_needs_refresh:
        unit.slug = ""
        changed = True

    if created:
        unit.save()
        report.units_created += 1
    elif changed:
        if slug_needs_refresh:
            unit.save()
        else:
            unit.save(update_fields=["name", "year_of_study", "is_active"])
        report.units_updated += 1
    return unit


def import_timetable_pdf(
    pdf_path: str | Path,
    *,
    dry_run: bool = False,
) -> TimetableImportReport:
    report = TimetableImportReport()
    clustered_rows, warnings = parse_timetable_pdf(pdf_path)
    report.parsed_rows = len(clustered_rows)
    report.clustered_units = len(clustered_rows)
    report.warnings.extend(warnings)

    unknown_courses = sorted(
        {
            row.course_code
            for row in clustered_rows
            if row.course_code not in COURSE_SPECS
        }
    )
    if unknown_courses:
        raise RuntimeError(
            "Unsupported timetable course codes: " + ", ".join(unknown_courses)
        )

    if dry_run:
        return report

    faculties_by_code = {
        code: _upsert_faculty(spec, report)
        for code, spec in FACULTY_SPECS.items()
    }
    departments_by_code = {
        code: _upsert_department(spec, faculties_by_code, report)
        for code, spec in DEPARTMENT_SPECS.items()
    }

    courses_by_code: dict[str, Course] = {}
    for code in sorted({row.course_code for row in clustered_rows}):
        courses_by_code[code] = _upsert_course(
            COURSE_SPECS[code],
            departments_by_code,
            report,
        )

    for row in clustered_rows:
        _upsert_unit(courses_by_code[row.course_code], row, report)

    return report


def preview_timetable_pdf(pdf_path: str | Path) -> TimetableImportReport:
    report = TimetableImportReport()
    clustered_rows, warnings = parse_timetable_pdf(pdf_path)
    report.parsed_rows = len(clustered_rows)
    report.clustered_units = len(clustered_rows)
    report.warnings.extend(warnings)
    return report
