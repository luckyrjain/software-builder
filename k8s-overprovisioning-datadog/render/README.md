# Renderers

The **decision graph** is the primary artifact. Renderers are views.

```
decision_graph (YAML/JSON)
        │
        ├── markdown.md  → DORA report (default)
        ├── json.md      → machine export
        ├── slack.md     → (future)
        ├── html.md      → (future)
        └── pdf.md       → (future)
```

## Default

Use [markdown.md](markdown.md) unless the user requests JSON.

## JSON

Use [json.md](json.md) for automation, diffing, or storage.

## Future

Slack/HTML/PDF renderers are **documented only** — do not implement in skill v3.0.

Schema: [decision-graph-schema.md](../reference/decision-graph-schema.md)
