"""A Textual TUI for exploring netcdf and zarr datasets."""

import argparse
import json
import multiprocessing as mp
import os
import time
from collections.abc import Mapping
from importlib.metadata import entry_points
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

import numpy as np
import xarray as xr
from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Tree
from textual_plotext import PlotextPlot

from xr_tui.hdf_reader import hdf5_to_datatree
from xr_tui.plotting import ErrorWidget, Plot1DWidget, Plot2DWidget, PlotNDWidget, TableNDWidget

mp.set_start_method("fork")


def is_remote_uri(path: str) -> bool:
    """Check if a given path is a remote URI."""
    parsed = urlparse(path)
    return parsed.scheme not in ("", "file")


def _normalize_path(path: str) -> Union[str, Path]:
    """Resolve local paths to an absolute Path; leave remote URIs untouched."""
    if is_remote_uri(path):
        return path
    return Path(path).resolve()


def _convert_nbytes_to_readable(nbytes: int) -> str:
    """Convert bytes to a human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if nbytes < 1024:
            return f"{nbytes:.2f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.2f} PB"


def _get_file_info(file: str) -> dict:
    """Get basic info about the file such as size and format."""
    if is_remote_uri(file):
        _, file_type = os.path.splitext(file)
        file_type = file_type.lower() if file_type else "N/A (remote file)"
        return {
            "File Size": "N/A (remote file)",
            "File Type": file_type,
            "Permissions": "N/A (remote file)",
            "Created Time": "N/A (remote file)",
            "Modified Time": "N/A (remote file)",
        }

    if os.path.isdir(file):
        file_size = sum(
            os.path.getsize(os.path.join(dirpath, filename))
            for dirpath, dirnames, filenames in os.walk(file)
            for filename in filenames
        )
    else:
        file_size = os.path.getsize(file)

    file_type = "Directory" if os.path.isdir(file) else os.path.splitext(file)[1].lower()
    permissions = oct(os.stat(file).st_mode)[-3:]
    return {
        "File Size": _convert_nbytes_to_readable(file_size),
        "File Type": file_type,
        "Permissions": permissions,
        "Created Time": time.ctime(os.path.getctime(file)),
        "Modified Time": time.ctime(os.path.getmtime(file)),
    }


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy scalar and array types found in xarray attrs."""

    def default(self, o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.bool_):
            return bool(o)
        return str(o)


def _group_to_dict(group: xr.DataTree) -> dict:
    """Recursively convert a DataTree group to a JSON-serialisable structure dict."""
    dims = {name: int(size) for name, size in group.dims.items()}

    coords = {}
    for name in group.coords:
        var = group.coords[name]
        coords[name] = {
            "dims": list(var.dims),
            "dtype": str(var.dtype),
            "size": _convert_nbytes_to_readable(var.nbytes),
            "attributes": dict(var.attrs),
        }

    data_vars = {}
    for name in group.data_vars:
        var = group.data_vars[name]
        data_vars[name] = {
            "dims": list(var.dims),
            "dtype": str(var.dtype),
            "size": _convert_nbytes_to_readable(var.nbytes),
            "attributes": dict(var.attrs),
        }

    return {
        "attributes": dict(group.attrs),
        "dimensions": dims,
        "coordinates": coords,
        "data_variables": data_vars,
        "groups": {child: _group_to_dict(group[child]) for child in group.children},
    }


