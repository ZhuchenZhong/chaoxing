# Migration Assets

This directory contains migration inputs and outputs for the web-platform rewrite.

Primary legacy source:

- `E:\\Project\\ARCHIVE\\chaoxing\\data\\migration\\user-data-export.sql`

Planned outputs:

- normalized staging extracts
- generated initial-password reports
- import validation reports

Generated from the current legacy dump:

- `legacy-migration-summary.json`
- `legacy-initial-passwords.csv`

Current dump findings:

- `6` legacy users
- `2` legacy registration invites
- `3` legacy Chaoxing accounts
- all `3` legacy Chaoxing accounts require manual rebind because their stored credentials are not decryptable by the current AES-based account flow
