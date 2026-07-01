<!-- PRs target `develop`, not `main`. See CONTRIBUTING.md. -->

## Summary

<!-- What does this change and why? -->

Closes #

## Checklist

- [ ] Branched from and targeting `develop`
- [ ] One logical change; PR stays focused
- [ ] Tests added/updated (`uv run pytest`) — **bug fixes include a regression test**
- [ ] New tenant-scoped models subclass `TrackedBase` (platform entities `PlatformBase`)
- [ ] Migration generated if a model changed (`uv run alembic revision --autogenerate`)
- [ ] Non-trivial feature has a `docs/spec/` spec
- [ ] Pre-commit hooks pass (ruff, mypy, tsc, eslint, gitleaks)
