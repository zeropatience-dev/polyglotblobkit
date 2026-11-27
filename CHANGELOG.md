# Changelog

Dates are omitted where not independently recorded. Version labels before the
beta describe development milestones, not necessarily published packages.

## 0.9.0-beta.1 — candidate, not yet released

- Prepared public-facing quickstart, contribution and private security reporting
  guidance, issue templates, compatibility matrix and beta release notes.
- Updated Python package version to `0.9.0b1` (PEP 440); no new runtime feature.
- Documented resource efficiency without promising cost savings.
- Retained historical test reports and runtime compatibility boundaries.

## 0.8.0 — integration preview

- Integrated optional authenticated HTTP gateway and Docker build configuration.
- Added resilience, authorization and parallel simulated round-trip tests.
- Recorded project philosophy and reversible metadata format.
- REST prototype from 0.5.0 was unavailable and reimplemented, not merged.

## 0.7.0 — storage preview

- Added optional S3 and MinIO adapters and SDK contract tests.

## 0.6.0 — security preview

- Added opt-in tenant bindings, authorization, per-tenant limits, static RS256
  verification and local audit events.

## 0.5.0 — prototype milestone

- Separate REST prototype; not retained as an independent commit in this history.

## 0.4.0

- Renamed to PolyglotBlobKit, preserved legacy Python imports, added shared JSON
  policy and eight draft UI translations.

## 0.3.0

- Added browser preflight, explicit legacy reads and Azurite CI configuration.

## 0.2.0

- Added configurable per-file size limits (default 50 decimal MB).

## 0.1.0

- Initial UUID naming and lossless Unicode filename metadata reference library.
