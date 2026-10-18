from __future__ import annotations

import asyncio
import re
import shutil
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.db.models import Document, Organisation, Project
from app.schemas.intake import IntakeExtraction
from app.services.project_rules import normalize_deadline
from app.services.records_search import extract_pages


def extract_intake_pages(path: Path) -> list[tuple[int | None, str]]:
    suffix = path.suffix.lower()
    pages = [] if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"} else extract_pages(path)
    if suffix == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            pdfplumber = None
        if pdfplumber:
            with pdfplumber.open(path) as pdf:
                for index, page in enumerate(pdf.pages):
                    tables = page.extract_tables() or []
                    table_text = "\n".join(" | ".join(str(cell or "").strip() for cell in row) for table in tables for row in table)
                    if table_text.strip() and index < len(pages):
                        number, body = pages[index]
                        if table_text not in body:
                            pages[index] = (number, f"{body}\n\nExtracted table rows:\n{table_text}")
    if not any(text.strip() for _, text in pages):
        try:
            import pytesseract
            from PIL import Image
            from pypdfium2 import PdfDocument
        except ImportError as exc:
            raise ValueError("This scanned document needs OCR. Install the optional OCR packages and Tesseract, then retry.") from exc
        if not shutil.which("tesseract"):
            raise ValueError("This scanned document needs OCR, but the Tesseract executable was not found.")
        if suffix == ".pdf":
            rendered = PdfDocument(str(path))
            pages = [(index + 1, pytesseract.image_to_string(page.render(scale=2).to_pil())) for index, page in enumerate(rendered)]
        elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}:
            pages = [(1, pytesseract.image_to_string(Image.open(path)))]
    return pages


def _normalized(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.casefold(), flags=re.UNICODE).strip()


def _mobilization_date(pages: list[tuple[int | None, str]]):
    text = " ".join(body for _, body in pages)
    patterns = (
        r"(?:contractor\s+)?mobilization(?:\s+(?:target|date))?\s*(?:is|on|of|:)?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
        r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+(?:is\s+the\s+)?(?:target\s+date\s+for\s+)?(?:contractor\s+)?mobilization",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return datetime.strptime(match.group(1), "%d %B %Y").date()
            except ValueError:
                try:
                    return datetime.strptime(match.group(1), "%d %b %Y").date()
                except ValueError:
                    pass
    return None


def quote_is_supported(quote: str, pages: list[tuple[int | None, str]]) -> bool:
    target = _normalized(quote)
    if len(target) < 8:
        return False
    for _, text in pages:
        source = _normalized(text)
        if target in source:
            return True
        # Compare compact sliding windows so a copied quote can survive line wraps and PDF spacing.
        words = source.split()
        target_words = target.split()
        width = len(target_words)
        for start in range(max(0, len(words) - width - 3)):
            candidate = " ".join(words[start : start + width + 3])
            if SequenceMatcher(None, target, candidate).ratio() >= 0.86:
                return True
    return False


def _alias_match(value: str | None, rows: list, *, fields: tuple[str, ...]) -> str | None:
    if not value:
        return None
    needle = _normalized(value)
    for row in rows:
        aliases = [getattr(row, field, None) for field in fields]
        for alias in aliases:
            for candidate in ([alias] if isinstance(alias, str) else alias or []):
                normalized = _normalized(candidate or "")
                if normalized and (normalized in needle or needle in normalized):
                    return row.name
    return None


def enrich_extraction(db: Session, result: IntakeExtraction, pages: list[tuple[int | None, str]]) -> tuple[IntakeExtraction, list[str]]:
    warnings: list[str] = []
    organisations = list(db.scalars(select(Organisation)))
    projects = list(db.scalars(select(Project)))
    mobilization_date = _mobilization_date(pages)
    if result.project_hint:
        result.project_hint = _alias_match(result.project_hint, projects, fields=("name", "aliases")) or result.project_hint
    for action in result.actions:
        action.quote_verified = quote_is_supported(action.source_quote, pages)
        action.owner_org = _alias_match(action.owner_org, organisations, fields=("name", "short_name", "aliases")) or action.owner_org
        action.project = _alias_match(action.project or result.project_hint, projects, fields=("name", "aliases")) or action.project or result.project_hint
        normalized = normalize_deadline(action.deadline_text, result.meeting_date, mobilization_date=mobilization_date) if result.meeting_date else None
        action.resolved_deadline = normalized.resolved_date if normalized else None
        action.deadline_precision = normalized.precision if normalized else "relative"
        action.needs_input = (not action.owner_org and not action.owner_person) or not action.deadline_text or (normalized.needs_input if normalized else True) or not action.project or not action.quote_verified
        if not action.quote_verified:
            warnings.append("An extracted action has a source quote that could not be verified.")
        if action.needs_input:
            warnings.append("An extracted action needs a reviewer to resolve its owner, project, or deadline.")
    for commitment in result.commitments:
        commitment.quote_verified = quote_is_supported(commitment.source_quote, pages)
        commitment.committed_by_org = _alias_match(commitment.committed_by_org, organisations, fields=("name", "short_name", "aliases")) or commitment.committed_by_org
        commitment.project = _alias_match(commitment.project or result.project_hint, projects, fields=("name", "aliases")) or commitment.project or result.project_hint
        normalized = normalize_deadline(commitment.due_text, result.meeting_date, mobilization_date=mobilization_date) if result.meeting_date else None
        commitment.resolved_due_date = normalized.resolved_date if normalized else None
        commitment.deadline_precision = normalized.precision if normalized else "relative"
        commitment.needs_input = not commitment.project or not commitment.due_text or (normalized.needs_input if normalized else True) or not commitment.quote_verified
        if not commitment.quote_verified:
            warnings.append("An extracted commitment has a source quote that could not be verified.")
        if commitment.needs_input:
            warnings.append("An extracted commitment needs a reviewer to resolve its project or due date.")
    return result, sorted(set(warnings))


async def extract_document(db: Session, *, document: Document, user_id: str) -> tuple[IntakeExtraction, list[str], str | None]:
    pages = extract_intake_pages(Path(document.file_path))
    text = "\n\n".join(f"[Page {number}]\n{body}" if number else body for number, body in pages)
    if not text.strip():
        raise ValueError("No readable text was found. Scanned PDFs require OCR support.")
    document.text_extracted = text
    prompt = (
        "Extract structured facts from this ministry document. Do not invent actions. Copy each source_quote verbatim "
        "from the supplied text, including action table rows. Preserve the original deadline words. Keep organization "
        "and project names as written. A person who merely presents information is not an action owner unless assigned. "
        "For non-minutes, classify and summarize with empty actions and commitments.\n\n" + text[:100000]
    )
    run_id: dict[str, str] = {}
    extracted = await AIGateway().chat(
        db, tool="document_extraction", role="extraction",
        messages=[{"role": "user", "content": prompt}],
        classification=document.classification, is_synthetic=document.is_synthetic,
        user_id=user_id, prompt_version="moitt-intake-v1", response_schema=IntakeExtraction,
        run_id_out=run_id, allow_confidential_cloud=document.cloud_ai_allowed,
    )
    assert isinstance(extracted, IntakeExtraction)
    enriched, warnings = enrich_extraction(db, extracted, pages)
    return enriched, warnings, run_id.get("run_id")
