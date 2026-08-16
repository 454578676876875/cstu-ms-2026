.PHONY: help policy policy-fail policy-injected policy-deprecated policy-all test validate plan plan-all clean

# The policy targets only need conftest -- they run against the plan JSON that
# is committed under plans/. The terraform targets regenerate that JSON and need
# terraform, but NOT an AWS account (mock creds + skip_* flags, see any s3.tf).

VARIANTS := compliant noncompliant injected deprecated-inline

help:
	@echo "Policy targets (need conftest only):"
	@echo "  make policy            - compliant plan          -> expect PASS"
	@echo "  make policy-fail       - Step 4 broken plan      -> expect 1 FAIL"
	@echo "  make policy-injected   - Step 5 injected plan    -> expect 2 FAIL"
	@echo "  make policy-deprecated - deprecated inline style -> expect 1 FAIL + 2 WARN"
	@echo "  make policy-all        - all four, in order"
	@echo "  make test              - Rego unit tests (conftest verify)"
	@echo ""
	@echo "Terraform targets (need terraform; no AWS account required):"
	@echo "  make validate          - terraform validate for every variant"
	@echo "  make plan-all          - regenerate every plans/tfplan-*.json"
	@echo "  make clean             - remove .terraform dirs and binary plans"

# --- policy checks -------------------------------------------------------

policy:
	conftest test plans/tfplan-compliant.json --policy policy/

policy-fail:
	@echo "Expect 1 FAILURE -- that is the Step 4 guardrail blocking a bad plan:"
	-conftest test plans/tfplan-noncompliant.json --policy policy/

policy-injected:
	@echo "Expect 2 FAILURES -- OPA blocking the prompt-injected plan:"
	-conftest test plans/tfplan-injected.json --policy policy/

policy-deprecated:
	@echo "Expect 1 FAILURE + 2 WARNINGS -- deprecated syntax warns, missing PAB denies:"
	-conftest test plans/tfplan-deprecated-inline.json --policy policy/

policy-all: policy policy-fail policy-injected policy-deprecated

test:
	conftest verify --policy policy/

# --- terraform -----------------------------------------------------------

validate:
	@for v in $(VARIANTS); do \
		echo "--- $$v ---"; \
		terraform -chdir=terraform/$$v init -input=false -backend=false >/dev/null && \
		terraform -chdir=terraform/$$v validate; \
	done

plan-all:
	@for v in $(VARIANTS); do \
		echo "--- $$v ---"; \
		terraform -chdir=terraform/$$v init -input=false >/dev/null && \
		terraform -chdir=terraform/$$v plan -input=false -out=tfplan.binary >/dev/null && \
		terraform -chdir=terraform/$$v show -json tfplan.binary > plans/tfplan-$$v.json && \
		echo "wrote plans/tfplan-$$v.json"; \
	done

clean:
	rm -rf terraform/*/.terraform terraform/*/tfplan.binary
