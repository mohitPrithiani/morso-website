"""
MORSO MENU UPDATER
==================
Reads Morso_Menu_Master.xlsx and applies all changes to index.html.

Usage:
    python3 morso_menu_updater.py <excel_file> <html_file> [--dry-run]

Examples:
    python3 morso_menu_updater.py Morso_Menu_Master.xlsx index.html
    python3 morso_menu_updater.py Morso_Menu_Master.xlsx index.html --dry-run

Only rows with Action = ADD, UPDATE, or REMOVE are processed.
Rows with blank Action or Action = NO CHANGE are skipped.

Output: updated index.html (saved in place unless --dry-run)
"""

import sys
import re
import json
from datetime import date
from bs4 import BeautifulSoup
import openpyxl

# ── COLUMN MAPPING (1-indexed, matches the Excel sheet) ──────────────────────
COL = {
    'action':        1,   # A
    'active':        2,   # B
    'food_bev':      3,   # C
    'category':      4,   # D
    'html_id':       5,   # E
    'subheader':     6,   # F
    'cat_priority':  7,   # G
    'item_priority': 8,   # H
    'product_code':  9,   # I
    'item_name':    10,   # J  ← data-name (permanent ID in HTML)
    'display_name': 11,   # K  ← shown to customer
    'desc':         12,   # L
    'diet':         13,   # M
    'price':        14,   # N
    'badge':        15,   # O
    'cat_upgrade':  16,   # P
    'item_upgrade': 17,   # Q
    'remarks':      18,   # R
    'last_updated': 19,   # S
}

DIET_MAP = {
    'veg':    'Veg',
    'egg':    'Egg',
    'nonveg': 'Non-Veg',
}
DIET_REVERSE = {v.lower(): k for k, v in DIET_MAP.items()}

# ─────────────────────────────────────────────────────────────────────────────

def cell(row, col_name):
    """Get cell value from a row by column name."""
    v = row[COL[col_name] - 1]
    if v is None:
        return ''
    return str(v).strip()

