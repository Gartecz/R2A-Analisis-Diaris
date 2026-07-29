import datetime
import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT_PATTERN = re.compile(
    r"^analisis/(?P<year>\d{4})/(?P<month>\d{2})/(?P<date>\d{4}-\d{2}-\d{2})\.json$"
)
STATUSES = {"normal", "watch", "alert", "insufficient_data"}


def fail(path: pathlib.Path, message: str) -> None:
    print(f"{path.relative_to(ROOT)}: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate(path: pathlib.Path) -> None:
    relative = path.relative_to(ROOT).as_posix()
    match = REPORT_PATTERN.fullmatch(relative)
    if not match:
        fail(path, "ruta no vàlida")

    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(path, f"JSON no vàlid: {error}")

    required = {
        "schema_version",
        "date",
        "generated_at",
        "bot",
        "status",
        "summary",
        "data_freshness",
        "metrics",
        "assessment",
        "alerts",
        "sources",
    }
    if set(report) != required:
        fail(path, f"claus esperades: {sorted(required)}")
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
    if report["status"] not in STATUSES:
        fail(path, "estat desconegut")
    if not isinstance(report["summary"], str) or not report["summary"].strip():
        fail(path, "resum buit")
    if not isinstance(report["alerts"], list) or not all(isinstance(item, str) for item in report["alerts"]):
        fail(path, "alertes no vàlides")
    if not isinstance(report["sources"], list) or not report["sources"]:
        fail(path, "cal indicar almenys una font")


def main() -> None:
    reports = sorted((ROOT / "analisis").glob("*/*/*.json"))
    for report in reports:
        validate(report)
    print(f"{len(reports)} informe(s) validat(s).")


if __name__ == "__main__":
    main()
