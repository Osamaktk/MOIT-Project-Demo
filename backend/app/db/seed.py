from datetime import date, datetime, time, timedelta, timezone
import json
import shutil
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import REPO_ROOT, settings
from app.core.permissions import ROLE_PRESETS
from app.core.security import hash_password
from app.db.models import Action, Commitment, ComplianceItem, Document, Engagement, Meeting, MinisterDecision, Organisation, Project, RegisterEntry, RegisterSerialCounter, RolePreset, ToolSwitch, Transcript, Transaction, TransactionEvent, User
from app.services.register import financial_year_for
from app.db.session import SessionLocal
from app.services.records_search import ingest_document

DEMO_PASSWORD = "Demo-Only-Change-Me-2026!"
PERSONAS = (
    ("Amina Shah", "minister@demo.example", "minister", "Minister"),
    ("Farid Khan", "cos@demo.example", "cos", "Chief of Staff"),
    ("Sana Malik", "director.td@demo.example", "director_td", "Director, Transformation & Delivery"),
    ("Bilal Ahmed", "liaison@demo.example", "liaison", "Liaison Lead"),
    ("Mariam Raza", "legal@demo.example", "legal", "Legal Vetting Desk"),
    ("Omar Siddiqui", "analyst@demo.example", "analyst", "Dashboard Analyst"),
    ("Noor Hassan", "data.coordinator@demo.example", "data_coordinator", "AI Data Coordinator"),
    ("Zain Qureshi", "admin@demo.example", "admin", "System Administrator"),
)

MOITT_PERSONAS = (
    ("Federal Minister", "minister@moitt.demo", "minister", "Federal Minister", "MoITT", "confidential"),
    ("Federal Secretary IT", "secretary@moitt.demo", "secretary", "Federal Secretary IT", "MoITT", "confidential"),
    ("Private Secretary / Chief of Staff", "ps@moitt.demo", "cos", "Chief of Staff", "MoITT", "confidential"),
    ("Joint Secretary (Dev)", "js.dev@moitt.demo", "project_lead", "Joint Secretary (Development)", "MoITT", "internal"),
    ("Legal Adviser", "legal@moitt.demo", "legal", "Legal Adviser", "MoITT", "internal"),
    ("Dashboard Analyst", "analyst@moitt.demo", "analyst", "Dashboard Analyst", "MoITT", "internal"),
    ("Records Coordinator", "records@moitt.demo", "data_coordinator", "Records Coordinator", "MoITT", "internal"),
    ("PSEB Liaison", "pseb.liaison@moitt.demo", "external_org", "PSEB Liaison", "PSEB", "public"),
    ("System Administrator", "admin@moitt.demo", "admin", "System Administrator", "MoITT", "internal"),
)

ORGANISATIONS = (
    ("Ministry of IT and Telecommunication", "MoITT", "ministry", ["Ministry of IT & Telecommunication", "Ministry of IT and Telecommunication"]),
    ("Pakistan Software Export Board", "PSEB", "attached_dept", ["Pakistan Software Export Board", "PSEB"]),
    ("Capital Development Authority", "CDA", "authority", ["Capital Development Authority", "CDA"]),
    ("National Information Technology Board", "NITB", "attached_dept", ["National Information Technology Board", "NITB"]),
    ("Government of Azad Jammu and Kashmir", "AJK Govt", "provincial", ["AJK Government", "Government of AJK"]),
    ("Government of Gilgit-Baltistan", "GB Govt", "provincial", ["GB Government", "Government of Gilgit-Baltistan"]),
)

ROLE_NAMES = {
    "minister": ("Minister", "Federal minister with office-wide read and approval access."),
    "secretary": ("Secretary", "Office-wide access for the Federal Secretary IT."),
    "cos": ("Chief of Staff", "Coordinates office actions, review and AI oversight."),
    "project_lead": ("Project Lead", "Maintains assigned projects and their actions."),
    "legal": ("Legal Adviser", "Reviews documents, actions and compliance."),
    "analyst": ("Analyst", "Views office dashboards and AI oversight."),
    "data_coordinator": ("Records Coordinator", "Uploads and classifies office documents."),
    "external_org": ("External Organisation", "Views and updates scoped organisation actions."),
    "admin": ("Administrator", "Manages system access and settings."),
}


