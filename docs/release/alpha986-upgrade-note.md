# Alpha986 upgrade notes

Alpha986 is an internal privacy/security build. The public release remains `0.1.0-alpha983`.

Before upgrading, create a fresh configuration backup. New backups contain no decrypted secrets or password hashes by default. After restoring such a backup, enter provider, connection and authentication credentials again. If credential portability is required, explicitly enable the encrypted bundle and keep its passphrase separately; a lost passphrase cannot be recovered. Legacy plaintext backups still import, but ARIA warns that they should be replaced.

Managed Compose upgrades now create migration copies with mode `0600`. Only after the upgraded stack passes its health and persistence checks are older copies pruned, leaving the newest two generations. A failed or `--no-start` upgrade does not prune prior copies. Persistent user-data volumes are not modified by this retention.

Shipped Compose definitions now bound `json-file` logs to three 10-MiB files per service. Native-agent traces default to minimal detail, seven-day retention and a 50-MiB instance cap. Full trace detail can contain document text, command output and Tool arguments and should be enabled only briefly for diagnosis.

The operational retention sweep removes only expirable runtime evidence, logs, tokens and confirmation state. It never sweeps personal memories, documents, notes or recipes. Factory reset remains an explicit destructive action and now lists its expanded ARIA-owned scope in the confirmation UI.
