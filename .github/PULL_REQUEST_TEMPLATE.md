<!-- Thanks for contributing. Keep this short — the diff explains what; tell us why. -->

## What and why

<!-- What was broken or missing, and how does this change address it? -->

## Verification

<!-- "Tests pass" is necessary, not sufficient. Unit tests cannot hear a dub. -->

- [ ] `ruff check .` passes
- [ ] `pytest` passes
- [ ] Ran it on a real video (paste the command and what you observed):

```
voxa ...
```

- [ ] If I changed the golden files, I re-recorded them with `UPDATE_GOLDEN=1 pytest
      tests/test_golden.py` and reviewed every line of the diff.

## Dependencies

- [ ] No new required dependency, **or** it is an optional extra and is recorded in
      [NOTICE.md](../NOTICE.md)
- [ ] No GPL-licensed required dependency was added

## Notes for the reviewer

<!-- Anything surprising, any trade-off you made, anything you are unsure about. -->
