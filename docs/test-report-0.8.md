# Local verification — 0.8 integration preview

- Python 3.13.5: 111 tests passed, zero failures or skips (93 inherited + 18 new HTTP/integration tests).
- Node.js 22: 15 tests passed, zero failures or skips.
- Translation catalog consistency: passed.
- Wheel build and installed import / old namespace alias / translation smoke: passed.
- Parallel simulated round trip: 40 files, eight caller threads, unique keys and SHA-256 equality.
- Simulated client disconnect: no cloud write; subsequent upload succeeds.
- Simulated provider error: redacted HTTP response; subsequent upload succeeds.
- HTTP size, capacity and per-tenant request limits; cross-tenant denial; real RS256 token signatures: passed.
- Filename recovery using only standard Python Base64/UTF-8: passed on simulated storage.

The HTTP tests use an in-process ASGI transport, not a real external network.
Storage providers are mocked or SDK-stubbed. No cloud performance benchmark,
Docker execution, Azurite, live providers, real browser or external security
review was performed. The earlier 0.5 prototype was unavailable and was
reimplemented from the 0.7 codebase. The test results do not establish production readiness.
