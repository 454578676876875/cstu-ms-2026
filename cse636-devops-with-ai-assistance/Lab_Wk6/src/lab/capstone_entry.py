"""Capstone integration point: run the Week 6 lab's ReAct agent with an incident description
supplied on argv (from ../capstone/pipeline.py, built out of Lab_Wk5's real anomaly signal)
instead of the hardcoded string in react_agent.py's __main__. No agent/runbook logic changes --
same run_agent(), same tools, same approval gate.
"""
import sys

from react_agent import run_agent  # sibling import -- script's own dir is on sys.path[0]

if __name__ == "__main__":
    incident = sys.argv[1] if len(sys.argv) > 1 else (
        "ALERT: payment-svc error rate has been above 5% for the past 4 minutes."
    )
    run_agent(incident)
