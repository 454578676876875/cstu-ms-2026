"""Approval gate shared by both agents.

Just a terminal input() standing in for a Slack "confirm" button -- it
actually blocks until someone answers, and it asks for a name so there's
something resembling an audit trail.
"""


def request_human_approval(action: str) -> tuple[bool, str]:
    print(f"\n{'=' * 60}")
    print(f"[APPROVAL GATE] Agent requests permission to: {action}")
    print(f"{'=' * 60}")
    response = input("Approve? (yes/no): ").strip().lower()
    if response != "yes":
        return False, ""

    approver = input("Enter your name for the audit log: ").strip()
    while not approver:
        approver = input("Name can't be blank -- enter your name for the audit log: ").strip()
    return True, approver
