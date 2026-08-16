from common.blast_radius import ErrorBudgetGate, KillSwitch, RemediationRateLimiter


class TestKillSwitch:
    def test_not_engaged_by_default(self, monkeypatch):
        monkeypatch.delenv(KillSwitch.ENV_VAR, raising=False)
        assert KillSwitch().is_engaged() is False

    def test_engaged_for_truthy_values(self, monkeypatch):
        for value in ("1", "true", "True", "yes", "on"):
            monkeypatch.setenv(KillSwitch.ENV_VAR, value)
            assert KillSwitch().is_engaged() is True, value

    def test_not_engaged_for_empty_or_zero(self, monkeypatch):
        for value in ("", "0", "false", "off"):
            monkeypatch.setenv(KillSwitch.ENV_VAR, value)
            assert KillSwitch().is_engaged() is False, value


class TestRemediationRateLimiter:
    def test_allows_first_action(self):
        limiter = RemediationRateLimiter(min_interval_seconds=600)
        allowed, remaining = limiter.check("notify-svc")
        assert allowed is True
        assert remaining == 0.0

    def test_blocks_second_action_within_cooldown(self):
        limiter = RemediationRateLimiter(min_interval_seconds=600)
        limiter.record("notify-svc")
        allowed, remaining = limiter.check("notify-svc")
        assert allowed is False
        assert remaining > 0

    def test_allows_again_after_cooldown_elapses(self, monkeypatch):
        limiter = RemediationRateLimiter(min_interval_seconds=1)
        limiter.record("notify-svc")

        real_monotonic = __import__("time").monotonic
        monkeypatch.setattr(
            "common.blast_radius.time.monotonic", lambda: real_monotonic() + 2
        )
        allowed, remaining = limiter.check("notify-svc")
        assert allowed is True
        assert remaining == 0.0

    def test_cooldown_is_per_service(self):
        limiter = RemediationRateLimiter(min_interval_seconds=600)
        limiter.record("notify-svc")
        allowed, _ = limiter.check("payment-svc")
        assert allowed is True


class TestErrorBudgetGate:
    def test_blocks_below_floor(self):
        gate = ErrorBudgetGate(min_budget_remaining=0.2)
        assert gate.allows(0.1) is False

    def test_allows_at_floor(self):
        gate = ErrorBudgetGate(min_budget_remaining=0.2)
        assert gate.allows(0.2) is True

    def test_allows_above_floor(self):
        gate = ErrorBudgetGate(min_budget_remaining=0.2)
        assert gate.allows(0.55) is True
