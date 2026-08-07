# Governance enforcement

`SPECIFICATION_LOCK.json` records SHA-256 hashes of the frozen research specification.
Local verification and CI fail when a governed file changes.

The lock may be regenerated only after Othmane explicitly approves a specification
amendment and the amendment is recorded in the project decision/amendment history.
Operational files such as build scripts and validation reports are deliberately not
part of this lock.
