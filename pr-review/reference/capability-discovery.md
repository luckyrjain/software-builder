# Repository capability discovery

Infer technology stack from the repo **after** Phase 1 step 2 builds the review boundary. Enables
checklist dimensions without relying only on diff keywords. Complements static `review-rules.yaml`.

Load in Phase 1 after fast-path classification. Pass **`capability_profile`** to Phase 2.

## Output

```
capability_profile: {
  detected_from: ["go.mod", "k8s/", "package.json"],
  capabilities: {
    kubernetes: true,
    terraform: false,
    spring: false,
    react: true,
    llm: false,
    postgres: true,
    ...
  },
  enabled_checklist_triggers: ["§9", "§17", "§15?"]
}
```

Store in session with `context_cache` when unchanged; re-infer when manifest/directory fingerprints change.

## Discovery signals

| Signal | Capability | Phase 2 effect |
|--------|------------|----------------|
| `k8s/`, `helm/`, `Chart.yaml`, `*deployment*.yaml` | **kubernetes** | §17 rollback, deploy/IaC checks; SRE-relevant §9 |
| `*.tf`, `terraform/`, `.terraform.lock.hcl` | **terraform** | §17 state/drift; infra review hints |
| `pom.xml`, `build.gradle`, `@SpringBootApplication` in boundary | **spring** | §4 transactions, §17 migration coupling |
| `package.json` + `react`/`next`/`vue` deps | **react** | §4 rendering/perf; client bundle hints |
| `go.mod`, `Cargo.toml`, `requirements.txt`, `Gemfile` | **runtime** | language-appropriate §2/§4 |
| `langchain`, `openai`, `anthropic` in deps or diff | **llm** | §15 AI/LLM (also keyword trigger) |
| `docker-compose`, `Dockerfile` | **containers** | §17 deploy, config drift |
| `.github/workflows`, `.gitlab-ci.yml` in boundary or root read | **ci** | Phase 1 CI heuristics context |

Use **root manifest reads** (cached in `context_cache`) plus **changed paths** in boundary. Do not scan
entire repo tree — cap at root + parent dirs of changed files for monorepos.

## Merge with review-rules.yaml

When repo YAML defines domains (payments, search), **union** with `capability_profile`:

- YAML `always_review` beats fast-path skip for that dimension (`reference/precedence.md`).
- Capability flags **enable** optional § triggers; they do not disable non-negotiable checks.

## Phase 2 usage

1. Print one line when non-obvious: *"ℹ️ **Stack:** Kubernetes, React — enabled deploy + client perf checks."*
2. Weight persona auto-detect (SRE if k8s+prod deploy in diff).
3. Feed detectors in `reference/detection-vs-judgment.md` — do not skip §17 on k8s MRs when
   `fast_path.skip_rollback` is false and capability is set.

## Anti-patterns

- **Do not** infer capabilities from unrelated repos in a monorepo — scope to changed module paths.
- **Do not** enable §15 on every JS repo — require LLM dep or diff keyword.
- **Do not** re-read all manifests on every re-review if cached fingerprints unchanged.
