# Contribution Guide

We welcome any and all contributions to `xr-tui`! Whether it's reporting issues, suggesting features, improving the documentation, or submitting pull requests, your input helps improve this tool for the community.

## Adding Multi-File Support for your Data Format

To keep `xr-tui` agnostic of specific data formats, multi-file loading is handled via **Custom Backends**. If you want to add support for a specific file grouping (e.g., `*.sdf`), you must create a plugin that implements the `open_mfdatatree` method.

### Architecture

When multiple files are passed to the CLI, `xr-tui` looks for an entry point matching the file extension. It then delegates the loading process to that plugin.

### Implementation Steps

#### A. Define the Entry Point

In your plugin's `pyproject.toml`, register your backend under the `xr_tui.backends` group. The name should match the file glob you want to support.

```toml
[project.entry-points."xr_tui.backends"]
"*.sdf" = "your_package.module:XrTUIEndpoint"
```

#### B. Create the Endpoint Class

Your plugin must provide a class with an `open_mfdatatree` method. This method is responsible for returning a valid `xarray.DataTree`.

```python
import xarray as xr
from pathlib import Path

class XrTUIEndpoint:
    @staticmethod
    def open_mfdatatree(tui_instance, paths: list[Path]) -> xr.DataTree:
        # Implement your custom concatenation logic here
        # Example: return xr.open_mfdataset(paths).to_datatree()
        return your_custom_loading_logic(paths)
```

### Requirements for Support
- All files in a multi-file load must share the same **directory** and **extension**.
- The plugin must be installed in the same environment as `xr-tui`.

### How to test locally

If you are developing a plugin, you can install it into your `xr-tui` environment to test the entry point:

```bash
pipx inject xr-tui ./path/to/your/plugin
# Or with uv
uv tool install xr-tui --with ./path/to/your/plugin
```