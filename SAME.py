# same_encoder.py
"""
A Python module to encode NOAA SAME (Specific Area Message Encoding) strings,
configured with the 35-county coverage map for NWS Pittsburgh (PBZ).
"""

from datetime import datetime

# Full official SAME event code catalog. This keeps the app from guessing at event names.
OFFICIAL_EVENT_CODES = {
    "ADR": "Administrative Message",
    "AVW": "Avalanche Warning",
    "BZW": "Blizzard Warning",
    "BHW": "Biological Hazard Warning",
    "BHA": "Biological Hazard Watch",
    "BHE": "Biological Hazard Emergency",
    "CAE": "Child Abduction Emergency",
    "CDW": "Civil Danger Warning",
    "CEM": "Civil Emergency Message",
    "CFA": "Coastal Flood Watch",
    "CFW": "Coastal Flood Warning",
    "CHW": "Chemical Hazard Warning",
    "CHA": "Chemical Hazard Watch",
    "CHE": "Chemical Hazard Emergency",
    "DMO": "Practice/Demo Warning",
    "DSW": "Dust Storm Warning",
    "EAN": "National Emergency Message",
    "EAT": "Emergency Action Termination",
    "EQW": "Earthquake Warning",
    "EVI": "Evacuation Immediate",
    "EWW": "Extreme Wind Warning",
    "FFA": "Flash Flood Watch",
    "FFW": "Flash Flood Warning",
    "FFS": "Flash Flood Statement",
    "FLA": "Flood Watch",
    "FLW": "Flood Warning",
    "FLS": "Flood Statement",
    "FRW": "Fire Warning",
    "FSW": "Flash Freeze Warning",
    "FZW": "Freeze Warning",
    "HLS": "Hurricane Statement",
    "HMW": "Hazardous Materials Warning",
    "HMA": "Hazardous Materials Watch",
    "HME": "Hazardous Materials Emergency",
    "HUA": "Hurricane Watch",
    "HUW": "Hurricane Warning",
    "HUR": "Hurricane Press Release",
    "LAE": "Local Area Emergency",
    "LEW": "Law Enforcement Warning",
    "MAV": "Marine Advisory",
    "MAR": "Marine Press Release",
    "MHW": "Marine Hazard Warning",
    "MHA": "Marine Hazard Watch",
    "NAT": "National Periodic Test",
    "NIC": "National Information Center",
    "NPT": "National Periodic Test",
    "NST": "National Silent Test",
    "NUW": "Nuclear Power Plant Warning",
    "NUA": "Nuclear Power Plant Watch",
    "NUE": "Nuclear Power Plant Emergency",
    "OEP": "Operational Emergency Message",
    "RHW": "Radiological Hazard Warning",
    "RHA": "Radiological Hazard Watch",
    "RHE": "Radiological Hazard Emergency",
    "RMT": "Required Monthly Test",
    "RWT": "Required Weekly Test",
    "SMW": "Special Marine Warning",
    "SPS": "Special Weather Statement",
    "SPW": "Shelter in Place Warning",
    "SSA": "Storm Surge Watch",
    "SSW": "Storm Surge Warning",
    "SVA": "Severe Thunderstorm Watch",
    "SVR": "Severe Thunderstorm Warning",
    "SVS": "Severe Weather Statement",
    "TOA": "Tornado Watch",
    "TOR": "Tornado Warning",
    "TRA": "Tropical Storm Watch",
    "TRW": "Tropical Storm Warning",
    "TSA": "Tsunami Watch",
    "TSW": "Tsunami Warning",
    "VOW": "Volcano Warning",
    "VOA": "Volcano Watch",
    "VOE": "Volcano Emergency",
    "WSA": "Winter Storm Watch",
    "WSW": "Winter Storm Warning",
    "PNS": "Public Safety Statement",
    "CWW": "Civil Weather Warning",
    "EAN": "Emergency Action Notification",
    "WSA": "Winter Storm Watch",
    "WSW": "Winter Storm Warning",
}

