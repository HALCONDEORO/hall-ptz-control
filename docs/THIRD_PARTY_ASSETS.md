# Third-Party Assets

## Icon pack

| Field    | Value                                  |
|----------|----------------------------------------|
| Name     | Lucide Icons                           |
| Usage    | Production UI icons                    |
| Licence  | ISC                                    |
| Source   | https://lucide.dev                     |
| Notes    | SVG icons adapted only for stroke width and viewBox consistency. No colour or shape changes. |

The SVG source files in `assets/icons/svg/` are based on Lucide Icons shapes,
adapted under the ISC licence.

Generated PNG files in `assets/icons/png/` are derived from those SVGs.

---

## Generating PNG files from SVG sources

Use any SVG renderer to produce PNGs at 24 px, 32 px and 48 px per icon.

Example using Inkscape (on the Pi or dev machine):

```bash
for svg in assets/icons/svg/*.svg; do
    name=$(basename "$svg" .svg)
    for size in 24 32 48; do
        inkscape "$svg" --export-png="assets/icons/png/${name}_${size}.png" \
            --export-width="$size" --export-height="$size"
    done
done
```

Or using `cairosvg` (Python):

```bash
pip install cairosvg
python - <<'EOF'
from pathlib import Path
import cairosvg

for svg in Path("assets/icons/svg").glob("*.svg"):
    for size in (24, 32, 48):
        cairosvg.svg2png(
            url=str(svg),
            write_to=f"assets/icons/png/{svg.stem}_{size}.png",
            output_width=size,
            output_height=size,
        )
EOF
```

Commit the generated PNGs alongside the SVG sources so Raspberry Pi
installations do not require a build step.

---

## PyATEMMax (optional ATEM dependency)

| Field | Value |
|---|---|
| Name | PyATEMMax |
| Technical baseline | 1.0b9 (prerelease; not a hardware validation result) |
| Licence in published sdist | GNU GPL version 3, see upstream LICENSE.md |
| Package | https://pypi.org/project/PyATEMMax/ |
| Source | https://github.com/clvLabs/PyATEMMax |

The previous MIT attribution was incorrect for the published 1.0b9 distribution.
Do not rely on it as permission to ship a proprietary bundle. A qualified licence
review must settle distribution obligations before shipping this optional package.
No legal compatibility decision is made here. Preserve upstream licence notices.

Without this optional dependency, ATEM monitoring is unavailable; PTZ control
continues. Real-device validation remains a separate release gate.
