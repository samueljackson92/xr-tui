# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

**xr-tui** is a Python TUI (terminal user interface) for interactively exploring multi-dimensional scientific datasets (NetCDF, Zarr, HDF5). Users navigate a tree of variables/groups, view statistics, and generate plots — all in the terminal. Built on [Textual](https://textual.textualize.io/) with xarray as the data backend.

## Commands

```bash
# Lint (matches CI)
ruff check .
pylint xr_tui

# Run the app locally
xr <path-to-dataset>          # local file
xr <path> --group <group>     # open a specific HDF5/NetCDF group
xr http://example.com/data.zarr  # remote file via HTTP/S3

# Install in development mode
uv sync
uv run xr <file>
```

There is no test suite — quality assurance relies entirely on `ruff` and `pylint`.

## Architecture

The package lives in `xr_tui/` and has three modules:

### `cli.py` — Application core
- **`XarrayTUI`** is the main `textual.App` subclass. It handles file loading, dataset tree construction, keybindings, and screen navigation.
- **`PlotScreen`** and **`StatisticsScreen`** are modal screens pushed onto the screen stack for secondary views.
- On launch, the app reads the file using xarray/h5py, builds a `DataTree`, then populates a `Tree` widget where each node's `.data` dict carries `{"name": ..., "type": "variable_node"|"group_node", "item": xr.DataArray|xr.Dataset}`.
- Multi-file loading uses the `xr_tui.backends` entry-point group — third-party packages can register backends that combine files into a single `DataTree`.

### `plotting.py` — Plot widgets
Four widget classes, selected based on variable dimensionality:
- **`ErrorWidget`**: unsupported types
- **`Plot1DWidget`**: line plots
- **`Plot2DWidget`**: matrix/heatmap
- **`PlotNDWidget`**: interactive N-D slicing — radio buttons choose X/Y axes, sliders slice the remaining dimensions, and plots update reactively

### `hdf_reader.py` — HDF5 adapter
- `hdf5_to_datatree()` converts arbitrary HDF5 files (not written as xarray datasets) into `DataTree` structures that the rest of the app can consume uniformly.
- Handles HDF5 object and region references, and infers dimension names from group structure.

### `xr-tui.tcss` — Textual CSS
Styling for modal screens and plot containers. Grid-based layouts; edit this when changing widget layout or colors.

## Key Conventions

- **Keybindings**: Vim-style (`j`/`k` up/down, `h`/`l` collapse/expand). Declared in the `BINDINGS` tuple of `XarrayTUI`.
- **Node metadata**: Tree node `.data` dicts are the contract between `cli.py` and `plotting.py`/statistics logic — always include `type` and `item` keys.
- **Dependency management**: Use `uv`. The `uv.lock` file is committed and should stay in sync.
- **Versioning**: Managed by `bump-my-version` (`.bumpversion.toml`). Do not manually edit version strings; use `bump-my-version bump <part>`.
- **CI**: `.github/workflows/lint.yml` runs `ruff check .` and `pylint xr_tui` on every push/PR to `main`. Both must pass before merging.
