# # data/log_parsers/EVTX/log_parsers_evtx.py

import re
from datetime import datetime
import logging
import lxml.etree as ET  # using lxml for XML parsing
import json

from evtx import PyEvtxParser  # pylint: disable=no-name-in-module # type: ignore # Rust-based parser

logger = logging.getLogger("LogParsersEVTX") #pylint: disable=no-member
logger.setLevel(logging.DEBUG) #pylint: disable=no-member
# NEW: Regex to find "returns an answer after :XXXX ms"
DURATION_PATTERN = re.compile(r"(\d+)\s*ms", re.IGNORECASE)

def parse_evtx_log(filepath):
    logger.info(f"Starting EVTX log parsing for file: {filepath}")
    rows = []
    min_time = None
    max_time = None

    try:
        parser = PyEvtxParser(filepath)
        record_count = 0
        for record in parser.records():
            record_count += 1
            if record_count % 1000 == 0:
                logger.info(f"Parsing record number: {record_count}")
            try:
                xml = record["data"]
                event = parse_evtx_record_xml(xml)
                if event:
                    rows.append(event)
                    ts_epoch = event.get("timestamp_epoch")
                    if ts_epoch:
                        if (min_time is None) or (ts_epoch < min_time):
                            min_time = ts_epoch
                            logger.debug(f"Updated min_time to: {min_time}")
                        if (max_time is None) or (ts_epoch > max_time):
                            max_time = ts_epoch
                            logger.debug(f"Updated max_time to: {max_time}")
            except Exception as e:
                logger.warning(f"Failed to parse a record at record {record_count}: {e}")
        logger.info(f"Completed parsing EVTX file: {filepath}. Total records parsed: {record_count}")
    except Exception as e:
        logger.error(f"Error opening or parsing EVTX '{filepath}': {e}")
    logger.info(f"Parsed {len(rows)} rows from EVTX log '{filepath}'.")
    return rows, min_time, max_time

def parse_evtx_record_xml(xml_str):
    """
    Parses the XML string of an EVTX record and extracts fields.
    It extracts the System fields (including TimeCreated) and then scans the EventData section.
    In EventData, it looks for a duration (using DURATION_PATTERN) and—if no system timestamp was found—
    it also looks for an ISO 8601 timestamp using TIMESTAMP_PATTERN.
    """
    try:
        # Ensure XML declaration exists
        if not xml_str.lstrip().startswith("<?xml"):
            xml_str = '<?xml version="1.0" encoding="utf-8"?>\n' + xml_str

        root = ET.fromstring(xml_str.encode("utf-8"))

        ns = "{http://schemas.microsoft.com/win/2004/08/events/event}"
        event = {}

        # 1. System section: extract default fields and try to get the timestamp
        system = root.find(ns + "System")
        if system is not None:
            event["EventID"] = system.findtext(ns + "EventID", "Unknown")
            event["RecordNumber"] = system.findtext(ns + "EventRecordID", "")
            time_elem = system.find(ns + "TimeCreated")
            time_str = time_elem.get("SystemTime") if time_elem is not None else ""
            event["timestamp_epoch"] = parse_timestamp(time_str)
            event["timestamp"] = time_str
            provider_elem = system.find(ns + "Provider")
            event["ProviderName"] = provider_elem.get("Name") if provider_elem is not None else "Unknown"
            event["Level"] = system.findtext(ns + "Level", "Unknown")
            event["Channel"] = system.findtext(ns + "Channel", "Unknown")
            event["Computer"] = system.findtext(ns + "Computer", "Unknown")

        # 2. EventData section
        event_data = {}
        data_texts = []
        event_data_elem = root.find(ns + "EventData")

        # We'll store a "time_taken" field (duration) if found
        time_taken_val = None

        # New: Regex to detect ISO timestamps (e.g., 2025-03-09T07:31:54 or with fractional seconds)
        TIMESTAMP_PATTERN = re.compile(
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)'
        )

        if event_data_elem is not None:
            for data in event_data_elem.findall(ns + "Data"):
                name = data.get("Name", "Unnamed")
                value = " ".join(data.itertext()).strip()
                key = re.sub(r'\W+', '_', name)
                event_data[key] = value

                if value:
                    data_texts.append(value)

                    # Check for a duration value (using your existing DURATION_PATTERN)
                    match = DURATION_PATTERN.search(value)
                    if match and time_taken_val is None:
                        try:
                            duration_ms = int(match.group(1))
                            time_taken_val = duration_ms
                        except ValueError:
                            pass

                    # If no system timestamp was set, try to find one in the event data text.
                    if event.get("timestamp_epoch") is None:
                        ts_match = TIMESTAMP_PATTERN.search(value)
                        if ts_match:
                            ts_str = ts_match.group(1)
                            try:
                                # Using fromisoformat (adjust "Z" if needed)
                                ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                                event["timestamp_epoch"] = ts_dt.timestamp()
                                event["timestamp"] = ts_str
                            except Exception:
                                pass

        # Save the EventData dictionary as JSON (for later display/analytics)
        event["EventData"] = json.dumps(event_data)
        event["EventData_display"] = "\n".join(data_texts)

        if time_taken_val is not None:
            event["time_taken"] = time_taken_val

        # Optionally store the raw XML if needed
        event["raw_xml"] = xml_str

        return event

    except ET.XMLSyntaxError as pe:
        logger.error(f"XML parsing error: {pe}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during XML parsing: {e}")
        return None


def parse_timestamp(time_str):
    if not time_str or len(time_str) < 23:
        return None
    try:
        return datetime(
            int(time_str[0:4]),
            int(time_str[5:7]),
            int(time_str[8:10]),
            int(time_str[11:13]),
            int(time_str[14:16]),
            int(time_str[17:19]),
            int(time_str[20:23]) * 1000
        ).timestamp()
    except Exception:
        return None
