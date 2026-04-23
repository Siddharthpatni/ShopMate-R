# Changelog

All notable changes to ShopMate-R are documented here.  The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Scripted demo mode** — `demo.py` runs the full customer flow
  against the real robots without voice or keyboard input. Five
  pre-baked scenarios (`happy`, `browse`, `alternative`, `cart_full`,
  `price_check`) make thesis-defense demos and regression runs
  one-command reproducible.
- **Test suite** — `tests/` with pytest coverage for `grocery_db`
  (lookup, fuzzy match, stock mutation, alternatives), orchestrator
  intent parser, full cart lifecycle, and every tablet screen's HTML
  output. `conftest.py` stubs `pypepper_ssh` and patches `requests` so
  the suite runs without Pepper or Temi on the network. 58 tests,
  all passing.
- **Makefile** — `make run / demo / preview / health / test / lint /
  inventory / zip / clean` etc. for one-command entry points.
- **Rendered tablet preview** — bundled `preview/*.html` shows the
  glass design in any desktop browser. Regenerate any time with
  `make preview`.

- **Apple-style glassmorphism tablet UI** — every Pepper tablet screen
  now renders from a single glass design-token system (`_UI_CSS_BASE`,
  `_CAT_COLORS`, `_CAT_SVG`, `_AURORA_BG`). Each card uses a
  four-layer glass recipe: translucent background, `backdrop-filter:
  blur() saturate()` (with `-webkit-` prefix for older WebViews),
  thin rgba-white border, inset top-edge highlight, and soft
  double-layer shadow. Backdrops use a vibrant multi-light aurora
  gradient so the frosted glass actually reads as glass.  Seven
  screens (welcome, goodbye, idle, categories, category_products,
  product, cart) now feel like one premium product.
- **2-column categories dashboard** — `pepper_show_categories` now
  lays out categories in a 2-column grid of larger glass tiles. Each
  tile shows its header (icon + name + stock summary) plus an inline
  2-column mini-preview of up to four products so the customer sees
  options at a glance. A "+N more" pill appears when the category has
  additional items beyond the preview.
- **2-column category-products grid** — `pepper_show_category_products`
  now uses `grid-template-columns: repeat(2, 1fr)` so each product
  card is bigger and easier to read from a few feet away.
- **Apple SF Symbols palette** — category colors swapped from Material
  hues to Apple SF Symbols accent colors (`#0A84FF`, `#34C759`,
  `#FF375F`, `#AF52DE`, etc.) for a more polished look.
- **Material palette on Temi's screen** — `_product_card_html` and
  `temi_show_categories` re-themed to match Pepper's palette so both
  robots look consistent.  All HTTP and webview-endpoint discovery
  logic is unchanged.
- `pepper_nod_yes()` — new named gesture for simple affirmations
  (`animations/Stand/Gestures/Yes_1`).
- **`mock_dashboard.py`** — the Flask dashboard `main.py` has always
  been trying to spawn.  Previously missing from the repo; now
  included.  Provides `/api/state`, `/api/log`, `/api/sensor`,
  `/api/snapshot`, `/api/inventory`, and a live single-page UI.
- **`m5stack_sensor.py`** — CLI to simulate M5Stack shelf-sensor
  events, documented in the README but previously missing.
- **`tablet_preview.py`** — renders every Pepper tablet screen to
  `./preview/*.html` so you can iterate on UI without the robot.
  Auto-opens a linked index page in your browser.
- **`gesture_tester.py`** — interactive or one-shot CLI to fire a
  single Pepper gesture (by name or raw NAOqi path).  Useful for
  confirming an animation path exists on the robot.
- **`health_check.py`** — pre-flight diagnostic: imports, dashboard,
  Pepper SSH port, Temi HTTP port, inventory sanity, OpenAI key.
  Supports `--json` and `--strict` exit codes.
- **`db_inspector.py`** — CLI to inspect and modify inventory.  Write
  operations route through `/api/sensor` so the running orchestrator
  reacts in real time — the same channel the real M5Stack IoT shelf
  sensors will use.

### Changed

- `pepper_wave_goodbye()` now plays `animations/Stand/Gestures/Bye_1`
  (a goodbye wave).  Previously used `BowShort_1` — a *bow*, not a
  wave — which didn't match the function name.
- `pepper_point_to_aisle()` now plays `animations/Stand/Gestures/Show_1`
  (forward/lateral pointing).  Previously used `ShowSky_1`, which
  points straight up and didn't communicate an aisle direction.
- `TALK_GESTURES` — removed `ShowSky_1` (jarring mid-sentence) and
  added `Explain_8`, `Enthusiastic_5`, and `YouKnowWhat_3` for more
  natural variety during conversation.
- **`main.py` cleanup** — imports moved to module top, the two separate
  mic-failure counters (`_mic_fail_count` and local `mic_fails`)
  merged into one, `import time` declared once.  Loop semantics
  identical.
- **`orchestrator.py` cleanup** — deferred imports of
  `pepper_talk_gesture`, `temi_navigate_to`, `temi_wait`, and
  `_push_state` hoisted to the top of the module.  Dead assignment
  `alt = _suggest_alternative_for_cart(...)` removed.  Cart-add
  logic extracted into `_add_to_cart()`.  Aisle-visit logic extracted
  into `_visit_aisle()`.  Intent dispatch replaced with a handler
  table.  Every Pepper/Temi call is byte-identical to the original.
- **README.md** rewritten — table of contents, architecture diagram,
  full file inventory across three categories (core / dashboard / dev
  tooling), configuration reference, gesture table, and a
  troubleshooting section.

### Fixed

- **Intent parser ambiguity** — "milk" is both a category name and a
  product key, so utterances like "how much is milk" or "I need milk"
  were being misclassified as `browse_category` instead of
  `check_price` / `find_item`. The fallback parser now checks
  price/alternative keywords first, then specific item matches, and
  only falls through to category browsing when no product is named.
  Caught by the new test suite.
- `main.py` could try to call `mock_dashboard.py` and fail silently
  because the file was missing from the repository.  It's now
  shipped.
- In `orchestrator._handle_find_item`, the `alt` variable was assigned
  but never read after `_suggest_alternative_for_cart(...)` — the
  function was already doing the side-effect cart append.  Removed.

### Not changed (intentionally)

- `pypepper_ssh.py` — the connection layer itself.  Every SSH command,
  every recording fallback path, every animation name mapping is
  preserved verbatim.
- All `_post_webview`, `/goto`, `/say`, `/save_location`, and
  endpoint-discovery loops in `temi_api.py`.
- `config.py` and `grocery_db.py` — already clean.
- Public function signatures across every module — diffing
  `ast.FunctionDef` nodes pre/post shows zero removals; the only
  addition is `pepper_nod_yes`.
