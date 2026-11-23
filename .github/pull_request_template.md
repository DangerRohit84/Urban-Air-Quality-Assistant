## Summary

<!-- What changed and why, in 2-4 sentences. -->

## Changes

<!-- Bullet the user-visible and internal changes. -->

## Verification

<!-- Paste the `python scripts/check_quality.py` summary or the commands you ran. -->

- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `mypy backend/app`
- [ ] `pytest -q`
- [ ] `python scripts/check_quality.py`

## Risk and rollback

<!-- Blast radius, migrations, config changes, and how to revert. -->

## Checklist

- [ ] Tests cover the new behaviour or regression
- [ ] No secrets, tokens or real user data in code, tests, logs or screenshots
- [ ] Backend modules stay under 150 lines
- [ ] Docs/CHANGELOG updated for user-visible changes
- [ ] Security-sensitive paths have an owner-scoping test
