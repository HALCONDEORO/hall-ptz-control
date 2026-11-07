# Privacy Notes

This document summarizes the customer and operator data handled by KH PTZ Control.
It is operational guidance only and does not replace a customer-specific privacy policy,
data-processing agreement, or legal review.

## Data Stored By The Application

The application can store the following local data:

| Data | Typical file/location | Notes |
|------|-----------------------|-------|
| Speaker names and seat assignments | `seat_names.json` | May identify people using the room. |
| Chairman personal preset mapping | `chairman_presets.json` | May reveal room usage patterns or named preset assignments. |
| Weekly login bypass schedule | `schedule.json` | Shows when password bypass is allowed. |
| Camera and ATEM addresses | `PTZ1IP.txt`, `PTZ2IP.txt`, `ATEMIP.txt` | Network configuration, not personal data by itself, but customer/site-specific. |
| Support/help contact text | `Contact.txt` | May contain business contact details. |
| Encrypted login password file | `password.enc` | Must be protected and never included in support bundles by default. |
| Logs and crash reports | `logs/` | Must not contain passwords or unnecessary personal data. |
| Backup ZIP files | User-selected/export location | May contain the data listed above. |

Production service installs use `/etc/khptz/` for site configuration,
`/var/lib/khptz/` for persistent runtime data, `/var/log/khptz/` for logs and
`/var/backups/khptz/` for local backup archives. Overrides and development
checkouts can use other paths. `~/.config/khptz/` is a legacy migration source,
not the production default. See [runtime path contract](RUNTIME_PATH_CONTRACT.md)
and inspect the actual installation before exporting or deleting data. Legacy
plain-text files can still exist beside development application code.

## Data That Must Not Be Logged Or Exported By Default

- Plain-text passwords.
- Attempted passwords.
- `password.enc` or `password.txt`.
- Tokens, secrets, `.env` files, or local developer credentials.
- Customer personal data unless the operator explicitly agrees it is needed for support.

## Support Bundles And Backups

- Support bundles should include version, mode, safe configuration and logs where useful.
- Support bundles must exclude password files and secrets.
- Files such as `seat_names.json`, `chairman_presets.json` and `schedule.json` should be included only when needed and with customer/operator approval.
- Backup files should be treated as customer data because they may contain names, schedules and site configuration.

## Customer Responsibilities To Confirm

- Who is responsible for deciding whether speaker names may be stored.
- How long backups and logs should be retained.
- Who may access the Raspberry Pi, data directory, logs and backup files.
- Whether exported support bundles may be sent to remote support.
- Whether local data-protection law requires additional notices, consent, access controls, retention rules or deletion procedures.

## Deployment Guidance

- Use a dedicated service user where practical.
- Keep runtime data and backups out of the Git repository.
- Do not commit real customer names, IP addresses, contact details, logs, backups or password files.
- Verify that `logs/`, backups and runtime data directories are not world-writable.
- Confirm privacy and retention expectations during customer handover.
