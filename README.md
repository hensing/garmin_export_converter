# Garmin Export Converter

A professional tool to process Garmin Data Takeout (GDPR) exports. It extracts activity files from Garmin's cryptic nested structure, renames them using intelligent metadata extraction, and optionally converts them to GPX.

## Why this tool?

Garmin's official data export is a mess of nested ZIP files and cryptic names like `garminuser_22226321318.fit`. This tool empowers you to **take control of your data sovereignty**:

- **Order from Chaos:** Automatically auto-discovers and extracts activities from multi-part ZIPs.
- **Human-Readable:** Converts cryptic IDs into meaningful names like `activity_2022-10-29_12-14-49.gpx`.
- **Intelligent Timezones:** Uses offline GPS-based lookup to ensure filenames match the local time where you actually trained.
- **Lightroom Ready:** Perfect for long-term backups or post-processing workflows like geotagging photos in Adobe Lightroom.

## Features

1. **Auto-discovery:** Automatically finds the `DI-Connect-Uploaded-Files` folder within your unzipped export.
2. **Multi-Format Extraction:** Processes `.fit`, `.gpx`, and XML-based `.txt` files from multiple ZIP parts.
3. **Smart Renaming:** 
   - Reading internal FIT metadata (`session.start_time`, `file_id.time_created`) to get exact start times.
   - Converts cryptic names like `garminuser_22226321318.fit` into human-readable files like `activity_2025-10-29_12-14-49.gpx`.
   - Preserves activity comments (e.g., "Morning Run") from original filenames.
   - Falls back to numeric IDs if no timestamp is found.
4. **Offline Timezone Detection:** Automatically determines the correct local timezone based on activity GPS coordinates (no internet required).
5. **Intelligent Processing:** 
   - Converts FIT files to GPX only if they contain actual location data.
   - Configurable skipping of indoor/gym activities without GPS data.
6. **Docker-First:** Runs in a clean, isolated environment without messing up your host system.

## Prerequisites

- <a href="https://www.docker.com/" target="_blank">Docker</a> installed on your system.
- Your Garmin Data Export. Request it here: <a href="https://www.garmin.com/en-US/account/datamanagement/exportdata" target="_blank">Garmin Account Data Management</a>

> **Note on Data Export:** Garmin typically takes about **48 hours** to prepare your export, but depending on the amount of data and current requests, it could take **up to 30 days**. You will receive an email with a download link once it's ready.

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

## Configuration (`config.yaml`)

```yaml
# Date and time settings
date_format: "%Y-%m-%d_%H-%M-%S"

# Automatic timezone detection based on GPS coordinates (offline via timezonefinder)
auto_timezone: true
# Fallback timezone if GPS data is missing or auto_timezone is false
default_timezone: "Europe/Berlin"

# File naming
prefix: "activity"

# Conversion settings
convert_to_gpx: true

# Indoor / Gym activity settings
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
