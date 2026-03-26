## Coding Standards

### Core Principles

1. **Functional Programming First**
   - Prefer pure functions without side effects
   - Use immutable data structures
   - Avoid mutable state
   - Functions should do one thing well
   - Compose functions to build complexity

2. **Simplicity Over Cleverness**
   - Write code that's easy to understand
   - Avoid clever tricks that obscure meaning
   - Explicit is better than implicit
   - Simple solutions are maintainable solutions
   - If it's hard to explain, it's probably too complex

3. **Immutability by Default**
   - Data structures should be immutable
   - Use const/final by default
   - Mutations should be rare and explicit
   - Build new data instead of modifying existing

4. **Fail Fast, Fail Explicitly**
   - Validate inputs early
   - Use explicit error types
   - Don't hide errors
   - Make failure cases obvious
   - Defensive programming at boundaries

5. **Composition Over Inheritance**
   - Prefer composition and interfaces
   - Avoid deep inheritance hierarchies
   - Use dependency injection
   - Separate concerns cleanly

6. **Security First**
   - Validate all inputs
   - Never trust external data
   - Use allow lists, not deny lists
   - Fail secure (deny by default)
   - Log security events with context

7. **Testing is Non-Negotiable**
   - Write tests first (TDD when possible)
   - Test edge cases and error paths
   - Integration tests for workflows
   - Security tests for critical paths
   - 85%+ coverage minimum, 100% for critical code

8. **Code as Documentation**
   - Use descriptive names (no abbreviations)
   - Functions should be self-documenting
   - Comments explain "why", not "what"
   - Type hints/annotations required
   - Complex logic needs explanation

### Language-Specific Standards

#### Python (Recommended Style)
```python
# GOOD: Functional, immutable, explicit
def calculate_total(items: List[Item]) -> Decimal:
    """Calculate total price with clear validation."""
    if not items:
        raise ValueError("Cannot calculate total of empty list")

    return sum(
        (item.price * item.quantity for item in items),
        start=Decimal("0")
    )

# GOOD: Type hints, immutable structures, explicit errors
@dataclass(frozen=True)
class PaymentResult:
    """Immutable payment result."""
    status: PaymentStatus
    transaction_id: str
    amount: Decimal
    timestamp: datetime

# GOOD: Pure function, no side effects
def validate_payment_request(request: PaymentRequest) -> Result[PaymentRequest, ValidationError]:
    """Validate payment request without side effects."""
    if request.amount <= Decimal("0"):
        return Err(ValidationError("Amount must be positive"))

    if not request.account_id:
        return Err(ValidationError("Account ID required"))

    return Ok(request)
```

#### Python Best Practices
- Use `dataclasses` with `frozen=True` for immutability
- Prefer `typing` module for type hints
- Use `Result` type for error handling (returns library)
- Generators for lazy evaluation
- Context managers for resource cleanup
- `__slots__` for performance-critical classes
- Abstract base classes for interfaces
- No global mutable state

#### TypeScript/JavaScript (Recommended Style)
```typescript
// GOOD: Functional, immutable, explicit types
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

#### TypeScript Best Practices
- Use `readonly` for immutability
- Prefer `interface` over `type` for objects
- Use discriminated unions for variant types
- `const` by default, never `var`
- Functional patterns (map, filter, reduce)
- No `any` types (use `unknown` if needed)
- Strict mode enabled
- Result type for error handling

#### Go (Recommended Style)
```go
// GOOD: Explicit errors, value types, clear structure
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

#### Go Best Practices
- Explicit error handling (no exceptions)
- Value types over pointers when possible
- Interfaces for abstraction
- Table-driven tests
- Context for cancellation
- Defer for cleanup
- Package names: short, lowercase, no underscores
- Don't use `panic` except for unrecoverable errors

### Testing Standards

#### Test Structure (AAA Pattern)
```python
def test_payment_validation_rejects_negative_amount():
    """Test that payment validation rejects negative amounts."""
    # Arrange: Set up test data
    request = PaymentRequest(
        account_id="test-123",
        amount=Decimal("-10.00"),
        currency="USD"
    )

    # Act: Execute the code under test
    result = validate_payment_request(request)

    # Assert: Verify expected outcome
    assert result.is_err()
    assert "positive" in str(result.error)
```

#### Coverage Requirements
- **85% minimum** for general code
- **100% required** for:
  - Security validation logic
  - Authentication/authorization
  - Payment processing
  - Data validation
  - Error handling paths
- Edge cases must be tested
- Security scenarios required
- Integration tests for workflows

### Security Standards

1. **Input Validation**
   - Validate at system boundaries
   - Use allow lists (not deny lists)
   - Reject invalid input early
   - Sanitize for context (SQL, HTML, etc.)

2. **Authentication & Authorization**
   - Never roll your own crypto
   - Use proven libraries
   - Fail closed (deny by default)
   - Log all auth events

3. **Data Protection**
   - Encrypt sensitive data at rest
   - Use TLS for data in transit
   - Never log secrets
   - Sanitize error messages

4. **Dependency Management**
   - Pin exact versions
   - Regular security updates
   - Audit dependencies
   - Minimize attack surface

