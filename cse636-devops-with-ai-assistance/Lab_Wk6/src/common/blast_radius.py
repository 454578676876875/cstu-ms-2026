"""Blast-radius controls for the assignment agent.

Three of the guardrails from week-06-notes.md's "Levels of Autonomy &
Blast-Radius Control" section:

- KillSwitch: one env var, if set, turns off all automated remediation.
  The notes say every autonomous system needs one of these, so I made it
  the simplest thing I could -- an env var check.
- RemediationRateLimiter: only lets a service get "fixed" once per cooldown
  window. This is meant to stop the classic flapping problem where the
  agent restarts something, it breaks again, and the agent restarts it
  again forever.
- ErrorBudgetGate: won't let the agent burn through what's left of a
  service's error budget on an automated guess -- below some floor it has
  to hand off to a human instead.
"""

import os
import time


class KillSwitch:
    ENV_VAR = "AUTOHEAL_KILL_SWITCH"

    def is_engaged(self) -> bool:
        return os.environ.get(self.ENV_VAR, "").strip().lower() in ("1", "true", "yes", "on")


class RemediationRateLimiter:
    def __init__(self, min_interval_seconds: float = 600):
        self.min_interval_seconds = min_interval_seconds
        self._last_action_at: dict[str, float] = {}

    def check(self, service: str) -> tuple[bool, float]:
        """Return (allowed, seconds_remaining_until_allowed)."""
        last = self._last_action_at.get(service)
        if last is None:
            return True, 0.0
        elapsed = time.monotonic() - last
        remaining = self.min_interval_seconds - elapsed
        return remaining <= 0, max(remaining, 0.0)

    def record(self, service: str) -> None:
        self._last_action_at[service] = time.monotonic()


class ErrorBudgetGate:
    def __init__(self, min_budget_remaining: float = 0.2):
        self.min_budget_remaining = min_budget_remaining

    def allows(self, error_budget_remaining: float) -> bool:
        return error_budget_remaining >= self.min_budget_remaining
