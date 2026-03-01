# Phase 3 UI/UX Overhaul Plan: Productized Experience

## Summary
This overhaul will convert the current utility-style UI into a polished product experience using a new `/app/*` information architecture, a marketing-quality `/` landing page, and immersive chat/graph workspaces.  
Chosen direction is locked as: `Product shell`, `Calm premium visual style`, `Phased rollout`, `shadcn + Tailwind`, `hard URL cutover`, `marketing + entry home`, `hover preview + click pin graph inspector`, and `search + pin + recent chat list with auto-generated conversation IDs`.

## Implementation Status (2026-02-28)
- Route cutover and product shell: `DONE`
- Marketing landing + `/app/*` IA: `DONE`
- Chat and graph workspace overhaul: `DONE`
- Tailwind + shadcn foundation adoption: `DONE`
- Remaining manual QA pass (desktop/mobile + keyboard/touch smoke): `PENDING`

## Public Interface and Route Changes
1. URL structure will hard-cut from current top-level product routes to grouped routes under `/app/*`.
2. New route map:
   - `/` -> marketing landing page with CTA into `/app`
   - `/app` -> product dashboard
   - `/app/chat`
   - `/app/graph`
   - `/app/conversations`
   - `/app/conversations/[conversation_id]`
   - `/app/entities`
   - `/app/entities/[entity_id]`
   - `/app/schema`
   - `/app/search`
   - `/app/explain/[kind]/[id]`
3. Old routes (`/workspace`, `/chat`, `/graph`, `/entities`, `/schema`, `/search`, `/conversations`, `/explain`) will be removed (no redirects).
4. Backend API contracts stay unchanged for this phase; frontend will continue using existing endpoints in `frontend/lib/api.ts`.
5. New client persistence interfaces (localStorage):
   - `librarian.chat.pins.v1`
   - `librarian.chat.lastConversation.v1`
   - `librarian.shell.sidebarCollapsed.v1`

## Implementation Plan

## 1. Foundation: Design System and App Shell
1. Add Tailwind and shadcn setup to the Next.js frontend and migrate global styling from `globals.css` to tokenized Tailwind + CSS variables.
2. Define a calm premium theme with explicit tokens for surfaces, borders, typography scale, spacing scale, and motion timings.
3. Introduce reusable primitives for `AppShell`, `SidebarNav`, `TopBar`, `Panel`, `DataTable`, `EmptyState`, `LoadingState`, and `ErrorState`.
4. Implement desktop-first shell with responsive behavior:
   - Desktop: left navigation rail + top utility strip + content canvas.
   - Mobile: collapsible drawer navigation + sticky top bar.
5. Add consistent page-level layout contracts so graph and chat can run in full-height immersive modes.

## 2. New Marketing Landing (`/`)
1. Replace redirect-only home page with a full landing page that communicates product value, trust, and transparency.
2. Build sections: hero, core capabilities, explainability proof strip, workflow preview, and CTA into `/app`.
3. Add purposeful motion for section reveal and interactive hover feedback; keep motion subtle and performant.
4. Ensure landing remains visually distinct from in-app workspace while sharing design tokens.

## 3. New Product Route Group (`/app/*`)
1. Create `/app` dashboard as the default in-product entry point (success stats, recent activity, quick actions).
2. Move all existing Phase 3 pages into `/app/*` equivalents and update internal links accordingly.
3. Keep feature parity first, then apply visual and spacing redesign per page.
4. Remove old route files only after all links and deep references are updated.

## 4. Chat Workspace Overhaul (`/app/chat`)
1. Convert chat into a 3-region workspace:
   - Left conversation rail (search + pinned + recent).
   - Center transcript and composer (dominant area).
   - Right contextual controls (system prompt, extraction toggle, metadata).
2. Add `New Chat` behavior with auto-generated conversation ID format `chat-YYYYMMDD-HHMMSS`.
3. Load conversation list via existing `getConversations` and support revisit by selecting items from the rail.
4. Add pin/unpin behavior persisted in localStorage and sorted above recent items.
5. Keep existing message edit/delete behaviors and extraction status messaging.
6. Preserve direct-opening compatibility via `conversation_id` query param when present.

## 5. Graph Workspace Overhaul (`/app/graph`)
1. Convert graph page into a full-height sandbox layout where canvas is the dominant surface.
2. Use side inspector behavior: hover shows quick preview, click pins full inspector with editable node details and related relations table.
3. Keep existing filtering and layout controls, but move them into a compact control bar/drawer to maximize canvas area.
4. Improve visual hierarchy of nodes, edges, labels, and highlights for dense graphs.
5. Maintain existing edit/delete flows for entities and relations in pinned inspector mode.

## 6. Cross-Page UX Polish for “Finished Product” Feel
1. Apply unified typography, spacing, and interaction patterns to `/app/conversations`, `/app/entities`, `/app/schema`, `/app/search`, and `/app/explain/*`.
2. Upgrade tables with consistent toolbars, sticky headers where helpful, clearer empty states, and stronger row affordances.
3. Standardize page headers with actionable context, not descriptive filler copy.
4. Introduce subtle animated transitions between major route views and panel state changes.
5. Ensure every page has explicit loading/error/empty states with consistent tone and layout.

## 7. Hard Cutover and Cleanup
1. Remove old route implementations and old nav references once `/app/*` is complete.
2. Update `AppNav` and route links everywhere to new paths.
3. Update README and AGENTS_LOG progress entries to reflect new IA and UI architecture.
4. Run final build and route smoke validation before declaring cutover complete.

## Test Cases and Validation Scenarios

## Automated/Command Validation
1. `npm run build` passes with no route compile errors.
2. TypeScript build passes for all new route files and migrated components.
3. No unresolved imports from deleted old routes remain.

## Manual Smoke and UX QA (Desktop + Mobile)
1. `/` renders marketing landing and CTA navigates into `/app`.
2. `/app` loads dashboard without layout shift.
3. `/app/chat` shows conversation rail, can create new chat, can switch to historical chats, and pinned chats persist after reload.
4. `/app/chat` preserves sending, editing, deleting, and extraction feedback behavior.
5. `/app/graph` uses full-height canvas and supports hover preview plus click-pinned inspector.
6. `/app/graph` keeps filter controls usable without reducing core canvas usability.
7. `/app/entities`, `/app/schema`, `/app/search`, `/app/conversations`, and `/app/explain/*` remain functionally correct after route migration.
8. Responsive behavior works at common breakpoints (mobile portrait, tablet, desktop wide).
9. Keyboard navigation works for primary nav, chat conversation list, and graph inspector focus flow.
10. Color contrast and focus indicators remain visible across interactive controls.

## Assumptions and Defaults
1. No backend endpoint changes are required for this overhaul.
2. Route migration is intentionally breaking (`hard cutover`) and existing bookmarks to old URLs are out of scope.
3. Conversation pinning is client-local only (no server persistence in Phase 3 addition).
4. Existing data models and CRUD semantics for chat/graph/entities/schema remain unchanged.
5. Visual QA depth is `smoke + structured manual checklist`, not Playwright automation in this pass.
