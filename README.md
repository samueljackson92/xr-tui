# xr-tui

[![CI](https://github.com/samueljackson92/xr-tui/workflows/Lint/badge.svg)](https://github.com/samueljackson92/xr-tui/actions)
[![GitHub stars](https://img.shields.io/github/stars/samueljackson92/xr-tui)](https://github.com/samueljackson92/xr-tui/stargazers)
[![GitHubIssues](https://img.shields.io/badge/issue_tracking-github-blue.svg)](https://github.com/samueljackson92/xr-tui/issues)
[![GitTutorial](https://img.shields.io/badge/PR-Welcome-%23FF8300.svg?)](https://github.com/samueljackson92/xr-tui/pulls)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/pylint-dev/pylint)
![PyPI - Status](https://img.shields.io/pypi/v/xr-tui)


xr-tui is an interactive terminal user interface (TUI) for exploring and visualizing multi-dimensional datasets. It uses xarray to support loading NetCDF, Zarr, and HDF5 tree structures, and provides a user-friendly interface for data exploration directly in the terminal.

![](demo.gif)

## Features
- Interactive navigation through NetCDF, Zarr, and HDF5 datasets.
- Visualization of 1D and 2D data using plotext for terminal-based plotting.
- Support for slicing multi-dimensional data.
- Easy-to-use command-line interface.
- Displays dataset statistics and metadata.
- Handles HDF5 files not formatted as xarray datasets.

## Installation
You can install xr-tui via pip:

```bash
pipx install xr-tui
```

Or as a uv tool:

```bash
uv tool install xr-tui
```

## Usage
To start xr-tui, simply run the following command in your terminal:

```bash
xr data.nc
```

This will launch the TUI, allowing you to explore the contents of `data.nc`.

xr-tui supports various file formats compatible with xarray, including NetCDF, Zarr, and HDF5.

You can also specify a particular group within a file to load:

```bash
xr data.nc --group summary
```

xr-tui also works with remote datasets accessible via HTTP:

```bash
xr http://example.com/data.zarr
```


## Key Command Reference

| Key | Action |
|-----|--------|
| `q` | Quit the application. |
| `h` | Show help menu. |
| `e` | Expand all nodes in the dataset tree. |
| `space` | Collapse all nodes in the dataset tree. |
| Arrow keys | Navigate through the dataset. |
| `Enter` | Select an item or open a variable |
| `s` | Show statistics of the selected variable. |
| `p` | Plot the selected variable. |
