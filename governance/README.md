# Governance enforcement

`SPECIFICATION_LOCK.json` records SHA-256 hashes of the authoritative research specification.
Local verification and CI fail when a governed file changes without a matching lock update.

The lock may be regenerated only after a specification amendment is formally documented.
Operational files such as build scripts and validation reports are deliberately not
part of this lock.