class StatisticsScreen(Screen):
    """A screen to display statistics of a variable."""

    BINDINGS = [("escape", "app.pop_screen", "Pop screen")]

    def __init__(self, variable: xr.DataArray, **kwargs) -> None:
        super().__init__(**kwargs)
        self.variable = variable
        self.n_bins = 100

    def compose(self) -> ComposeResult:
        """Create child widgets for the screen."""

        if self.variable.dtype.kind in ("U", "S", "O"):
            # String or object dtype - cannot compute statistics
            plot_widget = ErrorWidget(self.variable, id="plot-screen-error")
            plot_widget.border_title = f"[white]Statistics of {self.variable.name}[/]"
            plot_widget.border_subtitle = "[white]Press 'Esc' to return[/]"
            yield plot_widget
            return

        stats = self._compute_statistics(self.variable)
        data = self.variable.values.flatten()
        data = data[~np.isnan(data)]  # Remove NaN values

        plot_widget = PlotextPlot(id="hist-widget")
        plot_widget.plt.hist(data, bins=self.n_bins)
        plot_widget.plt.title(f"Histogram of {self.variable.name}")
        plot_widget.plt.xlabel("Value")
        plot_widget.plt.ylabel("Frequency")

        table = DataTable(id="stats-table")
        table.add_column("Statistic")
        table.add_column("Value")

        for stat_name, stat_value in stats.items():
            table.add_row(stat_name, f"{stat_value:.4f}")

        modal = Grid(plot_widget, table, id="stats-container")
        modal.border_title = f"[white]Statistics for {self.variable.name}[/]"
        modal.border_subtitle = "[white]Press 'Esc' to return[/]"
        yield modal

    def _compute_statistics(self, variable: xr.DataArray) -> dict:
        """Compute basic statistics for the variable."""
        data = variable.values.flatten()

        nan_count = np.isnan(data).sum()
        inf_count = np.isinf(data).sum()
        pct_nan = (nan_count / data.size) * 100
        pct_inf = (inf_count / data.size) * 100

        data = data[~np.isnan(data)]  # Remove NaN values

        pct_25 = np.percentile(data, 25)
        pct_50 = np.percentile(data, 50)
        pct_75 = np.percentile(data, 75)

        stats = {
            "Mean": data.mean(),
            "Median": np.median(data),
            "Standard Deviation": data.std(),
            "Range": data.max() - data.min(),
            "Minimum": data.min(),
            "25%": pct_25,
            "50%": pct_50,
            "75%": pct_75,
            "Maximum": data.max(),
            "Count": len(data),
            "NaN Count": nan_count,
            "NaN %": pct_nan,
            "Inf Count": inf_count,
            "Inf %": pct_inf,
        }
        return stats


class PlotScreen(Screen):
    """A screen to display plots of a 1D, 2D, and ND variables."""

    BINDINGS = [("escape", "app.pop_screen", "Pop screen")]

    def __init__(self, variable: xr.DataArray, **kwargs) -> None:
        super().__init__(**kwargs)
        self.variable = variable

    def compose(self) -> ComposeResult:
        """Create child widgets for the screen."""

        if self.variable.dtype.kind in ("U", "S", "O"):
            # String or object dtype - cannot plot
            plot_widget = ErrorWidget(self.variable, id="plot-screen-error")
            plot_widget.border_title = f"[white]Plot of {self.variable.name}[/]"
            plot_widget.border_subtitle = "[white]Press 'Esc' to return[/]"
            yield plot_widget
            return

        if len(self.variable.dims) == 1:
            plot_widget = Plot1DWidget(self.variable, id="plot-screen")
        elif len(self.variable.dims) == 2:
            plot_widget = Plot2DWidget(self.variable, id="plot-screen")
        else:
            plot_widget = PlotNDWidget(self.variable, id="plot-screen")

        plot_widget.border_title = f"[white]Plot of {self.variable.name}[/]"
        plot_widget.border_subtitle = "[white]Press 'Esc' to return[/]"
        yield plot_widget


class TableScreen(Screen):
    """A screen to display a variable's values as a navigable table."""

    BINDINGS = [("escape", "app.pop_screen", "Pop screen")]

    def __init__(self, variable: xr.DataArray, **kwargs) -> None:
        super().__init__(**kwargs)
        self.variable = variable

    def compose(self) -> ComposeResult:
        """Create child widgets for the screen."""
        if self.variable.ndim == 0:
            widget = ErrorWidget(self.variable, id="table-screen-error")
        else:
            widget = TableNDWidget(self.variable, id="table-screen")
        widget.border_title = f"[white]Table of {self.variable.name}[/]"
        widget.border_subtitle = "[white]Press 'Esc' to return[/]"
        yield widget


