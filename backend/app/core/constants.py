PROJECT_STAGES: tuple[tuple[str, str], ...] = (
    ("planning", "Planning"),
    ("initiation", "Initiation"),
    ("procurement", "Procurement"),
    ("implementation", "Implementation"),
    ("monitoring", "Monitoring"),
    ("completed", "Completed"),
)

# Kept for the existing demo endpoints until the product API moves to projects.
TRANSACTION_STAGES: tuple[tuple[str, str], ...] = (
    ("approval_inclusion", "Approval / inclusion"),
    ("adviser_hiring", "Adviser hiring"),
    ("due_diligence", "Due diligence"),
    ("eoi_prequalification", "EOI / pre-qualification"),
    ("bidding", "Bidding"),
    ("approvals", "Approvals"),
    ("closing", "Closing"),
)

TRANSACTION_STAGE_LABELS = dict(TRANSACTION_STAGES)
PROJECT_STAGE_LABELS = dict(PROJECT_STAGES)
