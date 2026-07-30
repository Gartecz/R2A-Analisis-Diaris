import datetime
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
ANALYSES = ROOT / "analisis"
WEEKLY = ROOT / "setmanals"
SOURCE_URL = "https://github.com/Gartecz/R2A-Analisis-Diaris"


def load_daily_reports(start: datetime.date, end: datetime.date) -> list[dict]:
    reports: list[dict] = []
    current = start
    while current <= end:
        path = ANALYSES / f"{current:%Y}" / f"{current:%m}" / f"{current.isoformat()}.json"
        if path.exists():
            try:
                reports.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError as error:
                raise RuntimeError(f"Informe diari invàlid: {path}: {error}") from error
        current += datetime.timedelta(days=1)
    return reports


def number_sum(reports: list[dict], key: str) -> float | None:
    values = [report["metrics"].get(key) for report in reports]
    if any(value is None for value in values):
        return None
    return round(sum(values), 2)


def integer_sum(reports: list[dict], key: str) -> int | None:
    values = [report["metrics"].get(key) for report in reports]
    if any(value is None for value in values):
        return None
    return sum(values)


def worst_floating(reports: list[dict]) -> float | None:
    values = [report["metrics"].get("worst_floating_day") for report in reports]
    numeric = [value for value in values if value is not None]
    return min(numeric) if numeric else None


def status_for(reports: list[dict], expected: int) -> str:
    statuses = {report.get("status") for report in reports}
    if "alert" in statuses:
        return "alert"
    if len(reports) < expected:
        return "insufficient_data"
    if "watch" in statuses or "insufficient_data" in statuses:
        return "watch"
    return "normal"


def build_report(today: datetime.date) -> tuple[pathlib.Path, dict]:
    monday = today - datetime.timedelta(days=today.weekday())
    friday = monday + datetime.timedelta(days=4)
    end = min(today, friday)
    expected = (end - monday).days + 1
    reports = load_daily_reports(monday, end)
    weekly_pnl = number_sum(reports, "daily_pnl")
    wins = integer_sum(reports, "wins")
    losses = integer_sum(reports, "losses")
    operations = integer_sum(reports, "closed_operations")
    win_rate = None
    if wins is not None and losses is not None and wins + losses > 0:
        win_rate = round(wins * 100 / (wins + losses), 2)

    status = status_for(reports, expected)
    missing = expected - len(reports)
    period = f"{monday:%d/%m}–{end:%d/%m}"
    summary = f"Resum automàtic verificat del {period}: {len(reports)}/{expected} informes diaris disponibles."
    alerts: list[str] = []
    if missing:
        alerts.append(f"Falten {missing} informe(s) diari(s) del període; el resum setmanal és parcial.")
    if any(report.get("status") in {"watch", "alert", "insufficient_data"} for report in reports):
        alerts.append("Hi ha almenys un informe diari amb estat de vigilància, alerta o dades insuficients.")

    last_metrics = reports[-1]["metrics"] if reports else {}
    report = {
        "schema_version": 1,
        "week": f"{today.isocalendar().year}-W{today.isocalendar().week:02d}",
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
        "bot": "R2-A",
        "status": status,
        "summary": summary,
        "coverage": {
            "start_date": monday.isoformat(),
            "end_date": end.isoformat(),
            "expected_daily_reports": expected,
            "available_daily_reports": len(reports),
        },
        "metrics": {
            "weekly_pnl": weekly_pnl,
            "closed_operations": operations,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": win_rate,
            "worst_floating": worst_floating(reports),
            "last_balance": last_metrics.get("balance"),
            "last_equity": last_metrics.get("equity"),
        },
        "assessment": {
            "performance": "El P&L setmanal és la suma dels informes diaris disponibles. No s'estima cap dia absent.",
            "risk": "El pitjor floating és el mínim registrat als informes disponibles; no representa mètriques no publicades.",
            "execution": "La qualitat de les dades depèn de la cobertura indicada. Les dades diàries antigues o absents es mantenen com a limitació explícita.",
            "conclusion": "Informe agregat automàticament a partir dels informes diaris validats, sense enviar ordres ni modificar MT5.",
        },
        "alerts": alerts,
        "sources": [SOURCE_URL],
    }
    path = WEEKLY / f"{today.isocalendar().year}" / f"{report['week']}.json"
    return path, report


def main() -> None:
    today = datetime.date.today()
    if len(sys.argv) == 2:
        today = datetime.date.fromisoformat(sys.argv[1])
    path, report = build_report(today)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
