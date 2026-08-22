# Changelog — security-review

## 1.0.0 — 2026-08-22

### Added

- Initial release: a dedicated security review skill covering authentication, authorization (incl.
  tenant isolation), secrets handling, injection, SSRF, data leakage, cryptography, and dependency
  exposure over supplied code/config/design content, via a linear `Inputs → Analyze → Report`
  pipeline producing `SECURITY_REVIEW_REPORT.md`.
