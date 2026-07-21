# Release checklist

1. Update the version in `manifest.json`, `const.py`, the dashboard card, and
   `README.md`.
2. Run Python, JSON, JavaScript, and image validation.
3. Create a Git tag in the form `v0.3.3`.
4. Create matching GitHub release notes.
5. Test installation through a HACS custom repository.

The public repository is `DjangoToni/gplug-energy-cockpit`. Confirm that the
release archive contains the MIT license and all four files in the local
`brand` directory.