# Common NOAA SAME event-code aliases used by NWS alert feeds.
EVENT_CODE_ALIASES = {
    "TORNADO WARNING": "TOR",
    "TORNADO WATCH": "TOA",
    "SEVERE THUNDERSTORM WARNING": "SVR",
    "SEVERE THUNDERSTORM WATCH": "SVA",
    "FLASH FLOOD WARNING": "FFW",
    "FLASH FLOOD WATCH": "FFA",
    "FLOOD WARNING": "FLW",
    "FLOOD WATCH": "FLA",
    "WINTER STORM WARNING": "WSW",
    "WINTER STORM WATCH": "WSA",
    "HIGH WIND WARNING": "HWW",
    "HIGH WIND WATCH": "HWA",
    "MARINE WARNING": "MWW",
    "MARINE WATCH": "MWW",
    "SEVERE WEATHER STATEMENT": "SVS",
    "SPECIAL WEATHER STATEMENT": "SPS",
    "PUBLIC SAFETY STATEMENT": "PNS",
    "ADMINISTRATIVE MESSAGE": "ADR",
    "TEST": "RWT",
    "NATIONAL PERIODIC TEST": "NPT",
    "LOCAL AREA EMERGENCY": "LAE",
    "RADIATION WARNING": "RHW",
    "RADIATION WATCH": "RHA",
}

ALL_EVENT_CODES = {**OFFICIAL_EVENT_CODES, **{k: v for k, v in EVENT_CODE_ALIASES.items() if len(k) > 3}}

# Common shorthand aliases for the most useful SAME/FIPS codes.
COUNTY_FIPS_SHORTCUTS = {
    "042003": "042003",
    "allegheny": "042003",
    "pgh": "042003",
    "pbz": "042003",
    "000000": "000000",
    "all": "000000",
    "all_counties": "000000",
    "all_pa": "000000",
    "042000": "042000",
    "cwa": "042000",
    "pgh_cwa": "042000",
    "all_pittsburgh_cwa": "042000",
    "all_cwa": "042000",
}

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

def normalize_event_code(event_code: str) -> str:
    """Map common alert names to valid 3-character SAME event codes."""
    if event_code is None:
        raise ValueError("Event code is required.")

    text = str(event_code).strip().upper()
    if len(text) == 3 and text.isalpha():
        return text

    # Prefer an exact official SAME alias match before falling back to the first 3 chars.
    lookup = " ".join(ch for ch in text if ch.isalnum() or ch == " ").upper().strip()
    if lookup in EVENT_CODE_ALIASES:
        return EVENT_CODE_ALIASES[lookup]

    compact = "".join(ch for ch in text if ch.isalnum()).upper()
    for alias, code in EVENT_CODE_ALIASES.items():
        if "".join(ch for ch in alias if ch.isalnum()).upper() == compact:
            return code

    return text[:3]


def resolve_county_fips(county_value: str) -> str:
    """Resolve a county input into a SAME/FIPS code, accepting direct FIPS values and common shortcuts."""
    if county_value is None:
        raise ValueError("County/FIPS value is required.")

    text = str(county_value).strip().lower().replace(" ", "_")
    if not text:
        raise ValueError("County/FIPS value is required.")

    if text in COUNTY_FIPS_SHORTCUTS:
        return COUNTY_FIPS_SHORTCUTS[text]

    if text in PITTSBURGH_CWA:
        return PITTSBURGH_CWA[text]

    if text.isdigit() and len(text) == 6:
        return text

    if text in {"all_pittsburgh_cwa", "all_cwa", "pgh_cwa", "cwa"}:
        return "042000"

    if text in {"all", "all_counties", "all_pa"}:
        return "000000"

    raise ValueError(f"Unknown county/FIPS shortcut or code: {county_value}")


