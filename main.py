import os
import zipfile
import argparse
import yaml
import logging
import re
import shutil
import tempfile
import sys
from datetime import datetime
from pathlib import Path
import pytz
import fitdecode
import gpxpy
import gpxpy.gpx
from lxml import etree

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Track if non-GPS warning has been shown
missing_waypoint_warning_shown = False

def load_config(config_path):
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {e}")
        return {}

def get_fit_start_time(fit_path, target_timezone):
    """Extract start time from FIT file and convert to target timezone."""
    try:
        # Prioritize session start_time
        with fitdecode.FitReader(fit_path) as fit:
            for frame in fit:
                if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name == 'session':
                    if frame.has_field('start_time'):
                        start_time = frame.get_value('start_time')
                        if isinstance(start_time, datetime):
                            if start_time.tzinfo is None:
                                start_time = pytz.utc.localize(start_time)
                            return start_time.astimezone(pytz.timezone(target_timezone))
        
        # Fallback to file_id time_created
        with fitdecode.FitReader(fit_path) as fit:
            for frame in fit:
                if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name == 'file_id':
                    if frame.has_field('time_created'):
                        time_created = frame.get_value('time_created')
                        if isinstance(time_created, datetime):
                            if time_created.tzinfo is None:
                                time_created = pytz.utc.localize(time_created)
                            return time_created.astimezone(pytz.timezone(target_timezone))

        # Fallback to first record timestamp
        with fitdecode.FitReader(fit_path) as fit:
            for frame in fit:
                if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name == 'record':
                    if frame.has_field('timestamp'):
                        timestamp = frame.get_value('timestamp')
                        if isinstance(timestamp, datetime):
                            if timestamp.tzinfo is None:
                                timestamp = pytz.utc.localize(timestamp)
                            return timestamp.astimezone(pytz.timezone(target_timezone))
    except Exception as e:
        logger.debug(f"Error reading FIT file {fit_path}: {e}")
    return None

def extract_id_from_filename(filename):
    """Extract the numeric ID from filename like 'hdickten_22226321318.fit'."""
    match = re.search(r'_(\d+)', filename)
    if match:
        return match.group(1)
    return None

def convert_fit_to_gpx(fit_path, gpx_path):
    """Convert FIT file to GPX using fitdecode and gpxpy. Returns False if no GPS data."""
    gpx = gpxpy.gpx.GPX()
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(gpx_track)
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)

    points_count = 0
    try:
        with fitdecode.FitReader(str(fit_path)) as fit:
            for frame in fit:
                if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name == 'record':
                    lat = None
                    lon = None
                    ele = None
                    timestamp = None
                    
                    if frame.has_field('position_lat') and frame.has_field('position_long'):
                        lat = frame.get_value('position_lat')
                        lon = frame.get_value('position_long')
                        if lat is not None: lat = lat * (180.0 / 2**31)
                        if lon is not None: lon = lon * (180.0 / 2**31)
                    
                    if frame.has_field('enhanced_altitude'):
                        ele = frame.get_value('enhanced_altitude')
                    elif frame.has_field('altitude'):
                        ele = frame.get_value('altitude')
                        
                    if frame.has_field('timestamp'):
                        timestamp = frame.get_value('timestamp')

                    if lat is not None and lon is not None:
                        point = gpxpy.gpx.GPXTrackPoint(lat, lon, elevation=ele, time=timestamp)
                        gpx_segment.points.append(point)
                        points_count += 1
        
        if points_count == 0:
            return False

        with open(gpx_path, 'w') as f:
            f.write(gpx.to_xml())
        return True
    except Exception as e:
        logger.debug(f"Conversion error for {fit_path}: {e}")
        return False

def get_gpx_start_time(gpx_path, target_timezone):
    """Extract start time from GPX/XML file."""
    try:
        tree = etree.parse(str(gpx_path))
        root = tree.getroot()
        namespaces = {'ns': root.nsmap.get(None, 'http://www.topografix.com/GPX/1/1')}
        
        time_node = root.find('.//ns:metadata/ns:time', namespaces)
        if time_node is not None:
            dt = datetime.fromisoformat(time_node.text.replace('Z', '+00:00'))
            return dt.astimezone(pytz.timezone(target_timezone))
            
        time_node = root.find('.//ns:trkpt/ns:time', namespaces)
        if time_node is not None:
            dt = datetime.fromisoformat(time_node.text.replace('Z', '+00:00'))
            return dt.astimezone(pytz.timezone(target_timezone))
            
    except Exception as e:
        logger.debug(f"Error reading GPX/XML file {gpx_path}: {e}")
    return None

def extract_comment(filename):
    """Extract comment part from filename like 'hdickten_12345_Comment.ext'."""
    match = re.search(r'[^_]+_\d+_(.+)\.[^.]+$', filename)
    if match:
        return match.group(1)
    return ""

def has_gps_data(fit_path):
    """Quickly check if FIT file contains any GPS coordinates."""
    try:
        with fitdecode.FitReader(str(fit_path)) as fit:
            for frame in fit:
                if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name == 'record':
                    if frame.has_field('position_lat') and frame.has_field('position_long'):
                        return True
    except: pass
    return False

