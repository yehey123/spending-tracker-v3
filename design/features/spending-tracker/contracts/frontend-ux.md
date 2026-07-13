# Frontend UX Contract — Spending Tracker

Framework: Next.js 14 (App Router). Mobile-first. Capacitor for iOS/Android.

---

## Navigation

Bottom tab bar (mobile), side nav (desktop ≥ 768px):

| Tab | Route | Icon |
|---|---|---|
| Dashboard | `/` | BarChart2 |
| Transactions | `/transactions` | List |
| Upload | `/upload` | Upload |
| Settings | `/settings` | Settings |

---

## Page: Dashboard `/`

Sections (top to bottom):

1. **Month picker** — prev/next arrows, current month label (`January 2026`)
2. **Cash flow summary** — two stat cards side by side: Total In (green) / Total Out (red); Net below them
3. **Spending by Category** — donut chart (`SpendingDonut`); legend below with category name + amount + %
4. **Monthly Cash Flow** — grouped bar chart (`CashFlowBar`) for last 6 months; credit = green bars, debit = red bars
5. **Recent Transactions** — last 5 transactions, tap → goes to `/transactions`

Empty state (no transactions for month): illustration + "Upload a statement to get started" CTA → `/upload`.

---

## Page: Transactions `/transactions`

Layout:
- Filter bar: month picker + direction toggle (All / Debit / Credit) + category dropdown
- Infinite scroll list (load 50 at a time)
- Each row:
  - Left: date (MMM DD), description (truncated 1 line)
  - Right: amount (red for debit, green for credit), category badge
- Tap row → inline edit sheet (slide up from bottom):
  - Description (text input, pre-filled)
  - Category (horizontal scroll of category chips)
  - Save / Cancel
- Long-press (or swipe left on mobile) → Delete with confirmation dialog

FAB (bottom right): "+" → inline form for manual entry.

---

## Page: Upload `/upload`

1. **Drop zone / file picker** — dashed border box, accepts PNG/JPEG/PDF
   - Mobile: tap opens native file picker (camera + files)
   - Desktop: drag-and-drop or click to browse
2. **File preview** — thumbnail for images, filename for PDFs; remove button
3. **Upload button** — disabled until file selected; shows spinner during upload
4. **Result card** (on success):
   - Statement type, filename, transaction count extracted
   - "View transactions" link → `/transactions`
5. **Error state**: red banner with error message from API

Upload is synchronous (wait for OCR + parse to complete before showing result). No progress bar in v1.

---

## Page: Settings `/settings`

Sections:

### Backend Connection
- Label: "Server URL"
- Input: URL field, placeholder `http://localhost:8000`
- Save button
- Status indicator: green dot "Connected" / red dot "Unreachable" (pings `/health`)

### OCR Provider
- Radio group: Tesseract (default) | Claude Vision | OpenAI Vision
- Conditional API key input:
  - Claude selected → "Anthropic API Key" input (password type)
  - OpenAI selected → "OpenAI API Key" input (password type)
  - Key field shows `••••••••` if already set; placeholder "Enter new key to update"
- Save button → `PUT /settings`

### Categories
- List of categories with color swatch, name, edit/delete actions
- "Add category" button → inline form (name + color picker)

---

## Backend URL flow (state machine)

```
State: UNSET
  → User enters URL + taps Save
    → CHECKING (pings /health)
      → success → CONNECTED (stored in localStorage)
      → fail    → ERROR (shown inline; not saved)

State: CONNECTED
  → All API calls use stored URL
  → If any API call returns network error → banner "Can't reach server" + link to Settings
```

Key: `spending_tracker_backend_url`
Default (env): `NEXT_PUBLIC_API_URL` (fallback for hosted deployments)

---

## Responsive breakpoints

| Width | Layout |
|---|---|
| < 768px | Mobile: bottom tabs, full-width cards, no sidebar |
| 768–1024px | Tablet/iPad: side nav (collapsible), 2-column dashboard grid |
| > 1024px | Desktop: fixed side nav, 3-column dashboard grid |

---

## PWA Manifest (public/manifest.json)

```json
{
  "name": "Spending Tracker",
  "short_name": "Tracker",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0f172a",
  "theme_color": "#6366f1",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```
