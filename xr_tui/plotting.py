"""Widgets for plotting xarray DataArray variables."""

import numpy as np
import xarray as xr
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import RadioButton, RadioSet, Static
from textual.widget import Widget
from textual_slider import Slider
from textual_plotext import PlotextPlot


class ErrorWidget(Widget):
    """A widget to display plot errors."""

    def __init__(self, variable: xr.DataArray, **kwargs) -> None:
        super().__init__(**kwargs)
        self.variable = variable

    def compose(self) -> ComposeResult:
        """Render the error message."""
        message = (
            f"Cannot plot variable [bold]'{self.variable.name}'[/]"
            f"with dtype [bold]{self.variable.dtype}[/]!\n"
            "Plotting is only supported for numeric data types."
        )
        error_widget = Static(message, id="plot-error-message")
        yield error_widget


class Plot1DWidget(Widget):
    """A widget to plot 1D variables."""

    def __init__(self, variable: xr.DataArray, **kwargs) -> None:
        super().__init__(**kwargs)
        self.variable = variable

    def compose(self) -> ComposeResult:
        """Render the 1D plot."""
        x_dim_name = self.variable.dims[0]

        if x_dim_name in self.variable.coords:
            x_coords = self.variable.coords[x_dim_name].values
        else:
            x_coords = np.arange(self.variable.shape[0])

        y_values = self.variable.values
        y_values = np.nan_to_num(y_values, nan=0.0)

        plot_widget = PlotextPlot(id="plot-container")
        plot_widget.plt.plot(x_coords.tolist(), y_values.tolist())
        xunit = self.variable.coords[x_dim_name].attrs.get("units", "")
        xlabel = f"{x_dim_name} ({xunit})" if xunit else x_dim_name
        plot_widget.plt.xlabel(xlabel)
        plot_widget.plt.ylabel(self.variable.name)
        plot_widget.plt.title(f"1D Plot of {self.variable.name}")
        yield plot_widget


class Plot2DWidget(Widget):
    """A widget to plot 2D variables."""

    def __init__(self, variable: xr.DataArray, **kwargs) -> None:
        super().__init__(**kwargs)
        self.variable = variable

    def compose(self) -> ComposeResult:
        """Render the 2D plot."""
        x_dim_name = self.variable.dims[1]
        y_dim_name = self.variable.dims[0]

        z = self.variable.values
        z = np.nan_to_num(z, nan=0.0)

        # Get coordinate values
        if x_dim_name in self.variable.coords:
            x_coords = self.variable.coords[x_dim_name].values
        else:
            x_coords = np.arange(z.shape[1])

        if y_dim_name in self.variable.coords:
            y_coords = self.variable.coords[y_dim_name].values
        else:
            y_coords = np.arange(z.shape[0])

        plot_widget = PlotextPlot(id="plot-container")
        plot_widget.plt.matrix_plot(z.tolist())
        plot_widget.plt.xticks(
            np.arange(len(x_coords)), labels=[f"{val:.4f}" for val in x_coords]
        )
        plot_widget.plt.yticks(
            np.arange(len(y_coords)), labels=[f"{val:.4f}" for val in y_coords]
        )

        xunit = self.variable.coords[x_dim_name].attrs.get("units", "")
        yunit = self.variable.coords[y_dim_name].attrs.get("units", "")

        xlabel = f"{x_dim_name} ({xunit})" if xunit else x_dim_name
        ylabel = f"{y_dim_name} ({yunit})" if yunit else y_dim_name
        plot_widget.plt.xlabel(xlabel)
        plot_widget.plt.ylabel(ylabel)

        plot_widget.plt.title(f"2D Plot of {self.variable.name}")

        yield plot_widget