def process_single_file(src_file, output_dir, config):
    """Process a single file (fit, gpx, or txt-gpx)."""
    global missing_waypoint_warning_shown
    
    date_format = config.get('date_format', '%Y-%m-%d_%H-%M-%S')
    target_tz = config.get('timezone', 'Europe/Berlin')
    prefix = config.get('prefix', 'activity')
    convert_to_gpx_flag = config.get('convert_to_gpx', True)
    skip_non_gps = config.get('skip_activities_without_gps', True)

    src_path = Path(src_file)
    ext = src_path.suffix.lower()
    comment = extract_comment(src_path.name)
    start_time = None
    
    if ext == '.fit':
        start_time = get_fit_start_time(src_file, target_tz)
        
        # Check GPS data if we need to skip or warn
        has_gps = has_gps_data(src_file)
        if not has_gps:
            if not missing_waypoint_warning_shown:
                if skip_non_gps:
                    logger.info("Found activity without GPS data. Skipping according to config. (Further occurrences will be silent)")
                else:
                    logger.info("Found activity without GPS data. FIT will be saved, but GPX conversion skipped. (Further occurrences will be silent)")
                missing_waypoint_warning_shown = True
            
            if skip_non_gps:
                return False
    else:
        start_time = get_gpx_start_time(src_file, target_tz)
        has_gps = True # GPX/XML files are assumed to have GPS or we just copy them

    name_part = None
    if start_time:
        name_part = start_time.strftime(date_format)
    else:
        name_part = extract_id_from_filename(src_path.name)
        if name_part:
            logger.debug(f"No timestamp found in {src_path.name}, falling back to ID: {name_part}")
    
    if name_part:
        suffix = f"_{comment}" if comment else ""
        new_base_name = f"{prefix}_{name_part}{suffix}"
        
        if ext == '.fit':
            target_fit = output_dir / f"{new_base_name}.fit"
            shutil.copy2(src_file, target_fit)
            logger.debug(f"Saved: {target_fit.name}")
            if convert_to_gpx_flag and has_gps:
                target_gpx = output_dir / f"{new_base_name}.gpx"
                if convert_fit_to_gpx(src_file, target_gpx):
                    logger.debug(f"Converted: {target_gpx.name}")
        else:
            target_gpx = output_dir / f"{new_base_name}.gpx"
            shutil.copy2(src_file, target_gpx)
            logger.debug(f"Saved GPX: {target_gpx.name}")
        return True
    else:
        logger.warning(f"Skipping {src_path.name}: Neither internal timestamp nor numeric ID found in filename.")
        return False

def main():
    parser = argparse.ArgumentParser(description="Garmin Export Converter")
    parser.add_argument("--input", required=True, help="Path to Garmin export directory")
    parser.add_argument("--output", required=True, help="Path to output directory")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    config = load_config(args.config)
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Scanning for Garmin export files...")
    
    # 1. Auto-discovery
    relevant_subfolder = "DI-Connect-Uploaded-Files"
    found_data_dir = None
    for root, dirs, files in os.walk(input_dir):
        if relevant_subfolder in dirs:
            found_data_dir = Path(root) / relevant_subfolder
            break
            
    if not found_data_dir:
        found_data_dir = input_dir

    # 2. Collect ZIPs and loose files
    zip_files = []
    loose_files = []
    for root, dirs, files in os.walk(found_data_dir):
        for file in files:
            full_path = os.path.join(root, file)
            if file.lower().endswith('.zip') and 'UploadedFiles' in file:
                zip_files.append(full_path)
            elif file.lower().endswith(('.fit', '.gpx')):
                loose_files.append(full_path)
            elif file.lower().endswith('.txt'):
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(500)
                        if '<?xml' in content and '<gpx' in content:
                            loose_files.append(full_path)
                except: continue

    logger.info(f"Scan complete. Found {len(zip_files)} ZIP archives and {len(loose_files)} loose files.")
    logger.info("Starting conversion process...")

    total_processed = 0

    # 3. Process iterative
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Process ZIPs
        if zip_files:
            for idx, zip_file in enumerate(zip_files):
                logger.info(f"[{idx+1}/{len(zip_files)}] Processing ZIP: {os.path.basename(zip_file)}")
                
                extracted_in_this_zip = []
                try:
                    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                        for file_info in zip_ref.infolist():
                            fname = file_info.filename.lower()
                            if fname.endswith(('.fit', '.gpx', '.txt')):
                                if fname.endswith('.txt'):
                                    with zip_ref.open(file_info) as f:
                                        content = f.read(500).decode('utf-8', errors='ignore')
                                        if '<?xml' not in content or '<gpx' not in content:
                                            continue
                                
                                base_name = os.path.basename(file_info.filename)
                                target_path = temp_path / base_name
                                if target_path.exists():
                                    base, ext = os.path.splitext(base_name)
                                    target_path = temp_path / f"{base}_{datetime.now().microsecond}{ext}"
                                
                                with zip_ref.open(file_info) as source, open(target_path, 'wb') as target:
                                    target.write(source.read())
                                extracted_in_this_zip.append(target_path)
                                
                        for f_idx, f in enumerate(extracted_in_this_zip):
                            if process_single_file(f, output_dir, config):
                                total_processed += 1
                            os.remove(f)
                            
                            if (f_idx + 1) % 500 == 0:
                                logger.info(f"  - Current ZIP: Processed {f_idx + 1}/{len(extracted_in_this_zip)} files...")

                except Exception as e:
                    logger.error(f"Failed to process ZIP {zip_file}: {e}")

        # Process loose files
        if loose_files:
            logger.info(f"Processing {len(loose_files)} loose files...")
            for idx, f in enumerate(loose_files):
                if process_single_file(f, output_dir, config):
                    total_processed += 1
                
                if (idx + 1) % 500 == 0:
                    logger.info(f"  - Loose files: Processed {idx + 1}/{len(loose_files)} files...")

    logger.info(f"Processing complete. Total files saved/converted: {total_processed}")

if __name__ == "__main__":
    main()
