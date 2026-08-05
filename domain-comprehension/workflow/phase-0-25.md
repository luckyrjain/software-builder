---
workflow_version: 1.10
phase: 0.25
produces:
  - contract_inventory
consumes:
  - inventory
---

# Comprehension Phase P0.25 — Cross-repo contracts

Centralize in `{map_file}` § Contracts. Run the grep recipes below per contract type across Tier 0/1
repos. Run parallel to the P0 tail when `inventory` Tier 0/1 rows are done.

## Investigation recipes

### HTTP / REST

```bash
# Find controllers and route definitions
rg -l 'swagger|openapi|@RestController|@RequestMapping|@GetMapping|@PostMapping|router\.' \
  --glob '!test*' --glob '!vendor' --glob '!node_modules' <repo>

# Find committed OpenAPI/Swagger spec files
find <repo> -name 'openapi.yaml' -o -name 'swagger.yaml' -o -name 'openapi.json' 2>/dev/null
```

**No OpenAPI/Swagger spec found?** Read request/response DTOs directly for validation constraints:

```bash
rg -o '@NotBlank|@NotNull|@Pattern\([^)]*\)|@Size\([^)]*\)|@Valid|@Min\([^)]*\)|@Max\([^)]*\)' \
  --glob '**/model/request/*.java' --glob '**/dto/*Request*.java' --glob '!test*' <repo>
```

Record findings as evidence notes alongside the Contract inventory row for that endpoint — do not invent a
field-level schema table; cite the DTO class + constraint found.

### gRPC / Proto

```bash
rg -l '\.proto' --glob '!vendor' <repo>
find <repo> -name '*.proto' | head -20
```

### Events (Kafka, RabbitMQ, SQS, SNS)

```bash
# Find topic/queue/exchange names and event handlers
rg -l 'topic|exchange|queue|KafkaListener|@EventHandler|@SqsListener|@RabbitListener' \
  --glob '!test*' --glob '!vendor' <repo>

# Find topic name constants
rg -rn 'TOPIC|QUEUE|EXCHANGE' --glob '!test*' <repo> | grep -i 'const\|val \|final '
```

### Shared database tables

```bash
# Find table names in migrations
find <repo> -name '*.sql' | xargs rg -l 'CREATE TABLE' 2>/dev/null

# Cross-repo: for each table found, grep other repos
rg -l 'FROM <table_name>\|INSERT INTO <table_name>\|JOIN <table_name>' \
  --glob '!test*' --glob '!*.sql' <other_repo>
```

### Shared packages / internal libraries

```bash
# npm / pnpm
cat <repo>/package.json | grep '"@<org>/'

# Maven
grep -A1 '<groupId>com\.<org>' <repo>/pom.xml | grep '<artifactId>'

# Go modules
grep '<org>/' <repo>/go.mod
```

### Idempotency / correlation keys

```bash
rg -l 'idempotency.key|requestId|X-Idempotency|x-request-id|correlationId' \
  --glob '!test*' <repo>
```

### Error codes

```bash
rg -l 'enum.*Error|ErrorCode|@ExceptionHandler|ErrorResponse' --glob '!test*' --glob '!vendor' <repo>
```

## Producer vs. consumer detection

| Signal | Role |
|--------|------|
| HTTP server handler (`@RestController`, `router.post`, `func handler`) | **Producer** |
| HTTP client (`FeignClient`, `RestTemplate`, `fetch`, `axios`) | **Consumer** |
| Migration that creates the table (`CREATE TABLE`) | **Producer** |
| `SELECT / INSERT` referencing a table created in another repo | **Consumer** |
| `@KafkaListener` / `@SqsListener` / `@RabbitListener` | **Consumer** |
| `kafkaTemplate.send` / `sns.publish` / `rabbitTemplate.send` | **Producer** |

**Anti-patterns:**
- Do not mark a Feign client or Retrofit interface as a producer — find the handler on the server side
- Do not infer producer from HTTP client alone — verify the handler exists in the target repo
- Do not mark a shared library as a producer unless it owns the event topic or table schema

## Contract inventory table (required)

| Contract | Type | Producer repo | Consumer repo(s) | Schema location | Evidence |
|----------|------|--------------|------------------|-----------------|----------|

## Error code catalog (required)

| Code | Message | HTTP status | Repo | Evidence |
|------|---------|-------------|------|----------|

## Sub-agents

One `explore` agent, multi-repo grep across Tier 0/1 repos.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Contract inventory | `{map_file}` § Contracts | Contract, Type, Producer repo, Consumer repo(s), Schema location, Evidence | Phase incomplete |
| API catalog | `API_CATALOG.md` | method, path, producer, consumers, implementation, exercise | Phase incomplete |
| Event catalog | `EVENT_CATALOG.md` | topic, schema, producer, consumers, implementation, exercise | Phase incomplete — UNKNOWN rows with reason allowed |
| Error code catalog | `{map_file}` § Contracts | Code, message, HTTP status, repo, evidence | Phase incomplete — UNKNOWN rows with reason allowed |

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md) · [phase-outputs.md § P0.25](../reference/phase-outputs.md#p025-contracts)
