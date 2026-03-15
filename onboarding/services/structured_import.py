"""
Structured data onboarding: import project metadata and payment plans from CSV.
Column mapping similar to CRM: flexible, tolerant of naming variations.
"""
import csv
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from onboarding.models import OnboardingBatch, OnboardingItem, OnboardingBatchType, OnboardingItemStatus
from knowledge.models import Project, ProjectPaymentPlan
from core.enums import FactSource


# Column name variants for project CSV
PROJECT_COL_MAP = {
    "name": ["name", "project_name", "project", "title"],
    "name_ar": ["name_ar", "name_ar", "arabic_name"],
    "location": ["location", "area", "district", "region"],
    "price_min": ["price_min", "min_price", "price_from", "from_price"],
    "price_max": ["price_max", "max_price", "price_to", "to_price"],
    "availability_status": ["availability_status", "availability", "status"],
    "property_types": ["property_types", "property_type", "types"],
}

PAYMENT_COL_MAP = {
    "installment_years_min": ["installment_years_min", "years_min", "installment_years", "years"],
    "installment_years_max": ["installment_years_max", "years_max"],
    "down_payment_pct_min": ["down_payment_pct_min", "down_payment", "down_payment_pct", "down_payment_min"],
    "down_payment_pct_max": ["down_payment_pct_max", "down_payment_max"],
}


def _find_value(row: dict, col_map: dict[str, list[str]]) -> dict[str, str]:
    """Map row dict to standard keys using column variants."""
    result = {}
    for key, variants in col_map.items():
        for v in variants:
            if v in row and row[v] is not None and str(row[v]).strip():
                result[key] = str(row[v]).strip()
                break
    return result


def _parse_decimal(s: str) -> Decimal | None:
    if not s:
        return None
    s = s.replace(",", "").strip()
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _parse_int(s: str) -> int | None:
    if not s:
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _parse_json_list(s: str) -> list:
    """Parse property_types: comma-separated or JSON-like."""
    if not s:
        return []
    s = s.strip().strip("[]")
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


@transaction.atomic
def import_structured_csv(
    file_path: str,
    company_id: int | None = None,
    created_by: str = "",
) -> OnboardingBatch:
    """
    Import project metadata from CSV. Creates/updates Project and ProjectPaymentPlan.
    Returns OnboardingBatch with summary.
    """
    batch = OnboardingBatch.objects.create(
        company_id=company_id,
        batch_type=OnboardingBatchType.STRUCTURED,
        status="in_progress",
        created_by=created_by,
    )
    imported = skipped = failed = 0

    try:
        with open(file_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        batch.status = "completed"
        batch.failed_count = 1
        batch.total_count = 1
        batch.save()
        OnboardingItem.objects.create(
            batch=batch,
            item_type="structured_row",
            source_name=Path(file_path).name,
            status=OnboardingItemStatus.FAILED,
            error_message=str(e)[:500],
        )
        return batch

    for i, row in enumerate(rows):
        source_name = f"Row {i + 2}"  # 1-indexed + header
        mapped = _find_value(row, {**PROJECT_COL_MAP, **PAYMENT_COL_MAP})
        name = mapped.get("name") or _find_value(row, {"name": ["name", "project_name", "project"]}).get("name")
        if not name or not str(name).strip():
            OnboardingItem.objects.create(
                batch=batch,
                item_type="structured_row",
                source_name=source_name,
                status=OnboardingItemStatus.SKIPPED,
                error_message="Missing project name",
            )
            skipped += 1
            continue

        try:
            project, created = Project.objects.get_or_create(
                name=name.strip(),
                company_id=company_id,
                defaults={
                    "name_ar": mapped.get("name_ar", ""),
                    "location": mapped.get("location", ""),
                    "price_min": _parse_decimal(mapped.get("price_min", "")),
                    "price_max": _parse_decimal(mapped.get("price_max", "")),
                    "availability_status": mapped.get("availability_status", ""),
                    "property_types": _parse_json_list(mapped.get("property_types", "")),
                    "pricing_source": FactSource.CSV_IMPORT,
                    "availability_source": FactSource.CSV_IMPORT,
                    "last_verified_at": timezone.now(),
                },
            )
            if not created:
                project.name_ar = mapped.get("name_ar") or project.name_ar
                project.location = mapped.get("location") or project.location
                if mapped.get("price_min"):
                    project.price_min = _parse_decimal(mapped["price_min"])
                if mapped.get("price_max"):
                    project.price_max = _parse_decimal(mapped["price_max"])
                if mapped.get("availability_status"):
                    project.availability_status = mapped["availability_status"]
                if mapped.get("property_types"):
                    project.property_types = _parse_json_list(mapped["property_types"])
                project.pricing_source = FactSource.CSV_IMPORT
                project.last_verified_at = timezone.now()
                project.save()

            # Payment plan if columns present
            y_min = _parse_int(mapped.get("installment_years_min", ""))
            y_max = _parse_int(mapped.get("installment_years_max", ""))
            dp_min = _parse_decimal(mapped.get("down_payment_pct_min", ""))
            dp_max = _parse_decimal(mapped.get("down_payment_pct_max", ""))
            if y_min is not None or y_max is not None or dp_min is not None or dp_max is not None:
                ProjectPaymentPlan.objects.update_or_create(
                    project=project,
                    defaults={
                        "installment_years_min": y_min,
                        "installment_years_max": y_max or y_min,
                        "down_payment_pct_min": dp_min,
                        "down_payment_pct_max": dp_max or dp_min,
                        "source": FactSource.CSV_IMPORT,
                        "last_verified_at": timezone.now(),
                    },
                )

            OnboardingItem.objects.create(
                batch=batch,
                item_type="structured_row",
                source_name=source_name,
                status=OnboardingItemStatus.SUCCESS,
                project_id=project.id,
            )
            imported += 1

        except Exception as e:
            OnboardingItem.objects.create(
                batch=batch,
                item_type="structured_row",
                source_name=source_name,
                status=OnboardingItemStatus.FAILED,
                error_message=str(e)[:500],
            )
            failed += 1

    batch.imported_count = imported
    batch.skipped_count = skipped
    batch.failed_count = failed
    batch.total_count = imported + skipped + failed
    batch.status = "completed" if failed == 0 else ("partial" if imported > 0 else "completed")
    batch.save()

    return batch
