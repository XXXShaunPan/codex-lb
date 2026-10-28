# Design

Use the existing CopyButton rather than duplicating clipboard state and focus
handling. Its synchronous execCommand fallback stays within the dialog's focus
trap and user gesture; Clipboard API remains available in secure contexts. Catch
synchronous API failures as well as rejected promises. Never report success when
both mechanisms fail, and do not change browser security policies.

Narrow both native cleanup engines to three keys. Track actual deletions to make
repeated cleanup a no-op even when the preserved actor header still identifies
the provider as a relay. Keep provider table identity even for dotted definitions
that become empty. Retain root/profile model_provider selectors and every other
setting; no history files are inspected or modified.

An outer single-quoted heredoc feeds /bin/bash explicitly. The caller's zsh does
not interpret the Bash body, and quoted token/model data cannot terminate the
outer heredoc. Existing native command tests are extended to run under zsh where
available, with macOS CI providing a real zsh environment.