def seed_permission_foundation() -> None:
    with SessionLocal() as db:
        organisations = {}
        for name, short_name, kind, aliases in ORGANISATIONS:
            organisation = db.scalar(select(Organisation).where(Organisation.short_name == short_name))
            if organisation is None:
                organisation = Organisation(name=name, short_name=short_name, type=kind, aliases=aliases)
                db.add(organisation)
            organisations[short_name] = organisation
        db.flush()

        for key, permissions in ROLE_PRESETS.items():
            name, description = ROLE_NAMES[key]
            preset = db.scalar(select(RolePreset).where(RolePreset.key == key))
            if preset is None:
                db.add(RolePreset(key=key, name=name, description=description, permissions=permissions))
            else:
                preset.name, preset.description, preset.permissions = name, description, permissions

        for name, email, role, designation, org_short, clearance in MOITT_PERSONAS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(name=name, email=email, role=role, designation=designation, password_hash=hash_password(DEMO_PASSWORD))
                db.add(user)
            user.document_clearance = clearance
            user.organisation_id = organisations[org_short].id

        legacy_org = organisations["MoITT"]
        for user in db.scalars(select(User).where(User.email.like("%@demo.example"))):
            user.document_clearance = "confidential" if user.role in {"minister", "cos", "admin"} else "internal"
            user.organisation_id = organisations["PSEB"].id if user.role == "liaison" else legacy_org.id
        db.commit()


def seed_moitt_domain_data() -> None:
    today = date.today()
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Project)):
            return
        organisations = {org.short_name: org for org in db.scalars(select(Organisation))}
        rows = [
            Project(code="MOITT-ITP", name="IT Park Islamabad", aliases=["IT Park", "Islamabad IT Park"], sector="Digital infrastructure", stage="implementation", health="on_track", health_reason="No overdue actions or near-term unmet commitments.", lead_org_id=organisations["MoITT"].id, summary="Synthetic demonstration project for the Islamabad IT Park."),
            Project(code="MOITT-AKC", name="Pakistan Asaan Khidmat Centres", aliases=["Pak Asaan Khidmat Centres", "Asaan Khidmat Centres"], sector="Digital public services", stage="monitoring", health="on_track", health_reason="No overdue actions or near-term unmet commitments.", lead_org_id=organisations["MoITT"].id, summary="Synthetic demonstration project for Pakistan Asaan Khidmat Centres."),
        ]
        db.add_all(rows)
        db.flush()
        fy = financial_year_for(today)
        db.add_all([
            Action(fy=fy, serial_no=1, description="Confirm the next construction coordination checkpoint for the Islamabad IT Park.", owner_org_id=organisations["CDA"].id, owner_person_name="Project coordination focal person", occurred_at=datetime.combine(today, time(10), tzinfo=timezone.utc), deadline=today + timedelta(days=14), deadline_text="Within two weeks", deadline_precision="relative", priority="B", status="open", status_source="open", project_id=rows[0].id),
            Action(fy=fy, serial_no=2, description="Share the next service-centre rollout status with the ministry.", owner_org_id=organisations["AJK Govt"].id, owner_person_name=None, occurred_at=datetime.combine(today - timedelta(days=6), time(10), tzinfo=timezone.utc), deadline=today - timedelta(days=3), deadline_text="Immediate", deadline_precision="relative", priority="A", status="open", status_source="open", project_id=rows[1].id),
        ])
        db.add(Commitment(project_id=rows[0].id, statement="Complete the next implementation checkpoint and report readiness.", committed_by_org_id=organisations["CDA"].id, committed_by_text="CDA project team", due_date=today + timedelta(days=60), due_text="Within the current quarter", precision="month", status="pending"))
        db.flush()
        from app.services.project_rules import recompute_project_health
        for project in rows:
            recompute_project_health(db, project, as_of=today)
        db.commit()


def seed_demo_users() -> None:
    with SessionLocal() as db:
        for name, email, role, designation in PERSONAS:
            if db.scalar(select(User).where(User.email == email)) is None:
                db.add(User(name=name, email=email, role=role, designation=designation, password_hash=hash_password(DEMO_PASSWORD)))
        db.commit()


