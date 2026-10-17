from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import ComplianceItem, Engagement, Meeting, MinisterDecision, RegisterEntry, Transaction, User
from app.services.dashboard import dashboard_summary
from app.services.records_search import index_structured_records, lexical_scores, retrieve
from app.services.register import financial_year_for


class JarvisState(TypedDict, total=False):
    user_id: str
    message: str
    context: dict[str, Any] | None
    tool: str
    answer: str
    citations: list[dict[str, Any]]
    proposal: dict[str, Any] | None


def _classifications(user: User) -> list[str]:
    return ["public", "internal", "confidential"] if user.role in {"minister", "cos"} else ["public", "internal"]


def _citation(kind: str, identifier: str, label: str, detail: str) -> dict[str, Any]:
    return {"type": kind, "id": identifier, "label": label, "detail": detail}


def choose_tool(message: str, context: dict[str, Any] | None) -> str:
    text = message.casefold()
    if re.search(r"\b(create|add|make|propose)\b.*\b(action|register|task)\b", text):
        return "propose_register_entry"
    if any(word in text for word in ("brief me", "daily brief", "today's brief", "today’s brief")):
        return "get_daily_brief"
    if "overdue" in text or "past due" in text:
        return "list_overdue"
    if "compliance" in text or "statutory" in text or "cabinet deadline" in text:
        return "get_compliance_due"
    code = re.search(r"\bTX-[A-Z]{1,3}\b", message, re.I)
    if code or (context or {}).get("transaction_code") or any(word in text for word in ("transaction status", "next milestone", "transaction c")):
        return "get_transaction"
    if any(word in text for word in ("engagement", "meeting this week", "calendar")):
        return "get_upcoming_engagements"
    if "minute" in text or "meeting" in text:
        return "get_minutes"
    if any(word in text for word in ("dashboard", "portfolio summary", "how many transactions")):
        return "get_dashboard_summary"
    if any(word in text for word in ("decision", "document", "paper", "what did we agree", "what did we decide", "adviser", "record")):
        return "search_records"
    return "search_records"


