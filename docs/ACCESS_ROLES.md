# Access roles

Only two access roles are stored: `user` and `admin`.

- User: daily camera operation, CALL presets and SET with confirmation, names
  and reconnect. No Settings entry or live ATEM CUT/AUTO.
- Admin: User operations plus Settings, configuration, credentials, diagnostics,
  backup/restore and live ATEM switching. Login/elevation requires the admin
  credential. Existing authentication and Linux permissions still apply.

## Compatibility

`camera_operator`, `basic_operator` and `operator` are read as `user`.
`technician`, `system_admin` and `admin_installer` are read as `admin`.
This applies to `access_mode.json`, `KHPTZ_ACCESS_ROLE` and its older alias
`KHPTZ_ACCESS_MODE`. ROLE takes precedence over MODE, then the file is used.
Unknown/invalid stored roles default to User. New role writes use only
`user`/`admin`. Old Python enum member names remain compatibility aliases.

Intentional permission change: former Basic Operator / legacy Operator now
can SET (overwrite a camera preset), with confirmation. User permission was
chosen to match the existing normal Camera Operator workflow.

Support, Demo, name editing, layout editing and preset testing remain separate
safety/work contexts. They cannot be persisted as roles, and their existing
camera-action blocks remain. Demo runtime isolation is unchanged.

This is not a Linux account/security redesign. The CLI and file access still
use operating-system permissions; hiding Settings alone is not a service-level
security boundary. Existing dedicated admin-password verification, its narrowly
scoped legacy fallback, and privileged reprovision checks are unchanged.
An authenticated User login replaces any previously persisted Admin role.
