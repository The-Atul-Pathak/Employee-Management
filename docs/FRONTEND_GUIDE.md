You are doing a full frontend polish pass on this entire Next.js 14 dashboard project. Read FRONTEND_GUIDE.md fully before touching any file.

Your job is to go file by file through the entire frontend and bring every component, page, and layout up to the standards defined in the guide — with a focus on the Motion & Smoothness section. This is a polish pass, not a rebuild. Do not change logic, routing, API calls, data structures, or business functionality. Only touch visual and interaction code.

---

## Step 1 — Global Setup (do this first, once)

1. In `globals.css`, add:
   - `@keyframes page-enter` and `.animate-page-enter` class
   - Dialog and drawer keyframe animations tied to `[data-state]`
   - `@media (prefers-reduced-motion: reduce)` block that nullifies all animations and transitions

2. Create `components/layout/page-wrapper.tsx` with the `<PageWrapper>` component that applies `animate-page-enter` to its children.

3. In `tailwind.config.ts`, extend the theme if needed to expose any custom animation utilities.

Do Step 1 before touching any other file.

---

## Step 2 — Layout Files

File order: `sidebar.tsx` → `header.tsx` → `breadcrumbs.tsx` → `(dashboard)/layout.tsx` → `(super-admin)/layout.tsx`

For each:
- Sidebar nav active indicator must slide (transition-transform), not jump
- Sidebar open/close: 220ms ease-in-out
- Header: no animation unless it has a dropdown or popover — those get 120ms ease-out
- All interactive elements get `transition-all duration-150 active:scale-[0.97]`

---

## Step 3 — Shared Components

File order: `stats-card.tsx` → `data-table.tsx` → `loading-skeleton.tsx` → `status-badge.tsx` → `empty-state.tsx` → `confirm-dialog.tsx`

Rules per component:

**stats-card.tsx**
- Add `transition-shadow duration-200 hover:shadow-md`
- If it shows a number metric, use Framer Motion's `useSpring` or `animate` to count up on mount (this is the approved Framer Motion use case)
- Support `animationDelay` via a `style` prop so pages can stagger up to 4 cards

**data-table.tsx**
- Table rows: `transition-colors duration-100 hover:bg-muted/50 cursor-pointer`
- Do NOT animate rows on every refetch — animation on mount only
- Wrap the table content (not the shell) in an opacity crossfade tied to `isLoading`:
  `transition-opacity duration-200` with `opacity-0` while loading, `opacity-100` when done

**loading-skeleton.tsx**
- Audit every skeleton variant — each must match its real layout pixel-for-pixel in height, column count, and spacing
- If any skeleton causes layout shift when content replaces it, fix the dimensions

**status-badge.tsx**
- No animation needed. Ensure color mapping is consistent and uses CSS variables, not hardcoded hex.

**empty-state.tsx**
- If it has an illustration or icon, add a subtle entrance: `animate-page-enter` is fine
- Framer Motion looping animation is approved here if there's an SVG illustration

**confirm-dialog.tsx**
- Must use the dialog keyframe animations from the guide via `[data-state="open"]` and `[data-state="closed"]`
- Do not suppress Radix UI's data-state attributes

---

## Step 4 — Pages

Wrap every `page.tsx` in `<PageWrapper>` as the outermost element (inside any auth/permission guards, but outside the actual content JSX).

File order:
`dashboard/page.tsx` → `users/page.tsx` → `users/[id]/page.tsx` → `attendance/page.tsx` → `leaves/page.tsx` → `teams/page.tsx` → `leads/page.tsx` → `projects/page.tsx` → `projects/[id]/page.tsx` → `tasks/page.tsx` → `companies/page.tsx` → `plans/page.tsx` → `features/page.tsx`

For each page:
- Wrap in `<PageWrapper>`
- Stats cards (if any) get staggered `animationDelay` in 50ms increments, max 4 items
- Skeleton → content swap uses opacity crossfade, not abrupt DOM replacement
- All buttons: `transition-all duration-150 active:scale-[0.97]`
- Modals triggered from this page: verify they use the dialog keyframe CSS
- Drawers triggered from this page: verify they use the drawer slide-in CSS

---

## Step 5 — Auth Page

`(auth)/login/page.tsx`:
- Form card entrance: `animate-page-enter`
- Input focus states: `transition-colors duration-150` (Tailwind's ring should already handle this — verify it's not suppressed)
- Submit button: loading spinner inline in the button, never disable the whole form while submitting

---

## Rules That Apply Everywhere

- `transition-all` is banned on elements that change width or height. Use `transition-transform`, `transition-opacity`, `transition-shadow`, or `transition-colors` specifically.
- No animation fires on TanStack Query background refetches — only on initial load or explicit user action.
- No `setTimeout` used to sequence animations — use `animation-delay` in CSS or `animationDelay` in style props.
- Framer Motion import is allowed only in: `stats-card.tsx`, `empty-state.tsx`, and any drag-and-drop component. Nowhere else.
- Every animation must have `animation-fill-mode: both` (or Tailwind's `fill-mode-both`) so there's no flash before or after.
- Do not add any new npm packages except Framer Motion if it's not already installed.

---

## Output Format

Work through the files in the exact order listed above. For each file:
1. State the filename
2. List what you changed in 1–2 lines
3. Output the full updated file

If a file already fully complies with the guide, write: `[filename] — no changes needed` and move on. Do not output the unchanged file.

Complete every file before stopping. Do not ask for confirmation between files.