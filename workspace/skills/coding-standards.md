---
name: coding-standards
description: Full coding standards reference with language-specific examples. Use when planning, implementing, or reviewing code for detailed style guidance.
---

# Coding Standards — Full Reference

This is the detailed version of the coding standards defined in CLAUDE.md. It includes language-specific code examples and extended best practices. The principles in CLAUDE.md are authoritative; this skill provides implementation guidance.

## Core Principles

1. **Functional Programming First** — Pure functions, immutable data, no mutable state, compose to build complexity
2. **Simplicity Over Cleverness** — Easy to understand, explicit over implicit, if it's hard to explain it's too complex
3. **Immutability by Default** — const/final by default, build new data instead of modifying existing
4. **Fail Fast, Fail Explicitly** — Validate early, explicit error types, defensive at boundaries
5. **Composition Over Inheritance** — Interfaces, dependency injection, separate concerns
6. **Security First** — Validate inputs, never trust external data, allow lists, fail secure
7. **Testing is Non-Negotiable** — TDD, edge cases, 85%+ coverage, 100% for critical code
8. **Code as Documentation** — Descriptive names, self-documenting, comments explain "why", type hints required

## Python (Recommended Style)

```python
# Immutable data structures
@dataclass(frozen=True)
class PaymentResult:
    status: PaymentStatus
    transaction_id: str
    amount: Decimal
    timestamp: datetime

# Pure function, explicit errors
def validate_payment_request(request: PaymentRequest) -> Result[PaymentRequest, ValidationError]:
    if request.amount <= Decimal("0"):
        return Err(ValidationError("Amount must be positive"))
    if not request.account_id:
        return Err(ValidationError("Account ID required"))
    return Ok(request)
```

**Best Practices:**
- `dataclasses` with `frozen=True` for immutability
- `typing` module for type hints on all public functions
- `Result` type for error handling (returns library)
- Generators for lazy evaluation
- Context managers for resource cleanup
- `__slots__` for performance-critical classes
- No global mutable state

## TypeScript (Recommended Style)

```typescript
interface PaymentRequest {
  readonly accountId: string;
  readonly amount: number;
  readonly currency: string;
}

type Result<T, E> = { ok: true; value: T } | { ok: false; error: E };

function validatePayment(request: PaymentRequest): Result<PaymentRequest, string> {
  if (request.amount <= 0) {
    return { ok: false, error: "Amount must be positive" };
  }
  if (!request.accountId) {
    return { ok: false, error: "Account ID required" };
  }
  return { ok: true, value: request };
}
```

**Best Practices:**
- `readonly` for immutability
- `interface` over `type` for objects
- Discriminated unions for variant types
- `const` by default, never `var`
- No `any` types (use `unknown` if needed)
- Strict mode enabled

## Go (Recommended Style)

```go
type PaymentRequest struct {
    AccountID string
    Amount    decimal.Decimal
    Currency  string
}

func (p PaymentRequest) Validate() error {
    if p.Amount.LessThanOrEqual(decimal.Zero) {
        return fmt.Errorf("amount must be positive: %v", p.Amount)
    }
    if p.AccountID == "" {
        return errors.New("account ID is required")
    }
    return nil
}
```

**Best Practices:**
- Explicit error handling (no exceptions)
- Value types over pointers when possible
- Interfaces for abstraction
- Table-driven tests
- Context for cancellation
- Defer for cleanup
- Don't use `panic` except for unrecoverable errors

## Testing Standards

### AAA Pattern
```python
def test_payment_validation_rejects_negative_amount():
    # Arrange
    request = PaymentRequest(account_id="test-123", amount=Decimal("-10.00"), currency="USD")
    # Act
    result = validate_payment_request(request)
    # Assert
    assert result.is_err()
    assert "positive" in str(result.error)
```

### Coverage Requirements
- **85% minimum** for general code
- **100% required** for: security validation, authentication/authorization, critical business logic, data validation, error handling paths

## Security Standards

1. **Input Validation** — Validate at boundaries, allow lists, reject invalid early, sanitize for context
2. **Authentication & Authorization** — Proven libraries, fail closed, log all auth events
3. **Data Protection** — Encrypt at rest, TLS in transit, never log secrets, sanitize errors
4. **Dependency Management** — Pin exact versions, regular security updates, audit dependencies
