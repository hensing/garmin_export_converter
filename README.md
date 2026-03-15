# Garmin Export Converter

A professional tool to process Garmin Data Takeout (GDPR) exports. It extracts activity files from multiple ZIP parts, renames them based on internal metadata, and optionally converts them to GPX format.

## Overview

Garmin's data export provides activity files in a nested structure. This tool automates the process of:
1. **Auto-discovery:** Finding the `DI-Connect-Uploaded-Files` folder within your unzipped export.
2. **Extraction:** Locating and extracting `UploadedFiles_*.zip` files, plus loose `.fit`, `.gpx`, and `.txt` (GPX-XML) files.
3. **Renaming:** 
   - Reading internal FIT metadata (`session.start_time`, `file_id.time_created`) to get exact start times.
   - Falls back to the numeric ID from the filename if no internal timestamp is found.
   - Preserves activity comments found in the original filenames.
4. **Intelligent Processing:** 
   - Converts FIT files to GPX only if they contain GPS data (waypoints).
   - Can automatically skip indoor/gym activities without location data (configurable).
5. **Efficiency:** Processes files iteratively and provides progress updates every 500 files to keep Docker logs clean.

## Prerequisites

- [Docker](https://www.docker.com/) installed on your system.
- Your Garmin Data Export. Request it here: [Garmin Account Data Management](https://www.garmin.com/en-US/account/datamanagement/exportdata)

## Quick Start (Docker)

1. **Unzip your Garmin export:**
   When you receive your export, you'll get a file like `6e3a1234-123b-1234-a004-1f4a9f695e2e_1.zip`. Unzip it.
   Example path: `~/Downloads/garmin_export_2026/`

2. **Prepare your folders:**
   - Create an empty folder named `export` for the results.
   - Your `config.yaml` should be in the project root.

3. **Run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

   *Alternatively, run with Docker directly (example with Mac paths):*
   ```bash
   docker run \
     -v ~/Downloads/garmin_export_2026:/app/data \
     -v $(pwd)/export:/app/export \
     -v $(pwd)/config.yaml:/app/config.yaml \
     garmin-converter
   ```

   **Note:** The tool will automatically look for `DI-Connect-Uploaded-Files` inside your mounted `/app/data`.

## Configuration (`config.yaml`)

```yaml
# Date and time settings
date_format: "%Y-%m-%d_%H-%M-%S"
timezone: "Europe/Berlin"

# File naming
prefix: "activity"

# Conversion settings
convert_to_gpx: true

# Indoor / Gym activity settings
# If true, activities without GPS waypoints will be completely ignored.
# If false, the .fit file will be saved, but no .gpx file will be created.
skip_activities_without_gps: true
```

## Folder Structure (Example)

```text
~/Downloads/garmin_export_2026/          <-- Mount this as /app/data
└── DI_CONNECT/
    └── DI-Connect-Uploaded-Files/      <-- Auto-discovered
        ├── UploadedFiles_0-_Part1.zip
        └── ...
```

## License

This project is licensed under the [GPLv3 License](LICENSE).

## Author

Created by [@hensing](https://github.com/hensing) (Dr. Henning Dickten).
