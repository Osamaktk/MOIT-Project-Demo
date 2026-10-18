from collections.abc import Generator
from datetime import date, datetime, timezone
from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models import Action, Commitment, Document, IntakeReview, Meeting, Organisation, Project, User
from app.main import app
from app.api.v1 import intake as intake_api
from app.schemas.intake import IntakeAction, IntakeCommitment, IntakeDecision, IntakeExtraction
from app.services.intake import enrich_extraction, quote_is_supported


@pytest.fixture
def db_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_quote_verification_handles_pdf_line_wrap_and_rejects_invented_text() -> None:
    pages = [(1, "Capital Development Authority to submit the revised renovation\nestimate to the Secretary by 25 October 2026.")]
    assert quote_is_supported("Capital Development Authority to submit the revised renovation estimate to the Secretary by 25 October 2026.", pages)
    assert not quote_is_supported("The Ministry approved an additional budget of 500 million rupees.", pages)


def test_mobilization_based_deadline_uses_date_found_in_minutes(db_factory: sessionmaker[Session]) -> None:
    quote = "Complete the project within 180 days of mobilization."
    with db_factory() as db:
        org = Organisation(name="Synthetic Digital Office", short_name="SDO", type="ministry", aliases=[])
        project = Project(code="MOB-TEST", name="Synthetic Centre", aliases=[], sector="Digital", stage="implementation", health="on_track", health_reason="Initial.", summary="Synthetic test.")
        db.add_all([org, project])
        db.flush()
        result = IntakeExtraction(doc_kind="minutes", meeting_date=date(2026, 8, 19), project_hint=project.name, actions=[IntakeAction(description="Complete the centre.", owner_org=org.name, deadline_text="within 180 days of mobilization", project=project.name, source_quote=quote)])
        enriched, warnings = enrich_extraction(db, result, [(1, "Contractor mobilization target: 13 September 2026.\n" + quote)])
        assert enriched.actions[0].resolved_deadline == date(2027, 3, 12)
        assert not enriched.actions[0].needs_input
        assert warnings == []


def test_extraction_aliases_and_deadline_flags(db_factory: sessionmaker[Session]) -> None:
    quote = "Capital Development Authority to submit the revised renovation estimate to the Secretary by 25 October 2026."
    with db_factory() as db:
        cda = Organisation(name="Capital Development Authority", short_name="CDA", type="authority", aliases=["Capital Development Authority (CDA)"])
        project = Project(code="CIT-TEST", name="Synthetic Citizen Services Centre", aliases=["Synthetic Services Centre"], sector="Digital", stage="implementation", health="on_track", health_reason="Initial.", summary="Synthetic test fixture.")
        db.add_all([cda, project])
        db.flush()
        extracted = IntakeExtraction(doc_kind="minutes", title="Synthetic review", meeting_date=date(2026, 10, 18), project_hint="Synthetic Services Centre", actions=[IntakeAction(description="Submit the revised renovation estimate.", owner_org="CDA", deadline_text="25 October 2026", project=None, source_quote=quote)], commitments=[IntakeCommitment(statement="The centre will be ready.", committed_by_org="Synthetic Digital Office", due_text="23 March 2027", project=None, source_quote="Synthetic Citizen Services Centre will be ready by 23 March 2027.")])
        pages = [(1, quote + "\nSynthetic Citizen Services Centre will be ready by 23 March 2027.")]
        enriched, warnings = enrich_extraction(db, extracted, pages)
        assert enriched.actions[0].owner_org == cda.name
        assert enriched.actions[0].project == project.name
        assert enriched.actions[0].quote_verified and not enriched.actions[0].needs_input
        assert enriched.commitments[0].project == project.name
        assert enriched.commitments[0].quote_verified and not enriched.commitments[0].needs_input
        assert warnings == []


