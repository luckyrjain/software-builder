# Universal Coding-Agent Compatibility
**Status:** Proposed — design-review complete
**Date:** 2026-08-31
**Type:** Architectural
**Target:** `luckyrjain/software-builder`
**Spec path:** `docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md`
---
# 1. Executive decision
`software-builder` SHALL become agent-portable through:
1. one canonical `SKILL.md` implementation per skill;
2. one canonical skill registry (`skills.yaml`);
3. one declarative coding-agent host registry (`agent-hosts.yaml`);
4. one packaging pipeline;
5. a small number of reusable installation targets;
6. capability-aware compatibility resolution;
7. evidence-backed host verification;
8. thin adapters only where native Agent Skills discovery is unavailable.
The architecture SHALL NOT create one implementation per coding agent.
The central abstraction is:
```text
                    skills.yaml
              skill requirements/contracts
                         │
                         │
                         ▼
                  canonical skill
                 <skill>/SKILL.md
                         │
                         ▼
                  package_skill.py
                         │
                         ▼
               verified skill package
                         │
                         │
              agent-hosts.yaml
        host discovery / surfaces / evidence
                         │
                         ▼
                 compatibility resolver
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   .agents/skills  .claude/skills  host-native target
          │              │              │
          ▼              ▼              ▼
    compatible agents  Claude      Kiro/Cline/etc.
```
---
# 2. Problem
`software-builder` is already largely portable at the skill-content layer, but host support is fragmented.
Today:
* canonical workflows already live in `SKILL.md`;
* packaging already creates self-contained verified bundles;
* `skills.yaml` already declares per-skill capabilities;
* `doctor.py` already calculates whether required capabilities are available;
* installer behavior is still largely host-specific;
* registry host models are hard-coded around Cursor, Claude, and Kiro;
* host compatibility is documented more broadly than it is represented programmatically.
This causes six systemic problems:
1. installation behavior and documentation can drift;
2. adding a host requires code changes instead of primarily data changes;
3. "supports Agent Skills" is incorrectly treated as equivalent to "can run every software-builder workflow";
4. discovery precedence, local/cloud execution, trust requirements, and catalog constraints are not modeled;
5. shared installation directories introduce collision and ownership risks;
6. support claims can become stale as coding-agent products change.
---
# 3. Goals
The implementation SHALL make it possible to answer these questions deterministically:
```text
Can host H discover skill S?
Can surface R of host H discover skill S?
Where should S be installed?
Will another copy shadow this installation?
Does H provide the capabilities S requires?
Can H satisfy S's isolation requirements?
Is this compatibility verified or merely inferred?
What evidence supports that answer?
```
A user SHALL be able to install a skill using:
```bash
bash scripts/install.sh --agent <host> <skill>
```
without learning host-specific filesystem conventions.
---
# 4. Non-goals
This feature SHALL NOT:
* create a coding-agent runtime;
* abstract model APIs;
* implement every vendor's plugin marketplace;
* install coding-agent products themselves;
* configure vendor credentials;
* duplicate canonical skill workflows;
* weaken skill permission or review-isolation contracts;
* claim runtime compatibility based solely on a Markdown file being discoverable;
* automatically migrate existing installations;
* redefine existing commands incompatibly;
* implement native Windows PowerShell installation in this phase;
* auto-detect all installed coding agents;
* add telemetry.
The supported installer platforms remain the repository's current Bash-compatible environments: macOS, Linux, and WSL.
---
# 5. Governing principles
## 5.1 Canonical skill content
Every skill SHALL have one authoritative implementation:
```text
<skill>/
  SKILL.md
  README.md
  SETUP.md
  workflow/
  reference/
  scripts/
  assets/
```
Host-specific directories SHALL NOT contain copied workflow bodies.
---
## 5.2 Agent Skills is the portable content ABI
Canonical skills SHALL conform to the Agent Skills specification.
At minimum, validation SHALL enforce:
```text
SKILL.md exists
valid YAML frontmatter
name present
description present
name length <= 64
name is lowercase kebab-case
no leading/trailing hyphen
no consecutive hyphens
name matches containing skill directory
description length <= 1024 characters
```
Canonical frontmatter SHOULD remain within the portable Agent Skills standard.
Host-specific fields SHALL NOT be added to canonical skills unless:
1. they are part of the open standard; or
2. every first-class target that receives the skill has documented safe behavior for the field.
Experimental fields that alter permissions MUST be treated conservatively.
In particular, a field that one host interprets as a permission grant MUST NOT be treated as a portable restriction mechanism.
---
# 6. One skill registry, one host registry
The implementation SHALL have exactly two canonical registries with non-overlapping ownership.
## `skills.yaml`
Owns:
```text
skill identity
skill path
invocation
composition
required capabilities
optional capabilities
any-of capability paths
degraded modes
risk classes
permissions
lint policy
artifact contracts
```
## `agent-hosts.yaml`
Owns:
```text
coding-agent identity
aliases
execution surfaces
discovery roots
installation targets
precedence
host capabilities
isolation primitives
trust requirements
layout/catalog constraints
verification evidence
maintainer support level
```
The same fact MUST NOT be independently maintained in both files.
---
# 7. Existing host-model migration
The existing hard-coded registry structures:
```text
HostCursor
HostClaude
HostKiro
Hosts
```
SHALL be removed from the per-skill data model once equivalent behavior is represented by `agent-hosts.yaml`.
Skill compatibility SHALL no longer be encoded as:
```text
skill -> Cursor config
skill -> Claude config
skill -> Kiro config
```
unless a specific skill has an exceptional host restriction.
Exceptions, if needed, SHALL be represented explicitly as compatibility overrides rather than restoring a host matrix inside every skill entry.
---
# 8. Hosts and installation targets are different concepts
A host represents a product.
A target represents a filesystem discovery location.
Many hosts may share one target.
Example:
```text
Cursor          ┐
GitHub Copilot  │
Gemini CLI      │
OpenCode        ├── project target: .agents/skills
Zed             │
Antigravity     │
Codex           │
others          ┘
```
This relationship MUST be many-to-many rather than hard-coded into the installer.
---
# 9. Execution surfaces
Compatibility SHALL be modeled per execution surface.
Minimum surface vocabulary:
```text
LOCAL
REMOTE
CLOUD
WEB
UNKNOWN
```
A host MAY expose only some surfaces.
Discovery and capabilities may differ by surface.
Example conceptual model:
```yaml
hosts:
  cursor:
    surfaces:
      local:
        ...
      cloud:
        ...
```
A user-level installation being available to a local IDE SHALL NOT imply that the same installation exists in a cloud agent.
Unknown surface behavior MUST remain `UNKNOWN`; it must not inherit optimistic assumptions.
---
# 10. Compatibility dimensions
Compatibility SHALL NOT be represented by one boolean or percentage.
The model SHALL expose orthogonal dimensions.
## Discovery mode
```text
NATIVE
ALIAS
ADAPTER
MANUAL
NONE
```
## Verification state
```text
VERIFIED
STALE
UNVERIFIED
CONFLICTED
```
## Maintainer support
```text
FIRST_CLASS
BEST_EFFORT
COMMUNITY
MANUAL_ONLY
DEPRECATED
```
## Workflow isolation
```text
STRONG
PARTIAL
SEQUENTIAL_ONLY
NONE
UNKNOWN
```
## Resolved skill status
The final host × surface × skill evaluation SHALL be:
```text
READY
DEGRADED
BLOCKED
UNVERIFIED
CONFLICTED
```
These axes MUST NOT be collapsed into a single status field internally.
---
# 11. Host × skill compatibility
This is a core requirement.
The project already declares skill capabilities and already contains logic that evaluates:
```text
required
optional
any_of
degraded_modes
```
The compatibility implementation SHALL reuse that capability vocabulary and resolution semantics.
It SHALL NOT build a second incompatible capability engine.
Conceptually:
```text
skills.yaml
    │
    └── skill.required_capabilities
                │
                ▼
         compatibility resolver
                ▲
                │
agent-hosts.yaml
    └── surface.available_capabilities
```
Example:
```text
architecture-review
requires:
  repository read
Host A provides:
  repository read
=> READY
```
while:
```text
loop-task-implementer
requires:
  repository write
  SCM write
  verification capabilities
  valid isolation path
Host B provides:
  repository read only
=> BLOCKED
```
Therefore documentation SHALL NOT state that an agent supports "all software-builder skills" merely because it supports `SKILL.md`.
---
# 12. Unknown capabilities fail closed
Host capability values SHALL support:
```text
AVAILABLE
UNAVAILABLE
UNKNOWN
```
`UNKNOWN` MUST NOT satisfy a required capability.
For optional capabilities, `UNKNOWN` MAY produce `DEGRADED` or `UNVERIFIED` depending on the skill's existing degraded-mode policy.
Security-sensitive workflows SHALL remain subject to their existing stricter completion rules.
---
# 13. Proposed `agent-hosts.yaml`
Illustrative schema:
```yaml
schema_version: 1
defaults:
  evidence_max_age_days: 90
targets:
  agents-project:
    scope: project
    path_template: "{project_root}/.agents/skills"
    format: agent-skills
  agents-user:
    scope: user
    path_template: "~/.agents/skills"
    format: agent-skills
  cursor-project:
    scope: project
    path_template: "{project_root}/.cursor/skills"
    format: agent-skills
  cursor-user:
    scope: user
    path_template: "~/.cursor/skills"
    format: agent-skills
  claude-project:
    scope: project
    path_template: "{project_root}/.claude/skills"
    format: agent-skills
  claude-user:
    scope: user
    path_template: "~/.claude/skills"
    format: agent-skills
  kiro-project:
    scope: project
    path_template: "{project_root}/.kiro/skills"
    format: agent-skills
  kiro-user:
    scope: user
    path_template: "~/.kiro/skills"
    format: agent-skills
  cline-project:
    scope: project
    path_template: "{project_root}/.cline/skills"
    format: agent-skills
  cline-user:
    scope: user
    path_template: "~/.cline/skills"
    format: agent-skills
hosts:
  cursor:
    aliases:
      - cursor-project
    maintainer_support: FIRST_CLASS
    surfaces:
      local:
        verification: VERIFIED
        discovery:
          project:
            - target: agents-project
              mode: NATIVE
            - target: cursor-project
              mode: NATIVE
          user:
            - target: agents-user
              mode: NATIVE
            - target: cursor-user
              mode: NATIVE
        preferred:
          project: agents-project
          user: agents-user
        capabilities:
          repository.read: AVAILABLE
          repository.write: AVAILABLE
        isolation:
          level: STRONG
      cloud:
        verification: VERIFIED
        discovery:
          project:
            - target: agents-project
              mode: NATIVE
          user: []
  claude:
    aliases:
      - claude-user
      - claude-project
    maintainer_support: FIRST_CLASS
    surfaces:
      local:
        verification: VERIFIED
        discovery:
          project:
            - target: claude-project
              mode: NATIVE
          user:
            - target: claude-user
              mode: NATIVE
        preferred:
          project: claude-project
          user: claude-user
  github-copilot:
    maintainer_support: FIRST_CLASS
    surfaces:
      local:
        verification: VERIFIED
        discovery:
          project:
            - target: agents-project
              mode: NATIVE
          user:
            - target: agents-user
              mode: NATIVE
        preferred:
          project: agents-project
          user: agents-user
  gemini:
    maintainer_support: FIRST_CLASS
    surfaces:
      local:
        verification: VERIFIED
        discovery:
          project:
            - target: agents-project
              mode: ALIAS
          user:
            - target: agents-user
              mode: ALIAS
        preferred:
          project: agents-project
          user: agents-user
```
The production schema SHALL include evidence records described later.
This is illustrative, not license to mark untested hosts verified.
---
# 14. Host-specific discovery precedence
Host discovery precedence MUST be modeled.
A host may discover the same skill name from:
```text
global universal directory
global native directory
project universal directory
project native directory
plugin
managed enterprise configuration
nested repository directory
```
The registry SHALL be able to encode precedence where authoritative behavior is known.
Doctor/preflight SHALL detect:
```text
SHADOWED
DUPLICATE_IDENTICAL
DUPLICATE_DIVERGENT
UNKNOWN_PRECEDENCE
```
A divergent higher-precedence skill with the same name SHALL prevent the installer from claiming that the newly installed skill is the one the host will execute.
---
# 15. Installation ownership
Expanding into `.agents/skills` significantly increases collision risk because it is a shared ecosystem location.
This feature MUST harden replacement behavior.
For destination:
```text
<target>/<skill>
```
the installer SHALL classify existing state as:
```text
ABSENT
SOFTWARE_BUILDER_OWNED
UNOWNED
CORRUPT_OWNERSHIP
SYMLINK
```
Behavior:
| Existing state         | Install      |
| ---------------------- | ------------ |
| ABSENT                 | allowed      |
| SOFTWARE_BUILDER_OWNED | safe replace |
| UNOWNED                | block        |
| CORRUPT_OWNERSHIP      | block        |
| SYMLINK                | block        |
The installer MUST NOT delete an unowned third-party skill merely because its folder name matches a software-builder skill.
There SHALL be no implicit force-overwrite behavior.
A future explicit adoption workflow may be designed separately.
---
# 16. Uninstall ownership
Uninstall SHALL be even stricter.
The installer may remove a skill directory only when its valid manifest proves software-builder ownership.
Missing or invalid ownership metadata SHALL cause:
```text
REFUSED_UNOWNED_UNINSTALL
```
No recursive deletion of unowned matching directories is allowed.
---
# 17. Package invariance
Canonical functional package content MUST remain host-neutral.
For identical:
```text
skill
source revision
distribution version
```
functional files produced for different hosts MUST be byte-equivalent.
Allowed differences are restricted to installer metadata explicitly excluded from functional-parity comparison.
Host-specific workflow text is forbidden.
---
# 18. Manifest semantics
The install manifest SHALL evolve explicitly.
Add:
```text
manifest_schema_version
target_id
package_format
source_revision
distribution_version
```
The existing `host` field SHALL remain readable for backward compatibility.
For shared installation targets, persisted identity SHOULD describe the canonical target/family rather than whichever host alias happened to initiate the installation.
Example:
```text
gemini
github-copilot
opencode
```
may all resolve to:
```text
agents-user
```
Reinstalling the same version through another alias MUST NOT create a functional package diff.
Old manifests MUST remain readable.
---
# 19. Standard-conformance validation
Packaging SHALL include an explicit Agent Skills validation phase.
Sequence:
```text
canonical skill
    ↓
repository policy validation
    ↓
Agent Skills conformance validation
    ↓
package
    ↓
internal reference validation
    ↓
manifest/hash validation
```
Validation SHOULD remain implemented locally or through a pinned dependency.
CI MUST NOT silently depend on an unpinned remote validator.
---
# 20. Host-specific frontmatter
Canonical `SKILL.md` SHALL use the portable subset by default.
Host extensions such as:
```text
host-specific path filters
host-specific fork/subagent directives
host-specific permission grants
host-specific invocation flags
```
SHOULD be implemented through thin host adapters where needed rather than added to every canonical skill.
An exception requires:
1. documented compatibility across all receiving hosts;
2. a regression test;
3. no unsafe permission broadening.
---
# 21. Trust and executable-skill security
Project skills are executable instructions, not passive documentation.
Project installation SHALL therefore be treated as a repository mutation.
The installer MUST:
* require explicit project target selection;
* never silently discover and modify arbitrary repositories;
* validate bundled scripts;
* preserve existing symlink protections;
* never execute installed scripts during installation merely to test them;
* warn in documentation that repository trust may activate skill instructions or permission metadata in the host.
Runtime execution remains governed by the host and the skill's existing permission contracts.
---
# 22. Layout and catalog constraints
Host-specific constraints SHALL be represented declaratively.
Examples:
```yaml
constraints:
  flat_skill_layout: true
  project_trust_required: true
  catalog_metadata_budget_bytes: 50000
```
The compatibility resolver/doctor SHOULD validate applicable constraints.
Installing all skills SHALL fail or warn before mutation when the resulting catalog is known to exceed a host's hard discovery limit.
Do not discover such failure only after the external agent silently drops skills.
---
# 23. Conflicting vendor evidence
The registry SHALL support evidence status:
```text
CONFLICTED
```
This is required when authoritative sources disagree.
Example behavior:
```text
project path: VERIFIED
global path: CONFLICTED
```
The project-level install can remain available while global installation is withheld.
The implementation MUST NOT resolve authoritative documentation conflict by guessing.
---
# 24. Evidence model
Every non-trivial host compatibility claim SHALL have evidence.
Conceptual shape:
```yaml
evidence:
  - claim: project_agent_skills_discovery
    status: OBSERVED
    provenance:
      source_type: vendor_documentation
      source_ref: github-copilot-agent-skills-doc
    observed_at: "2026-08-31"
    host_version: null
    limitations: []
  - claim: local_runtime_smoke
    status: OBSERVED
    provenance:
      source_type: runtime_smoke_test
      evidence_ref: host-smoke/cursor/2026-08-31
    observed_at: "2026-08-31"
```
Use the repository's existing evidence vocabulary wherever possible:
```text
OBSERVED
INFERRED
UNKNOWN
CONFLICTED
NOT_APPLICABLE
```
Do not invent another competing evidence semantic.
---
# 25. Freshness
Compatibility evidence becomes stale.
Each verified host SHALL record:
```text
observed_at
tested_version when available
source provenance
limitations
```
Generated documentation SHALL expose:
```text
last verified
verification status
```
A stale claim SHALL become:
```text
STALE
```
rather than silently remaining `VERIFIED`.
Staleness SHOULD block promotion to first-class but SHOULD NOT automatically make previously installed skills unusable.
---
# 26. First-class promotion gate
A host MUST NOT be marked `FIRST_CLASS + VERIFIED` merely because vendor documentation says it supports Agent Skills.
Promotion requires all applicable gates:
```text
authoritative discovery documentation
registry contract test
path resolution test
package install test
package verify test
uninstall ownership test
runtime discovery smoke test
skill invocation smoke test
bundled-resource loading smoke test
known limitations recorded
```
For multi-agent workflows:
```text
isolation primitive verified
```
is additionally required before claiming strong workflow compatibility.
---
# 27. Host baseline policy
Initial implementation SHALL be conservative.
Hosts with authoritative native Agent Skills documentation may begin as:
```text
maintainer_support: FIRST_CLASS
verification: UNVERIFIED
```
until runtime smoke evidence is recorded.
A host with conflicting installation documentation SHALL use:
```text
verification: CONFLICTED
```
for the affected surface/scope.
This prevents the registry example itself from overstating support.
---
# 28. Distribution channel is not discovery path
The architecture SHALL distinguish:
```text
filesystem discovery
plugin
marketplace
GitHub import
CLI package installer
vendor extension
```
A host may support several distribution channels while ultimately loading the same canonical skill.
For phase 1, filesystem installation is the primary implementation target.
Existing:
```text
.claude-plugin
.codex-plugin
.cursor rules
.kiro steering
```
must be inventoried and classified as distribution/discovery adapters.
They MUST NOT become competing canonical workflow sources.
---
# 29. Installer compatibility
Existing CLI behavior is a hard compatibility requirement.
These commands MUST retain their current behavior:
```bash
bash scripts/install.sh --agent cursor
bash scripts/install.sh --agent cursor --target-dir /repo
bash scripts/install.sh --agent cursor-project --target-dir /repo
bash scripts/install.sh --agent claude-user
bash scripts/install.sh --agent claude-project --target-dir /repo
```
---
# 30. Do not redefine `--agent all`
The previous design proposed changing the meaning of:
```bash
--agent all
```
That is rejected.
Today this command has existing behavior.
Changing it to suddenly install into many additional host directories would violate backward compatibility and could create shadowed duplicate skills.
`--agent all` SHALL preserve its existing semantics for this feature release.
Introduce a new selector:
```bash
--agent all-supported
```
or equivalent explicit profile.
Recommended name:
```bash
--profile portable
```
The final CLI name SHALL be selected once and remain unambiguous.
---
# 31. Universal target
Add explicit selector:
```bash
--agent agents
```
Meaning:
```text
install using the universal Agent Skills target
```
Example:
```bash
bash scripts/install.sh \
  --agent agents \
  pr-review
```
Default scope follows existing installer semantics.
---
# 32. New host selectors
Target first-class selectors:
```text
cursor
claude
codex
github-copilot
gemini
opencode
roo
zed
amp
antigravity
kiro
cline
```
Additional hosts may be added when verified.
Unverified hosts MUST NOT be added merely to inflate compatibility count.
---
# 33. Preferred-target resolution
When multiple discovery roots are valid, the registry SHALL designate a preferred target per:
```text
host
surface
scope
```
Example:
```text
Cursor local/project
→ .agents/skills preferred
Claude local/project
→ .claude/skills preferred
```
This avoids duplicate installations.
The resolver SHALL NOT install into every directory a host happens to support.
---
# 34. Portable multi-host profile
The portable multi-host profile SHALL compute a minimal target cover.
Goal:
```text
cover requested hosts
while minimizing duplicate discovery roots
```
For example, if six requested hosts all consume:
```text
.agents/skills
```
the operation installs there once.
It MUST NOT additionally install six identical copies into native directories unless required to cover a host.
---
# 35. Shadow prevention
Before write, the installer SHALL inspect known higher-precedence roots for the same skill ID.
If a divergent higher-precedence copy exists:
```text
BLOCKED_SHADOWED_INSTALL
```
unless the user explicitly requested installation into that higher-precedence location.
If precedence is unknown:
```text
UNVERIFIED_PRECEDENCE
```
and the installer must not claim activation success.
---
# 36. Multi-target execution semantics
A multi-target operation SHALL have explicit partial-failure behavior.
Implementation sequence:
```text
1. resolve every target
2. validate every target
3. inspect ownership
4. inspect shadowing
5. validate permissions/writability
6. create complete installation plan
7. stop if deterministic preflight errors exist
8. package and validate
9. mutate destinations
10. verify every mutation
```
All predictable failures MUST occur before mutation.
Unexpected filesystem failures MAY still create a partial result.
The command SHALL report:
```text
SUCCESS
PARTIAL
FAILED
```
and enumerate exact destinations changed.
It MUST NOT report global success when only some targets were installed.
---
# 37. Concurrent installation
Concurrent writes to the same target can corrupt backup/replace semantics.
Mutation SHALL acquire a target-scoped advisory lock.
The lock implementation must work on the repository's supported POSIX environments.
Concurrent lock contention SHALL fail clearly rather than race.
A stale-lock strategy must be documented and tested.
---
# 38. Atomic replacement
Preserve the existing staging strategy.
Per-target installation remains:
```text
package to staging
validate staging
backup owned prior install
atomic rename/move where filesystem permits
verify activated install
remove backup
```
If activation fails, restore the previous owned version.
An unowned version is never backed up and replaced; installation is blocked before this phase.
---
# 39. Uninstall semantics for shared targets
Host selectors can alias the same target.
Example:
```text
gemini
copilot
opencode
→ ~/.agents/skills
```
Therefore:
```bash
--agent gemini --uninstall pr-review
```
means:
> remove the software-builder-owned copy from the resolved shared target.
CLI output SHALL state the target and list other registered hosts that consume the same target.
The explicit uninstall command remains sufficient authorization; an extra interactive prompt is not required.
---
# 40. Doctor integration
Do not create a separate compatibility diagnostic system.
Extend the existing doctor.
New examples:
```bash
python scripts/doctor.py \
  --agent gemini \
  --skill loop-task-implementer
python scripts/doctor.py \
  --agent cursor \
  --surface cloud \
  --skill pr-review
```
Doctor SHALL combine:
```text
skill capability requirements
host capabilities
surface
installation state
manifest version
target ownership
shadowing
host constraints
verification evidence
```
---
# 41. Doctor status model
Doctor SHALL be able to surface at least:
```text
READY
DEGRADED
BLOCKED
NOT_INSTALLED
VERSION_MISMATCH
UNVERIFIED_HOST
STALE_HOST_EVIDENCE
CONFLICTED_HOST_EVIDENCE
SHADOWED
DUPLICATE_DIVERGENT
UNOWNED_COLLISION
INVALID_PACKAGE
```
Status priority rules SHALL be deterministic and unit-tested.
---
# 42. Backward-compatible doctor behavior
Existing doctor invocations without:
```text
--agent
```
SHALL preserve current behavior.
A migration to a new default host is out of scope for this release.
---
# 43. Compatibility documentation
Generate:
```text
docs/agent-compatibility.md
```
from:
```text
agent-hosts.yaml
+
skills.yaml
```
The document SHALL distinguish:
```text
host discovery support
verification
surface
scope
workflow isolation
limitations
last verified
```
It SHALL NOT publish invented compatibility percentages.
---
# 44. Skill matrix
The tooling SHOULD support generation of a detailed matrix:
```text
host × skill
```
Example conceptual output:
| Host         | Skill                 | Status   | Missing capability | Isolation | Evidence |
| ------------ | --------------------- | -------- | ------------------ | --------- | -------- |
| Cursor local | architecture-review   | READY    | —                  | N/A       | VERIFIED |
| Cursor cloud | skill X               | BLOCKED  | capability Y       | —         | VERIFIED |
| Host B       | loop-task-implementer | DEGRADED | subagent isolation | PARTIAL   | VERIFIED |
This is more useful than a generic "Agent X = 100% compatible" claim.
---
# 45. README
README SHALL contain only the concise support table.
Detailed evidence and limitations belong in:
```text
docs/agent-compatibility.md
```
README content MUST be generated or checked from the canonical registries.
---
# 46. Documentation drift gate
Add deterministic generation/checking:
```bash
python scripts/render_agent_support.py
python scripts/render_agent_support.py --check
```
CI SHALL run:
```text
--check
```
A registry change without matching generated documentation SHALL fail.
Manual duplicate compatibility tables are forbidden.
---
# 47. Host registry validation
Registry validation MUST reject:
```text
duplicate host IDs
duplicate target IDs
unknown targets
unknown aliases
alias cycles
unsupported enum values
unknown path variables
unsafe path traversal
project target without project root variable
user target containing project root variable
invalid evidence shape
duplicate precedence rank where ambiguous
unknown capability vocabulary
invalid surface
invalid constraint value
FIRST_CLASS + VERIFIED without required evidence
```
Unknown fields SHALL fail for schema version 1.
---
# 48. Safe path expansion
Allowed path variables SHALL be explicitly allowlisted.
Initial set:
```text
{project_root}
~
```
No arbitrary environment-variable interpolation.
Resolved project targets MUST remain beneath the canonicalized project root.
Destination leaf symlinks remain forbidden.
Existing documented ancestor-symlink limitations SHALL not be silently represented as solved unless this implementation actually hardens them.
---
# 49. Catalog validation
For hosts declaring catalog constraints, doctor/preflight SHALL calculate applicable package metadata footprint.
Known hard limits SHALL become preflight errors or warnings according to host semantics.
Flat-layout hosts SHALL only receive:
```text
<skills-root>/<skill>/SKILL.md
```
and never category-nested installations.
---
# 50. Runtime smoke-test contract
A runtime smoke record SHALL include:
```text
host
host version
surface
OS
scope
install target
skill ID
source revision
discovered
explicit invocation succeeded
automatic invocation tested where applicable
bundled reference readable
bundled script visible
isolation primitive tested where applicable
observed_at
evidence reference
limitations
```
The smoke skill SHALL be harmless and deterministic.
---
# 51. Compatibility fixture
Create or identify a minimal compatibility fixture skill.
It SHALL validate:
```text
frontmatter discovery
SKILL.md activation
one referenced Markdown file
one harmless bundled script
```
Its script SHALL:
```text
perform no network calls
read no credentials
modify no repository state
print a deterministic marker only
```
---
# 52. Isolation verification
Ordinary skill discovery and multi-agent workflow compatibility are separate gates.
For workflows requiring independent review, host evidence SHALL record supported primitives:
```text
SUBAGENT
FRESH_SESSION
BACKGROUND_AGENT
WORKTREE
CONTEXT_FORK
```
The existing workflow remains authoritative about which primitives count as genuinely isolated.
Compatibility infrastructure SHALL not relabel sequential role simulation as strong isolation.
---
# 53. Security-sensitive diffs
For security-sensitive workflows, unresolved isolation capability remains fail-closed.
No compatibility adapter may weaken this rule merely to make a host appear supported.
---
# 54. Kiro migration
Kiro's native Agent Skills directory SHALL become the preferred skill-installation path.
Existing steering files MAY remain as routing/discovery adapters during migration.
They MUST:
```text
reference canonical skills
contain no duplicated canonical workflow logic
```
A removal/deprecation decision for steering belongs in a later cleanup once native skill installation is proven.
---
# 55. Claude
Claude SHALL continue using its native skill hierarchy by default.
Do not route Claude through `.agents/skills` unless authoritative support is later verified.
Existing Claude plugin metadata remains an independent distribution channel.
Plugin skills and standalone skill installs SHALL not collide silently.
---
# 56. Cursor
Existing Cursor paths remain supported.
Universal `.agents/skills` may become the preferred target for new portable installations, but the existing Cursor CLI contract MUST remain unchanged.
Cloud/remote execution MUST be modeled separately from local execution.
---
# 57. Antigravity documentation conflict
Do not hard-code an Antigravity global target until the conflicting authoritative global-path information has been resolved.
Initial state:
```text
project installation:
  may be VERIFIED if evidence passes
global installation:
  CONFLICTED
```
The installer SHALL reject a global Antigravity install while evidence is conflicted unless the user explicitly selects a raw supported target such as the universal target independently of the Antigravity host selector.
---
# 58. Adapters
For hosts without native discovery, adapters SHALL be tiny routing artifacts.
Allowed:
```text
AGENTS.md fragment
host rule
host instruction file
loader configuration
```
Forbidden:
```text
copied SKILL.md body
copied workflow
forked policy
forked review criteria
```
Adapters MUST point back to canonical installed skill content.
---
# 59. Adapter promotion
Continue, Junie, Aider, OpenHands, Goose, or other hosts SHALL not automatically be placed into first-class support.
Each moves through:
```text
research
→ discovery contract
→ adapter/native implementation
→ deterministic tests
→ runtime smoke
→ verified support
```
---
# 60. Installation-plan abstraction
Before filesystem mutation, resolver SHALL produce an internal plan similar to:
```yaml
requested_selector: gemini
surface: local
scope: user
skills:
  - pr-review
destinations:
  - target_id: agents-user
    root: /home/user/.agents/skills
    skills:
      - pr-review
preflight:
  ownership: PASS
  shadowing: PASS
  capabilities: READY
  constraints: PASS
  evidence: VERIFIED
```
`--dry-run` SHOULD render this resolved plan.
---
# 61. Machine-readable output
The resolver/installer SHOULD provide JSON output for testing and automation.
Example:
```bash
bash scripts/install.sh \
  --agent gemini \
  --dry-run \
  --json \
  pr-review
```
Human and machine outputs must be derived from the same result object.
If introducing `--json` materially expands the first implementation candidate, it MAY land in the immediately following candidate without changing architecture.
---
# 62. Test strategy
Tests SHALL be driven from the registries rather than hand-maintaining a second list of hosts.
Required classes:
### Registry schema
```text
valid registry
bad target
bad alias
alias cycle
bad capability
bad surface
bad evidence
bad path template
unsafe traversal
invalid precedence
```
### Legacy regression
Golden tests for:
```text
cursor
cursor-project
claude-user
claude-project
all
target-dir
dry-run
verify
uninstall
```
### Resolution
```text
host
surface
scope
preferred target
fallback target
shared target
```
### Ownership
```text
absent
owned
unowned
corrupt manifest
wrong skill manifest
symlink
```
### Shadowing
```text
single install
identical duplicate
divergent lower precedence
divergent higher precedence
unknown precedence
```
### Capabilities
```text
READY
DEGRADED
BLOCKED
UNKNOWN required capability
any-of paths
```
### Constraints
```text
flat layout
catalog budget
project trust metadata
```
### Packaging
```text
Agent Skills conformance
reference validation
hash verification
host-neutral functional parity
old manifest compatibility
```
### Mutation
```text
fresh install
upgrade
interrupted install
rollback
concurrent install
partial multi-target I/O failure
uninstall
```
### Documentation
```text
registry/docs parity
stale generated docs
```
---
# 63. Negative testing requirement
Every security rule SHALL have at least one negative test.
Particularly:
```text
path escape
unowned replacement
unowned uninstall
symlink leaf
host alias cycle
shadowed skill
corrupt manifest
unknown required capability
conflicting evidence
```
A success-only test suite is insufficient.
---
# 64. Candidate implementation sequence
## Candidate 0 — Baseline freeze
Before structural changes:
* capture existing installer behavior;
* add golden tests for current Cursor/Claude flows;
* capture current doctor behavior;
* capture manifest fixture versions.
Exit:
```text
legacy behavior is executable evidence
```
---
## Candidate 1 — Agent Skills conformance
Implement standard-format validation for every canonical skill.
Exit:
```text
all current skills conform
CI blocks future violations
```
---
## Candidate 2 — Host registry schema
Add:
```text
agent-hosts.yaml
scripts/agent_hosts.py
registry models
schema validation
evidence model
```
No installer behavior change.
Exit:
```text
registry validated
legacy hosts represented
no duplicate host source of truth introduced
```
---
## Candidate 3 — Remove hard-coded host models
Generalize the current `HostCursor / HostClaude / HostKiro` registry model.
Preserve skill capability contracts.
Exit:
```text
all existing registry consumers pass
no behavior regression
```
---
## Candidate 4 — Compatibility resolver
Implement:
```text
host
surface
scope
discovery
precedence
capability resolution
constraints
verification state
```
Reuse existing doctor capability logic.
Exit:
```text
host × skill results deterministic
```
---
## Candidate 5 — Installer resolver migration
Move destination resolution from hard-coded Bash to the registry resolver.
Only legacy hosts enabled initially.
Exit:
```text
golden Cursor/Claude tests unchanged
```
---
## Candidate 6 — Ownership hardening
Before exposing shared universal directories:
```text
owned replacement only
unowned collision blocking
safe uninstall
```
Exit:
```text
no unowned recursive replacement/removal
```
This candidate is a release prerequisite for `.agents/skills`.
---
## Candidate 7 — Universal Agent Skills target
Add:
```text
agents
```
and verified universal-host mappings.
Add shared-target deduplication.
Exit:
```text
one operation per physical destination
```
---
## Candidate 8 — Shadowing and precedence
Implement duplicate discovery diagnostics and activation-confidence checks.
Exit:
```text
installer cannot falsely claim active installation when known shadowed
```
---
## Candidate 9 — Native additional hosts
Add verified host-native paths such as:
```text
Kiro
Cline
```
according to evidence.
Exit:
```text
runtime smoke evidence attached
```
---
## Candidate 10 — Doctor integration
Make doctor host/surface aware.
Exit:
```text
doctor computes host × skill compatibility from canonical registries
```
---
## Candidate 11 — Documentation generation
Add:
```text
docs/agent-compatibility.md
README generated section
render_agent_support.py --check
```
Exit:
```text
manual matrix drift impossible
```
---
## Candidate 12 — Remaining hosts and adapters
Add other agents based on evidence, not target count.
Exit:
```text
every published support claim has evidence
```
---
## Candidate 13 — Final combined review
Review the complete combined diff using independent lenses.
Required review dimensions:
```text
architecture
correctness
filesystem security
ownership safety
backward compatibility
schema migration
capability semantics
host evidence accuracy
shadowing
precedence
concurrency
rollback
package invariance
documentation drift
test sufficiency
maintainability
```
Candidate-level clean reviews do NOT replace this final review.
---
# 65. Rollout strategy
Rollout SHALL be additive.
Phase 1:
```text
registry exists
legacy installer unchanged
```
Phase 2:
```text
legacy installer powered by new resolver
```
Phase 3:
```text
universal target available explicitly
```
Phase 4:
```text
new host selectors available
```
Phase 5:
```text
additional adapters and verified surfaces
```
No automatic migration of existing installations occurs.
---
# 66. Rollback
A code rollback MUST leave already installed skill packages usable.
Therefore:
* existing manifests remain readable;
* canonical SKILL.md package structure remains unchanged;
* new metadata is additive;
* installation directories are not mass-migrated;
* old Cursor/Claude paths remain valid.
If compatibility-layer code is reverted, already installed packages must not depend on it at runtime.
---
# 67. Success metrics
No usage telemetry is required.
Release-quality metrics:
```text
100% canonical skills Agent Skills-valid
100% existing installer golden tests preserved
100% published hosts backed by evidence
0 unowned directories overwritten
0 unowned directories removed
0 duplicated canonical workflow bodies
0 registry/documentation drift
0 unresolved blocking final-review findings
```
Compatibility coverage SHALL be reported as factual counts:
```text
verified hosts
verified surfaces
READY host × skill combinations
DEGRADED combinations
BLOCKED combinations
UNVERIFIED combinations
```
Do not use invented percentages such as "95% compatible."
---
# 68. Acceptance criteria
**AC-01** — One canonical implementation exists for every skill.
**AC-02** — Canonical skills pass Agent Skills specification validation.
**AC-03** — `skills.yaml` remains the canonical source of skill capability requirements.
**AC-04** — `agent-hosts.yaml` is the canonical source of host discovery/capability information.
**AC-05** — Hard-coded Cursor/Claude/Kiro host dataclasses are migrated without losing behavior.
**AC-06** — Existing Cursor commands remain behaviorally compatible.
**AC-07** — Existing Claude commands remain behaviorally compatible.
**AC-08** — Existing `--agent all` semantics do not change.
**AC-09** — `.agents/skills` is available through an explicit universal target.
**AC-10** — Shared universal targets perform one physical installation.
**AC-11** — Installing through different aliases of the same target does not produce functional package differences.
**AC-12** — Host × skill compatibility reuses existing capability semantics.
**AC-13** — Unknown required capability never becomes READY.
**AC-14** — Multi-agent isolation compatibility is separately evaluated.
**AC-15** — Local, remote, and cloud surfaces can differ.
**AC-16** — Existing unowned destination directories are never silently overwritten.
**AC-17** — Unowned directories are never removed by uninstall.
**AC-18** — Known shadowing prevents false activation-success claims.
**AC-19** — Unknown precedence is surfaced.
**AC-20** — Project path resolution cannot escape project root.
**AC-21** — Existing symlink protections remain intact.
**AC-22** — Target-level concurrent installs cannot race silently.
**AC-23** — Predictable multi-target failures occur before mutation.
**AC-24** — Unexpected partial operations report PARTIAL and exact changed destinations.
**AC-25** — Old manifests remain readable.
**AC-26** — Canonical package functional content remains host-neutral.
**AC-27** — Host-specific permission fields are not silently introduced into portable skills.
**AC-28** — Host catalog/layout constraints are machine-readable.
**AC-29** — Evidence conflict is represented explicitly as CONFLICTED.
**AC-30** — Stale host evidence cannot remain silently VERIFIED.
**AC-31** — A host cannot be promoted to verified first-class support without runtime smoke evidence.
**AC-32** — Documentation is generated or checked from canonical registry data.
**AC-33** — Compatibility documentation distinguishes host, surface, skill, isolation, and evidence.
**AC-34** — No compatibility percentage is published without a defined measurable denominator.
**AC-35** — All new security rules have negative tests.
**AC-36** — Full repository lint/tests pass.
**AC-37** — Final combined-diff review contains zero unresolved accepted blocking findings.
---
# 69. Definition of done
The initiative is complete only when:
```text
[ ] baseline installer behavior is frozen in tests
[ ] all skills pass Agent Skills conformance
[ ] agent-hosts.yaml exists and validates
[ ] hard-coded host models are migrated
[ ] compatibility resolver exists
[ ] host × skill evaluation uses existing capability contracts
[ ] legacy Cursor behavior is unchanged
[ ] legacy Claude behavior is unchanged
[ ] legacy --agent all behavior is unchanged
[ ] universal .agents target works
[ ] target ownership protection exists
[ ] uninstall ownership protection exists
[ ] shadowing diagnostics exist
[ ] precedence is represented
[ ] local/cloud surface differences are represented
[ ] shared destinations deduplicate
[ ] package functional parity tests pass
[ ] old manifests remain valid
[ ] concurrent mutation is protected
[ ] doctor is host-aware
[ ] generated compatibility docs exist
[ ] evidence freshness is represented
[ ] verified hosts have runtime smoke evidence
[ ] adapters contain zero canonical workflow duplication
[ ] all tests/lint pass
[ ] final combined review has zero unresolved accepted blockers
```
---
# 70. Architectural decisions
**AD-01 — Canonical source**
`SKILL.md` remains the canonical workflow definition.
**AD-02 — Standard**
The open Agent Skills format is the portable content ABI.
**AD-03 — Registry ownership**
Skill requirements and host capabilities live in separate canonical registries with no duplicated ownership.
**AD-04 — Compatibility resolution**
Compatibility is computed as host × surface × skill.
**AD-05 — Universal directory**
`.agents/skills` is a first-class interoperability target, not a requirement for every host.
**AD-06 — Native paths**
Host-native paths remain supported when required or materially useful.
**AD-07 — Backward compatibility**
Existing installer commands retain their current meaning.
**AD-08 — `all`**
`--agent all` is not redefined in a feature release.
**AD-09 — Ownership**
Only software-builder-owned installations may be automatically replaced or removed.
**AD-10 — Evidence**
Compatibility claims are evidence-backed and freshness-aware.
**AD-11 — Conflict**
Conflicting authoritative evidence remains `CONFLICTED`; the implementation does not guess.
**AD-12 — Isolation**
Skill discovery compatibility and independent-review compatibility are separate contracts.
**AD-13 — Package neutrality**
Host differences belong in installation/discovery metadata, not canonical workflow bodies.
**AD-14 — Permissions**
Portable skill metadata must not accidentally broaden permissions on one host.
**AD-15 — No fake precision**
Compatibility is expressed through explicit states and capability results, not arbitrary percentages.
---
# 71. Deferred work
Explicitly outside this implementation:
```text
automatic host detection
native Windows PowerShell installer
skills.sh publishing
gh skill publishing
marketplace automation
organization-wide deployment
signed package distribution
remote skill registry
automatic vendor-doc crawling
automatic compatibility telemetry
automatic migration of old installations
```
Each may be added later without changing the architecture above.
---
# 72. Final invariant
The implementation is correct only if this remains true:
> A new coding agent should usually be supportable by adding verified declarative host data, not by copying or rewriting the 38 software-builder skills.
And a new skill should usually become usable across already-compatible hosts without adding host-specific implementation code.
That is the architectural property this project exists to create.