def read_excel(path):
    """Read Menu Master sheet, return list of action rows."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb['Menu Master']
    action_rows = []
    for row in ws.iter_rows(min_row=4, values_only=True):
        action = (row[COL['action'] - 1] or '').strip().upper()
        if action in ('ADD', 'UPDATE', 'REMOVE'):
            action_rows.append(row)
    return action_rows

def build_item_html(data):
    """Build a complete menu-item div from a data dict."""
    diet_attr = DIET_REVERSE.get(data['diet'].lower(), 'veg')
    name = data['item_name']
    display = data['display_name'] or name
    price = data['price']
    desc = data['desc']
    badge = data['badge']
    item_upgrade = data['item_upgrade']

    # Opening tag
    if diet_attr == 'veg':
        open_tag = f'<div class="menu-item" data-name="{name}">'
    else:
        open_tag = f'<div class="menu-item" data-diet="{diet_attr}" data-name="{name}">'

    # Display name with optional badge
    if badge:
        name_html = f'<span class="item-name">{display} <span class="chefs-pick">{badge}</span></span>'
    else:
        name_html = f'<span class="item-name">{display}</span>'

    # Item row
    diet_icon = f'<span class="diet-icon {diet_attr}"></span>'
    item_row = (
        f'    <div class="item-row">'
        f'<span class="item-name-wrap">{diet_icon}{name_html}</span>'
        f'<span class="item-price">₹{price}</span>'
        f'</div>'
    )

    lines = [open_tag, item_row]
    if desc:
        lines.append(f'    <span class="item-desc">{desc}</span>')
    if item_upgrade:
        lines.append(f'    <div class="upgrades">{item_upgrade}</div>')
    lines.append('  </div>')
    return '\n'.join(lines)

def find_item_block(content, item_name):
    """Find start and end positions of a menu-item div by data-name."""
    patterns = [
        f'<div class="menu-item" data-name="{item_name}">',
        f'<div class="menu-item" data-diet="egg" data-name="{item_name}">',
        f'<div class="menu-item" data-diet="nonveg" data-name="{item_name}">',
        # also handle reversed attribute order
        f'<div class="menu-item" data-name="{item_name}" data-diet="egg">',
        f'<div class="menu-item" data-name="{item_name}" data-diet="nonveg">',
    ]
    start = -1
    for p in patterns:
        idx = content.find(p)
        if idx != -1:
            start = idx
            break

    if start == -1:
        return -1, -1

    # Walk forward, count div depth
    depth = 0
    i = start
    while i < len(content):
        if content[i:i+4] == '<div':
            depth += 1
            i += 4
        elif content[i:i+6] == '</div>':
            depth -= 1
            if depth == 0:
                end = i + 6
                if end < len(content) and content[end] == '\n':
                    end += 1
                return start, end
            i += 6
        else:
            i += 1
    return start, -1

def find_section_block(content, html_id):
    """Find start and end of a section-block div by id."""
    start_tag = f'<div class="section-block" id="{html_id}">'
    start = content.find(start_tag)
    if start == -1:
        return -1, -1
    depth = 0
    i = start
    while i < len(content):
        if content[i:i+4] == '<div':
            depth += 1
            i += 4
        elif content[i:i+6] == '</div>':
            depth -= 1
            if depth == 0:
                end = i + 6
                if end < len(content) and content[end] == '\n':
                    end += 1
                return start, end
            i += 6
        else:
            i += 1
    return start, -1

def apply_update(content, data, log):
    """Update an existing menu item's fields."""
    item_name = data['item_name']
    start, end = find_item_block(content, item_name)
    if start == -1:
        log.append(f"  ✗ UPDATE — item not found: '{item_name}'")
        return content

    new_block = build_item_html(data)
    content = content[:start] + new_block + '\n' + content[end:]
    log.append(f"  ✓ UPDATE — '{item_name}'")

    # Update subheader if present
    html_id = data['html_id']
    subheader = data['subheader']
    if subheader and html_id:
        # Replace existing origin-note in this section, or add after content div
        section_start = content.find(f'<div class="section-block" id="{html_id}">')
        if section_start != -1:
            content_div = content.find('<div class="content">', section_start)
            if content_div != -1:
                after_content = content_div + len('<div class="content">')
                existing_note = content.find('<div class="origin-note">', after_content)
                note_end = content.find('</div>', existing_note)
                if existing_note != -1 and existing_note < after_content + 200:
                    # Replace existing note
                    content = (content[:existing_note] +
                               f'<div class="origin-note">{subheader}</div>' +
                               content[note_end + 6:])
                    log.append(f"  ✓ UPDATE subheader for '{html_id}'")

    return content

def apply_remove(content, data, log):
    """Remove a menu item from the HTML."""
    item_name = data['item_name']
    start, end = find_item_block(content, item_name)
    if start == -1:
        log.append(f"  ✗ REMOVE — item not found: '{item_name}'")
        return content
    content = content[:start] + content[end:]
    log.append(f"  ✓ REMOVE — '{item_name}'")
    return content

def apply_add(content, data, log):
    """Add a new menu item into the correct section."""
    html_id = data['html_id']
    item_name = data['item_name']

    # Check not already present
    if f'data-name="{item_name}"' in content:
        log.append(f"  ⚠ ADD skipped — '{item_name}' already exists (use UPDATE instead)")
        return content

    # Find section
    section_start = content.find(f'<div class="section-block" id="{html_id}">')
    if section_start == -1:
        log.append(f"  ✗ ADD failed — section '{html_id}' not found")
        return content

    # Find the content div closing — insert before it
    content_div_start = content.find('<div class="content">', section_start)
    if content_div_start == -1:
        log.append(f"  ✗ ADD failed — content div not found in section '{html_id}'")
        return content

    # Find item_priority to insert in correct order
    item_priority = int(data['item_priority']) if data['item_priority'] else 999

    # Get all existing items in section and find insertion point
    # Simple approach: insert before the item whose priority > new item's priority
    # or at end of content div if no such item
    section_start2, section_end = find_section_block(content, html_id)
    section_block = content[section_start2:section_end]

    # Find end of content div
    content_end = section_block.rfind('</div>\n</div>')
    if content_end == -1:
        content_end = section_block.rfind('</div>')

    insertion_absolute = section_start2 + content_end
    new_item = '\n' + build_item_html(data) + '\n'
    content = content[:insertion_absolute] + new_item + content[insertion_absolute:]
    log.append(f"  ✓ ADD — '{item_name}' into section '{html_id}'")
    return content

