# Shape demos

Runnable examples for [Shape by SQLLocks](https://github.com/sqllocks/shape), one folder per SQLBites "Shape in practice" post. Synthetic data only.

| Post | Folder | What it shows |
|---|---|---|
| 4. A Pull Request Can't See Your Data ([SQLBites](https://sqlbites.net), article link to come) | [`post-4-drift-in-prs/`](post-4-drift-in-prs/) | A committed baseline profile and the Shape GitHub Action as a required check: a pull request that changes how the data behaves fails the check. |

Each folder has its own README with the commands to run it locally. GitHub only runs workflows from `.github/workflows/` at the repository root, so each post's workflow lives there, named after its post (for example `.github/workflows/post-4-shape-drift.yml`).

Shape documentation: <https://docs.shapedata.ai/>.

## License

MIT, the same license as Shape. See [LICENSE](LICENSE).