def _parse_deadline(value: str) -> date | None:
    raw = value.strip().rstrip(".,?!")
    for fmt in ("%Y-%m-%d", "%B %d %Y", "%B %d, %Y", "%b %d %Y", "%b %d, %Y", "%B %d", "%b %d"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
            if parsed.year == 1900:
                parsed = parsed.replace(year=date.today().year)
            return parsed
        except ValueError:
            pass
    weekdays = {name.casefold(): index for index, name in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"))}
    target = weekdays.get(raw.casefold())
    if target is not None:
        delta = (target - date.today().weekday()) % 7 or 7
        return date.today() + timedelta(days=delta)
    return None


def _propose_action(db: Session, actor: User, message: str) -> tuple[str, dict[str, Any] | None]:
    pattern = re.compile(r"\b(?:create|add|make|propose)\b.*?\baction\s+for\s+(?P<owner>.+?)\s+to\s+(?P<task>.+?)\s+by\s+(?P<deadline>[A-Za-z]+\s+\d{1,2}(?:,?\s+\d{4})?|\d{4}-\d{2}-\d{2}|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*[.!?]*$", re.I)
    match = pattern.search(message.strip())
    if not match:
        return "Tell me the responsible officer, the action, and a calendar deadline. For example: ‘Create an action for the CoS to confirm the draft by 2026-10-28.’", None
    owner_text = match.group("owner").strip().casefold()
    owner_aliases = {"the cos": "cos", "cos": "cos", "chief of staff": "cos", "the liaison": "liaison", "liaison": "liaison", "the director": "director_td", "director": "director_td"}
    owner_key = owner_aliases.get(owner_text, owner_text)
    users = db.scalars(select(User).where(User.active.is_(True))).all()
    matches = [row for row in users if owner_key in {row.role.casefold(), row.name.casefold(), row.designation.casefold(), row.email.casefold()}]
    if len(matches) != 1:
        return "I could not identify exactly one active officer from that name. Please give the officer’s name or role.", None
    deadline = _parse_deadline(match.group("deadline"))
    if deadline is None or deadline < date.today():
        return "I could not verify a future calendar deadline. Please give a date such as 2026-10-28.", None
    task = match.group("task").strip().rstrip(".!? ")
    if len(task) < 4:
        return "Please include a clear action description.", None
    row = RegisterEntry(fy=financial_year_for(date.today()), serial_no=None, occurred_at=datetime.now(timezone.utc), occasion_type="on_the_move", occasion_ref="Jarvis proposal", description=task, officer_id=matches[0].id, deadline=deadline, priority="B", source_record="Jarvis proposal", status="open", origin="ai_proposed", review_state="proposed", ai_assistance={"tool": "jarvis", "model": "deterministic-agent-v1"})
    db.add(row)
    db.flush()
    citation = _citation("register_proposal", row.id, "Unnumbered Register proposal", f"{matches[0].name}: {task} by {deadline.isoformat()}")
    return "I prepared this as an unnumbered Register proposal. An authorized reviewer must approve it before it becomes an official action.", {"id": row.id, "description": task, "officer_id": matches[0].id, "officer_name": matches[0].name, "deadline": deadline.isoformat(), "priority": "B", "review_state": "proposed", "citation": citation}


def _execute(db: Session, actor: User, state: JarvisState) -> dict[str, Any]:
    message = state["message"]
    tool = state["tool"]
    context = state.get("context") or {}
    citations: list[dict[str, Any]] = []
    proposal = None
    if tool == "propose_register_entry":
        answer, proposal = _propose_action(db, actor, message)
        if proposal:
            citations.append(proposal["citation"])
        return {"answer": answer, "citations": citations, "proposal": proposal}
    if tool == "get_daily_brief":
        summary = dashboard_summary(db, None)
        counts = summary["kpis"]
        answer = f"Today’s office brief: {counts['actions_overdue']} approved actions are overdue, {counts['decisions_due_this_week']} minister decisions are due this week, and {counts['engagements_this_week']} engagements are scheduled this week across {counts['transactions_in_process']} transactions."
        citations.append(_citation("dashboard", "summary", "Friday dashboard", f"KPIs: {counts}; week ending {summary['week_ending']}"))
        for row in summary["overdue_actions"][:5]:
            citations.append(_citation("register", row["id"], f"Register {row['fy']}/{row['serial_no']:03d}", f"{row['description']} — {row['officer_name']}, due {row['deadline']}"))
        for row in summary["decisions_due"][:4]:
            citations.append(_citation("decision", row["id"], row["title"], f"Due {row['due_date']}"))
        for row in summary["upcoming_engagements"][:4]:
            citations.append(_citation("engagement", row["id"], row["title"], f"{row['starts_at']} at {row['location']}"))
        return {"answer": answer, "citations": citations, "proposal": None}
    if tool == "list_overdue":
        rows = db.scalars(select(RegisterEntry).options(joinedload(RegisterEntry.officer)).where(RegisterEntry.review_state == "approved", RegisterEntry.deadline < date.today(), RegisterEntry.status.not_in(("closed", "closed_with_note"))).order_by(RegisterEntry.deadline)).all()
        if not rows:
            return {"answer": "There are no approved Register actions overdue today.", "citations": [], "proposal": None}
        for row in rows[:15]:
            citations.append(_citation("register", row.id, f"Register {row.fy}/{row.serial_no:03d}", f"{row.description} — {row.officer.name}, due {row.deadline.isoformat()}"))
        return {"answer": f"I found {len(rows)} approved overdue actions. The first {len(citations)} are listed in the citations.", "citations": citations, "proposal": None}
    if tool == "get_transaction":
        code_match = re.search(r"\bTX-[A-Z]{1,3}\b", message, re.I)
        code = code_match.group(0).upper() if code_match else str(context.get("transaction_code", "")).upper()
        row = db.scalar(select(Transaction).where(Transaction.code == code)) if code else None
        if row is None:
            return {"answer": "Which transaction should I check? Please give its code, such as TX-A.", "citations": [], "proposal": None}
        citations.append(_citation("transaction", row.id, f"{row.code} · {row.name}", f"Stage: {row.stage}; next milestone: {row.next_milestone}, {row.next_milestone_date}; health: {row.health}. {row.summary}"))
        return {"answer": f"{row.code} is at {row.stage}. Its next milestone is {row.next_milestone}, due {row.next_milestone_date}, and its current health is {row.health}.", "citations": citations, "proposal": None}
    if tool == "get_dashboard_summary":
        summary = dashboard_summary(db, None)
        citations.append(_citation("dashboard", "summary", "Friday dashboard", f"KPIs: {summary['kpis']}; stage distribution: {summary['transactions_by_stage']}"))
        return {"answer": f"The portfolio has {summary['kpis']['transactions_in_process']} transactions in process, {summary['kpis']['actions_overdue']} overdue approved actions, {summary['kpis']['decisions_due_this_week']} decisions due this week, and {summary['kpis']['engagements_this_week']} engagements this week.", "citations": citations, "proposal": None}
    if tool == "get_upcoming_engagements":
        now = datetime.now(timezone.utc)
        rows = db.scalars(select(Engagement).options(joinedload(Engagement.owner)).where(Engagement.starts_at >= now, Engagement.starts_at <= now + timedelta(days=14)).order_by(Engagement.starts_at)).all()
        for row in rows[:10]:
            citations.append(_citation("engagement", row.id, row.title, f"{row.starts_at.isoformat()} · {row.location} · pack {row.pack_status} · {row.owner.name}"))
        answer = f"I found {len(rows)} engagements in the next fortnight." if rows else "No engagements are scheduled in the next fortnight."
        return {"answer": answer, "citations": citations, "proposal": None}
    if tool == "get_compliance_due":
        today = date.today()
        rows = db.scalars(select(ComplianceItem).options(joinedload(ComplianceItem.owner)).where(ComplianceItem.due_date >= today, ComplianceItem.due_date <= today + timedelta(days=14), ComplianceItem.status != "complete").order_by(ComplianceItem.due_date)).all()
        for row in rows:
            citations.append(_citation("compliance", row.id, row.title, f"{row.category} · due {row.due_date} · owner {row.owner.name} · {row.status}"))
        return {"answer": f"There are {len(rows)} open compliance item(s) due in the next fortnight." if rows else "No open compliance items are due in the next fortnight.", "citations": citations, "proposal": None}
    if tool == "get_minutes":
        rows = db.scalars(select(Meeting).where(Meeting.classification.in_(_classifications(actor))).order_by(Meeting.occurred_at.desc())).all()
        needle = re.search(r"TX-[A-Z]{1,3}", message, re.I)
        if needle:
            rows = [row for row in rows if needle.group(0).upper() in row.title.upper()]
        for meeting in rows[:5]:
            draft = next((item for item in meeting.minutes if item.status == "issued"), None)
            if draft:
                citations.append(_citation("minutes", draft.id, meeting.title, draft.body_markdown[:900]))
        answer = f"I found {len(citations)} issued minute record(s) matching your request." if citations else "I found no issued minutes matching that request. Drafts are not treated as official minutes."
        return {"answer": answer, "citations": citations, "proposal": None}
    if tool == "search_records":
        index_structured_records(db)
        rows = retrieve(db, query=message, classification_access=_classifications(actor), top_k=5, user_id=actor.id)
        for chunk, _ in rows:
            document = chunk.document
            citations.append(_citation("document", document.id, document.title, chunk.text[:700]))
        if not citations or not any(lexical_scores(message, [chunk for chunk, _ in rows]).values()):
            return {"answer": "I could not confirm an answer from the records available to your role. Try a transaction code, Register description, meeting subject, or document phrase.", "citations": [], "proposal": None}
        answer = "I found these matching records. Check the cited excerpts for the supporting details."
        return {"answer": answer, "citations": citations, "proposal": None}
    return {"answer": "I could not find a connected office-record tool for that request.", "citations": [], "proposal": None}


def build_jarvis_graph(db: Session):
    def plan(state: JarvisState) -> dict[str, Any]:
        return {"tool": choose_tool(state["message"], state.get("context"))}

    def call_tool(state: JarvisState) -> dict[str, Any]:
        actor = db.get(User, state["user_id"])
        if actor is None:
            raise ValueError("Current user is no longer active")
        return _execute(db, actor, state)

    graph = StateGraph(JarvisState)
    graph.add_node("plan", plan)
    graph.add_node("tool", call_tool)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "tool")
    graph.add_edge("tool", END)
    return graph.compile()