def encode_same_string(event_code: str, target_counties: list, duration_hours: int = 1, start_time: datetime = None, originator: str = "WXR", station_id: str = "KPBZ", duration_hhmm: str = None) -> str:
    """
    Constructs a standard uppercase validation header string for EAS/SAME equipment.

    Format: ZCZC-ORG-EEE-PSSCCC-PSSCCC+TTTT-JJJHHMM-LLLLLLLL-
    where TTTT is a 4-digit HHMM duration field in the SAME header.
    """
    preamble = "ZCZC"
    originator = str(originator or "WXR").strip().upper()[:3]
    event = normalize_event_code(event_code)

    resolved_fips = []
    seen = set()
    for county in target_counties:
        resolved = resolve_county_fips(county)
        if resolved not in seen:
            resolved_fips.append(resolved)
            seen.add(resolved)

    if not resolved_fips:
        raise ValueError("No valid SAME/FIPS target counties were found.")

    if duration_hhmm is not None:
        hhmm = str(duration_hhmm).strip()
    else:
        hhmm = f"{int(duration_hours):02d}00"

    if len(hhmm) != 4 or not hhmm.isdigit():
        raise ValueError("Duration must be a 4-digit HHMM value, such as 0100 or 0230.")

    location_segment = "-".join(resolved_fips)
    duration_str = f"+{hhmm}"
    timestamp_segment = generate_timestamp(start_time)

    station_id = str(station_id or "KPBZ").strip().upper()[:8].ljust(8, "X")
    raw_same_sequence = f"{preamble}-{originator}-{event}-{location_segment}{duration_str}-{timestamp_segment}-{station_id}-"
    return raw_same_sequence


if __name__ == "__main__":
    import tkinter as tk
    from tkinter import ttk, messagebox

    def build_event_menu_options():
        options = []
        for code, label in sorted(ALL_EVENT_CODES.items()):
            options.append(f"{code} - {label}")
        return options

    root = tk.Tk()
    root.title("SAME Header Generator")
    root.geometry("780x520")
    root.minsize(700, 420)

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Event code:").pack(anchor=tk.W)
    event_var = tk.StringVar()
    event_combo = ttk.Combobox(frame, textvariable=event_var, values=build_event_menu_options(), state="readonly", width=70)
    event_combo.pack(fill=tk.X, pady=(0, 10))
    event_combo.set("ADR - Administrative Message")

    ttk.Label(frame, text="County keys (comma-separated):").pack(anchor=tk.W)
    county_entry = ttk.Entry(frame, width=70)
    county_entry.insert(0, "allegheny_pa")
    county_entry.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text="Duration (HHMM):").pack(anchor=tk.W)
    duration_entry = ttk.Entry(frame, width=20)
    duration_entry.insert(0, "0100")
    duration_entry.pack(anchor=tk.W, pady=(0, 10))

    ttk.Label(frame, text="Originator (3 chars):").pack(anchor=tk.W)
    originator_entry = ttk.Entry(frame, width=20)
    originator_entry.insert(0, "WXR")
    originator_entry.pack(anchor=tk.W, pady=(0, 10))

    ttk.Label(frame, text="Station ID (up to 8 chars):").pack(anchor=tk.W)
    station_entry = ttk.Entry(frame, width=20)
    station_entry.insert(0, "KPBZ")
    station_entry.pack(anchor=tk.W, pady=(0, 10))

    ttk.Label(frame, text="Generated SAME header:").pack(anchor=tk.W)
    output = tk.Text(frame, height=10, width=90, font=("Courier", 10), wrap="none")
    output.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    def generate():
        try:
            codestr = event_var.get().split(" - ", 1)[0].strip()
            counties = [c.strip().lower() for c in county_entry.get().split(",") if c.strip()]
            duration_text = (duration_entry.get() or "0100").strip()
            originator = originator_entry.get().strip() or "WXR"
            station = station_entry.get().strip() or "KPBZ"
            if not counties:
                raise ValueError("At least one county key is required.")
            output.delete("1.0", tk.END)
            output.insert("1.0", encode_same_string(codestr, counties, duration_hhmm=duration_text, originator=originator, station_id=station))
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    ttk.Button(frame, text="Generate SAME Header", command=generate).pack(fill=tk.X)
    root.mainloop()
