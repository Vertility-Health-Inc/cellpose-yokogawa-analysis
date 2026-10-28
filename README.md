# Yokogawa image analysis: Cellpose segmentation → measurement → scatter

This folder holds a small toolkit for basic analysis of a Yokogawa CellVoyager plate run
(single timepoint, no tracking):

| File | What it does |
|---|---|
| `cellpose_segment_measure_scatter.ipynb` | **The main notebook.** It segments nuclei (default) or whole cells with Cellpose-SAM, measures every object in every channel, writes per-object and per-well CSVs, and makes scatter plots. |
| `Stitch_yokogawa_by_well.py` | Optional. Tiles one field from every well into a single plate-layout overview image (`.tif`), for a quick look at the whole plate. |
| `environment.yml`, `requirements.txt` | The Python dependencies (see Install). |

---

## 1. Install (one time)

You need **conda**. If you don't have it, install Miniforge first:
<https://github.com/conda-forge/miniforge> (on an Apple-silicon Mac, use the `arm64` installer).

Then, in Terminal:

```bash
cd /path/to/yokogawa-cellpose-analysis
conda env create -f environment.yml
```

This creates an environment named `cellpose` (Python 3.10, Cellpose 4.0.4, PyTorch, JupyterLab, etc.).
It downloads about 1–2 GB and takes several minutes. You only do this once.

The first time the notebook runs, Cellpose also downloads its model weights (~1 GB) to `~/.cellpose/`.
This also happens only once.

**Without conda:** any Python 3.10–3.12 works:
```bash
python -m venv cellpose-env && source cellpose-env/bin/activate
pip install -r requirements.txt
```

