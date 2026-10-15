# Post 4: A Pull Request Can't See Your Data

The project from SQLBites post 4 of "Shape in practice", built with Shape 0.9.3 by following the article's steps 1 to 6.
The data is synthetic: 5,000 retail orders from Shape's retail domain (seed 42).

## What it shows

- `data/orders.csv` is the "feed". Its sha256 is `c7ec6218f6a181dd438a3cc0e4b515bbdf730d00cc3d0d7df04e96499ac72487`.
- `baseline/orders.shape` is the baseline profile of that file, committed to Git.
- `shape.yml` names one source, `orders`, and pins it to that baseline.
- The workflow **Shape drift check** runs the Shape GitHub Action (`sqllocks/shape@v0.9.3`) on every pull request that touches this folder. Its job, `shape`, re-profiles the data, compares it with the baseline, posts one comment and fails when it finds drift (`fail-on: drift`). The check shows as **Shape drift check / shape**.
- `blank_order_totals.py` is the script from step 8. It blanks `order_total` on every eighth order (625 of 5,000). The open pull request from the `blank-order-totals` branch does exactly that, and the check fails on it: `order_total` goes from a null rate of 0.0 to 0.125.

## Where the workflow is

GitHub only runs workflows from `.github/workflows/` at the repository root, so this post's workflow is
[`.github/workflows/post-4-shape-drift.yml`](../.github/workflows/post-4-shape-drift.yml), not a file in this folder.
It's the article's workflow with one change: `project: post-4-drift-in-prs` instead of `project: .`,
because `shape.yml` is in this folder. It runs on every pull request, so the required check always
reports, whatever folder a pull request changes.

For the same reason, `shape git-setup` wrote `.gitattributes` and `.gitignore` at the repository root.

## Run it locally

You need Python 3.11 or later and Git. From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
pip install "sqllocks-shape[domains]==0.9.3"
pip install "sqllocks-shape[yaml]==0.9.3"

cd post-4-drift-in-prs
sha256sum data/orders.csv          # c7ec6218f6a181dd438a3cc0e4b515bbdf730d00cc3d0d7df04e96499ac72487
shape project validate
shape git-setup                    # once per clone: readable `git diff` of .shape files

mkdir -p _runner
shape profile orders -o _runner/current.shape
shape diff baseline/orders.shape _runner/current.shape --fail-on-drift
echo $?                            # 0 on main: no drift
```

To see it fail, check out the pull request's branch (or run `python blank_order_totals.py data/orders.csv` on a branch of your own) and run the last three commands again. `shape diff` reports `order_total: null_rate_change [breaking]` and exits 1.

`_runner/` is in `.gitignore`, so the scratch profile is never committed.

## Read more

- The article: [SQLBites](https://sqlbites.net) (link to come).
- [Pull request check](https://docs.shapedata.ai/v0.9.3/PR_BOT/) and [Drift](https://docs.shapedata.ai/v0.9.3/DRIFT/) in the Shape 0.9.3 documentation.
