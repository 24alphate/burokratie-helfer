# Private Mode — design note

Phase E/E6 deliverable. **This is a planning document, not an implementation.**

The user can already wipe everything via the "Delete my saved data" button
([DeleteSavedData.tsx](../burokratie-helfer/frontend/src/components/layout/DeleteSavedData.tsx)).
That covers the explicit-delete case. Private Mode would cover the implicit-delete
case: the user closes the tab and trusts that nothing they entered persists.

## Current persistence (status quo)

Backed by [Zustand `persist`](https://github.com/pmndrs/zustand) with `name: "bh-store"`.
Storage backend: `localStorage` (default for Zustand persist when no
`storage:` option is set). What gets persisted:

- pdfToken, pdfUploadedAt, lastSavedAt
- fields, extractedFieldIds, fieldsForCaseId
- answeredValues, answeredKeys
- documentId, currentFilename, currentFileSize, currentFileLastModified
- uploadAttemptId, fieldsForUploadAttemptId
- supportLevel, templateId
- locale

Key facts:
- `localStorage` survives tab close, browser close, OS reboot.
- It is per-origin, per-browser-profile.
- It is NOT shared across devices.
- It is NOT shared across browsers (Safari ↔ Chrome on the same Mac = separate).
- The token itself is signed but readable; the PDF is reconstructable from it.

## Threat model Private Mode would address

A user on a shared computer (library, family computer, coworker's laptop)
who completes a form, downloads it, and walks away. Today, the next user
of that browser can:

1. Open the app and see "Continue saved form" with the prior user's
   filename, answer count, and reconstructable PDF (until 4h token expiry).
2. Click "Continue" and see all previous answers in plain text.

The "Delete my saved data" button addresses this — but only if the prior
user remembers to click it. Private Mode would make the safe behavior the
default, not the explicit-action behavior.

## Proposed design

Add a single new toggle to the home page, BEFORE the language picker:

```
[ ] Private mode — your data disappears when you close this tab
```

Default: **off** (preserves the existing "continue tomorrow" UX which is
the right choice for the majority case — an immigrant filling out a form
over multiple days on their own phone).

When ON:
- Zustand `persist` middleware switches `storage` to a thin adapter around
  `sessionStorage` instead of `localStorage`.
- Behavior changes:
  - State survives navigation within the tab (essential — the multi-page
    flow depends on it).
  - State survives a refresh of the same tab (sessionStorage rule).
  - State does NOT survive closing the tab.
  - State is NOT shared between tabs (sessionStorage rule).

When OFF (current behavior):
- Same as today. State persists in `localStorage`. User can use
  "Delete my saved data" for explicit cleanup.

## Implementation sketch (small enough to do in one PR)

1. Add `privateMode: boolean` to the case store; persist this single field
   in `localStorage` so the toggle preference itself survives across tabs.

2. Build a `createSessionStoragePersistor()` adapter that implements the
   Zustand `StateStorage` interface against `sessionStorage`.

3. Switch the persist `storage` option to a function that returns
   `sessionStorage` when `privateMode === true`, `localStorage` otherwise.
   Note: Zustand `persist` reads its config once at store initialization.
   Switching mid-session requires a small workaround — call `persist.clearStorage()`
   when toggled and re-hydrate from the new backend on next mount.
   Easier alternative: require a page reload after toggling.

4. Add the toggle UI to [app/page.tsx](../burokratie-helfer/frontend/src/app/page.tsx).
   Single checkbox, locale-aware label, disabled when there is already a
   saved form in localStorage (force the user to "Delete my saved data"
   first before changing modes).

5. Add a test (currently no Jest setup — see Phase C/C5 manual QA pattern):
   - localStorage starts empty
   - Enable private mode → reload → fill form → close tab → re-open URL
     → no saved form visible
   - Disable private mode → fill form → close tab → re-open URL → saved
     form is visible

## Estimated effort

- Adapter + store changes: 1–2 hours
- UI toggle + locales (10 strings × 10 locales): 1 hour
- Manual QA across browsers (sessionStorage behavior varies on iOS Safari
  in private browsing): 1 hour
- Total: half a day

## Why we did not implement in Phase E

The user spec explicitly said "Optional: session/private mode plan only.
Do not implement unless small." The toggle is small but the cross-tab
behavior, the iOS Safari edge cases (private browsing throws on
sessionStorage write in some versions), and the mid-session switch UX all
deserve a focused phase. Recommended for a future Phase F/Privacy.