**Hardware:** On an Apple-silicon Mac, Cellpose uses the GPU (MPS) automatically, at about 25 s per 2000×2000 tile.
On an NVIDIA machine, install the CUDA build of PyTorch first (see <https://pytorch.org/get-started/locally/>).
CPU-only machines work but are very slow (minutes per tile).

---

## 2. Run the notebook

```bash
conda activate cellpose
cd /path/to/yokogawa-cellpose-analysis
jupyter lab cellpose_segment_measure_scatter.ipynb
```

If you open it in VS Code instead, choose the **`cellpose`** environment as the kernel
(top right → *Select Kernel* → *Python Environments* → `cellpose`).

### Edit the **Config** cell, and nothing else

| Setting | Meaning |
|---|---|
| `IMAGE_DIR` | The run's image folder, e.g. `<run>/Image` (sometimes `.../Projection`). It must contain files named like `W0014F0001T0001Z001C1.tif` (W = well, F = field, T = timepoint, Z = z-slice, C = channel). Projection images use `Z000` (e.g. `W0014F0002T0001Z000C3.tif`) or a label such as `ZMAX`. |
| `OUT_DIR` | Where results are written. It is created if missing. Keep it outside `IMAGE_DIR`. |
| `TAG` | Prefix for output file names, e.g. the experiment name. |
| `SEG_CHANNEL` | The channel Cellpose segments. The default `1` (Hoechst) gives **nuclei**. Set it to the brightfield channel (e.g. `2`) for **whole cells**. Each choice writes to its own output subfolder (`seg_C1_<model>/`, `seg_C2_<model>/`), so you can switch back and forth without mixing results. |
| `CHANNEL_NAMES` | Every channel to measure → a display name, e.g. `{1: "Hoechst", 2: "brightfield"}`. Check the channel order in the acquisition settings (`MeasurementProtocol.xml` in the run folder lists each channel's name). Intensities from a brightfield channel are not a fluorescence signal. |
| `DIAMETER` | Leave as `None`. Set an object diameter in pixels only if the QC image shows objects split or merged. |
| `MODEL` | Which Cellpose model to use. These are the same choices as the GUI:<br>• `"cpsam"`: the built-in Cellpose-SAM (the GUI's *run CPSAM* button). This is the default.<br>• A model **name** from the GUI's *custom models* dropdown, e.g. `"my_custom_model"`. These live in `~/.cellpose/models/`.<br>• A **path** to a model file anywhere on disk, like the GUI's *add custom model*.<br>The Setup cell prints the installed models, and an unknown name stops with an error. Each model writes to its own output subfolder. |
| `FLOW_THRESHOLD`, `CELLPROB_THRESHOLD`, `NORM_PERCENTILES`, `NITER`, `MIN_SIZE` | The GUI's *additional settings*, with the GUI defaults (0.4, 0.0, (1, 99), 200, 15). Raise `FLOW_THRESHOLD` or lower `CELLPROB_THRESHOLD` to get more or larger masks. |
| `SHARPEN_RADIUS`, `SMOOTH_RADIUS`, `TILE_NORM_BLOCKSIZE`, `INVERT` | The GUI's *custom filter settings* (image filtering before segmentation). All are off (0 / False) by default. |
| `Z_PLANE` | Leave as `"auto"`. It uses the projection (`Z000`/`ZMAX`/…) if the folder has one, or the only z-slice if there is just one. If the folder holds a z-stack and no projection, the notebook stops and asks you to set this to a slice number (e.g. `3`). |
| `WELLS`, `FIELDS` | Optional subset for a quick test, e.g. `WELLS = [14, 15]`, `FIELDS = [1, 2]`. Set both to `None` for everything. |
| `CONDITIONS` | Plate map: well name → condition label, e.g. `{"B02": "ctrl", "B03": "treated"}`. Wells you leave out are plotted under their well name. **Double-check this against the real plate.** A shifted layout is the most common source of wrong conclusions. |
| `X_COL`, `Y_COL` | Which per-object columns to scatter (see the column list below). The default is `area` vs `mean_intensity_C1`. |
| `LOG_AXES` | `True` for raw intensities. Set it to `False` for background-subtracted columns, which can be ≤ 0. |
| `MIN_AREA` | Objects smaller than this many pixels are dropped as debris. |

**Well numbering:** wells are numbered 1–96, row by row across 12 columns. A01 = 1, A12 = 12, B01 = 13, B02 = 14, and so on.
The notebook converts the numbers to names (`B02`) for you.

### Then run everything

Use *Run → Run All Cells*. The notebook works in this order:

1. **Index:** lists the z-plane used and the wells, fields and channels it found. Check that this matches what you imaged.
   Tiles missing one of the `CHANNEL_NAMES` / `SEG_CHANNEL` images are skipped, and the number skipped is printed.
2. **QC tile:** shows the first tile with object outlines in red. **Look at this before waiting on the full run.**
   Nearly every in-focus nucleus (or cell) should have an outline. The very brightest saturated blobs (often dead or condensed
   cells) are sometimes skipped. That is normal.
3. **Segment + measure:** the slow step, ~25 s per tile with a progress bar. A 96-well plate × 9 fields takes about 6 h.
   Masks are cached in `OUT_DIR/seg_C#_<model>/masks/`, so if the notebook is interrupted, re-run it and it resumes where it stopped.
   The settings that made the masks are saved in `segmentation_settings.json` next to them. If you change `DIAMETER` or a
   threshold/filter setting, the notebook stops rather than mix old and new masks. Delete the `masks/` folder (or change
   `OUT_DIR`) to re-segment.
4. **Per-well summary:** a table of cell counts and medians.
5. **Scatter:** the plot is displayed and saved.

To try different plots, change `X_COL`/`Y_COL` in Config and re-run only the Config cell and the last cell.

---

## 3. Outputs (in `OUT_DIR/seg_C#_<model>/`, where # = `SEG_CHANNEL` and `<model>` = `MODEL`'s name)

| File | Contents |
|---|---|
| `segmentation_settings.json` | The model and settings used to make the masks. |
| `masks/W####F####T####Z###_masks.tif` | One label image per tile (0 = background, 1…n = object IDs). Opens in Fiji/ImageJ. |
| `<TAG>_cells.csv` | **One row per segmented object** (nucleus or cell). This is the main data table. |
| `<TAG>_well_summary.csv` | One row per well: `n_cells` and median area and intensities. |
| `<TAG>_scatter_<X>_vs_<Y>.png` | The scatter figure. |

### Columns in `<TAG>_cells.csv`

| Column | Meaning |
|---|---|
| `well`, `well_name`, `field`, `timepoint`, `z` | Where the cell came from (`well` = 1–96, `well_name` = `B02`). |
| `label` | Object ID within that tile's mask. |
| `condition` | From the `CONDITIONS` plate map. |
| `area`, `perimeter` | Size, in pixels. |
| `centroid_x`, `centroid_y` | Position in the tile, in pixels. |
| `major_axis_length`, `minor_axis_length`, `eccentricity`, `solidity` | Shape. Eccentricity 0 = round, →1 = elongated. Solidity < ~0.9 = irregular or merged. |
| `mean_intensity_C#` | Mean raw pixel value inside the object for channel # (the MFI). |
| `max_intensity_C#` | Brightest pixel in the object. |
| `total_intensity_C#` | Mean × area (integrated intensity). |
| `bg_C#` | Background for that tile and channel: the median of pixels away from any segmented object. |
| `mfi_bgsub_C#` | `mean_intensity_C#` − `bg_C#`. Use this to compare wells whose background differs. |

---

## 4. Tips and gotchas

- **Background varies well to well**, especially at 640 nm, so compare wells using `mfi_bgsub_C#`. If a dye sits
  in the medium, many nuclei will be at or below background (`mfi_bgsub` ≈ 0 or negative). That is real, not a bug.
- **Only one channel is segmented** (`SEG_CHANNEL`). Every channel is measured inside those masks. With nuclear
  masks, signal outside the nucleus (cytoplasm, membrane) is not captured. Segment on brightfield to measure whole cells.
- **Matching the Cellpose GUI:** with the default Config, the notebook matches the GUI's *run CPSAM* with default
  settings. If you load the same tile and channel in the GUI, you should get the same number of objects. To match a GUI
  run that used a custom model or changed settings, set `MODEL` and the same values in Config.
- **Sharing a custom model:** a custom model is a single ~1.2 GB file in `~/.cellpose/models/` and is not in this repo.
  To use it on another computer, copy the file over, then either set `MODEL` to its path, or put it in that computer's
  `~/.cellpose/models/` and add it in the GUI (*Models → add custom model*) so it can be used by name.
- **Older models (`cyto3`, `nuclei`, `livecell`, …)** are from Cellpose 3 and are not available in Cellpose 4, which
  this environment uses. Cellpose-SAM generally does as well or better on both nuclei and cells.
- **Tiles missing locally?** Yokogawa folders are sometimes synced without images. Copy the `W*.tif` files into
  `IMAGE_DIR` first. The Index cell reports `0 tiles` if none are present.
- **macOS "OMP: Error #15 … libomp.dylib already initialized":** the notebook already sets
  `KMP_DUPLICATE_LIB_OK=TRUE` to avoid this. If you write your own script, set it before importing cellpose/torch.
- **Whole-plate overview image** (optional), using the stitching script:
  ```bash
  conda activate cellpose
  python Stitch_yokogawa_by_well.py --folder_path /path/to/run/Image --plate_type 96 --frame 5 --channel 1 --output_name F5_C1_stitch.tif
  ```
  This writes `F5_C1_stitch.tif` (field 5 of every well, channel 1, laid out as the plate) into the image folder. Open it in Fiji.
  `--z_slice` defaults to `auto`, which works the same way as `Z_PLANE` above. For a z-stack with no projection, pass a slice number (`--z_slice 3`).

## License

BSD 3-Clause. See [LICENSE](LICENSE). Copyright (c) 2026 Vertility Health, Inc.
