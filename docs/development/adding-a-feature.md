# Adding a feature safely

1. Write the user problem and observable acceptance criteria.
2. Read `docs/project/current-state.md` and the module-specific LLD.
3. Decide the smallest existing boundary; do not add a new framework/service without measured need.
4. Define input/output types, failure behavior, and provenance before implementation.
5. Add focused unit tests and service-backed tests when an adapter is involved.
6. Run the full suite and inspect the actual output.
7. Update the relevant portal page, status table, ADR if a technology/algorithm decision changed, and roadmap.
8. Report unverified behavior and resource impacts explicitly.
