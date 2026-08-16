"""Scripted brain for the assignment agent's simulation mode.

Same idea as lab/simulated_brain.py: walks
runbooks/assignment-notify-svc-oom-crashloop.yaml step by step, prints a
Thought before each tool call, and stops at the real approval gate. Thought
text is built from whatever the last tool call actually returned.

Difference from the lab: the blast-radius checks (kill switch, error
budget, rate limiter) are called here as check_blast_radius(), not just
described in a prompt. I did it this way because relying on the model to
remember and follow a safety rule felt too easy to break -- putting the
check in code means it runs the same way no matter what this brain (or a
live Claude call) decides to do.
"""

import json


def _thought(text: str) -> None:
    print(f"[Agent Thought] {text}")


def _act(execute_tool, tool_name: str, tool_input: dict) -> str:
    print(f"\n[Agent Action] Calling tool: {tool_name}({json.dumps(tool_input)})")
    result = execute_tool(tool_name, tool_input)
    print(f"[Tool Result] {result}")
    return result


def _postmortem(bullets: list[str]) -> None:
    print(f"\n{'-' * 60}")
    print("[Postmortem Draft]")
    for bullet in bullets:
        print(bullet)
    print(f"{'-' * 60}")


def triage(incident: str, service: str, execute_tool, request_human_approval, check_blast_radius) -> None:
    _thought(
        f"Incident alert: '{incident}' names {service}. Per the runbook, step 1 "
        "(check_metrics) is to confirm this against live metrics before doing "
        "anything else."
    )
    metrics_raw = _act(execute_tool, "get_metrics", {"service": service})
    metrics = json.loads(metrics_raw)

    if metrics["restart_count_15m"] < 3 or metrics["error_rate"] <= 0.03:
        _thought(
            f"restart_count_15m={metrics['restart_count_15m']}, "
            f"error_rate={metrics['error_rate']}. Neither crosses this runbook's "
            "trigger (restart_count_15m >= 3 AND error_rate_5m > 0.03). Branch "
            "'below_threshold' applies: not a matching incident."
        )
        print("\n[Agent] Triage complete.")
        _postmortem(
            [
                f"- {service} metrics did not cross the OOM-crash-loop trigger threshold.",
                "- Runbook branch: below_threshold -> resolved with no action taken.",
            ]
        )
        return

    _thought(
        f"restart_count_15m={metrics['restart_count_15m']} and "
        f"error_rate={metrics['error_rate']} both cross the trigger. Runbook step 2 "
        "(check_pod_status): confirm this is actually a crash loop before assuming so."
    )
    pod_raw = _act(execute_tool, "get_pod_status", {"service": service})
    pod = json.loads(pod_raw)

    if not pod["crash_loop_backoff"]:
        _thought(
            "crash_loop_backoff=False. Elevated error rate without an active crash "
            "loop is outside this runbook's failure signature. Escalating rather "
            "than guessing at a different remediation."
        )
        print("\n[Agent] Escalating to on-call-primary.")
        _postmortem(
            [
                f"- {service} metrics crossed the trigger, but pod status showed no active crash loop.",
                "- Runbook branch: check_pod_status -> escalate (signature mismatch).",
                "- No remediation attempted; no approval gate was invoked.",
            ]
        )
        return

    _thought(
        f"crash_loop_backoff=True, restarts_15m={pod['restarts_15m']}, "
        f"memory_usage_pct={pod['memory_usage_pct']}, oom_killed_last={pod['oom_killed_last']}. "
        "This looks like a crash loop. Runbook step 3 (check_logs): confirm an "
        "OOM/heap signature before proposing any remediation."
    )
    logs = _act(execute_tool, "get_recent_logs", {"service": service, "tail": 30})

    if "OutOfMemoryError" not in logs and "heap space" not in logs:
        _thought(
            "No OutOfMemoryError / heap-space signature in the logs. A crash loop "
            "without that signature is likely a different root cause (e.g. a bad "
            "dependency) -- outside this runbook's scope. Escalating."
        )
        print("\n[Agent] Escalating to on-call-primary.")
        _postmortem(
            [
                f"- {service} is in a crash loop, but logs did not show an OOM/heap signature.",
                "- Runbook branch: check_logs -> escalate (signature mismatch, different root cause suspected).",
                "- No remediation attempted; no approval gate was invoked.",
            ]
        )
        return

    _thought(
        "Logs show repeated 'java.lang.OutOfMemoryError: Java heap space' followed "
        "by an OOMKilled restart -- this matches the runbook's memory-leak "
        "signature. Runbook step 4 (check_recent_deploy): note whether a recent "
        "deploy correlates, for the postmortem -- this does not change the "
        "remediation itself, restarting is the right first move either way."
    )
    deploy_raw = _act(execute_tool, "get_deployment_history", {"service": service})
    deploy = json.loads(deploy_raw)
    deployed_recently = "hour" not in str(deploy.get("deployed_at", "")) and "minute" in str(
        deploy.get("deployed_at", "")
    )
    if deployed_recently:
        deploy_note = (
            f"Deploy was {deploy.get('deployed_at')} -- likely a regression in "
            f"{deploy.get('current_version')}. Postmortem should recommend a code "
            "rollback in addition to the restart."
        )
    else:
        deploy_note = (
            f"Deploy was {deploy.get('deployed_at')} -- too long ago to be the "
            "trigger. This looks like a long-standing slow leak that just crossed "
            "the memory limit. Postmortem should recommend a heap-limit or "
            "leak-detection follow-up."
        )
    _thought(deploy_note)

    _thought(
        "Runbook step 5 (blast_radius_checks): before even running a dry run, "
        "every guardrail must pass -- kill switch, error budget, and the "
        "remediation rate limiter."
    )
    allowed, block_reason = check_blast_radius(service, metrics["error_budget_remaining"])
    if not allowed:
        _thought(
            f"Blast-radius check failed: {block_reason} Per the runbook, any failed "
            "check means escalate -- I will not attempt a dry run or a restart."
        )
        print("\n[Agent] Escalating to on-call-primary.")
        _postmortem(
            [
                f"- {service} matched the OOM-crash-loop signature (logs, pod status, and metrics all agreed).",
                f"- {deploy_note}",
                f"- Blast-radius control BLOCKED automated remediation: {block_reason}",
                "- Escalated to on-call-primary; no restart was attempted.",
            ]
        )
        return

    _thought("All blast-radius checks passed. Runbook step 6: dry_run_then_restart.")
    dry_run = _act(execute_tool, "dry_run_restart", {"service": service})

    _thought(
        f"Dry run confirms a safe rolling restart plan: '{dry_run}'. restart_service "
        "is a destructive action (it will briefly cycle live pods), so the runbook "
        "requires human approval before I may call it. Requesting approval now."
    )
    approved, approver = request_human_approval(f"restart_service on {service}")

    if not approved:
        print(
            "\n[Tool Result] Restart DECLINED by operator. "
            "Escalate to human on-call for manual intervention."
        )
        _thought(
            "Approval was declined. Per the runbook's approval_declined branch, I "
            "must not proceed. Escalating to human on-call for manual intervention."
        )
        print("\n[Agent] Escalating to on-call-primary.")
        _postmortem(
            [
                f"- {service} matched the OOM-crash-loop signature and passed all blast-radius checks.",
                f"- Dry run confirmed a safe rolling-restart plan: {dry_run}",
                "- Approval gate: operator DECLINED the restart.",
                "- Escalated to on-call-primary for manual intervention; no destructive action was taken.",
            ]
        )
        return

    # request_human_approval() stands in for a real, unbounded-latency human
    # decision -- guardrail state (kill switch, rate limiter, error budget)
    # could change while we waited. Don't trust the earlier check; re-verify
    # right before the destructive call actually fires.
    recheck_metrics = json.loads(_act(execute_tool, "get_metrics", {"service": service}))
    still_allowed, recheck_reason = check_blast_radius(
        service, recheck_metrics["error_budget_remaining"]
    )
    if not still_allowed:
        _thought(
            f"Blast-radius state changed while waiting for approval: {recheck_reason} "
            "Per the runbook, any failed check means escalate -- I will not restart."
        )
        print("\n[Agent] Escalating to on-call-primary.")
        _postmortem(
            [
                f"- {service} matched the OOM-crash-loop signature and was approved by {approver}.",
                f"- Blast-radius control BLOCKED at re-check, just before executing: {recheck_reason}",
                "- Escalated to on-call-primary; no restart was attempted.",
            ]
        )
        return

    restart_result = _act(
        execute_tool, "restart_service", {"service": service, "approved_by": approver}
    )

    _thought(
        "Restart executed and approved by a human. Runbook's final step (verify): "
        "re-check pod status to confirm the crash loop actually cleared before "
        "declaring this resolved."
    )
    verify_raw = _act(execute_tool, "get_pod_status", {"service": service})
    verify = json.loads(verify_raw)

    if not verify["crash_loop_backoff"]:
        _thought(
            f"Post-restart crash_loop_backoff={verify['crash_loop_backoff']}, "
            f"restarts_15m={verify['restarts_15m']}. The crash loop cleared. "
            "Branch 'crash_loop_cleared' applies: incident mitigated."
        )
        print("\n[Agent] Triage complete.")
        _postmortem(
            [
                f"- {service} entered an OOM crash loop (repeated OutOfMemoryError, OOMKilled restarts).",
                f"- {deploy_note}",
                "- All blast-radius checks (kill switch, error budget, rate limiter) passed before remediation.",
                f"- Restart approved by {approver} and executed: {restart_result}",
                "- Verified: crash_loop_backoff cleared after restart. Incident mitigated -- "
                "underlying leak still needs a code fix, tracked separately.",
            ]
        )
    else:
        _thought(
            f"Post-restart crash_loop_backoff={verify['crash_loop_backoff']} -- the "
            "crash loop did NOT clear. This confirms the leak is a real bug, not a "
            "transient condition. Escalating; the rate limiter will now block a "
            "second automated restart attempt for this service."
        )
        print("\n[Agent] Escalating to on-call-primary.")
        _postmortem(
            [
                f"- {service} entered an OOM crash loop; restart was approved and executed.",
                "- Verification failed: crash loop did not clear after restart.",
                "- Escalated to on-call-primary -- this needs a code fix, not another restart.",
                "- The rate limiter now blocks a second automated restart for this service for the cooldown window.",
            ]
        )
