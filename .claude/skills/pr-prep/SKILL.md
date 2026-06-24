---
name: pr-prep
description: Audits modified files, updates documentation, and drafts a clean git commit message.
disable-model-invocation: true
---
## Steps to Execute
1. Run the local test suite using `pytest` (or your chosen runner) to verify 100% compliance.
2. Look at the local `git diff` of changes made during this session.
3. Automatically update the `README.md` or `CHANGELOG.md` if any environment variables or setup steps changed.
4. Draft a concise, professional Git commit message summarizing the exact fixes.
