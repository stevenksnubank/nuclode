---
name: security-review
description: Security review checklist for code changes. Lightweight checklist for code-reviewer or code-implementer. For full offensive testing with exploit POCs, use the active-defender agent instead.
---

# Security Review Checklist

## When to Use
- Any code change touching authentication or authorization
- New API endpoints or modified request handling
- Database queries with user-provided parameters
- File system operations with user-provided paths
- Changes to encryption, hashing, or token handling
- New external service integrations

## Checklist

### Input Validation
- [ ] All user inputs validated at system boundary
- [ ] Allow-list validation (not deny-list)
- [ ] Type checking enforced (no implicit coercion)
- [ ] Length/size limits on all string/array inputs
- [ ] Parameterized queries for all database operations
- [ ] Path traversal prevention for file operations
- [ ] Content-type validation for file uploads

### Authentication & Authorization
- [ ] Authentication required for all non-public endpoints
- [ ] Authorization checked for every resource access
- [ ] No hardcoded credentials or API keys
- [ ] Tokens have appropriate expiration
- [ ] Session invalidation on logout
- [ ] Rate limiting on auth endpoints
- [ ] Failed auth attempts logged

### Data Protection
- [ ] Sensitive data encrypted at rest
- [ ] TLS required for data in transit
- [ ] PII not logged or minimally logged
- [ ] Error messages don't leak internal details
- [ ] Secrets stored in env vars or secret manager (not code)
- [ ] Database connections use least-privilege accounts

### Dependencies
- [ ] No known CVEs in direct dependencies
- [ ] Dependencies pinned to exact versions
- [ ] No unnecessary dependencies added
- [ ] Transitive dependencies reviewed for risk

### Output Encoding
- [ ] HTML output properly escaped (XSS prevention)
- [ ] JSON responses use proper content-type headers
- [ ] SQL output uses parameterized queries
- [ ] Command output properly escaped (injection prevention)
