# Contributing

Thanks for helping. Keep it small and safe.

1. **Safety first.** Code that changes the system (`install`, `reinstall`, `restore`, `cert-remove`) must keep its guards:
   `--yes`, Administrator check, `--dry-run`, protected classes, read-back after the change. Do not weaken them.
2. **Tests never touch the system.** Use the fake runner in `tests/test_fili.py`. A test that runs a real command is a bug.
   Run `python -I tests/test_fili.py` and `python -I tests/test_bundle.py` before every pull request; add a test for every change in behaviour (and, for a safety
   rule, check it fails when you remove the rule).
3. **Real-install testing is manual**, on a disposable VM or PC: follow `docs/piano-prove-installazione.md` and paste the
   results table in the pull request. Do not claim a real-install feature works without it.
4. **Clean room.** Do **not** copy or adapt code from Zadig (`zadig.c`, GPL-3.0-or-later). Describe behaviour from the
   documentation or by observing the program. libwdi / wdi-simple (LGPL-3.0-or-later) are used only as a separate
   executable, never linked or pasted into this code. See `docs/licenza.md`.
5. Python standard library only (no third-party runtime dependencies), Python 3.9+, Windows target.
6. One topic per pull request; describe what you ran and what you did not.
