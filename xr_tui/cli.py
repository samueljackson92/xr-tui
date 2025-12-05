import argparse
import xarray as xr
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Tree


class XarrayTUI(App):
    """A Textual app to view xarray Datasets."""

    BINDINGS = [
        ("q", "quit_app", "Quit"),
        ("t", "toggle_expand", "Toggle expand/collapse of current node"),
        ("e", "expand_all", "Expand all nodes"),
        ("c", "collapse_all", "Collapse all nodes"),
        ("d", "toggle_dark", "Toggle dark mode"),
    ]

    def __init__(self, file: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.file = file
        self.dataset = xr.open_datatree(file)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()

        tree: Tree[str] = Tree(f"xarray Dataset: {self.file}")
        tree.root.expand()

        for group_name in self.dataset.groups:
            group = self.dataset[group_name]

            num_vars = len(group.data_vars)
            num_coords = len(group.coords)
            group_node = tree.root.add(
                f"Group: {group_name} (Data Variables: {num_vars}, Coordinates: {num_coords})"
            )
            group_node.expand()

            dims_node = group_node.add("Dimensions")
            for dim_name, dim_size in group.dims.items():
                dims_node.add_leaf(f"{dim_name}: {dim_size}")
            dims_node.expand()

            coords_node = group_node.add("Coordinates")
            coords_node.expand()

            for coord_name in group.coords.keys():
                self._add_var_node(coords_node, group[coord_name])

            data_vars_node = group_node.add("Data Variables")
            data_vars_node.expand()

            for var_name in group.data_vars.keys():
                self._add_var_node(data_vars_node, group[var_name])

        yield tree

    def _add_var_node(self, parent_node: Tree, var: xr.DataArray) -> None:
        """Helper method to add a variable node to the tree."""
        nbytes = self._convert_nbytes_to_readable(var.nbytes)
        var_node = parent_node.add(f"{var.name}: {var.dims} {var.dtype} {nbytes}")

        num_attributes = len(var.attrs)
        attr_node = var_node.add(f"Attributes ({num_attributes})")
        for attr, value in var.attrs.items():
            attr_node.add_leaf(f"{attr}: {value}")

    def _convert_nbytes_to_readable(self, nbytes: int) -> str:
        """Convert bytes to a human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if nbytes < 1024:
                return f"{nbytes:.2f} {unit}"
            nbytes /= 1024
        return f"{nbytes:.2f} PB"

    def action_expand_all(self) -> None:
        """An action to expand all tree nodes."""
        self.query_one(Tree).root.expand_all()

    def action_collapse_all(self) -> None:
        """An action to collapse all tree nodes."""
        self.query_one(Tree).root.collapse_all()

    def action_toggle_expand(self) -> None:
        """An action to collapse all tree nodes."""
        current_node = self.query_one(Tree).cursor_node
        if current_node.is_collapsed:
            current_node.expand()
        else:
            current_node.collapse()

    def action_quit_app(self) -> None:
        self.exit()

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )


def main():
    parser = argparse.ArgumentParser(
        description="A Textual TUI for managing xarray Datasets."
    )
    parser.add_argument("file", type=str, help="Path to the xarray Dataset file.")
    args = parser.parse_args()

    app = XarrayTUI(args.file)
    app.run()


if __name__ == "__main__":
    main()