class XarrayTUI(App):
    """A Textual app to view xarray Datasets."""

    CSS_PATH = "xr-tui.tcss"

    SCREENS = {"plot_screen": PlotScreen}

    BINDINGS = [
        ("q", "quit_app", "Quit"),
        ("e", "expand_all", "Expand all nodes"),
        ("c", "collapse_all", "Collapse all nodes"),
        ("p", "plot_variable", "Plot variable"),
        ("s", "show_statistics", "Show statistics"),
        ("t", "show_table", "Show table"),
        ("d", "toggle_dark", "Toggle dark mode"),
        ("j", "cursor_down", "Move down"),
        ("k", "cursor_up", "Move up"),
        ("h", "cursor_left", "Collapse node"),
        ("l", "cursor_right", "Expand node"),
    ]

    def __init__(
        self,
        path_list: list[str],
        group: Optional[str] = None,
        engine: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.title = "xr-tui"
        self.theme = "monokai"
        self.group = group
        self.engine = engine

        self.paths = [_normalize_path(p) for p in path_list]

        if len(self.paths) == 1:
            self._init_single_file(self.paths[0])
        else:
            self._init_multi_file(self.paths)

    def _init_single_file(self, path: Union[str, Path]) -> None:
        """Load single file xarray or HDF5 datatree"""
        self.file = str(path)
        self.file_info = _get_file_info(self.file)

        try:
            self.dataset = xr.open_datatree(
                path, chunks=None, create_default_indexes=False, engine=self.engine
            )
        except ValueError:
            self.dataset = hdf5_to_datatree(path)

    def _init_multi_file(self, paths: list[Path]) -> None:
        """Load multi file xarray datatree"""
        parent_dirs = list({p.parent for p in paths})
        file_suffixes = list({p.suffix for p in paths})

        if len(parent_dirs) > 1 or len(file_suffixes) > 1:
            raise ValueError("All files must share the same directory and extension.")

        self.file_glob = f"*{file_suffixes[0]}"
        self.file = f"{parent_dirs[0]}/{self.file_glob}"
        self.file_info = [_get_file_info(str(path)) for path in paths]

        plugins = entry_points(group="xr_tui.backends")
        plugins_dict = {p.name: p for p in plugins}
        plugin = plugins_dict.get(self.file_glob.lower())

        if plugin:
            backend = plugin.load()
            self.dataset = backend.open_mfdatatree(self, paths)
        else:
            raise NotImplementedError(
                f"No backend found for loading files with the extension '{self.file_glob}'\n"
                "To install a plugin to support this please run \n"
                "uv tool install xr-tui --with <package-name>\n"
                "OR\n"
                "pipx install xr-tui & pipx inject xr-tui <package-name>"
            )

    def _get_file_summary_info(self, paths: list[Path], file_glob: str) -> dict:
        """Get summary information about the files"""
        total_file_size = sum(os.path.getsize(file) for file in paths)
        first_created_time = time.ctime(os.path.getctime(paths[0]))
        last_created_time = time.ctime(os.path.getctime(paths[-1]))
        return {
            "File Glob": file_glob,
            "Total Files Loaded": len(paths),
            "Total Files Size": _convert_nbytes_to_readable(total_file_size),
            "First File Created": first_created_time,
            "Last File Created": last_created_time,
        }

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()

        tree: Tree[str] = Tree(f"xarray Dataset: [bold]{self.file} [/bold]")
        tree.root.expand()
        # add file info as first child
        file_info_node = tree.root.add("File Information")
        file_info_node.expand()

        if not hasattr(self, "file_glob"):
            self._add_leaf_items(file_info_node, self.file_info)

        elif hasattr(self, "file_glob"):
            file_summary = self._get_file_summary_info(self.paths, self.file_glob)
            self._add_leaf_items(file_info_node, file_summary)

            file_list_node = file_info_node.add("Individual File Information")
            for i, file in enumerate(self.file_info):
                file_info_list_node = file_list_node.add(self.paths[i].name)
                self._add_leaf_items(file_info_list_node, file)

        def add_group_node(
            parent_node: Tree, group: xr.DataTree, group_name: str = ""
        ) -> None:
            """Recursively add group nodes to the tree."""
            num_vars = len(group.data_vars)
            num_coords = len(group.coords)
            label = f"Group: {group_name}" if group_name else "Root"
            group_node = parent_node.add(
                f"{label} (Data Variables: [blue]{num_vars}[/blue]"
                f" Coordinates: [blue]{num_coords}[/blue])"
            )
            group_node.expand()

            self._add_dims_node(group_node, group)
            self._add_coords_node(group_node, group)
            self._add_data_vars_node(group_node, group)

            # Recursively add child groups
            for child_name in group.children:
                child_group = group[child_name]
                add_group_node(group_node, child_group, child_name)

        add_group_node(tree.root, self.dataset)

        num_attributes = len(self.dataset.attrs)
        # NOTE This is hardcoded to find the second node which should be the
        # "Root" node. It may need changing if the above code changes node ordering
        attributes_node = tree.root.children[1].add(
            f"Attributes ([blue]{num_attributes}[/blue])", before=0
        )
        self._add_attributes_node(attributes_node, self.dataset.attrs)

        yield tree

    def _add_leaf_items(self, parent_node: Tree, iterator: dict) -> None:
        """Helper method to add dictionary items to a node's leaf."""
        for key, value in iterator.items():
            parent_node.add_leaf(f"[yellow]{key}[/]: {value}")

    def _add_attributes_node(self, parent_node: Tree, attributes: dict) -> None:
        """Recursively add global attributes to File Information node."""
        for key, value in attributes.items():
            if isinstance(value, Mapping):
                attr_node = parent_node.add(f"{key}")
                self._add_attributes_node(attr_node, value)
            else:
                parent_node.add_leaf(f"[yellow]{key}[/yellow]: {value}")

    def _add_dims_node(self, parent_node: Tree, group) -> None:
        """Helper method to add dimension nodes to the tree."""
        dims_node = parent_node.add("Dimensions")
        dims_node.expand()
        for dim_name, dim_size in group.dims.items():
            dims_node.add_leaf(f"{dim_name}: [blue]{dim_size}[/blue]")

    def _add_data_vars_node(self, parent_node: Tree, group) -> None:
        """Helper method to add data variable nodes to the tree."""
        data_vars_node = parent_node.add("Data Variables")
        data_vars_node.expand()
        for var_name in group.data_vars.keys():
            self._add_var_node(data_vars_node, group.data_vars[var_name])

    def _add_coords_node(self, parent_node: Tree, group) -> None:
        """Helper method to add coordinate nodes to the tree."""
        coords_node = parent_node.add("Coordinates")
        coords_node.expand()
        for coord_name in group.coords.keys():
            self._add_var_node(coords_node, group.coords[coord_name])

    def _add_var_node(self, parent_node: Tree, var: xr.DataArray) -> None:
        """Helper method to add a variable node to the tree."""
        nbytes = _convert_nbytes_to_readable(var.nbytes)
        var_node = parent_node.add(
            f"{var.name}: [red]{var.dims}[/] [green]{var.dtype}[/] [blue]{nbytes}[/]",
        )
        var_node.data = {"name": var.name, "type": "variable_node", "item": var}

        num_attributes = len(var.attrs)
        attr_node = var_node.add(f"Attributes ([blue]{num_attributes}[/blue])")
        self._add_leaf_items(attr_node, var.attrs)

    def action_plot_variable(self) -> None:
        """An action to plot the currently selected variable."""
        tree = self.query_one(Tree)
        current_node = tree.cursor_node
        if current_node is None:
            return

        if (
            current_node.data is None
            or current_node.data.get("type") != "variable_node"
        ):
            return

        self.push_screen(PlotScreen(current_node.data["item"]))

    def action_show_statistics(self) -> None:
        """An action to show statistics of the currently selected variable."""
        tree = self.query_one(Tree)
        current_node = tree.cursor_node
        if current_node is None:
            return

        if (
            current_node.data is None
            or current_node.data.get("type") != "variable_node"
        ):
            return

        self.push_screen(StatisticsScreen(current_node.data["item"]))

    def action_show_table(self) -> None:
        """An action to show the selected variable's values as a table."""
        tree = self.query_one(Tree)
        current_node = tree.cursor_node
        if current_node is None:
            return

        if (
            current_node.data is None
            or current_node.data.get("type") != "variable_node"
        ):
            return

        self.push_screen(TableScreen(current_node.data["item"]))

    def action_expand_all(self) -> None:
        """An action to expand all tree nodes."""
        self.query_one(Tree).root.expand_all()

    def action_collapse_all(self) -> None:
        """An action to collapse all tree nodes."""
        self.query_one(Tree).root.collapse_all()

    def action_quit_app(self) -> None:
        """An action to quit the app."""
        self.exit()

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )

    def action_cursor_down(self) -> None:
        """Move cursor down in the tree (vim j key)."""
        tree = self.query_one(Tree)
        tree.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up in the tree (vim k key)."""
        tree = self.query_one(Tree)
        tree.action_cursor_up()

    def action_cursor_left(self) -> None:
        """Collapse current node in the tree (vim h key)."""
        tree = self.query_one(Tree)
        if tree.cursor_node and tree.cursor_node.allow_expand:
            tree.cursor_node.collapse()

    def action_cursor_right(self) -> None:
        """Expand current node in the tree (vim l key)."""
        tree = self.query_one(Tree)
        if tree.cursor_node and tree.cursor_node.allow_expand:
            tree.cursor_node.expand()


def main():
    """Entry point for the xr-tui CLI."""
    parser = argparse.ArgumentParser(
        description="A Textual TUI for managing xarray Datasets."
    )
    parser.add_argument(
        "path_list",
        type=str,
        nargs="+",
        help="Path to the xarray Dataset file(s).",
    )
    parser.add_argument(
        "--group",
        type=str,
        help="Path to a specific group within the dataset.",
        default=None,
    )
    parser.add_argument(
        "--engine",
        type=str,
        help="The xarray engine to use for opening the dataset.",
        default=None,
    )
    parser.add_argument(
        "--export-json",
        nargs="?",
        const=True,
        default=None,
        metavar="FILE",
        help="Export dataset structure to JSON and exit. Writes to FILE or stdout if omitted.",
    )
    args = parser.parse_args()

    if args.export_json is not None:
        paths = [_normalize_path(p) for p in args.path_list]

        if len(paths) == 1:
            file_info = {"file_info": _get_file_info(str(paths[0]))}
            try:
                dataset = xr.open_datatree(
                    paths[0], chunks=None, create_default_indexes=False, engine=args.engine
                )
            except ValueError:
                dataset = hdf5_to_datatree(paths[0])
        else:
            parent_dirs = list({p.parent for p in paths})
            file_suffixes = list({p.suffix for p in paths})
            if len(parent_dirs) > 1 or len(file_suffixes) > 1:
                raise ValueError("All files must share the same directory and extension.")
            file_glob = f"*{file_suffixes[0]}"
            summary = {
                "File Glob": file_glob,
                "Total Files Loaded": len(paths),
                "Total Files Size": _convert_nbytes_to_readable(
                    sum(os.path.getsize(p) for p in paths)
                ),
                "First File Created": time.ctime(os.path.getctime(paths[0])),
                "Last File Created": time.ctime(os.path.getctime(paths[-1])),
            }
            per_file = {p.name: _get_file_info(str(p)) for p in paths}
            file_info = {"file_info": {"summary": summary, "files": per_file}}

            plugins = entry_points(group="xr_tui.backends")
            plugin = {p.name: p for p in plugins}.get(file_glob.lower())
            if not plugin:
                raise NotImplementedError(f"No backend found for '{file_glob}'")
            dataset = plugin.load().open_mfdatatree(None, paths)

        output = {**file_info, "dataset": _group_to_dict(dataset)}
        json_str = json.dumps(output, indent=2, cls=_NumpyEncoder)

        if args.export_json is True:
            print(json_str)
        else:
            Path(args.export_json).write_text(json_str, encoding="utf-8")
        return

    app = XarrayTUI(args.path_list, group=args.group, engine=args.engine)
    app.run()


if __name__ == "__main__":
    main()
