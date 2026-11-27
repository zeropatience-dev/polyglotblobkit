# Contributing

Thank you for helping evaluate PolyglotBlobKit. Read [the philosophy](PHILOSOPHY.md)
and [compatibility and limitations](docs/compatibility.md) first. For this beta
candidate, fixes, reproducible reports, documentation and tests take precedence
over new functionality. Use synthetic data and systems you are authorized to test.

## Report a regular bug

Open an issue using the bug or compatibility template. Include version/commit,
OS, Python/Node and SDK versions, selected modules, provider or emulator version,
expected/actual results and a minimal reproduction. Never share real customer
files, tokens, connection strings or sensitive logs. Report security issues
privately as described in [SECURITY.md](SECURITY.md).

## Submit changes

Create a branch from the current main branch; keep changes focused. Add a test
for a bug fix, preserve the legacy import and metadata contract unless a change
is explicitly discussed, and document changed behavior and limitations. Retain
license notices and disclose relevant third-party code and its license. Review
AI-assisted changes just as you would any other change.

From a virtual environment in the repository root:

```sh
python -m pip install '.[security,s3,http,test]'
python -m unittest discover -s tests -v
python tools/generate_messages.py --check
node --test web/*.test.mjs
```

Node 22 is the reference JS test runtime. For translation changes, update
`blob_filename_fix/messages.json`, run `python tools/generate_messages.py`, and
review the generated browser catalog. Follow the relevant integration test
instructions if you have an isolated emulator or dedicated test account.

Open a pull request describing the problem, changes, tests actually run and
remaining risks. Do not claim unexecuted tests or universal compatibility.
By submitting a contribution, you agree that your contribution may be distributed
under the repository's MIT license, and confirm you have the right to submit it.
