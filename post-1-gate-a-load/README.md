# Post 1: Copy Succeeded. The Data Didn't. Gate the Load.

The runnable Fabric material from SQLBites post 1 of "Shape in practice": the `shape_finale` pipeline, the contract
and the notebooks it runs, on Shape 0.9.3. All the data is synthetic.

The article: [Copy Succeeded. The Data Didn't. Gate the Load.](https://sqlbites.net/gate-a-load-in-fabric-with-shape/)
(live once published).

## What the pipeline does

- Two Copy activities land the day's orders (Parquet) and customers (CSV) from the `shape-landing` container in the lakehouse.
- `ProfileLakehouse` runs `finale_profile`: it profiles the day with Shape, checks the contract, compares the day with the same weekday a week earlier (drift), checks the promotions workbook, writes history and exits with a JSON verdict.
- `GateLakehouse` reads `passed`. When it's false, the Fail activity `Quarantined` stops the run with `ShapeQuarantine`, and the warehouse is never touched.
- Otherwise the promotions workbook is copied, the orders are staged to the warehouse, and `LoadWarehouse` deletes the day and inserts it from stage.
- `ProfileWarehouse` runs the same checks on the warehouse copy and also compares it with the lakehouse profile of the same day.
- `GateWarehouse` fails the run with `ShapeWarehouseMismatch` when it doesn't match. The `plantLoadBug` parameter truncates `order_total` to whole numbers to prove it.

## The files

| File | What it is |
|---|---|
| [`pipeline/shape_finale.pipeline-content.json`](pipeline/shape_finale.pipeline-content.json) | The `shape_finale` pipeline definition (Fabric's `pipeline-content.json`), with placeholders for your IDs. |
| [`notebooks/finale_profile.notebook.py`](notebooks/finale_profile.notebook.py) | The profiling notebook both Notebook activities run, with `layer = "lakehouse"` or `"warehouse"`. |
| [`notebooks/finale_reset.notebook.py`](notebooks/finale_reset.notebook.py) | Resets the demo to "history through `keepThrough`": removes later landing folders, `.shape` files, chaos logs and lakehouse rows. Starts as a dry run. |
| [`notebooks/finale_report.notebook.py`](notebooks/finale_report.notebook.py) | Turns saved `.shape` files into HTML reports with `shape.load(path).to_html()`. |
| [`contracts/finale_orders.json`](contracts/finale_orders.json) | The contract, as the article prints it. |

The notebooks are in Fabric's notebook source format (`notebook-content.py`, as Fabric stores a notebook in Git). Each
installs Shape with `%pip install "sqllocks-shape[domains,excel]==0.9.3"`; the pipeline turns on `%pip` for its
Notebook activities with `_inlineInstallationEnabled = true`. Apart from that line and the placeholders below, the
files are as exported from the demo workspace.

The data comes from post 5's `finale_generate` notebook:
[`../post-5-generate-into-fabric/notebook/finale_generate.notebook.py`](../post-5-generate-into-fabric/notebook/finale_generate.notebook.py).

## Import it into your workspace

You need a Fabric workspace on a capacity, permission to create items, and an ADLS Gen2 account. The names
`shape_demo`, `shape_wh`, `finale_profile` and `shape_finale` are the article's; use your own if you like.

1. **Lakehouse.** Create a lakehouse (the article's is `shape_demo`). Note its ID and the workspace ID: they're in the
   item's URL.
2. **Warehouse.** Create a warehouse (`shape_wh`). Create `dbo.finale_order_stage` and `dbo.finale_order` with the
   columns `order_id, customer_id, store_id, shipping_address_id, promotion_id, order_date, status, order_total, load_date`.
   In `dbo.finale_order`, `order_total` is `DECIMAL(12,2)`. Note the warehouse ID and its SQL connection string
   (the warehouse's settings show it).
3. **Landing container and connection.** Create the ADLS container `shape-landing`. In the lakehouse, create the
   shortcut `Files/shape-landing` to it. Create a connection to the ADLS account for the Copy activities and note its ID
   (Manage connections and gateways shows it).
4. **Notebooks.** Create Python notebooks `finale_profile`, `finale_reset` and `finale_report`, each with your lakehouse
   as the default lakehouse. Copy the cells in from the files above and mark each parameters cell as the parameter
   cell. Or create them from the files with Fabric's Git integration or the
   [Items API](https://learn.microsoft.com/rest/api/fabric/core/items/create-item) (definition part
   `notebook-content.py`, format `fabricGitSource`), after replacing `<lakehouse-id>` and `<workspace-id>`.
   Note the ID of `finale_profile`.
5. **Pipeline.** Replace the placeholders in `pipeline/shape_finale.pipeline-content.json` (table below), then create
   the pipeline `shape_finale` from it: with the
   [pipeline REST API](https://learn.microsoft.com/fabric/data-factory/pipeline-rest-api-capabilities#create-a-pipeline-with-definition)
   (definition part `pipeline-content.json`, Base64-encoded), or through Git integration.
6. **Set the placeholders** in the notebook parameters cells too (table below). If you don't want the safe profile
   committed to Git, set `commitToGit` to `false` in both Notebook activities; then `gitRepo`, `vaultUrl` and
   `secretName` aren't used.
7. **Contract.** Upload [`contracts/finale_orders.json`](contracts/finale_orders.json) to `Files/contracts/` in the lakehouse.
8. **Data.** Generate the landing files with post 5's
   [`finale_generate`](../post-5-generate-into-fabric/notebook/finale_generate.notebook.py) notebook, one run per
   `batchDate`. It writes `order/`, `customer/` and `promotion/` day folders through `Files/shape-landing`.
   Its `chaos` parameter defaults to `True`; set it to `False` for clean days.
   Land at least eight days, then run the pipeline once with `mode = backfill` to seed the history.
9. **Daily runs.** Run with `mode = day` and `loadDate = <the day>`. The exported defaults are `loadDate = 2026-10-06`
   and `mode = backfill`. Try a clean day, a chaos day (`chaos = True` in `finale_generate`) and `plantLoadBug = true`.

## Placeholders

Every value below was replaced in the export. Set each one to yours.

| Field | File and place | Placeholder | Where to find or set your value |
|---|---|---|---|
| Notebook metadata `default_lakehouse` and `known_lakehouses[].id` | all three notebooks, top `META` block | `<lakehouse-id>` | Your lakehouse ID, or attach the lakehouse as default in the notebook editor. |
| Notebook metadata `default_lakehouse_workspace_id` | all three notebooks, top `META` block | `<workspace-id>` | Your workspace ID. |
| `workspace` parameter | `finale_profile` parameters cell; `ProfileLakehouse` and `ProfileWarehouse` base parameters | `<workspace-name>` | Your workspace name (used in the OneLake `abfss://` path; use the ID if the name has a space). |
| `gitRepo` parameter | `finale_profile` parameters cell; both Notebook activities | `<owner>/<profiles-repo>` | A GitHub repository you own for the safe profiles, or leave it and set `commitToGit = false`. |
| `vaultUrl` parameter | `finale_profile` parameters cell; both Notebook activities | `https://<your-key-vault>.vault.azure.net/` | Your Key Vault URL. Only needed with `commitToGit = true`. |
| `secretName` parameter | `finale_profile` parameters cell; both Notebook activities | `<your-secret-name>` | The Key Vault secret holding a GitHub token. Only needed with `commitToGit = true`. |
| `TABLES` path | `finale_reset`, code cell | `abfss://<workspace-name>@onelake.dfs.fabric.microsoft.com/<lakehouse-name>.Lakehouse/Tables` | Your workspace and lakehouse names. |
| Copy source `connection` | pipeline: `LoadToLakehouse`, `LoadCustomersCsv`, `LoadPromotionsExcel` | `<adls-connection-id>` | The ID of your ADLS connection (step 3). |
| Lakehouse `workspaceId` and `artifactId` | pipeline: sinks of the three landing Copy activities, source of `StageToWarehouse` | `<workspace-id>`, `<lakehouse-id>` | Your workspace and lakehouse IDs. |
| `notebookId` and `workspaceId` | pipeline: `ProfileLakehouse`, `ProfileWarehouse` | `<notebook-id>`, `<workspace-id>` | The ID of your `finale_profile` notebook and your workspace ID. |
| Warehouse `endpoint`, `artifactId` and `workspaceId` | pipeline: `LoadWarehouse` linked service, `StageToWarehouse` sink | `<warehouse-sql-endpoint>`, `<warehouse-id>`, `<workspace-id>` | The warehouse's SQL connection string host, its ID, and your workspace ID. |

The lakehouse name `shape_demo`, the warehouse name `shape_wh` and the container `shape-landing` are kept where the
export has them, because the article prints them. If you use other names, change them in the pipeline's linked
services, in the `lakehouse` and `warehouse` parameters, and in `finale_reset` (`connect_to_artifact("shape_wh")`).

## Read more

- The article: <https://sqlbites.net/gate-a-load-in-fabric-with-shape/> (live once published).
- [Contracts](https://docs.shapedata.ai/v0.9.3/CONTRACTS/), [Drift](https://docs.shapedata.ai/v0.9.3/DRIFT/),
  [Excel workbooks](https://docs.shapedata.ai/v0.9.3/EXCEL/) and [Install](https://docs.shapedata.ai/v0.9.3/INSTALL/)
  in the Shape 0.9.3 documentation.
