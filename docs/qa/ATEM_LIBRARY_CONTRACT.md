# ATEM published-library contract

The optional dependency is pinned to PyATEMMax 1.0b9. The dedicated
`ATEM published API contract` CI job installs that exact package and runs
`tests/test_atem_real_library_contract.py` against its real classes.

## What is checked

- Constructor, `connect(ip)`, `waitForConnection(timeout=...)` and `disconnect()`
  signatures; real connection threads start and stop against a loopback UDP
  receiver, and a bounded wait returns false without a switcher handshake.
- Production adapter CUT, AUTO and preview selection serialize real DCut, DAut
  and CPvI datagrams to a local UDP receiver without communication threads.
  No ATEM address is contacted in any test.
- Real program/preview constants, status, connection-test reads, input names
  and one monitor poll.
- The PiP API gap and absence of any guessed keyer write.

This verifies compatibility, not physical hardware operation or command
acknowledgement. Connection handshakes and real keyer routing still need an
operator-present hardware test.

## Known unsupported PiP path

The pinned package has no `pictureInPicture`, `setPIPEnabled` or
`setPictureInPictureEnabled`. Production PiP polling currently receives no
state through that path and PiP writes return `API_NOT_FOUND`. Mock objects
that invent arbitrary attributes cannot verify compatibility.

The package does expose `keyer[mE][keyer].onAir.enabled`, `fillSource` and
`setKeyerOnAirEnabled(mE, keyer, enabled)`. These are upstream-keyer controls,
not a universal PiP alias. Do not substitute them until the operator confirms:

- the M/E and upstream keyer used for PiP, by their displayed names/numbers;
- whether that keyer is dedicated to PiP rather than chroma/luma or another
  on-air overlay.

The library uses zero-based indexes internally. The operator should report
normal UI names such as M/E 1 and USK 1, not internal indexes. No native PiP
keyer write is enabled by this change.

## Sources

- Pinned dependency: `requirements-atem.txt`.
- Published package: https://pypi.org/project/PyATEMMax/1.0b9/
- Upstream source and documentation: https://github.com/clvLabs/PyATEMMax
  and https://clvlabs.github.io/PyATEMMax
- Exact distribution checked: `PyATEMMax-1.0b9.tar.gz`, especially
  `ATEMMax.py`, `ATEMConnectionManager.py`, `ATEMSetterMethods.py`,
  `ATEMSwitcherState.py` and `StateData/Keyer.py`.

Distribution SHA-256: `6ef556ce17242ad90ad2ed793311226c37a083a6b7b03f6fdaea439f82f62f41`.
