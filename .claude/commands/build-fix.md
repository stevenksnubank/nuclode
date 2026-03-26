---
description: Diagnose and fix build or compilation errors
---

# Build Fix

When invoked, follow this process:

1. **Reproduce the error** - Run the build command and capture the full error output
2. **Identify the root cause** - Read the error message, identify the failing file and line
3. **Read the failing code** - Use Read tool to examine the file
4. **Identify the fix** - Determine the minimal change needed
5. **Apply the fix** - Use Edit tool to make the change
6. **Verify** - Re-run the build command to confirm the fix
7. **Run tests** - Ensure the fix doesn't break anything

## Common patterns:
- **Import errors**: Missing dependency or wrong import path
- **Type errors**: Mismatched types, missing type annotations
- **Syntax errors**: Missing brackets, incorrect indentation
- **Version conflicts**: Incompatible dependency versions

## Do NOT:
- Suppress errors without fixing root cause
- Add `# type: ignore` or `@ts-ignore` without explaining why
- Downgrade dependencies to avoid type errors
- Delete tests that fail due to the build error
