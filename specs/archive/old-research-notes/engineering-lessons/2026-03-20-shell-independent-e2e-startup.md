# Shell-independent Playwright startup and preserved onboarding

## Lesson

For this repository, keep browser e2e startup shell-independent and treat README onboarding as part of the product surface, not optional polish.

## Why it mattered

The prior Playwright config embedded fixture preparation and backend startup in one shell command that depended on heredocs and shell chaining. That made failures environment-specific and easy to misread as app regressions. In the same area, README edits had drifted toward architecture summary and lost practical onboarding steps that new operators actually need.

## Guardrail

Use dedicated preparation scripts plus direct process spawning or Playwright global setup/teardown for e2e startup. When editing README, preserve clone/install/config/LM Studio/run/test/output guidance alongside architecture notes so a new user can still operate the app from scratch.
