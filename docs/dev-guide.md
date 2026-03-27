# Developer Guide

Adjacency follows the same docs-as-code flow as the other repos in the stack.

## Useful commands

```bash
pytest
mypy src/adjacency
ruff check src tests
black --check src tests
isort --check-only src tests
interrogate src
mkdocs build
```

The public docs are intentionally small: they describe the stable workflow and
API surfaces, not every internal helper or experiment.
