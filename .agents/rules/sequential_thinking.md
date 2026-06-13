# Sequential Thinking Rule

> **Mandatory**: Before editing any code, you must invoke the `sequential_thinking` MCP tool to map out dependencies.

---

## When to Invoke

You **must** call the `sequentialthinking` tool on the `sequential-thinking` MCP server **before** making any code changes, including:

- Creating new files
- Modifying existing files
- Refactoring or restructuring code
- Adding new dependencies or imports
- Changing configuration files (`pyproject.toml`, `Dockerfile`, Terraform `.tf` files, GitHub Actions `.yml`)

## Purpose

Use sequential thinking to:

1. **Identify affected files** — Which files will this change touch?
2. **Map dependency chains** — What imports, calls, or references connect the affected files?
3. **Determine execution order** — In what sequence should edits be made to avoid broken intermediate states?
4. **Surface side effects** — Will this change break tests, configs, or downstream consumers?
5. **Validate against the DAG model** — Does this change respect the component dependency graph?

## How to Invoke

Call the `sequentialthinking` tool with a thought that describes:

- **What** you are about to change
- **Why** the change is needed
- **Which files and modules** are likely involved
- **What dependencies** exist between them

Example thought:
```
I need to add a Redis health check. This will involve:
1. Creating app/services/checks/redis_check.py (new file, extends BaseCheck)
2. Registering it in app/services/health_checker.py (imports redis_check)
3. Adding redis config to app/core/config.py (new Settings fields)
4. Adding the redis dependency to pyproject.toml
5. Writing tests in tests/unit/test_redis_check.py
Dependencies: redis_check.py depends on base.py and config.py, so those must be correct first.
```

## Exceptions

You may skip sequential thinking for:

- Fixing typos or comments
- Updating documentation-only files (`.md`)
- Running commands that don't modify source code (e.g., `git status`, `pytest`, `ruff check`)
- Viewing or reading files for research purposes
