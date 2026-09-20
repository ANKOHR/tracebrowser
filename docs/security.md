# Security and safety boundaries

TraceBrowser is designed to stop transparently when a browser task leaves its allowed operating envelope.

- Navigation is restricted to task-configured domains.
- Downloads are disabled by default.
- External submission is disabled by default and requires both policy permission and an approval flag on the action.
- Action, page and runtime budgets are enforced.
- Authentication-required, CAPTCHA, robot-check and access-denied signals stop a run; the runtime does not bypass them.
- DOM evidence is bounded to limit accidental artifact growth.
- Run history, failures and audit events are append-oriented records.
- The data model carries organization IDs, but production identity/session authentication is not implemented in this local project.
- A PostgreSQL-ready SQLAlchemy URL is supported through an optional `psycopg` dependency; local verification uses SQLite.

Do not put real credentials, personal inboxes or sensitive customer data into the synthetic showcase. The demo websites are intentionally local and credential-free.
