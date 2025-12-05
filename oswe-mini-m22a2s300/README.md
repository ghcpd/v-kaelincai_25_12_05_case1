OSWE Mini Greenfield Replacement

This workspace contains a greenfield replacement prototype for an appointment scheduling system. It includes:
- src/: minimal runtime with in-memory DB, idempotency, outbox
- mocks/: external API mocks (calendar, notifications)
- data/: test input and expected output
- tests/: integration tests for crash points and resilience
- scripts to run tests and collect reports

See run_all.sh and run_tests.sh for usage.

Quick start:
- setup: ./setup.sh
- run unit & integration: ./run_tests.sh
- one-click integration runner: python run_one_click.py

Deliverables:
- architecture_and_delivery.md: analysis, design, migration plan, tests & acceptance
- compare_report.md: rollout guidance and metrics comparison template
- results/: run artifacts and aggregated metrics
