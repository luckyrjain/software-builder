# Security Policy

## Supported versions

This repository does not yet publish tagged releases — `main` is the only supported line. Security
fixes land as regular commits/PRs against `main`; there is no backport policy until a release process
exists (tracked in the repository backlog).

## Reporting a vulnerability

**Please do not open a public GitHub issue for a security report.** Use
[GitHub Security Advisories](../../security/advisories/new) for this repository to report privately —
this reaches the maintainers without disclosing the issue publicly while a fix is prepared.

If you cannot use Security Advisories, open a regular issue that says only "security issue, please
contact me privately" with a way to reach you, and a maintainer will follow up out of band.

Include, where applicable:

- The affected skill(s) or shared framework file(s).
- Whether the issue is exploitable through untrusted content a skill ingests (an MR description, a
  ticket body, a webhook payload, a log paste — see
  [docs/skill-framework/shared/prompt-injection.md](docs/skill-framework/shared/prompt-injection.md))
  versus a defect in a script (`scripts/`, `*/scripts/`).
- A reproduction: the exact invocation/input, and the unsafe behavior observed.
- Your assessment of impact (unauthorized write/post/merge, data exposure, credential handling).

## Scope

This repository is a library of **agent instructions** (Markdown skill definitions) plus a small number
of Python/Bash helper scripts. Its security-relevant surface is narrower than a typical application:

- **In scope:** a skill's documented guardrails being bypassable via crafted input (prompt injection
  achieving an unauthorized write, merge, or credential exposure); a helper script under `*/scripts/`
  with a real injection/traversal/RCE path; the installer (`scripts/install.sh`) behaving unsafely
  (path traversal, unintended overwrite outside the target directory); secrets committed to the
  repository.
- **Out of scope:** the underlying model's general susceptibility to prompt injection (report that to
  the model/host provider), vulnerabilities in third-party MCP servers this repository's setup docs
  reference (e.g. `@zereight/mcp-gitlab`) — report those upstream — and purely theoretical concerns with
  no concrete exploitation path through a skill's actual documented workflow.

## Design context for reviewers

Every skill treats content it reads from external sources (MR/PR descriptions, issue/ticket bodies,
webhook payloads, log pastes, CODEOWNERS files, etc.) as untrusted data, never as instructions — see
[docs/skill-framework/shared/prompt-injection.md](docs/skill-framework/shared/prompt-injection.md) for
the normative rule and [docs/skill-framework/shared/safe-output.md](docs/skill-framework/shared/safe-output.md)
for output-side sanitization (filenames, paths, rendered Markdown). A report showing a concrete case
where a skill's actual documented behavior violates one of these is exactly the kind of finding this
policy exists for.
