# ADR 0001: Static evidence pipeline

**Status:** Accepted

**Date:** 2026-07-20

## Context

The project needs repeatable historical comparisons, public evidence, and very low recurring
cost. It does not need accounts, private data, alerts, or request-time computation.

## Decision

Use a Python ingestion pipeline to produce privacy-minimised state, immutable change events,
and static Astro assets. Run it on a schedule in GitHub Actions and deploy the built site to
GitHub Pages.

Use JSON state for the initial release because it is transparent, reviewable, and requires no
binary data dependency. Revisit partitioned Parquet only when repository growth measurements
justify the extra build and review complexity.

## Consequences

- Hosting has no application server or database cost.
- Every published result can be tied to repository data and a workflow run.
- Scheduled updates depend on GitHub Actions availability and source API health.
- Repository size must be monitored as history grows.
