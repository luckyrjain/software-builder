# JSON renderer

Emit the validated `decision_graph` as JSON for automation.

## Rules

1. **Lossless** — entire graph object; no fields dropped
2. `schema_version` must be `3`
3. Pretty-print with 2-space indent when shown to user
4. Optionally write to `decision-graph.json` if user requests a file artifact

## Usage

- Diff two assessments programmatically
- Feed Slack/dashboard bots (future renderer)
- Store in ticket/CMDB alongside markdown summary

## With markdown

Default deliverable remains markdown DORA report. JSON is **additive** unless user asks for JSON only.

Example shape: [decision-graph.example.yaml](../reference/decision-graph.example.yaml) (YAML authoring; JSON export is equivalent structure).
