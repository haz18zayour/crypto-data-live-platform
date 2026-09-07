# Coding standards

The best code is the code you never wrote. Before writing any, walk this ladder and stop at
the first rung that works:

1. Does this need to exist at all?
2. Is it already in this codebase?
3. Is it in the standard library?
4. Is it a native platform feature?
5. Is it in a dependency already installed?
6. Can it be one line?
7. Only then: the smallest implementation that satisfies the acceptance criteria.

No abstraction for single-use code. No configurability nobody asked for. No error handling
for cases the criteria do not name. Match the surrounding style even where you would differ.

Autonomous agents over-engineer by default — they are rewarded for producing, not for
declining to produce. This ladder is the counterweight, and it is why a story's criteria
are the ceiling on its scope as well as the floor.

## Changes

Every changed line should trace to the story being implemented. If your change orphans an
import or a variable, remove it. If you notice unrelated dead code, mention it in the
progress notes — do not delete it.

## Tests

A test that asserts nothing fails verification, and rightly so. Name the behaviour, not the
function. For a bug fix, write the test that reproduces it first and watch it fail.
