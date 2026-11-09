# Releasing

Releases go to PyPI through GitHub Actions with **Trusted Publishing**: PyPI trusts this
repository's workflow, so no API token is created or stored.

## One-time setup (a maintainer, on pypi.org and test.pypi.org)

1. Create the PyPI project name `reportnet-api` (the first upload does this) and enable
   two-factor authentication on the account.
2. On PyPI, open *Your projects → reportnet-api → Publishing* (for a project that does not
   exist yet, *Account settings → Publishing → Add a pending publisher*) and add a
   GitHub publisher with: owner `eeadata`, repository `reportnet-api-python`, workflow
   `release.yml`, environment `pypi`.
3. Repeat on test.pypi.org with environment `testpypi`.
4. In the GitHub repository settings, create the two environments `pypi` and `testpypi`
   (for `pypi` you can require a reviewer's approval).
5. Add a second owner or maintainer to the PyPI project, so it never depends on one person.
6. Docs site: enable *Settings → Pages → Source: GitHub Actions*. The *Docs* workflow is
   manual while the repository is private (Pages for private repositories needs a paid
   plan); once public, add a `push` trigger to `.github/workflows/docs.yml`.
7. Actions are pinned to exact commits; Dependabot (`.github/dependabot.yml`) proposes
   updates monthly.

## Each release

1. Update `version` in `pyproject.toml` and the entry in `CHANGELOG.md`.
2. `uv run ruff check . && uv run mypy reportnet_api && uv run pytest` must pass (CI runs
   them on Python 3.11 to 3.14).
3. **Rehearse:** run the *Release* workflow by hand (Actions tab → Release → Run workflow).
   It uploads to TestPyPI. Install from there in a clean environment and import it:
   `pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ reportnet-api`.
4. **Release:** create a GitHub release whose tag is `v<version>` (for example `v0.1.0`).
   The workflow refuses to publish if the tag and `pyproject.toml` disagree.
5. Update the README's install line when the first release is out.
6. Before the first upload, change the README logo's two `docs/assets/...` paths to
   `https://raw.githubusercontent.com/eeadata/reportnet-api-python/main/docs/assets/...`:
   PyPI cannot resolve relative image paths. Those links only work once the repository
   is public, which is why the README uses relative paths until then.

A version number on PyPI can never be reused, even after deleting it, so always rehearse
first.
