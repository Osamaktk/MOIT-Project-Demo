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
