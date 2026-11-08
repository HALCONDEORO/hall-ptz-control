# Setup wizard language

The setup wizard uses English for its own titles, instructions, safety messages
and standard navigation buttons. This matches the existing application UI.
Buttons are set explicitly so a different desktop Qt locale cannot mix languages.
The close and timeout warnings retain their meaning: closing does not cancel
provisioning, and an unknown result must be checked before retrying or restarting.

User-entered room names, addresses and messages returned by an external service
are not translated. This change does not add a language selector, cancel backend
work or fix provisioner overlap. It changes no authentication or request format.

Tests cover English safety messages and button text with Spanish/French desktop
locales. Pixel review must use the exact composed head at 800x480 and 1280x720.
