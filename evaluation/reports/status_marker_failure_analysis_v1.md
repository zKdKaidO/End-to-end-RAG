# Status Marker Failure Analysis V1

- Previous failure case: `v2_bank_loan_limit_exceptions`
- Previous raw output contained two complete answer/status blocks.
- Reproduction runs: 3
- Duplicate markers reproduced: 3
- Strict parser changed: **NO**

The duplicate was already present in raw provider text, so it was not created by streaming or parsing. It reproduced identically in all three new runs. The old combined formulation therefore has a repeatable prompt/model output-contract failure, plausibly primed by repeated marker descriptions/examples and the absence of an explicit no-repeat rule. Multiple markers remain invalid and are not silently accepted.
