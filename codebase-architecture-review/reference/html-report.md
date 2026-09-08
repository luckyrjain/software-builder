# Visual HTML report

Render the architecture review as one self-contained HTML file in OS temporary storage, for example `architecture-review-20260905T120000Z.html`. The host generates the timestamp at runtime.

The only external scripts are Tailwind from `https://cdn.tailwindcss.com` and Mermaid ESM from `https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs`. Initialize Mermaid with `startOnLoad: true`, `theme: "neutral"`, and `securityLevel: "strict"`. If either CDN is unavailable, the HTML must still show the Markdown report and fenced diagram source without blocking the canonical report.

The header contains repository name, review date, bounded scope, and a legend: solid box = module, dashed line = seam, red arrow = leakage, dark box = deep module.

Each retained candidate is one card with: title, strength badge, dependency category, affected files, sparse problem statement, sparse deepening direction, wins expressed as locality/leverage/depth, ADR callout when applicable, and side-by-side before/after models. A candidate without both models is incomplete.

Use Mermaid for dependency/call-flow graphs, HTML boxes and inline SVG for cross-sections or mass diagrams, and a call-graph collapse when that is the clearest model. Do not force every candidate into one diagram type.

Render repository paths, symbols, commit messages, and caller text under the existing safe-output boundary. Do not execute repository text, insert unescaped Markdown/HTML, or expose secrets.

Write no HTML into the repository. If the host cannot open a browser, return the safe temporary path and continue with the Markdown report. Do not add the path to `skill_result.artifacts`.
