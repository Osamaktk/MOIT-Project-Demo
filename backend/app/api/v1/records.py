from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_roles
from app.db.models import Document, DocumentChunk, Transaction, User
from app.schemas.documents import Citation, DocumentList, DocumentResponse, SearchFilters, SearchResponse
from app.services.audit import add_audit_event
from app.services.records_search import index_structured_records, ingest_document, lexical_scores, retrieve

router = APIRouter(tags=["records search"])
READ_ROLES = ("minister", "cos", "director_td", "liaison", "legal", "analyst", "data_coordinator", "admin")
INGEST_ROLES = ("cos", "data_coordinator")
DOC_TYPES = {"board_paper", "cabinet_paper", "ccop", "wing_paper", "minute", "brief", "register", "other"}
CLASSIFICATIONS = {"public", "internal", "confidential"}


def allowed_classifications(actor: User) -> list[str]:
    return ["public", "internal", "confidential"] if actor.role in {"minister", "cos"} else ["public", "internal"]


def document_response(db: Session, document: Document) -> DocumentResponse:
    count = db.scalar(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document.id)) or 0
    return DocumentResponse.model_validate({**{column.name: getattr(document, column.name) for column in Document.__table__.columns}, "chunk_count": count})


@router.get("/api/v1/documents", response_model=DocumentList)
def list_documents(db: Session = Depends(get_db), actor: User = Depends(require_roles(*READ_ROLES))) -> DocumentList:
    docs = db.scalars(select(Document).where(Document.classification.in_(allowed_classifications(actor))).order_by(Document.created_at.desc())).all()
    return DocumentList(items=[document_response(db, document) for document in docs])


@router.post("/api/v1/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(request: Request, file: UploadFile = File(...), title: str = Form(...), doc_type: str = Form("other"), classification: str = Form("internal"), transaction_id: str | None = Form(None), source_note: str | None = Form(None), db: Session = Depends(get_db), actor: User = Depends(require_roles(*INGEST_ROLES))) -> DocumentResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(status_code=415, detail="Upload a PDF, DOCX, TXT, or MD document")
    if doc_type not in DOC_TYPES or classification not in CLASSIFICATIONS:
        raise HTTPException(status_code=422, detail="Select a supported document type and classification")
    if classification == "confidential" and actor.role != "cos":
        raise HTTPException(status_code=403, detail="Only the CoS may classify a document as confidential")
    if transaction_id and db.get(Transaction, transaction_id) is None:
        exists_by_code = db.scalar(select(Transaction.id).where(Transaction.code == transaction_id.upper()))
        if exists_by_code is None:
            raise HTTPException(status_code=422, detail="Linked transaction was not found")
        transaction_id = exists_by_code
    content = await file.read(30 * 1024 * 1024 + 1)
    if not content or len(content) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Document must be between 1 byte and 30 MB")
    storage = settings.resolved_data_dir / "documents"
    storage.mkdir(parents=True, exist_ok=True)
    path = storage / f"{uuid4()}{suffix}"
    path.write_bytes(content)
    try:
        document = ingest_document(db, title=title.strip(), doc_type=doc_type, classification=classification, transaction_id=transaction_id, source_note=source_note, is_synthetic=False, saved_path=path, user_id=actor.id)
    except (ValueError, OSError) as exc:
        db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    add_audit_event(db, actor, request, action="document_ingested", entity_type="document", entity_id=document.id, after={"title": document.title, "doc_type": document.doc_type, "classification": document.classification, "chunk_count": len(document.chunks)})
    db.commit()
    return document_response(db, document)


@router.post("/api/v1/records/search", response_model=SearchResponse)
def search_records(payload: SearchFilters, db: Session = Depends(get_db), actor: User = Depends(require_roles(*READ_ROLES))) -> SearchResponse:
    index_structured_records(db)
    rows = retrieve(db, query=payload.query, classification_access=allowed_classifications(actor), transaction_id=payload.transaction_id, doc_type=payload.doc_type, date_from=payload.date_from, date_to=payload.date_to, top_k=payload.top_k, user_id=actor.id)
    if not rows:
        return SearchResponse(query=payload.query, answer="I could not find supporting evidence in the records available to your role.", declined=True, citations=[])
    all_chunks = [chunk for chunk, _ in rows]
    lexical = lexical_scores(payload.query, all_chunks)
    if not any(score > 0 for score in lexical.values()):
        return SearchResponse(query=payload.query, answer="I could not find supporting evidence in the records available to your role.", declined=True, citations=[])
    citations = []
    for number, (chunk, _) in enumerate(rows, start=1):
        document = db.get(Document, chunk.document_id)
        if document is None or document.classification not in allowed_classifications(actor):
            continue
        citations.append(Citation(number=len(citations) + 1, document_id=document.id, title=document.title, doc_type=document.doc_type, page=chunk.page, section=chunk.section, snippet=chunk.text[:700], chunk_id=chunk.id))
    answer = "\n\n".join(f"{citation.snippet} [{citation.number}]" for citation in citations)
    return SearchResponse(query=payload.query, answer=answer, declined=not bool(citations), citations=citations)


@router.get("/api/v1/documents/{document_id}/source")
def get_document_source(document_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(*READ_ROLES))) -> FileResponse:
    document = db.get(Document, document_id)
    if document is None or document.classification not in allowed_classifications(actor):
        raise HTTPException(status_code=404, detail="Document source was not found")
    path = Path(document.file_path).resolve()
    if settings.resolved_data_dir not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Document source was not found")
    return FileResponse(path, filename=f"{document.id[:8]}-{Path(document.title).name}{path.suffix}")
