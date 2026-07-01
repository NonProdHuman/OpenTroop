# Security Policy

## Supported Versions

OpenTroop is currently in early development. Security fixes are applied to
the `main` branch only.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

To report a vulnerability, use GitHub's private
[Security Advisories](../../security/advisories/new) feature. This lets you
describe the issue confidentially so it can be assessed and patched before
public disclosure.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- The affected file(s) and line numbers if known
- Any suggested fix, if you have one

We aim to acknowledge reports within 48 hours and will keep you updated as
we work toward a fix.

## Scope

The following are in scope:

- The FastAPI backend (`backend/`)
- The Next.js frontend (`apps/web/`)
- Authentication and tenant isolation logic
- SQL injection, privilege escalation, or cross-tenant data leakage
- Any exposure of PII (personally identifiable information), especially for minors

The following are **out of scope** for this project at this stage:

- Third-party services (Clerk, Cloud SQL, etc.) — report those to their vendors

## Disclosure Policy

Once a fix is merged we will publish a GitHub Security Advisory crediting
the reporter (unless they prefer to remain anonymous).