def seed_register_entries() -> None:
    today = date.today()
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(RegisterEntry)):
            return
        officers = {
            user.role: user
            for user in db.scalars(select(User).where(User.role.in_(("cos", "director_td", "liaison"))))
        }
        officer_roles = ("cos", "director_td", "liaison")
        summaries = (
            "Confirm the revised adviser scope and return a tracked copy.",
            "Prepare a short risk note for the next transaction review.",
            "Reconcile the milestone dates with the latest committee record.",
            "Share the requested briefing points with the coordination desk.",
            "Review the open questions and record a response against each item.",
            "Collect the supporting paper and confirm its source reference.",
            "Update the delivery timeline after the stakeholder meeting.",
            "Prepare a decision note with options and a clear recommendation.",
            "Confirm the owner and next checkpoint for the outstanding action.",
            "Check the draft against the meeting record and report changes.",
        )
        serial_by_fy: dict[str, int] = {}
        for number in range(1, 61):
            officer = officers[officer_roles[(number - 1) % len(officer_roles)]]
            overdue = number <= 6
            due_this_week = 7 <= number <= 13
            status = "in_progress" if overdue or number % 4 == 0 else "closed" if number % 9 == 0 else "open"
            occurred_days_ago = min(55, 8 + (number * 7) % 50)
            occurred = datetime.combine(today - timedelta(days=occurred_days_ago), time(10 + number % 6, (number * 7) % 60), tzinfo=timezone.utc)
            entry_fy = financial_year_for(occurred.date())
            serial_by_fy[entry_fy] = serial_by_fy.get(entry_fy, 0) + 1
            if overdue:
                deadline = today - timedelta(days=number)
            elif due_this_week:
                deadline = today + timedelta(days=number - 6)
            else:
                deadline = today - timedelta(days=2 + number % 15) if status == "closed" else today + timedelta(days=8 + (number * 11) % 32)
            db.add(RegisterEntry(
                fy=entry_fy,
                serial_no=serial_by_fy[entry_fy],
                occurred_at=occurred,
                occasion_type=("meeting", "engagement", "file", "on_the_move")[(number - 1) % 4],
                occasion_ref=f"Synthetic coordination record {number:03d}",
                description=summaries[(number - 1) % len(summaries)],
                minister_words=None,
                officer_id=officer.id,
                deadline=deadline,
                priority=("A", "B", "C")[(number - 1) % 3],
                source_record=f"SYN-{today.year}-{number:04d}",
                status=status,
                closed_at=datetime.combine(today - timedelta(days=1), time(16), tzinfo=timezone.utc) if status == "closed" else None,
                closure_note="Completed and checked against the source record." if status == "closed" else None,
                origin="manual",
                review_state="approved",
            ))
        proposed_descriptions = (
            "Confirm the revised adviser milestone with the transaction lead.",
            "Prepare a follow-up note for the next review meeting.",
            "Verify the source record for the committee decision.",
            "Return the updated schedule with the owner identified.",
            "Draft a short status update for the office review.",
            "Confirm the next action and proposed completion date.",
        )
        proposal_fy = financial_year_for(today)
        serial_by_fy.setdefault(proposal_fy, 0)
        for index, description in enumerate(proposed_descriptions):
            officer = officers[officer_roles[index % len(officer_roles)]]
            db.add(RegisterEntry(
                fy=proposal_fy,
                serial_no=None,
                occurred_at=datetime.combine(today - timedelta(days=2 + index), time(11), tzinfo=timezone.utc),
                occasion_type="meeting",
                occasion_ref=f"Synthetic minutes review {index + 1}",
                description=description,
                officer_id=officer.id,
                deadline=today + timedelta(days=3 + index),
                priority=("A", "B", "C")[index % 3],
                source_record=f"SYN-MIN-{index + 1:03d}",
                status="open",
                origin="ai_proposed",
                review_state="proposed",
                ai_assistance={"tool": "minutes_assistant", "model": "demo-recorded-output", "run_id": None},
                evidence={"meeting_id": f"synthetic-meeting-{index + 1}", "quote": "Synthetic supporting evidence excerpt.", "confidence": 0.88},
            ))
        for fy, last_serial in serial_by_fy.items():
            existing_counter = db.get(RegisterSerialCounter, fy)
            if existing_counter is None:
                db.add(RegisterSerialCounter(fy=fy, last_serial=last_serial))
            else:
                existing_counter.last_serial = max(existing_counter.last_serial, last_serial)
        db.commit()


