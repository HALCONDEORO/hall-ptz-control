# Light auditorium background

The application still loads `ui/khptz_background.jpg` through the existing
`MainWindow._build_background` path. The new 1920 x 1080 JPEG uses a light
blue-gray auditorium (#c9d9e6) and a darker platform (#a9bfd2). Only the three
central platform icons occupy the platform area. Its lower edge has borderless
diagonal corners; both wheelchair positions remain in the auditorium area.

The editable source is `assets/backgrounds/auditorium-bluegray.svg`. Rasterize
at its native size and export a high-quality JPEG to update the runtime asset.
The SVG is original project artwork under the repository MIT license.

The JPEG contains no dot texture. The existing Call-mode dot overlay remains
unchanged and is visible on top of it; Set-mode fill and the transition remain
unchanged too. Neither mode semantics nor any seat positions, camera settings,
attendee names or runtime data paths change.

`docs/screenshots/auditorium-bluegray-background.png` shows a synthetic default
seat layout rendered with the real seat widgets and existing Call overlay.
It is not a live device capture. The focused test uses Qt's JPEG decoder and
checks dimensions and color samples around the platform and diagonal corners.

Revert the JPEG to roll back this visual change. No data migration is needed.
