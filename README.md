# Shape demos

Runnable examples for [Shape by SQLLocks](https://github.com/sqllocks/shape), one folder per SQLBites "Shape in practice" post. Synthetic data only.

| Post | Folder | What it shows |
|---|---|---|
| 1. Copy Succeeded. The Data Didn't. Gate the Load. ([SQLBites](https://sqlbites.net/gate-a-load-in-fabric-with-shape/), live once published) | [`post-1-gate-a-load/`](post-1-gate-a-load/) | The `shape_finale` Fabric pipeline: a notebook profiles each day with Shape, checks a contract and drift, and an If Condition with a Fail activity stops the load before the warehouse, then again after it. With the contract and the notebooks; the data comes from post 5. |
| 4. A Pull Request Can't See Your Data ([SQLBites](https://sqlbites.net), article link to come) | [`post-4-drift-in-prs/`](post-4-drift-in-prs/) | A committed baseline profile and the Shape GitHub Action as a required check: a pull request that changes how the data behaves fails the check. |
| 5. Good Test Data Breaks on Purpose ([SQLBites](https://sqlbites.net), article link to come) | [`post-5-generate-into-fabric/`](post-5-generate-into-fabric/) | Reproducible retail data from a seed, a landing layout like a source system's, planted faults with a ground-truth log to score checks against, and the `finale_generate` notebook that lands a day in a Fabric Lakehouse. |

Each folder has its own README with the commands to run it locally. GitHub only runs workflows from `.github/workflows/` at the repository root, so each post's workflow lives there, named after its post (for example `.github/workflows/post-4-shape-drift.yml`).

Shape documentation: <https://docs.shapedata.ai/>.

## License

MIT, the same license as Shape. See [LICENSE](LICENSE).
