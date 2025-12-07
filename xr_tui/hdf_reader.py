"""Utilities for reading HDF5 files into xarray DataTrees"""

import h5py
import numpy as np
import xarray as xr


def resolve_reference(file, ref):
    """Return object or region referenced by an HDF5 reference."""
    obj = file[ref]

    # Object reference → dataset or group
    if isinstance(obj, h5py.Dataset):
        return obj[()]  # return array

    if isinstance(obj, h5py.Group):
        return {
            k: v[()] if isinstance(v, h5py.Dataset) else "group" for k, v in obj.items()
        }

    return None


def resolve_region_reference(dataset, regref):
    """Return the sliced region referenced in a region reference."""
    return dataset[regref]  # h5py handles slicing internally


def load_dataset_with_refs(file, dataset):
    """Load HDF5 dataset, resolving any object/region references."""
    arr = dataset[()]  # read raw data

    if dataset.dtype == h5py.ref_dtype:
        # Convert array of references → Python objects
        out = np.empty(arr.shape, dtype=object)
        for idx, ref in np.ndenumerate(arr):
            out[idx] = resolve_reference(file, ref)
        return out

    if dataset.dtype.kind == "O" and isinstance(arr.flat[0], h5py.Reference):
        # Sometimes references appear as object dtype
        out = np.empty(arr.shape, dtype=object)
        for idx, ref in np.ndenumerate(arr):
            out[idx] = resolve_reference(file, ref)
        return out

    # Region references (rare but possible)
    if dataset.dtype == h5py.regionref_dtype:
        out = np.empty(arr.shape, dtype=object)
        for idx, regref in np.ndenumerate(arr):
            out[idx] = resolve_region_reference(dataset, regref)
        return out

    return arr  # normal dataset


def infer_dims(name, arr):
    """Infer dimension names for an array based on its number of dimensions."""
    return tuple(f"{name}_dim_{i}" for i in range(arr.ndim))


def hdf5_group_to_datatree(name, group, file):
    """Recursively convert a group, resolving references."""
    variables = {}
    coords = {}

    # Load datasets
    for key, item in group.items():
        if isinstance(item, h5py.Dataset):
            data = load_dataset_with_refs(file, item)
            dims = infer_dims(key, data)
            variables[key] = (dims, data)

            if np.ndim(data) == 1:
                coords[key] = (dims, data)

    ds = xr.Dataset(variables)
    if coords:
        ds = ds.assign_coords(coords)

    # Load children groups
    children = {
        key: hdf5_group_to_datatree(key, item, file)
        for key, item in group.items()
        if isinstance(item, h5py.Group)
    }

    return xr.DataTree(
        name=name, dataset=ds if ds.data_vars else None, children=children
    )


def hdf5_to_datatree(path, group: str = None) -> xr.DataTree:
    """Read HDF5 file into a hierarchical DataTree with reference resolution."""
    with h5py.File(path, "r") as f:
        tree = hdf5_group_to_datatree("root", f, f)

    if group:
        try:
            return tree[group]
        except KeyError as exc:
            raise ValueError(f"Group '{group}' not found in the HDF5 file.") from exc

    return tree