class PlotNDWidget(Widget):
    """A widget to plot ND variables."""

    def __init__(self, variable: xr.DataArray, **kwargs) -> None:
        super().__init__(**kwargs)
        self.variable = variable

    def compose(self) -> ComposeResult:
        """Create child widgets for the screen."""
        dims = list(self.variable.dims)

        dim1 = 0
        dim2 = 1

        r1_buttons = []
        for i, dim in enumerate(dims):
            disabled = i == dim2
            button = RadioButton(dim, value=i == dim1, disabled=disabled)
            r1_buttons.append(button)

        r2_buttons = []
        for i, dim in enumerate(dims):
            disabled = i == dim1
            button = RadioButton(dim, value=i == dim2, disabled=disabled)
            r2_buttons.append(button)

        r1 = RadioSet(*r1_buttons, id="x-dim-select-1")
        r1.border_title = "[white]Y Dimension[/]"
        r2 = RadioSet(*r2_buttons, id="y-dim-select-2")
        r2.border_title = "[white]X Dimension[/]"

        slice_inputs = self.create_slice_sliders(dim1, dim2)

        plot_widget = self._plot_variable_nd()
        plot_widget = Vertical(
            Horizontal(r1, r2, id="dim-select-container"),
            slice_inputs,
            plot_widget,
            id="plot-container",
        )

        yield plot_widget

    def create_slice_sliders(self, dim1: int = 0, dim2: int = 1) -> None:
        """Create sliders for slicing dimensions other than dim1 and dim2."""
        slice_inputs = []
        dims = list(self.variable.dims)
        for dim in dims:
            if dim not in [dims[dim1], dims[dim2]]:
                dim_size = self.variable.sizes[dim]
                slider = Slider(
                    0,
                    dim_size - 1,
                    step=1,
                    id=f"slice-{dim}",
                    name=dim,
                    value=dim_size // 2,
                )
                slider.border_title = f"[white]Slice Position for {dim}[/]"
                slice_inputs.append(slider)

        slice_inputs = Horizontal(*slice_inputs, id="slice-inputs-container")
        return slice_inputs

    @on(Slider.Changed)
    async def on_slider_changed_normal(self, _event: Slider.Changed) -> None:
        """Handle slider change events to update the plot."""
        slicers = self.query_one("#slice-inputs-container")
        slicers = slicers.children
        slice_positions = {
            slicer.name: slicer.value
            for slicer in slicers
            if isinstance(slicer, Slider)
        }

        dim1_group = self.query_one("#x-dim-select-1")
        dim2_group = self.query_one("#y-dim-select-2")

        dim1 = self._get_selected_dim(dim1_group)
        dim2 = self._get_selected_dim(dim2_group)

        new_plot = self._plot_variable_nd(dim1, dim2, slice_positions)
        plot_container = self.query_one("#plot-container")

        # Swap out the old plot with the new one
        await plot_container.children[-1].remove()
        await plot_container.mount(new_plot)

    def _get_selected_dim(self, radio_set: RadioSet) -> int:
        for i, radio in enumerate(radio_set.children):
            if isinstance(radio, RadioButton) and radio.value:
                return i
        return 0

    async def on_radio_set_changed(self, _message: RadioSet.Changed):
        """Handle radio button changes to update the plot."""
        dim1_group = self.query_one("#x-dim-select-1")
        dim2_group = self.query_one("#y-dim-select-2")

        dim1 = self._get_selected_dim(dim1_group)
        dim2 = self._get_selected_dim(dim2_group)

        for i, radio in enumerate(dim1_group.children):
            if isinstance(radio, RadioButton):
                radio.disabled = i == dim2

        for i, radio in enumerate(dim2_group.children):
            if isinstance(radio, RadioButton):
                radio.disabled = i == dim1

        dim1_group.refresh()
        dim2_group.refresh()

        slice_inputs = self.create_slice_sliders(dim1, dim2)

        # Re-plot with new dimensions
        new_plot = self._plot_variable_nd(dim1, dim2)
        plot_container = self.query_one("#plot-container")
        await plot_container.children[-1].remove()
        await plot_container.children[-1].remove()
        await plot_container.mount(slice_inputs)
        await plot_container.mount(new_plot)

    # pylint: disable-msg=too-many-locals
    def _plot_variable_nd(
        self, dim1: int = 0, dim2: int = 1, slice_positions: dict = None
    ) -> PlotextPlot:
        if slice_positions is None:
            slice_positions = {}

        # Default to last two dimensions for x and y
        y_dim_name = self.variable.dims[dim1]
        x_dim_name = self.variable.dims[dim2]

        # Get the indices for other dimensions (set to middle slice)
        slice_dict = {}
        for dim in self.variable.dims:
            if dim not in [x_dim_name, y_dim_name]:
                if dim in slice_positions:
                    slice_dict[dim] = slice_positions[dim]
                else:
                    dim_size = self.variable.sizes[dim]
                    slice_dict[dim] = dim_size // 2

        # Slice the variable to get 2D data
        sliced_var = self.variable.isel(slice_dict)

        z = sliced_var.values
        z = np.nan_to_num(z, nan=0.0)

        # Get coordinate values
        if x_dim_name in sliced_var.coords:
            x_coords = sliced_var.coords[x_dim_name].values
        else:
            x_coords = np.arange(z.shape[1])

        if y_dim_name in sliced_var.coords:
            y_coords = sliced_var.coords[y_dim_name].values
        else:
            y_coords = np.arange(z.shape[0])

        plot_widget = PlotextPlot(id="plot-widget")
        plot_widget.plt.matrix_plot(z.tolist())
        plot_widget.plt.xticks(
            np.arange(len(x_coords)), labels=[f"{val:.4f}" for val in x_coords]
        )
        plot_widget.plt.yticks(
            np.arange(len(y_coords)), labels=[f"{val:.4f}" for val in y_coords]
        )

        unit = sliced_var.coords[y_dim_name].attrs.get("units", "")
        label = f"{y_dim_name} ({unit})" if unit else y_dim_name
        plot_widget.plt.xlabel(label)

        unit = sliced_var.coords[x_dim_name].attrs.get("units", "")
        label = f"{x_dim_name} ({unit})" if unit else x_dim_name
        plot_widget.plt.ylabel(label)

        # Add info about sliced dimensions to title
        slice_info = ", ".join([f"{dim}={idx}" for dim, idx in slice_dict.items()])
        title = (
            f"{self.variable.name} ({slice_info})"
            if slice_info
            else f"{self.variable.name}"
        )
        plot_widget.plt.title(title)
        return plot_widget
