# Provider adapters

Use one review policy for every provider. Adapt only target resolution, retrieval, anchoring, posting,
and head-SHA verification.

## Normalized target

Inputs produces this immutable object before Phase 0:

```yaml
review_target:
  provider: github | gitlab
  host: github.com | github.example.com | gitlab.com | gitlab.example.com
  authority: github.com:443 | github.example.com:8443 | gitlab.com:443 | gitlab.example.com:9443
  repository_path: owner/repo | group/project
  review_number: 482
  web_url: https://host/...
```

Use **PR #N** for GitHub and **MR !N** for GitLab in rendered output. An explicit review URL wins over
`origin`; if that supplied URL is unsupported or unconfirmed, stop without consulting `origin`. The
hostname and normalized authority (lowercase hostname plus explicit/effective port) never change after
Inputs. A bare number is valid only when the provider, authority, and repository are unambiguous.

For a custom enterprise hostname that cannot be inferred from its name, use the connected provider MCP/App
descriptor or exact-host `gh auth status` to classify the host before accepting a current-branch or bare-
number request. Only `github.com` and `gitlab.com` are recognized without configuration; host-name
prefixes are not provider evidence. Do not guess that an unknown forge is GitHub or GitLab.

## Capability contract

Phase 0 records provider capabilities by semantic operation, not connector brand:

| Capability | Purpose |
|---|---|
| `read_target` | Metadata and current head SHA |
| `read_diff` | Changed files and diff hunks |
| `list_open` | Open review discovery |
| `read_comments` | Existing summary/inline comments for re-review dedupe |
| `read_ci` | Checks/pipeline state |
| `post_inline` | A line-anchored finding comment |
| `post_summary` | One review summary comment |
| `post_draft` | Provider-native draft comments, if available |

Use connected MCP/App tools first. For GitHub, authenticated `gh` is a read fallback only unless an
explicit GitHub write capability is present. Bind `gh pr` commands with
`--repo <host>/<owner>/<repo>` (or command-scoped `GH_HOST=<host>`); use `--hostname` only on commands
whose help supports it, such as `gh auth status` and `gh api`. Never default a GitHub Enterprise Server
request to GitHub.com.

## Provider invariants

- Every finding remains anchored to a changed diff line.
- Re-fetch the target immediately before the first provider write and compare its head SHA with Phase 1.
- On a mismatch, return `REVISION_MISMATCH` and perform zero provider writes in `full`, `summary-only`,
  `general-only`, and draft modes. Never remap positions, degrade to a summary, or continue a partial
  batch against the new revision; restart the review from Phase 1.
- The skill may write comments only. It never approves, requests changes, submits a review verdict,
  merges, closes, or reopens a GitHub PR or GitLab MR.
