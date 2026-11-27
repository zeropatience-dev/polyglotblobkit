# Security policy

## Scope

PolyglotBlobKit is an experimental beta candidate. There is no production
security certification, guaranteed support period or response-time SLA. Use
synthetic data in an isolated test environment; do not expose the preview gateway
publicly or process confidential documents with it.

## Report a vulnerability privately

Use the repository's Security tab → Report a vulnerability if private
vulnerability reporting is enabled. If that option is not available, contact the
maintainer privately through an available GitHub contact channel and request a
secure reporting route before sharing details. Do not post exploitable details,
credentials, personal data or real documents in a public issue, discussion or PR.
Do not upload them as artifacts or logs. Do not test other people's infrastructure
without explicit authorization.

Include affected version/commit, module, reproduction with synthetic data,
expected and observed behavior, impact and any suggested mitigation. Redact
secrets and environment identifiers. Coordinate public disclosure with the
maintainer; no fixed response time or bounty is promised.

## Integration responsibilities

- Use least-privilege credentials and verified identities. UUIDs are not secrets.
- Enforce authorization, tenant isolation, quotas and request limits on every path.
- Use TLS, safe logging, protected temporary storage, and deployment-managed secrets.
- Do not depend on the browser size limiter for security or signature checks for
  malware detection. The static RS256 example lacks automated key rotation and
  revocation; rate and concurrency limits are per process.
- Review dependencies, provider policies and configuration before any evaluation.

See [compatibility](docs/compatibility.md) for verification boundaries. No
project-operated telemetry or central file registry is required. Security-relevant
bindings must still come from trusted configuration.
