# Dependency Graph

Four views — **do not merge** edge types. Cross-link sections when the same entity appears in multiple views.

## Logical context graph

Bounded contexts and external integrations. Produced P1.

```mermaid
graph LR
```

**View:** logical context · **Confidence:**

## Service call graph

Repo/service calls from code and mechanical graph. Produced P0.5.

```mermaid
graph LR
```

**View:** service call · **Confidence:**

## Deployment graph

Service → runtime placement (K8s, namespace, ingress). Produced P2.

```mermaid
graph LR
```

**View:** deployment · **Confidence:**

### Base URLs

Always populated (UNKNOWN with reason if not discoverable). Sources: `application*.yml`, Jenkinsfile, K8s
ingress manifests.

| Env | BFF base URL | Direct ingress (debug only) | Evidence |
|-----|--------------|------------------------------|----------|

## Runtime graph

Datadog-confirmed edges. Produced P2b.

*Populated in P2b — runtime validates behavior, not intent.*

```mermaid
graph LR
```

**View:** runtime · **Edges confirmed:** 0 / 0
