from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook

from app.models.lead import Lead

REPORT_COLUMNS = [
    "Run Date",
    "Captured At",
    "Source",
    "Platform",
    "Link",
    "Author",
    "Competitor",
    "Pain Category",
    "Pain Point",
    "Recency",
    "Intent",
    "Suggested Hook",
    "Suggested Reply",
    "Status",
    "Reviewed By",
    "Reviewed At",
    "Posted At",
]


class ReportExporter:
    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _fmt_datetime(value: datetime | None) -> str:
        if not value:
            return ""
        return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    def _write_rows(self, sheet, leads: list[Lead], report_date: date) -> None:
        for lead in leads:
            pain_point = ", ".join(lead.detected_pain_points) if lead.detected_pain_points else "Unspecified"
            sheet.append(
                [
                    report_date.isoformat(),
                    self._fmt_datetime(lead.created_at),
                    lead.source,
                    lead.platform or "",
                    lead.source_url,
                    lead.author or "",
                    lead.competitor,
                    lead.pain_category or "",
                    pain_point,
                    lead.recency_signal or "",
                    lead.intent_label.value,
                    lead.suggested_hook or "",
                    lead.suggested_reply,
                    lead.response_status.value.upper(),
                    lead.reviewed_by or "",
                    self._fmt_datetime(lead.reviewed_at),
                    self._fmt_datetime(lead.posted_at),
                ]
            )

    def export_new_leads_excel(self, leads: list[Lead], report_date: date) -> Path:
        file_path = self.output_dir / f"new_leads_{report_date.isoformat()}.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "New Leads"
        sheet.append(REPORT_COLUMNS)
        self._write_rows(sheet, leads, report_date)
        workbook.save(file_path)
        return file_path

    def export_all_leads_excel(self, leads: list[Lead], report_date: date) -> Path:
        file_path = self.output_dir / "all_leads_master.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "All Leads"
        sheet.append(REPORT_COLUMNS)
        self._write_rows(sheet, leads, report_date)
        workbook.save(file_path)
        return file_path
