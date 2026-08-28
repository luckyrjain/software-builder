PR E — Release Readiness v2 Integration Implementation Plan v10

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Goal: Extend release readiness with backward-compatible manifest v2 and an optional production-readiness gate for exact release candidates.

Architecture: Preserve manifest-v1 behavior byte/semantics-wise, parse v2 through scripts/release_readiness_v2.py, reuse trusted candidate-scoped production-readiness evidence first, and conditionally invoke the child only when identity/context/capability are sufficient. Existing PR/K8s/incident release checks remain authoritative and unchanged.

Tech Stack: Python 3, YAML registry/composition/eval contracts, pytest, release manifest parsing, Markdown skill contracts.

Spec: ./2026-08-23-engineering-decision-delivery-after-pr159-design-v10.md

Global Constraints

• Execute only with the sibling v10 design artifact whose SHA-256 is 78f8810b1b7d45508c413eb46cff654824205cca8976d6319931dbe8456bf57b; if the file is missing or the digest differs, stop and re-review before implementation.
• Start every PR from fresh reviewed main; PR #159 is merged and must not be treated as a stacked prerequisite.
• Execute in a dedicated isolated clean worktree/branch. Before Task 0 and after every task commit, git status --porcelain must be empty; if unrelated changes appear, stop and isolate them before any git add -A.
• Preserve canonical registry ownership: edit skills.yaml and source registries, then regenerate projections with make generate; do not hand-edit generated projections.
• Machine gates fail closed on missing, stale, conflicting, untrusted, or target-mismatched evidence; UNKNOWN/NOT_APPLICABLE are never silently promoted to PASS.
• Preserve evidence authority through handoffs; producer trust never upgrades caller/model/repository evidence authority.
• Keep explicit PR/MR code-review ownership with pr-review; do not create competing numbered-PR owners.
• Use TDD for behavioral changes and run the repository-wide final gate before claiming the PR ready.
• Do not merge or perform destructive remote actions from this plan without explicit authorization.

Note: this file records the implementation-plan text supplied for PR E, preserved as-received for reference alongside the sibling v10 design artifact. Task-by-task execution and commit history for this work live in the git log of this branch.
