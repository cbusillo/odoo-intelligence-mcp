# Security Policy

## Supported Versions

Security fixes target the current `main` branch. There are no separate
supported release lines.

## Reporting a Vulnerability

Report suspected vulnerabilities privately through GitHub's
[Report a vulnerability](https://github.com/cbusillo/odoo-intelligence-mcp/security/advisories/new)
form. Do not open a public issue for a vulnerability.

Include the commit, the MCP tool and arguments, the impact, and the
smallest steps that reproduce it.

Do not send database contents, customer data, credentials, `.env` files, or
other personal data. Use redacted or made-up values.

This is a single-maintainer project. Reports are handled on a best-effort
basis, and I aim to reply within seven days.

## Scope

Relevant reports include:

- tool arguments that run commands or code in the container beyond the
  intended analysis;
- tools reading files or data outside the configured Odoo project;
- credentials from environment files showing up in tool output or logs; and
- dependency or GitHub Actions supply-chain problems.

Problems in Odoo itself should go to Odoo S.A.
