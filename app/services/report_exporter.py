from datetime import date
from pathlib import Path

from openpyxl import Workbook

from app.models.lead import Lead

REPORT_COLUMNS = ["Date", "Source", "Link", "Competitor", "Pain Point", "Intent", "Suggested Reply", "Status"]


class ReportExporter:
    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_daily_excel(self, leads: list[Lead], report_date: date) -> Path:
        file_path = self.output_dir / f"lead_report_{report_date.isoformat()}.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Daily Leads"
        sheet.append(REPORT_COLUMNS)

        for lead in leads:
            pain_point = ", ".join(lead.detected_pain_points) if lead.detected_pain_points else "Unspecified"
            sheet.append(
                [
                    report_date.isoformat(),
                    lead.source,
                    lead.source_url,
                    lead.competitor,
                    pain_point,
                    lead.intent_label.value,
                    lead.suggested_reply,
                    "New",
                ]
            )

        workbook.save(file_path)
        return file_path
