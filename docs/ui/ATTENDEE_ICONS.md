# Attendee panel icons

The attendee heading, search field, Add, Undo last assignment and Bring All
Back actions use local SVG assets, not Unicode emoji. This avoids missing-glyph
boxes on Linux systems whose installed fonts do not contain emoji. No extra
font package or online font download is required.

`ui.icon_loader.get_svg_icon` loads the editable sources in `assets/icons/svg`.
Qt's SVG support is already used by the application. The new attendees, search,
add and undo assets are original project artwork under the repository license;
Bring All Back reuses the existing refresh asset. Text labels and accessible
names are retained. If an asset is missing, production logs a warning and keeps
the action's text; `KHPTZ_STRICT_ICONS=1` makes missing assets fail fast.

## Validation

- Automated checks render every affected vector into non-transparent pixels.
- A fresh Qt process constructs the panel with a normal text font, verifies
  readable labels, search action, counters and Call/Set enabled states.
- Confirm the panel on the target touchscreen after an approved deployment:
  heading, search, Add, Undo, Bring All Back and assigned/total counts must be
  legible. Add/undo/clear behaviour must be unchanged.
- The local preview is not a hardware certification. No installer, camera,
  session, data path or deployment behaviour changes in this fix.

Rollback is a normal code release rollback. No customer data migration is
needed. Other application panels may still contain emoji; this focused fix
covers the attendee panel only.
