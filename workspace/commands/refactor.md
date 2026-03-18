---
description: Refactor code safely with test verification
---

# Refactor

When invoked, follow this process:

1. **Understand current state** - Read the code to refactor, understand its purpose
2. **Check test coverage** - Run existing tests to establish a green baseline
3. **Plan the refactoring** - Identify specific changes (extract function, rename, simplify)
4. **Make incremental changes** - One refactoring at a time, not batch changes
5. **Test after each change** - Run tests to verify behavior is preserved
6. **Verify no behavior change** - The refactored code must produce identical outputs

## Safe refactoring types:
- **Extract function** - Pull out repeated code into named function
- **Rename** - Improve clarity of names (variables, functions, classes)
- **Simplify conditionals** - Flatten nested if/else, use early returns
- **Remove dead code** - Delete unused imports, functions, variables
- **Consolidate duplicates** - DRY up repeated patterns

## Do NOT:
- Change behavior during refactoring (that's a feature change)
- Refactor without existing tests (write tests first)
- Make multiple unrelated refactorings in one step
- Add new features "while you're in there"