def seed_transactions_dashboard() -> None:
    today = date.today()
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Transaction)):
            return
        users = {user.role: user for user in db.scalars(select(User).where(User.role.in_(("cos", "director_td", "liaison"))))}
        stage_counts = (
            ("approval_inclusion", 2), ("adviser_hiring", 3), ("due_diligence", 3),
            ("eoi_prequalification", 3), ("bidding", 2), ("approvals", 2), ("closing", 2),
        )
        names = (
            ("Power Distribution Company A", "Energy"), ("Power Distribution Company B", "Energy"),
            ("Airline A", "Transport"), ("Airline B", "Transport"), ("Hotel Group C", "Hospitality"),
            ("Port Services D", "Logistics"), ("Industrial Estate E", "Infrastructure"),
            ("Fertiliser Company F", "Manufacturing"), ("Telecom Tower Company G", "Technology"),
            ("Insurance Company H", "Financial services"), ("Banking Services I", "Financial services"),
            ("Minerals Company J", "Natural resources"), ("Rail Services K", "Transport"),
            ("Energy Services L", "Energy"), ("Logistics Company M", "Logistics"),
            ("Manufacturing Company N", "Manufacturing"), ("Property Portfolio O", "Real estate"),
        )
        stages = [stage for stage, count in stage_counts for _ in range(count)]
        transactions: list[Transaction] = []
        for index, (name, sector) in enumerate(names):
            code = f"TX-{chr(65 + index)}"
            stage = stages[index]
            health = "delayed" if stage == "adviser_hiring" and index == 2 else "at_risk" if stage == "bidding" and index == 12 else "on_track"
            lead_role = "director_td" if index % 3 == 0 else "liaison"
            transaction = Transaction(
                code=code,
                name=name,
                sector=sector,
                stage=stage,
                next_milestone=("Confirm the next review pack", "Complete the advisory checkpoint", "Close the diligence questions", "Prepare the bidder information update", "Record the committee decision")[(index + 1) % 5],
                next_milestone_date=today + timedelta(days=5 + (index * 7) % 55),
                health=health,
                lead_user_id=users[lead_role].id,
                summary=f"Synthetic {sector.lower()} transaction. Status and milestones are fictional demo records.",
                updated_by=users["cos"].id,
            )
            db.add(transaction)
            transactions.append(transaction)
        db.flush()
        for index, transaction in enumerate(transactions):
            db.add(TransactionEvent(
                transaction_id=transaction.id,
                occurred_at=datetime.now(timezone.utc) - timedelta(days=2 + index),
                event_type="milestone" if index % 2 == 0 else "note",
                description=f"Synthetic status checkpoint recorded for {transaction.code}.",
                source_ref=f"SYN-TX-{index + 1:03d}",
            ))
        decisions = (
            ("Review the synthetic CCoP summary", 1, 0),
            ("Confirm the adviser contract options", 3, 1),
            ("Review the synthetic committee reply", 5, 3),
            ("Confirm the transaction stage recommendation", 6, 5),
        )
        for title, days, transaction_index in decisions:
            db.add(MinisterDecision(title=title, due_date=today + timedelta(days=days), transaction_id=transactions[transaction_index].id, status="open", context_ref=f"Synthetic decision note {transaction_index + 1:02d}"))
        engagement_types = ("Board review", "Stakeholder meeting", "Adviser checkpoint", "Portfolio briefing", "Committee session", "Delivery review")
        pack_states = ("ready", "in_progress", "not_started", "ready", "in_progress", "not_started")
        for index in range(6):
            starts_at = datetime.combine(today + timedelta(days=index + 1), time(10 + index % 5, 0), tzinfo=timezone.utc)
            db.add(Engagement(
                title=f"Synthetic {engagement_types[index]} {chr(65 + index)}",
                engagement_type=engagement_types[index],
                starts_at=starts_at,
                location=f"Synthetic venue {chr(65 + index)}",
                pack_status=pack_states[index],
                pack_due_at=starts_at - timedelta(hours=48),
                owner_id=users["director_td" if index % 2 == 0 else "cos"].id,
                transaction_id=transactions[(index * 2) % len(transactions)].id,
            ))
        db.commit()


def seed_tool_switches() -> None:
    with SessionLocal() as db:
        for tool in ("jarvis", "minutes_assistant", "records_search", "brief_generator", "document_extraction"):
            if db.get(ToolSwitch, tool) is None:
                db.add(ToolSwitch(tool=tool, suspended=False))
        db.commit()