def test_upload_detects_sha256_duplicates_and_returns_existing_review(db_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from app.core.config import settings

    monkeypatch.setattr(type(settings), "resolved_data_dir", property(lambda _: tmp_path))
    async def fake_extract(db: Session, *, document: Document, user_id: str):
        document.text_extracted = "Synthetic look-alike project memo with readable content."
        return IntakeExtraction(doc_kind="other", title="Synthetic upload", summary="Synthetic test."), [], None

    monkeypatch.setattr(intake_api, "extract_document", fake_extract)
    with db_factory() as db:
        minister = User(name="Synthetic Minister", email="minister-upload@test.invalid", role="minister", designation="Minister", password_hash="x")
        db.add(minister)
        db.commit()
        token = create_access_token(minister.id)

    def override_db() -> Generator[Session, None, None]:
        with db_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {token}"}
            first = client.post("/api/v1/intake", headers=headers, data={"classification": "internal"}, files={"file": ("synthetic.txt", b"Synthetic look-alike project memo with readable content.", "text/plain")})
            assert first.status_code == 201, first.text
            second = client.post("/api/v1/intake", headers=headers, data={"classification": "internal"}, files={"file": ("renamed.txt", b"Synthetic look-alike project memo with readable content.", "text/plain")})
            assert second.status_code == 201, second.text
            assert first.json()["id"] == second.json()["id"]
            assert second.json()["duplicate"] is True
            queue = client.get("/api/v1/intake", headers=headers)
            assert queue.status_code == 200 and len(queue.json()) == 1
    finally:
        app.dependency_overrides.clear()


def test_confirmed_intake_creates_dashboard_records_and_updates_project_health(db_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(intake_api, "index_intake_document", lambda db, document: None)
    with db_factory() as db:
        org = Organisation(name="Capital Development Authority", short_name="CDA", type="authority", aliases=[])
        minister = User(name="Synthetic Minister", email="minister@test.invalid", role="minister", designation="Minister", password_hash="x")
        project = Project(code="SYN-CIT", name="Synthetic Citizen Services Centre", aliases=[], sector="Digital", stage="implementation", health="on_track", health_reason="Initial.", summary="Synthetic project for intake acceptance coverage.")
        db.add_all([org, minister, project])
        db.flush()
        document = Document(title="Synthetic minutes", doc_type="minute", classification="internal", file_path="/tmp/synthetic.txt", text_extracted="Evidence: CDA will submit this estimate by 1 January 2025.\nThe centre will be ready by 23 March 2027.\nThe synthetic centre plan is approved.", is_synthetic=True, ingest_status="review")
        db.add(document)
        db.flush()
        payload = IntakeExtraction(doc_kind="minutes", title="Synthetic Citizen Services Centre review", meeting_date=date(2025, 1, 1), chair="Synthetic Minister", venue="Synthetic room", participants=[{"text": "Synthetic Secretary", "org_hint": "Synthetic Ministry"}], project_hint=project.name, summary="Synthetic acceptance fixture.", actions=[IntakeAction(description="CDA to submit the revised estimate.", owner_org=org.name, deadline_text="Immediate", project=project.name, source_quote="CDA will submit this estimate by 1 January 2025.", source_page=1, quote_verified=True)], commitments=[IntakeCommitment(statement="The service centre was due to be ready.", committed_by_org=org.name, due_text="1 December 2024", project=project.name, source_quote="The centre was to be ready by 1 December 2024.", source_page=1, quote_verified=True)], decisions=[IntakeDecision(text="Proceed with the synthetic centre plan.", source_quote="The synthetic centre plan is approved.", source_page=1, quote_verified=True)])
        document.text_extracted += "\nThe centre was to be ready by 1 December 2024."
        review = IntakeReview(document_id=document.id, owner_id=minister.id, status="review", doc_kind="minutes", payload=payload.model_dump(mode="json"), warnings=[])
        db.add(review)
        db.commit()
        token = create_access_token(minister.id)

    def override_db() -> Generator[Session, None, None]:
        with db_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post(f"/api/v1/intake/{review.id}/confirm", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200, response.text
            dashboard = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {token}"})
            assert dashboard.status_code == 200
            assert dashboard.json()["moitt"]["open_actions"] == 1
            assert dashboard.json()["moitt"]["open_commitments"] == 1
            assert dashboard.json()["moitt"]["overdue_actions"] == 1
            meetings = client.get("/api/v1/meetings", headers={"Authorization": f"Bearer {token}"})
            assert meetings.status_code == 200
            assert meetings.json()[0]["decisions"][0]["text"] == "Proceed with the synthetic centre plan."
            assert meetings.json()[0]["summary"] == "Synthetic acceptance fixture."
            assert meetings.json()[0]["source_document_id"] == review.document_id
            assert meetings.json()[0]["intake_actions"][0]["description"] == "CDA to submit the revised estimate."
        with db_factory() as db:
            saved_meeting = db.scalar(select(Meeting).where(Meeting.source_document_id == review.document_id))
            assert saved_meeting is not None
            assert saved_meeting.decisions == [{"text": "Proceed with the synthetic centre plan.", "source_quote": "The synthetic centre plan is approved.", "source_page": 1, "quote_verified": True}]
            actions = list(db.scalars(select(Action).where(Action.source_document_id == review.document_id)))
            assert len(actions) == 1 and actions[0].serial_no == 1 and actions[0].review_state == "approved"
            assert db.scalar(select(Commitment).where(Commitment.source_document_id == review.document_id)) is not None
            project = db.scalar(select(Project).where(Project.code == "SYN-CIT"))
        assert project and project.health == "delayed"
    finally:
        app.dependency_overrides.clear()


def test_letter_review_can_create_project_and_owner_then_confirm_action(db_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(intake_api, "index_intake_document", lambda db, document: None)
    quote = "Synthetic Digital Office will submit the connectivity plan by 25 October 2026."
    with db_factory() as db:
        minister = User(name="Synthetic Minister", email="minister-letter@test.invalid", role="minister", designation="Minister", password_hash="x")
        db.add(minister)
        db.flush()
        document = Document(title="Synthetic project letter", doc_type="letter", classification="internal", file_path="/tmp/synthetic-letter.txt", text_extracted=quote, is_synthetic=True, ingest_status="review")
        db.add(document)
        db.flush()
        payload = IntakeExtraction(doc_kind="letter", title="Synthetic project letter", project_hint="Synthetic Connectivity Project", summary="Synthetic letter asks for a connectivity plan by 25 October 2026.", actions=[IntakeAction(description="Submit the connectivity plan.", owner_org="Synthetic Digital Office", deadline_text="25 October 2026", project="Synthetic Connectivity Project", source_quote=quote, quote_verified=True)])
        review = IntakeReview(document_id=document.id, owner_id=minister.id, status="review", doc_kind="letter", payload=payload.model_dump(mode="json"), warnings=[])
        db.add(review)
        db.commit()
        review_id, document_id = review.id, document.id
        token = create_access_token(minister.id)

    def override_db() -> Generator[Session, None, None]:
        with db_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(app) as client:
            edited = client.patch(f"/api/v1/intake/{review_id}", headers=headers, json={"payload": payload.model_dump(mode="json"), "create_organisations": ["Synthetic Digital Office"], "create_projects": ["Synthetic Connectivity Project"]})
            assert edited.status_code == 200, edited.text
            assert edited.json()["payload"]["actions"][0]["needs_input"] is False
            confirmed = client.post(f"/api/v1/intake/{review_id}/confirm", headers=headers)
            assert confirmed.status_code == 200, confirmed.text
            dashboard = client.get("/api/v1/dashboard", headers=headers)
            assert dashboard.status_code == 200
            assert dashboard.json()["moitt"]["open_actions"] == 1
            assert client.get("/api/v1/meetings", headers=headers).json() == []
        with db_factory() as db:
            project = db.scalar(select(Project).where(Project.name == "Synthetic Connectivity Project"))
            organisation = db.scalar(select(Organisation).where(Organisation.name == "Synthetic Digital Office"))
            document = db.get(Document, document_id)
            action = db.scalar(select(Action).where(Action.source_document_id == document_id))
            assert project is not None and document is not None and document.project_id == project.id
            assert organisation is not None and action is not None and action.owner_org_id == organisation.id
            assert action.project_id == project.id and action.serial_no == 1 and action.source_quote == quote
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "filename",
    [
        "Minutes_of_the_Meeting_-_IT_Park_Islamabad_Operationalization_-_24-08-2026.pdf",
        "Minutes_of_Meeting_-_Update_on_Pak_Asaan_Khidmat_Centres_-_19-08-2026-1.pdf",
    ],
)
def test_real_ministry_pdf_fixtures_are_optional_and_text_extractable(filename: str) -> None:
    fixture = Path(__file__).parents[1] / "samples" / "ministry" / filename
    if not fixture.exists():
        pytest.skip("Local ministry fixture was not supplied in this checkout")
    from app.services.intake import extract_intake_pages
    text = "\n".join(page for _, page in extract_intake_pages(fixture)).casefold()
    assert len(text) > 200
    assert "extracted table rows:" in text
    if "IT_Park" in filename:
        assert "it park" in text and "tender" in text
    else:
        assert "khidmat" in text and ("180" in text or "23 march" in text)


def test_image_upload_uses_tesseract_ocr(tmp_path: Path) -> None:
    if not shutil.which("tesseract"):
        pytest.skip("Tesseract executable is not installed")
    from PIL import Image, ImageDraw, ImageFont
    from app.services.intake import extract_intake_pages

    image_path = tmp_path / "synthetic-ocr.png"
    image = Image.new("RGB", (1800, 300), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    font = ImageFont.truetype(str(font_path), 72) if font_path.exists() else ImageFont.load_default(size=72)
    draw.text((60, 90), "SYNTHETIC OCR TEST PROJECT UPDATE", fill="black", font=font)
    image.save(image_path)
    pages = extract_intake_pages(image_path)
    assert "SYNTHETIC OCR TEST" in pages[0][1].upper()


def test_scanned_image_reports_missing_tesseract_clearly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from PIL import Image
    import app.services.intake as intake_service

    image_path = tmp_path / "blank-scan.png"
    Image.new("RGB", (32, 32), "white").save(image_path)
    monkeypatch.setattr(intake_service.shutil, "which", lambda _: None)
    with pytest.raises(ValueError, match="Tesseract executable was not found"):
        intake_service.extract_intake_pages(image_path)
