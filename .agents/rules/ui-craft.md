# UI & UX Craftsmanship Rules (Impeccable & Intent)

All AI agents working on user interfaces in this project MUST adhere to these rules:

## 1. Eliminate AI Clichés
- **No Unjustified Gradients**: Never wrap entire headers, cards, or hero backgrounds in multi-stop purple/blue/pink radial gradients unless explicitly specified in docs/DESIGN.md.
- **No Card Clutter**: Do not default to wrapping every single item in a card with heavy borders and drop shadows. Use clear typographic hierarchy and whitespace for separation.
- **No Meaningless Microcopy**: Replace placeholder buzzwords ("Revolutionize your digital paradigm") with direct, clear, high-signal explanations.

## 2. Design System Alignment
- Read and follow docs/DESIGN.md for color tokens, typography scales, and component standards.
- Read and follow docs/PRODUCT.md for company voice, target audience, and service details.
- Use semantic design tokens and framework utility classes rather than arbitrary hardcoded hex values in components.

## 3. Accessibility & Contrast
- Maintain WCAG AA compliance (4.5:1 minimum contrast ratio for standard text, 3:1 for large text).
- Always include accessible labels, keyboard focus rings, and proper ARIA attributes where semantic HTML alone is insufficient.

## 4. UI Quality Verification
- Before presenting UI changes to the user, run `npx impeccable detect` to catch anti-patterns and contrast regressions.