def update_nav_link(content, html_id, new_title, log):
    """Update a nav link display text for a section."""
    pattern = re.compile(rf'<a href="#{re.escape(html_id)}">[^<]+</a>')
    new_link = f'<a href="#{html_id}">{new_title}</a>'
    new_content, n = pattern.subn(new_link, content)
    if n:
        log.append(f"  ✓ Nav link updated for '{html_id}' → '{new_title}'")
    return new_content

def update_section_title(content, html_id, new_title, log):
    """Update a section's button title."""
    old = content
    pattern = re.compile(
        rf'(<div class="section-block" id="{re.escape(html_id)}">\s*<button class="section-title">)'
        rf'[^<]+'
        rf'(<span class="chevron">)'
    )
    new_content = pattern.sub(rf'\g<1>{new_title} \g<2>', content)
    if new_content != old:
        log.append(f"  ✓ Section title updated: '{html_id}' → '{new_title}'")
    return new_content

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    dry_run = '--dry-run' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]

    if len(args) < 2:
        print("Usage: python3 morso_menu_updater.py <excel_file> <html_file> [--dry-run]")
        sys.exit(1)

    excel_path = args[0]
    html_path  = args[1]

    print(f"\n{'DRY RUN — no files will be changed' if dry_run else 'LIVE RUN'}")
    print(f"Excel: {excel_path}")
    print(f"HTML:  {html_path}\n")

    action_rows = read_excel(excel_path)
    print(f"Rows to process: {len(action_rows)}\n")

    if not action_rows:
        print("No rows with Action = ADD/UPDATE/REMOVE found. Nothing to do.")
        return

    with open(html_path, 'r') as f:
        content = f.read()

    original_count = content.count('<div class="menu-item"')
    log = []

    for row in action_rows:
        action = cell(row, 'action').upper()
        active = cell(row, 'active').upper()
        data = {
            'action':       action,
            'active':       active,
            'food_bev':     cell(row, 'food_bev'),
            'category':     cell(row, 'category'),
            'html_id':      cell(row, 'html_id'),
            'subheader':    cell(row, 'subheader'),
            'cat_priority': cell(row, 'cat_priority'),
            'item_priority':cell(row, 'item_priority'),
            'product_code': cell(row, 'product_code'),
            'item_name':    cell(row, 'item_name'),
            'display_name': cell(row, 'display_name'),
            'desc':         cell(row, 'desc'),
            'diet':         cell(row, 'diet') or 'Veg',
            'price':        cell(row, 'price').replace('₹','').replace(',','').strip() or '0',
            'badge':        cell(row, 'badge'),
            'cat_upgrade':  cell(row, 'cat_upgrade'),
            'item_upgrade': cell(row, 'item_upgrade'),
            'remarks':      cell(row, 'remarks'),
        }

        log.append(f"\n[{action}] {data['item_name']} — {data['category']}")
        if data['remarks']:
            log.append(f"  Note: {data['remarks']}")

        if action == 'REMOVE' or active == 'N':
            content = apply_remove(content, data, log)
        elif action == 'UPDATE':
            content = apply_update(content, data, log)
            # If category name changed, update nav + title
            # (category field in sheet vs current HTML checked externally)
        elif action == 'ADD':
            content = apply_add(content, data, log)

    # Summary
    new_count = content.count('<div class="menu-item"')
    print('\n'.join(log))
    print(f"\n{'─'*50}")
    print(f"Items before: {original_count}")
    print(f"Items after:  {new_count}")
    print(f"Net change:   {new_count - original_count:+d}")

    if not dry_run:
        with open(html_path, 'w') as f:
            f.write(content)
        print(f"\n✅ Saved: {html_path}")
    else:
        print(f"\n⚠ Dry run — {html_path} NOT changed")

if __name__ == '__main__':
    main()
