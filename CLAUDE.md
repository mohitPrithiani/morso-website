# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Static HTML website for **Morso**, a neighbourhood café in Balewadi, Pune. Deployed to Cloudflare Pages at `https://morso-in.pages.dev` via GitHub auto-deployment.

## Commands

### Menu Updates (primary workflow)
```bash
# Apply menu changes from Excel sheet
python3 morso_menu_updater.py Morso_Menu_Master.xlsx index.html

# Preview changes without modifying files
python3 morso_menu_updater.py Morso_Menu_Master.xlsx index.html --dry-run
```
**Requires**: `openpyxl`, `beautifulsoup4` Python packages.

### Deploy
```bash
git push origin main  # Cloudflare Pages auto-deploys on push
```

No build step, linter, or test suite exists — this is a static site.

## Architecture

`index.html` is a single ~1,940-line file containing all HTML, CSS (~900 lines in `<head>`), and JavaScript (~170 lines at bottom of `<body>`). No external JS/CSS frameworks are used.

### Key HTML structure
```
header          — logo, tagline, hours badge
.cat-nav-wrapper — sticky navigation with 16 category links
toolbar         — search input, dietary filter buttons (Veg/Egg/Non-Veg), dark mode toggle
.accordion      — 16 .section-block elements, each containing .menu-item cards
reviews section — auto-rotating testimonials carousel
signup section  — Google Forms integration via silent iframe
footer
```

### Menu item anatomy
Each `.menu-item` has: name, description, price (₹), dietary indicator (green/orange/red circle or triangle), optional badge (`★ Chef Pick` / `★ Chef Fav`), and optional upgrade options.

### JavaScript behavior
- `applyFilters()` — controls accordion open/close, search filtering, and dietary filter logic; called on every search/filter interaction
- Sticky nav active state tracked via `IntersectionObserver`
- Dark mode toggle writes to `localStorage`
- Reviews carousel auto-rotates every 4s

### Python menu updater (`morso_menu_updater.py`)
Reads `Morso_Menu_Master.xlsx` and processes rows where `Action` column is `ADD`, `UPDATE`, or `REMOVE`. Directly manipulates `index.html` using regex and string operations (minimal BeautifulSoup usage). The updater handles section ordering via a `priority` field and can update nav link text when section titles change.

### Deployment pipeline
```
Excel file → morso_menu_updater.py → index.html → git push → GitHub → Cloudflare Pages
```

## Content notes

- **16 menu sections** (Morsels, Morso Bowls, Burger Club, Grilled Panini, All That Pizzazz, Pasta Classics, Toast Tribe, Eggs all right, Protein & Greens, Smashin' Croissants, You Dessert This, Coolers and Shakers, Matcha Room, The Hot Bar, Chilled Coffee Bar, Bottles)
- Brand fonts: `TwCenMTStd.otf` (regular) and `TwCenMTStdSemiBold.otf` — loaded via `@font-face`, files must remain in repo root
- `indexv1.html` and `Trash/` directory are legacy backups — do not modify