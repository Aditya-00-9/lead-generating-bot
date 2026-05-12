from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadReportRow


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert_from_leads(self, leads: list[Lead], report_date: date) -> list[LeadReportRow]:
        rows: list[LeadReportRow] = []
        for lead in leads:
            pain_point = ", ".join(lead.detected_pain_points) if lead.detected_pain_points else "Unspecified"
            row = LeadReportRow(
                date=report_date,
                source=lead.source,
                link=lead.source_url,
                competitor=lead.competitor,
                pain_point=pain_point,
                intent=lead.intent_label.value,
                suggested_reply=lead.suggested_reply,
                status="New",
            )
            self.session.add(row)
            rows.append(row)
        await self.session.commit()
        return rows