def seed_meeting_sample() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Meeting)):
            return
        director = db.scalar(select(User).where(User.role == "director_td"))
        if director is None:
            raise RuntimeError("Seed role accounts before the sample meeting")
        sample_dir = REPO_ROOT / "backend" / "samples"
        source_audio = sample_dir / "synthetic_minutes_review.wav"
        source_transcript = sample_dir / "synthetic_minutes_review.json"
        audio_dir = settings.resolved_data_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_audio, audio_dir / source_audio.name)
        segments = json.loads(source_transcript.read_text(encoding="utf-8"))
        occurred_at = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)
        meeting = Meeting(
            title="Synthetic TX-A transaction review", occurred_at=occurred_at,
            occasion_type="meeting", location="Synthetic conference room",
            attendees=[{"name": "Sana Malik", "role": "Director (Transformation & Delivery)"}, {"name": "Farid Khan", "role": "Chief of Staff"}, {"name": "Bilal Ahmed", "role": "Liaison"}],
            audio_path=f"audio/{source_audio.name}", language_hint="en", classification="internal",
            is_synthetic=True, status="transcribed", draft_due_at=occurred_at + timedelta(hours=24),
            issue_due_at=occurred_at + timedelta(hours=48), created_by=director.id,
        )
        db.add(meeting)
        db.flush()
        db.add(Transcript(meeting_id=meeting.id, language="en", segments=segments, stt_provider="synthetic-seed", stt_model="synthetic-english-review-v1"))
        db.commit()


def seed_sample_documents() -> None:
    sample_dir = REPO_ROOT / "backend" / "samples" / "records"
    sample_dir.mkdir(parents=True, exist_ok=True)
    examples = {
        "tx-a-milestone-brief.md": ("TX-A milestone briefing note", "brief", "internal", "Synthetic summary of the TX-A advisory and transaction milestones. The transaction is in the due diligence stage. The next milestone is review of the updated diligence pack by 25 October 2026. The Transformation and Delivery director coordinates the pack and the Liaison confirms milestone readiness. This demonstration briefing contains no real Commission data."),
        "synthetic-board-paper.txt": ("Synthetic Board Paper: Project Cedar", "board_paper", "confidential", "Purpose: Synthetic board paper for the Project Cedar demonstration. Decision requested: note the diligence timetable and confirm the proposed sequencing. The board review is scheduled for 30 October 2026. This fictional paper has been created solely to demonstrate confidential-document clearance and contains no real Commission data."),
        "register-handling-guide.md": ("Synthetic Register handling guide", "other", "public", "Register actions must name one responsible officer and include a calendar deadline. AI-assisted suggestions remain proposals until an authorized reviewer approves them. Approved actions receive a financial-year serial number. Only approved entries are counted in dashboard totals. This synthetic guide is for the PC Command Center demo."),
    }
    for filename, (title, doc_type, classification, contents) in examples.items():
        path = sample_dir / filename
        if not path.exists():
            path.write_text(contents, encoding="utf-8")
    with SessionLocal() as db:
        existing = set(db.scalars(select(Document.title)).all())
        if len(existing) >= len(examples):
            return
        transaction = db.scalar(select(Transaction).where(Transaction.code == "TX-A"))
        for filename, (title, doc_type, classification, note) in examples.items():
            if title in existing:
                continue
            storage = settings.resolved_data_dir / "documents"
            storage.mkdir(parents=True, exist_ok=True)
            saved_path = storage / filename
            shutil.copyfile(sample_dir / filename, saved_path)
            ingest_document(db, title=title, doc_type=doc_type, classification=classification, transaction_id=transaction.id if filename.startswith("tx-a") and transaction else None, source_note="Synthetic demonstration record", is_synthetic=True, saved_path=saved_path)


def seed_compliance_items() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(ComplianceItem)):
            return
        legal = db.scalar(select(User).where(User.role == "legal"))
        cos = db.scalar(select(User).where(User.role == "cos"))
        if legal is None or cos is None:
            raise RuntimeError("Seed role accounts before compliance items")
        today = date.today()
        rows = [
            ("statutory", "Synthetic statutory filing review", 3, legal, "SYN-STAT-026"),
            ("cabinet_ccop", "Synthetic cabinet committee submission", 6, cos, "SYN-CCOP-014"),
            ("board", "Synthetic board paper clearance", 10, legal, "SYN-BRD-008"),
            ("audit", "Synthetic internal audit evidence pack", 13, legal, "SYN-AUD-003"),
            ("transaction_milestone", "TX-A diligence milestone check", 20, cos, "TX-A"),
        ]
        db.add_all([ComplianceItem(category=category, title=title, due_date=today + timedelta(days=offset), owner_id=owner.id, status="open", reference=reference) for category, title, offset, owner, reference in rows])
        db.commit()


if __name__ == "__main__":
    seed_demo_users()
    seed_permission_foundation()
    seed_register_entries()
    seed_transactions_dashboard()
    seed_moitt_domain_data()
    seed_tool_switches()
    seed_meeting_sample()
    seed_sample_documents()
    seed_compliance_items()
