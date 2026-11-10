# Third-party notices

KH PTZ Control's original code is published under [MIT](LICENSE). That does not
relicense its dependencies or make a complete installed image MIT-only. Preserve
upstream copyright and licence notices when sharing a build.

This is a dependency review record, not a complete software bill of materials or
legal approval for a particular distribution. Check the exact installed versions,
including transitive Python packages and OS packages, before a handover.

## Required runtime components

| Component | Purpose | Licence evidence and limits |
|---|---|---|
| PyQt5 | GUI | Riverbank's open-source edition is GPL v3; a separate commercial licence exists. PyQt5 is **not LGPL**. Its licence must be compatible with the Qt licence in use. |
| Qt, including SVG support | GUI libraries used by PyQt5 | Terms vary by module and build. Inspect the Qt packages actually installed; do not treat the PyQt5 licence as a complete Qt inventory. |
| PyQt5-sip | PyQt5 extension support | Inspect the installed release's LICENSE. The 12.15.0 source archive checked on 2026-11-07 contains a two-clause BSD-style licence, despite PyPI metadata saying SIP. This does not identify the version shipped by every Pi OS image. |
| PyYAML | YAML configuration | MIT, according to the 6.0.3 upstream package. Raspberry Pi installs use the OS package `python3-yaml`, whose version and notices must be recorded separately. |

Sources:

- [PyQt5 licensing documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/introduction.html#license)
- [PyQt5-sip 12.15.0 metadata](https://pypi.org/project/PyQt5-sip/12.15.0/)
- [PyQt5-sip 12.15.0 source archive](https://files.pythonhosted.org/packages/1b/15/78318d50f10062c428e97e7ce387e772616a4673c356018b905f247a6a85/PyQt5_sip-12.15.0.tar.gz)
- [PyYAML](https://pypi.org/project/PyYAML/)

The reviewed PyQt5-sip archive SHA256 is
`d23fdfcf363b5cedd9d39f8a9c5710e7d52804f5b08a58e91c638b36eafcb702`.
This is an evidence digest, not a runtime pin or a reproducible-build claim.

## Optional ATEM component

**PyATEMMax 1.0b9 is GPL v3, not MIT.** Its published source archive contains
GNU GPL version 3 in `LICENSE.md`. `requirements-atem.txt` fixes this prerelease
as a technical baseline only. It is not permission to redistribute a bundled
image and does not validate a real switcher.

- [Upstream package](https://pypi.org/project/PyATEMMax/1.0b9/)
- [Project](https://github.com/clvLabs/PyATEMMax)
- [Inspected archive and digest](docs/ATEM_DEPENDENCY_DECISION.md)

Missing PyATEMMax disables the ATEM integration; it is not required for the
camera-only path. Follow the dependency, licensing and hardware gates in
[ATEM_DEPENDENCY_DECISION.md](docs/ATEM_DEPENDENCY_DECISION.md) before enabling it.

## Before sharing an installed system or image

1. Record the application revision, OS image and exact installed package versions.
2. Collect their licence texts, attribution and required notices.
3. Review the intended conveyance against the applicable GPL terms, including
   Corresponding Source and any applicable installation-information obligations.
   A public source repository alone is not proof that every obligation is met.
4. Remove site data and secrets from any reusable image. Never publish a live backup.
5. Record the review and unresolved limits with the release evidence. Neither a
   free handover nor an MIT label removes third-party obligations.

This change does not replace the application's MIT licence, select a commercial
licence, approve a distribution or resolve the outstanding release gates.

## Development and OS tools

pytest is MIT-licensed ([upstream](https://docs.pytest.org/)). Development tools
are separate from the production runtime. Raspberry Pi OS also distributes Qt,
Python, systemd and other packages under their own terms; their archive notices
must be retained as applicable. This short list is not an exhaustive inventory.
