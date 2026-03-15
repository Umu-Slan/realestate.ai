"""
Excel CRM adapter - reads first sheet as lead rows.
"""
from pathlib import Path
from typing import Iterator, Optional

from .base import BaseCRMAdapter, CRMLeadRow
from .csv_adapter import _find_value, _parse_datetime


class ExcelCRMAdapter(BaseCRMAdapter):
    """Excel file adapter. Uses first sheet, first row as headers."""

    def iter_leads(self, file_path: str, sheet_name: Optional[str] = None, **kwargs) -> Iterator[CRMLeadRow]:
        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl required for Excel import")
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheet = wb[sheet_name] if sheet_name else wb.active
        rows = list(sheet.iter_rows(values_only=True))
        wb.close()
        if len(rows) < 2:
            return
        headers = [str(h or "").strip() for h in rows[0]]
        for i, row in enumerate(rows[1:], start=2):
            d = {}
            for j, h in enumerate(headers):
                if not h:
                    continue
                val = row[j] if j < len(row) else None
                d[h] = str(val).strip() if val is not None else ""
            crm_id = _find_value(d, "crm_id") or f"excel_row_{i}"
            score_s = _find_value(d, "historical_score")
            try:
                score = int(score_s) if score_s else None
            except (ValueError, TypeError):
                score = None
            tags_s = _find_value(d, "tags")
            tags = [t.strip() for t in tags_s.split(",") if t.strip()] if tags_s else []
            yield CRMLeadRow(
                crm_id=crm_id,
                name=_find_value(d, "name"),
                phone=_find_value(d, "phone"),
                email=_find_value(d, "email"),
                username=_find_value(d, "username"),
                source=_find_value(d, "source"),
                campaign=_find_value(d, "campaign"),
                historical_classification=_find_value(d, "historical_classification"),
                historical_score=score,
                notes=_find_value(d, "notes"),
                project_interest=_find_value(d, "project_interest"),
                status=_find_value(d, "status"),
                crm_created_at=_parse_datetime(_find_value(d, "crm_created_at")),
                crm_updated_at=_parse_datetime(_find_value(d, "crm_updated_at")),
                raw=dict(zip(headers, row or [])),
                owner=_find_value(d, "owner"),
                lead_stage=_find_value(d, "lead_stage") or _find_value(d, "status"),
                tags=tags,
            )
