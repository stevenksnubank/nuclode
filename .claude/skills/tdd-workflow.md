---
name: tdd-workflow
description: Test-driven development workflow. Use when implementing features or fixing bugs to ensure tests are written before code. For post-implementation test generation, use the test-writer agent instead.
---

# TDD Workflow

## When to Use
- Implementing any new feature (write failing test first)
- Fixing bugs (write failing test to reproduce, then fix)
- Refactoring (ensure tests exist before changing code)

## The Cycle

### 1. RED - Write Failing Test
Write a test that describes the desired behavior. Run it. It MUST fail.

```bash
# Python
pytest tests/path/test_feature.py::test_name -v
# Expected: FAIL

# TypeScript
npx vitest run tests/feature.test.ts -t "test name"
# Expected: FAIL

# Go
go test -run TestName ./path/...
# Expected: FAIL
```

### 2. GREEN - Minimal Implementation
Write the MINIMUM code to make the test pass. No extras. No "while I'm here" improvements.

```bash
# Run the same test
pytest tests/path/test_feature.py::test_name -v
# Expected: PASS
```

### 3. REFACTOR - Clean Up
With green tests as a safety net, improve the code:
- Extract common patterns
- Rename for clarity
- Remove duplication
- Simplify logic

```bash
# Run full test suite to ensure nothing broke
pytest
# Expected: ALL PASS
```

### 4. REPEAT
Move to the next behavior. Aim for short cycles — if a single RED-GREEN-REFACTOR cycle takes significantly longer than expected, break the behavior into smaller increments.

## Test Quality Checklist
- [ ] Tests one specific behavior (not multiple)
- [ ] Uses AAA pattern (Arrange, Act, Assert)
- [ ] Has descriptive name: `test_[function]_[scenario]_[expected]`
- [ ] Is isolated (no test-to-test dependencies)
- [ ] Is deterministic (no flaky behavior)
- [ ] Covers edge cases (empty, null, boundary values)
- [ ] Includes error cases (invalid input, failures)

## Anti-Patterns to Avoid
- Writing tests after implementation (defeats TDD purpose)
- Writing multiple features before testing
- Tests that test implementation details instead of behavior
- Tests that are tightly coupled to each other
- Skipping the RED step (you must see the test fail first)
