# Source Profiles

A source profile records the **authorization basis** under which CSIP may
collect from a platform or supplier data source. Per `goals.md` G1 and
`agent.md` section 6:

- A source MUST NOT be enabled without: access basis, approved methods, page
  scope, rate limits, retention rules, owner, approval evidence, review/expiry
  date, and stop conditions.
- Approval status is change-controlled and time-bounded (`ApprovalEvidence`,
  `approval_expires_at`).
- A permissive robots.txt is **never** treated as authorization.
- The deterministic policy evaluator (`csip.services.source_policy`) enforces
  these fields at request time; it fails closed.

## Template

```markdown
## <source name>

- source_id: <namespace:id>
- canonical_domain: <host>
- owner: <team/person>
- access_basis: official_api | partner_integration | supplier_export | written_permission | permitted_public_pages
- approved_methods: [lowest-complexity first]
- allowed_page_families: [...]
- allowed_hosts / url patterns: [...]
- rate_limits: {requests/min, concurrency, pages/run}
- retention: {raw_days, artifacts, redistribution}
- approval evidence: reviewer, date, reference (contract/ticket)
- approval_expires_at: <date>
- stop_conditions: [403, captcha, login, rate, ...]
```

No live source is registered yet. The `fixture:synthetic-supplier` profile used
in tests is synthetic and grants only the local `fixture` method.
