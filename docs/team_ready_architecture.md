# Team-ready Architecture

The product remains a single-user, local-only application. `local-user` is created as an
`owner`; roles `owner`, `developer`, and `viewer` are schema-level preparation only.
Projects and tasks store creator, assignee, local user, and `private` visibility metadata.

A future team version still requires authenticated identities, tenant isolation, access
checks on every project/task/artifact query, encrypted transport, audit retention, concurrent
edit policy, and secret management. None of those controls may be inferred from the current
role columns.

Do not expose the server on an untrusted network or enable shared visibility before real
authentication and authorization exist. The current CORS and host defaults are intended for
localhost use.
