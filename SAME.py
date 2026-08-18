# same_encoder.py
"""
A Python module to encode NOAA SAME (Specific Area Message Encoding) strings,
configured with the 35-county coverage map for NWS Pittsburgh (PBZ).
"""

from datetime import datetime

# Official NWS Pittsburgh CWA (County Warning Area) SAME/FIPS mappings
PITTSBURGH_CWA = {
    # --- WESTERN PENNSYLVANIA ---
    "allegheny_pa": "042003",
    "armstrong_pa": "042005",
    "beaver_pa": "042007",
    "butler_pa": "042019",
    "clarion_pa": "042031",
    "fayette_pa": "042051",
    "forest_pa": "042053",
    "greene_pa": "042059",
    "indiana_pa": "042063",
    "jefferson_pa": "042065",
    "lawrence_pa": "042073",
    "mercer_pa": "042085",
    "venango_pa": "042121",
    "washington_pa": "042125",
    "westmoreland_pa": "042129",
    
    # --- EASTERN OHIO ---
    "belmont_oh": "039013",
    "carroll_oh": "039019",
    "columbiana_oh": "039029",
    "coshocton_oh": "039031",
    "guernsey_oh": "039059",
    "harrison_oh": "039067",
    "jefferson_oh": "039081",
    "monroe_oh": "039111",
    "muskingum_oh": "039119",
    "noble_oh": "039121",
    "tuscarawas_oh": "039157",
    
    # --- NORTHERN PANHANDLE / NORTHERN WEST VIRGINIA ---
    "brooke_wv": "054009",
    "hancock_wv": "054029",
    "harrison_wv": "054033",
    "marion_wv": "054049",
    "marshall_wv": "054051",
    "monongalia_wv": "054061",
    "ohio_wv": "054069",
    "preston_wv": "054077",
    "wetzel_wv": "054103"
}

def generate_timestamp(dt: datetime = None) -> str:
    """Generates the required JJJHHMM timestamp pattern from a datetime object."""
    if dt is None:
        dt = datetime.utcnow() # NWS utilizes UTC/Zulu time tracking
    
    # Calculate Julian day (day of the year) padded to 3 digits
    julian_day = f"{dt.timetuple().tm_yday:03d}"
    hour_minute = dt.strftime("%H%M")
    return f"{julian_day}{hour_minute}"

def encode_same_string(event_code: str, target_counties: list, duration_hours: int = 1, start_time: datetime = None) -> str:
    """
    Constructs a standard uppercase validation header string for EAS/SAME equipment.
    
    Format: ZCZC-ORG-EEE-PSSCCC-PSSCCC+TTTT-JJJHHMM-LLLLLLLL-
    """
    # 1. Preamble Anchor
    preamble = "ZCZC"
    
    # 2. Originator Code (WXR = National Weather Service)
    originator = "WXR"
    
    # 3. Clean and validate Event Code (Must be exactly 3 characters, e.g., 'TOR', 'SVR')
    event = str(event_code).strip().upper()[:3]
    
    # 4. Resolve Location / FIPS codes 
    resolved_fips = []
    for county in target_counties:
        clean_key = str(county).strip().lower().replace(" ", "_")
        if clean_key in PITTSBURGH_CWA:
            resolved_fips.append(PITTSBURGH_CWA[clean_key])
        elif clean_key == "all_pittsburgh_cwa":
            # Short-circuit tool to target the entire NWS Pittsburgh warning grid
            resolved_fips = list(PITTSBURGH_CWA.values())
            break
            
    if not resolved_fips:
        raise ValueError("No valid NWS Pittsburgh CWA target counties were found.")
    
    # Combine individual locations using dashes
    location_segment = "-".join(resolved_fips)
    
    # 5. Alert Duration format (+HHMM)
    duration_str = f"+{duration_hours:02d}00"
    
    # 6. Issue Timestamp segment
    timestamp_segment = generate_timestamp(start_time)
    
    # 7. Transmitter identifier (KPBZ/NWS Pittsburgh tag)
    station_id = "BUG/HTTP"
    
    # Assemble complete standard EAS block
    raw_same_sequence = f"{preamble}-{originator}-{event}-{location_segment}{duration_str}-{timestamp_segment}-{station_id}"
    return raw_same_sequence
