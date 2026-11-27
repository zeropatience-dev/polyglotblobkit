# Compatibility and verification matrix

Status at beta preparation. A passed unit test or emulator job is not a live
provider result. The 0.8 GitHub check statuses below were reported by the
maintainer; exact CI logs and versions should be reviewed before release.

| Area | Evidence / scope | Remaining gaps |
| --- | --- | --- |
| Python core | 0.8 local Python 3.13: 111 tests across modules; initial GitHub unit checks reported green; CI configured for 3.10 and 3.13 | Other versions, OS and application integrations not independently verified |
| JavaScript | 0.8 local Node 22: 15 tests; Chromium smoke reported green in initial GitHub import | Safari, Firefox, desktop/mobile integration and full real drag gestures |
| Unicode | Exact UTF-8 metadata round trips and edge cases in tests | Arbitrary external filesystem rules and UI rendering; no universal compatibility claim |
| Azure | Mock/SDK behavior and Azurite check reported green | Actual Azure account, Data Lake/SFTP, scoped tenant credentials, external systems |
| S3 | boto3 Stubber and fake storage | Live AWS, policy and versioning behaviors |
| MinIO | S3-compatible adapter and fake/contract tests | Real MinIO endpoint and versions |
| HTTP | In-process ASGI tests and simulated errors | Real network failure, reverse proxy, production deployment |
| Docker | Build check reported green on initial GitHub import | Running deployment and operational behavior |
| Security | Negative tests, JWT signatures and simulated tenant isolation | Independent review, identity lifecycle, true provider isolation, distributed limits |
| Reversibility | Standard Base64/UTF-8 recovery tested with simulated storage | Live migration, metadata-preserving copy, full export utility |
| Performance | 40 simulated round trips with eight caller threads in 0.8 | Production throughput, disk pressure and memory benchmarks |
| i18n | Eight draft catalogs, consistency checks, Arabic RTL demo | Professional linguistic/accessibility review |

The old documentation in this repository records previous milestone-specific
limitations, some of which were addressed by 0.8. No production-ready claim is
made. The beta candidate does not include complete MIME preservation, extension
preservation, malware detection, multi-worker quotas or a dynamic tenant admin API.
No automatic cloud migration or integration into closed third-party UIs is provided.

## Dependency and release checks

Run the tests in [CONTRIBUTING.md](../CONTRIBUTING.md) and review the exact GitHub
Actions logs for the release commit. A fresh, isolated virtual environment with
all supported extras installed is needed to audit the resolved dependencies:

```sh
python -m pip install '.[azure,s3,minio,security,http,test]' pip-audit
python -m pip check
python -m pip_audit
```

This requires network access to install packages and query a vulnerability
service. It may report known vulnerabilities in direct or transitive packages;
review and resolve applicable findings rather than ignoring them. A clean result
is not proof of security. Dependency versions are ranges, not a frozen lockfile;
record the versions and date of the audit, and repeat for supported environments.
No successful vulnerability audit is claimed by this documentation.
