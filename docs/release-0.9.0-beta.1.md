# PolyglotBlobKit v0.9.0-beta.1 — draft release notes

**Trust through transparency, not dependency.**

First intended public beta of our modular, multilingual file upload and object
storage toolkit. This is a draft; publication and final release checks are pending.

## Included

- UUID object keys with exact Unicode names in documented metadata.
- Configurable browser and backend upload limits and shared JSON policy.
- Eight draft translations; explicit legacy reads; optional Azure, S3 and MinIO
  adapters; optional security and HTTP gateway previews.
- Quickstart, contribution guidance, security reporting instructions and issue
  templates. No new runtime functionality compared to 0.8 integration preview.

Early validation can reduce unnecessary resource consumption and potentially
costs, depending on workload and infrastructure pricing. No savings are guaranteed.

## Test scope and warnings

See [compatibility](compatibility.md) and the exact Actions runs for the release
commit. Previous tests include mock/SDK contracts, Azurite and browser checks
reported by the maintainer, but live cloud validation and independent security
review remain open. Use synthetic data in isolated test environments only; do not
use the gateway in production or on the public Internet. No mandatory hosted
service or project telemetry is required; you control your infrastructure and
its costs. License: MIT.

## Feedback

Non-sensitive bugs and compatibility results: GitHub Issues. Vulnerabilities:
private reporting as described in [SECURITY.md](../SECURITY.md). External testers
are invited to report environment, reproduction, expected and observed behavior.
