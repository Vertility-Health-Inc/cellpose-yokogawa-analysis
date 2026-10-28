#!/usr/bin/env python3
"""
Yokogawa Image Stitching Script

Converted from Jupyter notebook to command line script.

Takes in a folder of single images and desired stiching parameters and returns stiched .tif images in well-plate format for easy overview.
"""

import os
import re
import pandas as pd
import tifffile
import numpy as np
import argparse

def extract_metadata(folder_path):
    """Extract metadata from .tif files and return as pandas DataFrame"""
    
    # List to store all metadata dictionaries
    metadata_list = []
    
    # Pattern to match W####F####T####Z###C#
    # Z may be a slice number (Z000) or a projection label (ZSUM, ZMAX)
    pattern = r'W(\d+)F(\d+)T(\d+)Z(\d+|[A-Za-z]+)C(\d+)$'
    
    try:
        for filename in os.listdir(folder_path):
            if filename.endswith('.tif'):
                # Remove .tif extension
                base_name = filename.replace('.tif', '')
                
                # Extract metadata using regex
                match = re.match(pattern, base_name)
                
                if match:
                    metadata = {
                        'filename': filename,
                        'W': int(match.group(1)),
                        'F': int(match.group(2)),
                        'T': int(match.group(3)),
                        'Z': int(match.group(4)) if match.group(4).isdigit() else match.group(4).upper(),
                        'C': int(match.group(5))
                    }
                    metadata_list.append(metadata)
                else:
                    print(f"Could not parse: {filename}")
    
    except FileNotFoundError:
        print(f"Folder '{folder_path}' not found")
        return pd.DataFrame()
    
    # Convert to DataFrame
    df = pd.DataFrame(metadata_list)

    if len(df) > 0:  # FIX: Only create summary if we have data
        meta_summary = pd.DataFrame([{ 'W': len(df['W'].unique()), 'F': len(df['F'].unique()), 'T': len(df['T'].unique()), 'Z': len(df['Z'].unique()), 'C': len(df['C'].unique())}])

        print(f"""
    Found:
    - Unique Wells: {meta_summary['W'][0]}
    - Unique Frames: {meta_summary['F'][0]}
    - Unique Timepoints: {meta_summary['T'][0]}
    - Unique Z slices: {meta_summary['Z'][0]}
    - Unique Channels: {meta_summary['C'][0]}
        """)

    return df


def stitch_images_by_well(metadata,plate_type,frame,timepoint,z_slice,channel):
    # note prepopulates matrix based on dims of first loaded image, ALL IMAGES MUST THEREFORE BE THE SAME SIZE
    stitch_list = metadata[(metadata['F'] == frame) & (metadata['T'] == timepoint) & (metadata['Z'] == z_slice) & (metadata['C'] == channel)]

    # FIX: Check if any images were found
    if len(stitch_list) == 0:
        print(f"ERROR: No images found for F{frame} T{timepoint} Z{z_slice} C{channel}")
        print("Available parameters:")
        print(f"  Frames: {sorted(metadata['F'].unique())}")
        print(f"  Timepoints: {sorted(metadata['T'].unique())}")
        print(f"  Z-slices: {sorted(metadata['Z'].unique(), key=str)}")
        print(f"  Channels: {sorted(metadata['C'].unique())}")
        return None

    # plate layout: (rows, columns)
    layouts = {'6': (2, 3), '12': (3, 4), '24': (4, 6), '96': (8, 12), '384': (16, 24)}

    if plate_type not in layouts:
        print(f"ERROR: Unknown plate type '{plate_type}'. Choose from: {', '.join(layouts)}")
        return None

    n_rows, n_cols = layouts[plate_type]

    # FIX: catch wells that cannot exist on the requested plate before indexing
    max_well = int(stitch_list['W'].max())
    if max_well > n_rows * n_cols:
        print(f"ERROR: Found well {max_well}, but a {plate_type}-well plate only has {n_rows * n_cols} wells.")
        for name, (r, c) in layouts.items():
            if max_well <= r * c:
                print(f"       Try --plate_type {name}")
                break
        return None

    with tifffile.TiffFile(stitch_list['filename'].iloc[0]) as tif:
        shape = tif.pages[0].shape

    y_px = shape[0]
    x_px = shape[1]

    tile = np.full((y_px * n_rows, x_px * n_cols), 0, dtype=np.uint16)

    for i in range(len(stitch_list)):
        file = stitch_list['filename'].iloc[i]
        wellnum = int(stitch_list['W'].iloc[i])

        # FIX: wells are numbered 1-based, row-major -> convert to 0-based grid coords
        row, col = divmod(wellnum - 1, n_cols)
        TLy = row * y_px
        TLx = col * x_px

        img = tifffile.imread(file)

        tile[TLy:TLy + y_px, TLx:TLx + x_px] = img

    return tile

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder_path", required=True)
    parser.add_argument("--plate_type", default='96')  # Keep as string since you compare with strings
    parser.add_argument("--frame", type=int, default=1)        # FIX: Convert to int
    parser.add_argument("--timepoint", type=int, default=1)    # FIX: Convert to int
    parser.add_argument("--z_slice", default="auto")           # "auto" (projection Z000/ZMAX if present, else the only slice), a slice number, or a label like SUM/MAX
    parser.add_argument("--channel", type=int, required=True)  # FIX: Convert to int
    parser.add_argument("--output_name", required=True)

    args = parser.parse_args()

    # FIX: Get metadata before changing directory
    metadata = extract_metadata(args.folder_path)
    
    if len(metadata) == 0:
        print("No valid images found. Exiting.")
        return

    # Z can be numeric (a slice; Z000 = projection) or a projection label -> normalise to match the parsed column
    if str(args.z_slice).lower() == "auto":
        z_values = sorted(metadata['Z'].unique(), key=str)
        projections = [z for z in z_values if z == 0 or isinstance(z, str)]
        if len(projections) == 1 or len(z_values) == 1:
            z_slice = (projections or z_values)[0]
        else:
            print(f"ERROR: several z-planes found {z_values}; pass --z_slice")
            return
        print(f"Using Z = {z_slice}")
    else:
        z_slice = int(args.z_slice) if str(args.z_slice).isdigit() else str(args.z_slice).upper()

    os.chdir(args.folder_path)

    tile = stitch_images_by_well(metadata,args.plate_type,args.frame,args.timepoint,z_slice,args.channel)

    if tile is not None:  # FIX: Check if stitching succeeded
        tifffile.imwrite(args.output_name,tile)
        print(f"Successfully created: {args.output_name}")
    else:
        print("Stitching failed.")

if __name__ == "__main__":
    main()