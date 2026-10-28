# Code Discipline Rules (Ponytail Minimalism)

"The best code is the code you never wrote."

All AI agents writing code in this repository MUST evaluate requirements against the **7-Step Necessity Ladder** before generating implementation:

1. **Does this need to exist at all?** (YAGNI — if it's speculative, don't build it).
2. **Is it already in this codebase?** (Reuse existing components, utilities, and styles).
3. **Does the standard library do it?** (Use built-in JS/TS, Python, or standard primitives).
4. **Does a native platform feature do it?** (Use native HTML elements, CSS grid/flexbox, native dialogs, or browser/runtime primitives before reaching for libraries).
5. **Does an already installed dependency do it?** (Check package manifest before adding any new package).
6. **Can it be done in one clean line or utility?** (Keep solutions compact and simple).
7. **Only then**: Write the absolute minimum amount of code that satisfies the requirement.

## Non-Negotiable Standards
- **Lazy about solutions, rigorous about quality**: Never compromise on security, input validation at boundaries, error handling, or accessibility.
- **Mark intentional shortcuts**: If a deliberate shortcut or simplification is made to defer complex behavior, mark it with `shortcut:` or `ponytail:` comments so it can be indexed into the debt ledger (`ponytail-debt`).
- **No speculative architecture**: Do not introduce custom state managers, abstract factories, or premature abstractions for simple interactions.
