# tech-debt-assessor

Turns a raw backlog of tech-debt items into a **ranked priority list**. Scores each item on business
impact, engineering drag, operational risk, and effort, combines them into an explicit priority score
(`business impact × engineering drag × operational risk ÷ effort`), and derives a `Now | Next | Later |
Won't-fix now` verdict per item.

Unlike gut-feel triage, this skill makes every scoring dimension explicit and shows its work — every
item's score is traceable to cited evidence, and an item that can't be scored is flagged as an honest
`Unknown` rather than silently defaulted into a low-priority bucket.

## When to use

- Rank a backlog of tech-debt items before quarterly planning
- Turn vague "this code is bad" complaints into a scored, ranked list
- Decide relative priority across many debt items with different evidence quality
- Build a defensible case for why one item outranks another

## Install

```bash
make install-tech-debt-assessor
```

Details: [SETUP.md](SETUP.md).

## Pipeline

```
Inputs → Analyze → Report
```

Agent instructions: [SKILL.md](SKILL.md).
