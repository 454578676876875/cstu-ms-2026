"""Approval gate shared by both agents. Same pattern as Lab_Wk6's common/approval_gate.py:
a blocking input() standing in for an approval UI (GitHub environment reviewer, Jenkins
`input` step). Blocks until answered, and records who approved for an audit trail.
"""


def request_human_approval(action: str) -> tuple[bool, str]:
    print(f"\n{'=' * 60}")
    print(f"[APPROVAL GATE] {action}")
    print(f"{'=' * 60}")
    response = input("Approve? (yes/no): ").strip().lower()
    if response != "yes":
        return False, ""

    approver = input("Enter your name for the audit log: ").strip()
    while not approver:
        approver = input("Name can't be blank -- enter your name for the audit log: ").strip()
    return True, approver
