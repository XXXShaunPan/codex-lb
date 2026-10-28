## Why

The operator wants to retire the temporary `codex-lb-native-config` maintenance checkout without losing the verified proxy fixes or making the running service depend on it. Inspection confirms that the service, editable package, launcher, and isolated Python imports already resolve to `codex-lb-custom`. However, the production `.git` file points to a deleted older worktree parent, and recent tests/specifications exist only in the maintenance checkout.

## What Changes

- Publish the verified Responses include compatibility and bounded diagnostic changes to the fork's `custom/main` with scoped, non-force-pushed commits.
- Restore an independent production Git directory from the published branch without replacing its virtual environment, application assets, configuration, or data.
- Synchronize only reviewed source-controlled differences (tests and documentation); retain runtime source bytes unchanged.
- Document runtime boundaries and checks required before deleting a disposable maintenance checkout.

## Impact

- Capability: `relay-fork` operations and maintenance.
- No service restart, migration, key change, runtime dependency reinstall, or automatic deletion of the old maintenance directory.
- Preserve the invalid Git pointer and the one-off historical deployment helper in local backups, outside source control.
