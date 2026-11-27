# PolyglotBlobKit

*Every Language. Every File. Every Storage.*

**Trust through transparency, not dependency.**

PolyglotBlobKit is a modular, multilingual, MIT-licensed toolkit for separating
technical object keys from human filenames, validating uploads and integrating
with object storage. It is an independent project, not an official Azure fix.

**Public beta candidate v0.9.0-beta.1:** for evaluation with synthetic data in
isolated test environments only. Do not use the gateway for production workloads,
confidential files or Internet-facing services. No independent security review
or live cloud validation has been completed. See [compatibility](docs/compatibility.md)
and [security policy](SECURITY.md).

## Choose only what you need

| Module | Integration |
| --- | --- |
| Unicode filenames | Python helpers; UUIDv4 keys and lossless metadata |
| Browser preflight | Dependency-free JavaScript size checks |
| Backend limiter | Python byte/stream validation before storage |
| Shared policy and i18n | JSON configuration; eight draft translations |
| Azure adapter | Optional Azure SDK integration, including explicit legacy reads |
| S3 / MinIO adapters | Optional boto3 integration; preview |
| Security / HTTP gateway | Optional authenticated tenant gateway; experimental |

No project-operated cloud service or registry is required at runtime. Your
application must integrate the selected modules; closed third-party systems are
not automatically patched. The project does not transmit diagnostic telemetry.
Storage SDKs and optional services may have their own network behavior.

Early rejection can reduce unnecessary transfer, processing and storage; actual
cost savings depend on the workload and billing model. No savings are guaranteed.

## Quickstart — no cloud account needed

Clone or download the repository and open a terminal in its root. Python 3.10+
is required. For the standalone Python core, use a virtual environment:

```sh
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` in Windows PowerShell (or use
`.venv\Scripts\python.exe` directly), or `source .venv/bin/activate` on macOS/Linux.
Then run:

```sh
python -m pip install .
python -c "from polyglotblobkit import new_key, encode_filename, decode_filename; n='Rechnung_Müller_東京.pdf'; print(new_key()); assert decode_filename(encode_filename(n)) == n"
```

The install uses the source checkout; no public package registry release is
assumed. Build tooling may be downloaded by pip. The core has no runtime package
dependencies. Older `blob_filename_fix` imports are retained; uninstall any old
`universal-blob-filename-fix` distribution first to avoid overlapping files.

Try the browser-only demo (from the repository root):

```sh
python -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/web/`, choose a language and a size limit, and drop a
synthetic test file. The demo checks the browser's file size locally and does not
upload contents. Stop the server with Ctrl+C. Do not expose this development
server to other machines. The default demo limit is 5 MB; the library defaults to
50 MB. `1 MB = 1,000,000 bytes`; exactly the configured limit is accepted.

## Integrate the standalone modules

```python
from polyglotblobkit import UploadSizeLimiter, UploadTooLargeError

try:
    with UploadSizeLimiter(5).checked(b'example') as data:
        pass  # pass data to a synchronous storage writer within this context
except UploadTooLargeError:
    pass  # reject the request (HTTP 413 in an HTTP application)
```

Binary streams are staged locally, spilling to temporary disk above 1 MiB.
Configure disk, concurrency, request and time limits separately. Browser checks
are for user experience, not security; direct uploads can bypass them.

```javascript
import { validateFiles } from './web/upload-limiter.mjs';
const { accepted, rejected } = validateFiles(files, 5);
// Show rejected files safely; send only accepted files to your upload handler.
```

Use `config.example.json` for shared policy, and `Config.load` / `browser_policy()`
for trusted server-owned settings. UI settings must not override server policy.
See [integration guidance](docs/quickstart.md) for storage and HTTP examples.

## Filename contract and reversibility

New keys are UUIDv4 as 32 lowercase hexadecimal characters, without a suffix.
The original filename is stored in `original_filename_b64` metadata: standard
Base64 of its exact UTF-8 bytes. Base64 is not encryption. No normalization or
transliteration is applied. Empty names, `.` / `..`, path separators and control
characters are rejected, and filenames are limited to 1024 UTF-8 bytes.

An independent program can recover the name using
`base64.b64decode(value).decode('utf-8')`. Preserve metadata and the application's
key/ownership references during backup or migration. Never treat recovered names
as trusted local paths. Existing objects are not renamed or migrated automatically.
New writes are conditional; collisions are rejected rather than overwritten.
There is no automatic provider migration or full export tool.

## Verification and known limitations

See [compatibility and test scope](docs/compatibility.md), the historical
[0.8 local test report](docs/test-report-0.8.md) the [beta preparation report](docs/test-report-0.9-beta-preparation.md) and the repository Actions logs.
Local unit tests, simulated HTTP/storage tests and SDK contract tests do not
establish production security or universal compatibility. The maintainer reported
successful Azurite, browser smoke, build and unit checks on the initial GitHub
import; exact job logs should be reviewed before the beta is published.

No live Azure, AWS S3 or MinIO results or independent security review are claimed.
MIME/extension preservation, distributed limits, full identity-provider lifecycle,
malware detection and per-document authorization are not implemented as complete
solutions. See [security preview](docs/security-preview.md), [storage preview](docs/storage-preview.md)
and [HTTP integration preview](docs/integration-preview.md) for detailed design;
these are historical preview documents, not new beta test results.

## Contribute

Use GitHub Issues for reproducible non-sensitive bugs, and read
[CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes. Use the private
security reporting route described in [SECURITY.md](SECURITY.md) for vulnerabilities.
See [CHANGELOG.md](CHANGELOG.md), [release notes](docs/release-0.9.0-beta.1.md) and
[PHILOSOPHY.md](PHILOSOPHY.md). This project is developed with AI assistance;
maintainers remain responsible for review and release decisions.

## Deutsch

PolyglotBlobKit ist ein modularer Open-Source-Baukasten für internationale
Dateinamen und kontrollierte Uploads. Einzelne Module sind unabhängig nutzbar.
Die Beta ist ausschließlich für isolierte Tests mit unkritischen Beispieldaten
bestimmt. Kein offizieller Azure-Fix, keine Produktionsfreigabe.

## License

[MIT](LICENSE). Retain the copyright and license notices on redistribution.
