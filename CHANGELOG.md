# Changelog

## v0.4 — 2026-10-09

- Select USER mode and perform a software reset to start the application.
- Support the standard WCH Arduino application linker at address zero.
- Retain the three-second UART phrase window and existing upload protocol.
- Include an Arduino PD2 blink example with the manual-reset hook.
- Basic stock-Arduino compilation and UART upload flow confirmed by the
  maintainer on Holt hardware.

## v0.3 — development revision

- Shorten the entry window from five seconds to three seconds.
- Preserve the experimental direct application jump, requiring applications
  linked at 0x08000000. Superseded by v0.4; those linker edits are unnecessary
  with the current release.

## Earlier prototypes

- Initial five-second UART phrase entry, UART programming and verification.
- Explore direct handoff and establish that Holt manual-reset entry requires
  an application hook. Do not use these prototypes as customer release files.
