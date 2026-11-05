# Optional ATEM dependency: technical baseline and release gates

## Correction to the earlier decision

The earlier document described PyATEMMax as MIT and approved a >=0.9,<1 range.
Those claims do not match the published package checked on 2026-11-05:

- PyPI lists releases 1.0b1 through 1.0b9, all prereleases. It lists no 0.9 release.
- The 1.0b9 sdist includes a GNU GPL version 3 LICENSE.md. PyPI metadata says GPL.
- requirements-atem.txt now fixes 1.0b9 as a reproducible technical baseline,
  not an approval for customer distribution or a claim of hardware compatibility.

Sources:
- https://pypi.org/project/PyATEMMax/
- https://github.com/clvLabs/PyATEMMax
- https://files.pythonhosted.org/packages/71/53/481ca89c0d2b1e2a5a1e71bf42991e4e67f09f0387ba46f3034151209e76/PyATEMMax-1.0b9.tar.gz

The downloaded sdist SHA256 is
`6ef556ce17242ad90ad2ed793311226c37a083a6b7b03f6fdaea439f82f62f41`.
This digest records what was inspected; requirements-atem.txt is not a complete
transitive, hash-locked customer build.

## Scope

PyATEMMax remains optional and isolated behind ATEM adapters. Missing the library
must leave PTZ operation available. Local tests use mocks or fake ATEM devices;
they do not prove compatibility with a physical switcher or its firmware.
No package installation on an appliance or network connection is part of this change.

## Gates before shipping or deployment

1. Have a qualified reviewer settle the licence obligations for the intended
   distribution. Do not repeat the old MIT/proprietary-compatibility claim.
2. Record a reviewed dependency set, upstream notices and a reproducible build.
3. Validate the exact package version against the target ATEM model and firmware,
   including reconnects, manual switching and coexistence with Software Control.
4. Keep automatic switching disabled until its own safety review passes.
5. Record limitations and approval in the release evidence. A pin is not approval.

Any future version or adapter change must repeat the relevant licence, dependency,
automated regression and hardware checks. The port boundary allows a replacement
adapter, but this document does not select an alternative library.
