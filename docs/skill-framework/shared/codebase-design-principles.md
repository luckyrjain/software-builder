# Codebase Design Principles

This doctrine defines the shared terms and decision rules for evaluating or changing
codebase architecture. These rules are normative: a proposed change **MUST** explain
the observed need it addresses and **MUST NOT** treat a vocabulary label or a static
measurement as proof by itself.

## Contract surface

The **contract surface** is the set of behaviors, data shapes, failure modes, and
operational expectations that a consumer may rely on. A change **MUST** preserve an
existing contract surface or deliberately migrate every affected consumer. Contracts
should be explicit at boundaries so callers do not depend on incidental internals.

## Change locality

**Change locality** is the degree to which one product change can be made in one
bounded area. Design work **SHOULD** improve locality when repeated changes require
coordinated edits across unrelated modules; it **MUST NOT** move code merely to make
the directory tree look more regular.

## Behavioral leverage

**Behavioral leverage** is the amount of useful product behavior enabled or protected
by a design choice relative to its ongoing complexity. A refactor **MUST** identify
the behavior, reliability, or change it improves, rather than counting indirection or
lines moved as its benefit.

## Seam

A **seam** is a stable point where an implementation can vary, be supplied, or be
observed without changing its consumer's contract. Seams **MUST** solve observed
needs, such as a real variation, integration boundary, or test isolation requirement.
One implementation does not justify an abstraction or a new seam.

## Adapter

An **adapter** translates one contract into another at a boundary. An adapter **MUST**
keep source-specific details on the boundary side and present the consumer contract
on the other side. It **SHOULD NOT** become a general-purpose pass-through layer
without a translation or isolation responsibility.

## Cohesion

**Cohesion** is the extent to which a module's responsibilities change for the same
reasons. A module **SHOULD** group behavior around one coherent responsibility and
**MUST NOT** become a convenient container for unrelated helpers simply because they
are nearby.

## Coupling

**Coupling** is the degree to which one module depends on another module's details.
Dependencies **SHOULD** use the smallest meaningful contract and **MUST NOT** expose
or rely on private representation when a public behavior is sufficient.

## Dependency direction

**Dependency direction** describes which layer knows about which other layer. Policy,
domain, and application behavior **MUST NOT** depend directly on delivery mechanisms
when a boundary can invert that dependency. Lower-level details may depend on stable
higher-level contracts, not the reverse.

## Test surface

The **test surface** is the production-facing behavior a test exercises and observes.
Tests **MUST** use meaningful production contracts: fakes and fixtures may stand in
for external systems, but assertions must remain tied to behavior that production
consumers can observe. Tests **MUST NOT** require new abstractions solely to inspect
private implementation details.

## Abstraction cost

**Abstraction cost** is the cognitive, maintenance, and change burden introduced by a
new interface, layer, or indirection. An abstraction **MUST** earn that cost through
an observed need and durable behavioral leverage. A large file, duplicate-looking
code, or a desire to refactor is evidence to investigate, not sufficient justification
for an abstraction.

## AI navigability

**AI navigability** is how readily a human or AI can locate the ownership, contracts,
and change path for a behavior. Code **SHOULD** use intention-revealing names, bounded
modules, and explicit boundaries so a reader can trace a request without reconstructing
hidden conventions. It **MUST NOT** be improved by scattering a single responsibility
across layers without an observed need.

## Module depth

A deep module hides substantial behavior behind a smaller meaningful interface. A shallow pass-through exposes nearly the same knowledge callers need to perform the behavior themselves. Depth is judged from contract surface, caller knowledge, and behavioral leverage; file size and class count are not depth measures.

## Interface surface

Interface surface includes operations, parameters, ordering, invariants, errors, configuration, performance expectations, and state assumptions. A short type signature can still have a wide contract surface when callers must understand incidental sequencing or representation.

## Deletion test

Ask what happens if the proposed module or abstraction is deleted. If the behavior and complexity disappear, the module was likely an unnecessary pass-through. If the complexity spreads into multiple callers or duplicates policy, the module may be earning its abstraction cost. The result is evidence for a decision, not an automatic refactor mandate.

## Real versus hypothetical seams

A seam earns its cost when an observed variation, integration boundary, or production-observable test need exists. One hypothetical implementation is not enough for a generic adapter. Count concrete variations when available, and document the exception when a single external integration boundary is itself the reason for isolation.

## Interface as test surface

Production callers and tests should cross the same meaningful interface. Tests may substitute a real external dependency at an earned seam, but they must not expose private helpers or create a mock-only seam.

## Evidence threshold

A static smell alone, such as file size, dependency counts, duplication reports, or
directory shape, does not independently prove that refactoring is warranted. Smells
may prompt investigation, but a refactoring decision **MUST** connect evidence to an
observed cost, a production contract, and an expected improvement in change locality
or behavioral leverage.
