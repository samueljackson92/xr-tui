"""A Textual TUI for exploring netcdf and zarr datasets."""

import argparse
import os
import time

import numpy as np
import xarray as xr
from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Tree
from textual_plotext import PlotextPlot
from xr_tui.plotting import Plot1DWidget, Plot2DWidget, PlotNDWidget, ErrorWidget
from xr_tui.hdf_reader import hdf5_to_datatree


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
        ("d", "toggle_dark", "Toggle dark mode"),
        ("j", "cursor_down", "Move down"),
        ("k", "cursor_up", "Move up"),
        ("h", "cursor_left", "Collapse node"),
        ("l", "cursor_right", "Expand node"),
    ]

    def __init__(self, file: str, group: str = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.title = "xr-tui"
        self.theme = "monokai"

        self.file = file
        self.group = group

        self.file_info = self._get_file_info(file)

        try:
            dataset = xr.open_datatree(file, chunks=None, create_default_indexes=False)
        except ValueError:
            dataset = hdf5_to_datatree(file)

        self.dataset = dataset

    def _get_file_info(self, file: str) -> None:
        """Get basic info about the file such as size and format."""

        if os.path.isdir(file):
            file_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(file)
                for filename in filenames
            )
        else:
            file_size = os.path.getsize(file)
        file_type = os.path.splitext(file)[1].lower()
        permissions = oct(os.stat(file).st_mode)[-3:]
        created_time = time.ctime(os.path.getctime(file))
        modified_time = time.ctime(os.path.getmtime(file))
        file_info = {
            "File Size": self._convert_nbytes_to_readable(file_size),
            "File Type": file_type,
            "Permissions": permissions,
            "Created Time": created_time,
            "Modified Time": modified_time,
        }
        return file_info

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()

        tree: Tree[str] = Tree(f"xarray Dataset: [bold]{self.file} [/bold]")
        tree.root.expand()
        # add file info as first child
        file_info_node = tree.root.add("File Information")
        file_info_node.expand()
        for key, value in self.file_info.items():
            file_info_node.add_leaf(f"[yellow]{key}[/]: {value}")

        def add_group_node(parent_node: Tree, group, group_name: str = "") -> None:
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

        yield tree

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
        nbytes = self._convert_nbytes_to_readable(var.nbytes)
        var_node = parent_node.add(
            f"{var.name}: [red]{var.dims}[/] [green]{var.dtype}[/] [blue]{nbytes}[/]",
        )
        var_node.data = {"name": var.name, "type": "variable_node", "item": var}

        num_attributes = len(var.attrs)
        attr_node = var_node.add(f"Attributes ([blue]{num_attributes}[/blue])")
        for attr, value in var.attrs.items():
            attr_node.add_leaf(f"[yellow]{attr}[/]: {value}")

    def _convert_nbytes_to_readable(self, nbytes: int) -> str:
        """Convert bytes to a human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if nbytes < 1024:
                return f"{nbytes:.2f} {unit}"
            nbytes /= 1024
        return f"{nbytes:.2f} PB"

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
    parser.add_argument("file", type=str, help="Path to the xarray Dataset file.")
    parser.add_argument(
        "--group",
        type=str,
        help="Path to a specific group within the dataset.",
        default=None,
    )
    args = parser.parse_args()

    app = XarrayTUI(args.file, group=args.group)
    app.run()


if __name__ == "__main__":
    main()
