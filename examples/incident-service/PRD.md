# Incident Desk — production-oriented acceptance benchmark
An internal operations team needs a small single-tenant incident API for up to
20 operators. No frontend is required. The service must run on one persistent
host behind the organization's TLS reverse proxy. It must not expose incident
data without an API key. The key is supplied at runtime, never committed.

REQ-001: Persist incident titles and open/resolved status in SQLite. Preserve
records over process restarts. Use parameterized SQL and atomic transactions.
REQ-002: POST /incidents accepts a nonempty title up to 120 characters and
returns 201 with an ID. Reject malformed JSON and invalid input with 400.
REQ-003: GET /incidents returns newest first with limit (1..100) and offset
(nonnegative). Defaults are 20 and 0. Clients cannot read data without X-API-Key.
REQ-004: PATCH /incidents/{id} allows open/resolved only; return 404 for an unknown
ID, 400 for invalid status, and 401 for missing or incorrect API keys.
REQ-005: GET /healthz is public and returns 200 when storage is usable, 503 when
storage is unavailable. Error responses must not expose stack traces or keys.
REQ-006: Provide repeatable tests, launch instructions, graceful termination,
and deployment notes covering TLS termination, one-host scope, secret rotation,
SQLite backup/restore, and persistent-volume permissions.

Non-goals: public internet deployment in this test, external identity provider,
multi-tenancy, high availability, attachments, billing, or production load tests.
No deployment is authorized by running this benchmark.

Change scenario after initial completion: title maximum becomes 80 characters.
Existing stored titles remain readable. New oversized titles must be rejected.
