---
description: Check test coverage and identify untested code paths
---

# Test Coverage

When invoked, follow this process:

1. **Run coverage** - Execute the test suite with coverage reporting:
   - Python: `pytest --cov=src --cov-report=term-missing`
   - TypeScript: `npx vitest run --coverage`
   - Go: `go test -coverprofile=coverage.out ./... && go tool cover -func=coverage.out`

2. **Identify gaps** - Find files/functions below 85% coverage

3. **Prioritize** - Focus on:
   - Security-critical code (must be 100%)
   - Error handling paths
   - Edge cases and boundary conditions
   - Business logic

4. **Report** - List uncovered lines grouped by priority:
   - CRITICAL: Security/auth code without tests
   - HIGH: Error handling without tests
   - MEDIUM: Business logic without tests
   - LOW: Utility code without tests

5. **Suggest tests** - For each gap, suggest specific test cases with names and scenarios
