import datetime
import json
import pathlib
import re
import sys

from jsonschema import Draft202012Validator, FormatChecker


ROOT = pathlib.Path(__file__).resolve().parents[1]
DAILY_SCHEMA = json.loads((ROOT / "schema" / "analysis.schema.json").read_text(encoding="utf-8"))
WEEKLY_SCHEMA = json.loads((ROOT / "schema" / "weekly-analysis.schema.json").read_text(encoding="utf-8"))
DAILY_VALIDATOR = Draft202012Validator(DAILY_SCHEMA, format_checker=FormatChecker())
WEEKLY_VALIDATOR = Draft202012Validator(WEEKLY_SCHEMA, format_checker=FormatChecker())
DAILY_PATH = re.compile(r"^analisis/(?P<year>\d{4})/(?P<month>\d{2})/(?P<date>\d{4}-\d{2}-\d{2})\.json$")
WEEKLY_PATH = re.compile(r"^setmanals/(?P<year>\d{4})/(?P<week>\d{4}-W\d{2})\.json$")
STATUSES = {"normal", "watch", "alert", "insufficient_data"}


def fail(path: pathlib.Path, message: str) -> None:
    print(f"{path.relative_to(ROOT)}: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_common(path: pathlib.Path, report: dict) -> None:
    if report["status"] not in STATUSES:
        fail(path, "estat desconegut")
    if not isinstance(report["summary"], str) or not report["summary"].strip():
        fail(path, "resum buit")
    if not isinstance(report["alerts"], list) or not all(isinstance(item, str) for item in report["alerts"]):
        fail(path, "alertes no vàlides")
    if not isinstance(report["sources"], list) or not report["sources"]:
        fail(path, "cal indicar almenys una font")


def validate_schema(path: pathlib.Path, report: dict, validator: Draft202012Validator, label: str) -> None:
    errors = sorted(validator.iter_errors(report), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "<arrel>"
        fail(path, f"esquema {label} no vàlid a {location}: {error.message}")


def validate_daily(path: pathlib.Path, report: dict, match: re.Match[str]) -> None:
    validate_schema(path, report, DAILY_VALIDATOR, "diari")
    expected = {"schema_version", "date", "generated_at", "bot", "status", "summary", "data_freshness", "metrics", "assessment", "alerts", "sources"}
    if set(report) != expected:
        fail(path, f"claus esperades: {sorted(expected)}")
    if report["schema_version"] != 1 or report["bot"] != "R2-A":
        fail(path, "versió o bot incorrecte")
    if report["date"] != match.group("date"):
        fail(path, "la data interna no coincideix amb el nom")
    if report["date"][:4] != match.group("year") or report["date"][5:7] != match.group("month"):
        fail(path, "la data no coincideix amb les carpetes")
    try:
        datetime.date.fromisoformat(report["date"])
        datetime.datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        fail(path, f"data no vàlida: {error}")
    validate_common(path, report)


def validate_weekly(path: pathlib.Path, report: dict, match: re.Match[str]) -> None:
    validate_schema(path, report, WEEKLY_VALIDATOR, "setmanal")
    expected = {"schema_version", "week", "generated_at", "bot", "status", "summary", "coverage", "metrics", "assessment", "alerts", "sources"}
    if set(report) != expected:
        fail(path, f"claus esperades: {sorted(expected)}")
    if report["schema_version"] != 1 or report["bot"] != "R2-A":
        fail(path, "versió o bot incorrecte")
    if report["week"] != match.group("week") or report["week"][:4] != match.group("year"):
        fail(path, "la setmana interna no coincideix amb la ruta")
    try:
        report_year, report_week = report["week"].split("-W", 1)
        datetime.date.fromisocalendar(int(report_year), int(report_week), 1)
        datetime.datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        fail(path, f"setmana o data no vàlida: {error}")
    if report["coverage"]["available_daily_reports"] > report["coverage"]["expected_daily_reports"]:
        fail(path, "cobertura setmanal inconsistent")
    validate_common(path, report)


def validate(path: pathlib.Path) -> None:
    relative = path.relative_to(ROOT).as_posix()
    daily_match = DAILY_PATH.fullmatch(relative)
    weekly_match = WEEKLY_PATH.fullmatch(relative)
    if not daily_match and not weekly_match:
        fail(path, "ruta no vàlida")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(path, f"JSON no vàlid: {error}")
    if daily_match:
        validate_daily(path, report, daily_match)
    else:
        validate_weekly(path, report, weekly_match)


def main() -> None:
    reports = sorted((ROOT / "analisis").glob("*/*/*.json"))
    reports += sorted((ROOT / "setmanals").glob("*/*.json"))
    for report in reports:
        validate(report)
    print(f"{len(reports)} informe(s) validat(s).")


if __name__ == "__main__":
    main()
