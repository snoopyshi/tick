/**
 * List of available font names (visit the url `/settings/appearance`).
 * This array is used to generate dynamic font classes (e.g., `font-inter`, `font-manrope`).
 *
 * 📝 How to Add a New Font (Tailwind v4+):
 * 1. Add the font name here.
 * 2. Self-host the font (prefer `@fontsource` / `@fontsource-variable`) and import
 *    its CSS from `src/main.tsx`. Do not load fonts from fonts.googleapis.com.
 * 3. Add the new font family to `theme.css` using `@theme inline` / `font-family`.
 *
 * Example:
 * fonts.ts           → Add 'roboto' to this array.
 * main.tsx           → `import '@fontsource-variable/roboto/wght.css'`
 * theme.css          → `--font-roboto: 'Roboto Variable', 'Roboto', sans-serif;`
 */
export const fonts = ['inter', 'manrope', 'system'] as const
