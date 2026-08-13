import tkinter as tk
from tkinter import ttk, messagebox
import datetime
# --- CUSTOM & ALL OPERATIONAL FCC/NOAA SAME CODES ---
ORIGINATORS = ["CRS", "DAV", "BUG", "WXR", "CIV", "EAS", "PEP"]

EVENT_CODES = {
    # Custom Household Micronation Protocols
    "INT": "INT (Internal Test)",
    "CVW": "CVW (Cat Vomit Warning ) ",
    "ICW": "ICW (Ice Cream Warning - TRUCK ONLY ) ",
    "ICA": "ICA (Ice Cream Watch  -  TRUCK ONLY ) ",
    "AZW": "AZW (Package Warning ) ",
    "AZA": "AZA (Package Watch ) ",
    "SHA": "SHA (Shovel Watch ) ",
    "SHW": "SHW (Shovel Warning ) ",
    "BSI": "BSI (Basement Storage Immediate ) ",
    "PCW": "PCW (Park Car Warning - Garage ) ",
    "ETH": "ETH (Ethernet Warning)",
    "BUG": "BUG (BugAlert)",
    
    # Official FCC / NOAA SAME Operational Event Codes
    "ADR": "ADR (Administrative Message ) ",
    "BLW": "BLW (Blizzard Warning ) ",
    "BHW": "BHW (Biological Hazard Warning ) ",
    "BHA": "BHA (Biological Hazard Watch ) ",
    "BHE": "BHE (Biological Hazard Emergency ) ",
    "CAE": "CAE (Child Abduction Emergency / AMBER Alert ) ",
    "CDW": "CDW (Civil Danger Warning ) ",
    "CEM": "CEM (Civil Emergency Message ) ",
    "CFA": "CFA (Coastal Flood Watch ) ",
    "CFW": "CFW (Coastal Flood Warning ) ",
    "CHW": "CHW (Chemical Hazard Warning ) ",
    "CHA": "CHA (Chemical Hazard Watch ) ",
    "CHE": "CHE (Chemical Hazard Emergency ) ",
    "DMO": "DMO (Practice / Demo Warning ) ",
    "DSW": "DSW (Dust Storm Warning ) ",
    "EAN": "EAN (National Emergency Message ) ",
    "EAT": "EAT (Emergency Action Termination ) ",
    "EQW": "EQW (Earthquake Warning ) ",
    "EVI": "EVI (Evacuation Immediate ) ",
    "EWW": "EWW (Extreme Wind Warning ) ",
    "FFA": "FFA (Flash Flood Watch ) ",
    "FFW": "FFW (Flash Flood Warning ) ",
    "FFS": "FFS (Flash Flood Statement ) ",
    "FLA": "FLA (Flood Watch ) ",
    "FLW": "FLW (Flood Warning ) ",
    "FLS": "FLS (Flood Statement ) ",
    "FRW": "FRW (Fire Warning ) ",
    "FSW": "FSW (Flash Freeze Warning ) ",
    "FZW": "FZW (Freeze Warning ) ",
    "HLS": "HLS (Hurricane Statement ) ",
    "HMW": "HMW (Hazardous Materials Warning ) ",
    "HMA": "HMA (Hazardous Materials Watch ) ",
    "HME": "HME (Hazardous Materials Emergency ) ",
    "HUA": "HUA (Hurricane Watch ) ",
    "HUW": "HUW (Hurricane Warning ) ",
    "HUR": "HUR (Hurricane Press Release ) ",
    "LAE": "LAE (Local Area Emergency ) ",
    "LEW": "LEW (Law Enforcement Warning ) ",
    "MAV": "MAV (Marine Advisory ) ",
    "MAR": "MAR (Marine Press Release ) ",
    "MHW": "MHW (Marine Hazard Warning ) ",
    "MHA": "MHA (Marine Hazard Watch ) ",
    "NAT": "NAT (National Periodic Test ) ",
    "NIC": "NIC (National Information Center ) ",
    "NPT": "NPT (National Periodic Test ) ",
    "NST": "NST (National Silent Test ) ",
    "NUW": "NUW (Nuclear Power Plant Warning ) ",
    "NUA": "NUA (Nuclear Power Plant Watch ) ",
    "NUE": "NUE (Nuclear Power Plant Emergency ) ",
    "OEP": "OEP (Operational Emergency Message ) ",
    "RHW": "RHW (Radiological Hazard Warning ) ",
    "RHA": "RHA (Radiological Hazard Watch ) ",
    "RHE": "RHE (Radiological Hazard Emergency ) ",
    "RMT": "RMT (Required Monthly Test ) ",
    "RWT": "RWT (Required Weekly Test ) ",
    "SMW": "SMW (Special Marine Warning ) ",
    "SPS": "SPS (Special Weather Statement ) ",
    "SPW": "SPW (Shelter in Place Warning ) ",
    "SSA": "SSA (Storm Surge Watch ) ",
    "SSW": "SSW (Storm Surge Warning ) ",
    "SVA": "SVA (Severe Thunderstorm Watch ) ",
    "SVR": "SVR (Severe Thunderstorm Warning ) ",
    "SVS": "SVS (Severe Weather Statement ) ",
    "TOA": "TOA (Tornado Watch ) ",
    "TOR": "TOR (Tornado Warning ) ",
    "TRA": "TRA (Tropical Storm Watch ) ",
    "TRW": "TRW (Tropical Storm Warning ) ",
    "TSA": "TSA (Tsunami Watch ) ",
    "TSW": "TSW (Tsunami Warning ) ",
    "VOW": "VOW (Volcano Warning ) ",
    "VOA": "VOA (Volcano Watch ) ",
    "VOE": "VOE (Volcano Emergency ) ",
    "WSA": "WSA (Winter Storm Watch ) ",
    "WSW": "WSW (Winter Storm Warning ) "
}

ZONES = {
    # Macro Layout
    "00": "00 (Full Basement/Garage ) ", "01": "01 (Full First Floor ) ", "02": "02 (Full Second Floor ) ",
    "03": "03 (Full Attic Crawlspace ) ", "04": "04 (Entire House ) ", "05": "05 (Full Back Yard/Deck ) ",
    "06": "06 (Full Front/Side Lawn ) ",
    # Subterranean Sectors
    "40": "40 (Garage ) ", "41": "41 (Basement Main ) ", "42": "42 (Pittsburgh Potty ) ",
    "43": "43 (Storage/Wind Shelter ) ", "44": "44 (Staircase Landing ) ", "45": "45 (Under Staircase ) ",
    "46": "46 (Lower Basement Stairs ) ",
    # Main Operations Hub (First Floor)
    "10": "10 (Top Basement Stairs ) ", "11": "11 (Kitchen ) ", "12": "12 (Dining Room ) ",
    "13": "13 (Dining/Living Border ) ", "14": "14 (Living Room ) ", "15": "15 (Entranceway ) ",
    "16": "16 (Back Sliding Door ) ", "17": "17 (Catio ) ", "18": "18 (2nd Floor Landing ) ",
    "19": "19 (Bottom 2nd Floor Stairs ) ",
    # High Council Quarters (Second Floor)
    "20": "20 (Top 2nd Floor Stairs ) ", "21": "21 (Landing/Litter Box ) ", "22": "22 (Central Hallway ) ",
    "23": "23 (Upstairs Bathroom ) ", "24": "24 (Dads Room ) ", "25": "25 (Mums Room ) ",
    "26": "26 (My Room ) ", "27": "27 (Banister Reach Zone ) ", "28": "28 (Shower Sector ) ",
    "29": "29 (Test Sector ) ",
    # Perimeter Outposts (Backyard & Deck)
    "50": "50 (The Deck ) ", "51": "51 (Deck Staircase ) ", "52": "52 (The Patio ) ",
    "53": "53 (Patio/Garden Strip ) ", "54": "54 (Wildflower Garden ) ", "55": "55 (Side Strip Back ) ",
    "56": "56 (Side Strip Front/Grass ) ", "57": "57 (Driveway ) ", "58": "58 (Driveway Landing ) ",
    "59": "59 (East Fence Plants ) ",
    # Outer Border Infrastructure (Front & Streets - Meme Protection Active)
    "60": "60 (Front Porch ) ", "61": "61 (Front West Lawn ) ", "62": "62 (Front East Lawn ) ",
    "63": "63 (Front Walkway ) ", "64": "64 (Public Sidewalk ) ", "65": "65 (Oglethorpe Ave ) ",
    "66": "66 (Antoinette St ) ", "68": "68 (Retaining Wall ) ", "70": "70 (Side Lawn ) ",
    "71": "71 (All 3 Lawns Combined ) ", "72": "72 (All Walkways/Streets ) "
}

def generate_purge ( ) :
    try:
        r_iss = combo_iss.get ( )
        # Splits on whitespace and grabs the dictionary key directly
        selected_text = combo_al.get ( )
        r_al = selected_text.split ( " " ) [0]
        
        r_tm = entry_tm.get ( ) .strip ( ) .upper ( )
        r_dt = entry_dt.get ( ) .strip ( )
        
        chks = sorted ( [int ( k) for k, v in zone_vars.items ( ) if v.get ( ) ])
        
        if not chks or not r_iss or not r_al or not r_tm or not r_dt:
            return messagebox.showerror ( "Error", "Missing fields or no zones selected!")
        
        # Span optimization loop
        spans, start, prev = [], chks[0], chks[0]
        for c in chks[1:]:
            if c == prev + 1:
                prev = c
            else:
                spans.append ( ( start, prev ) )
                start = prev = c
        spans.append ( ( start, prev ) )
        
        out = ""
        for s, e in spans:
            if s == e:
                out += f"+{s:02d}"
            else:
                out += f"+{s:02d}/{e:02d}"
            
        output_text.delete ( "1.0", tk.END)
        output_text.insert ( tk.END, f"OGZC-{r_iss}-{r_al}-{r_tm}-{r_dt}{out}")
    except Exception as e:
        messagebox.showerror ( "Error", str ( e ) )

# --- UI STRUCTURAL GRID SETUP ---
root = tk.Tk ( )
root.title ( "OAME Mini v4 - Oglethorpe Alert Message Encoding Encoder")
root.geometry ( "650x550")

# Top Telecom Configuration Panel
f_top = ttk.LabelFrame ( root, text=" Telecommunications Protocol Configuration ", padding=5)
f_top.pack ( fill=tk.X, padx=10, pady=5)

combo_iss = ttk.Combobox ( f_top, values=ORIGINATORS, width=7, state="readonly")
combo_iss.pack ( side=tk.LEFT, padx=5 ) ; combo_iss.set ( "EAS")

# Alphabetically sorts the massive array of emergency codes
sorted_events = [EVENT_CODES[k] for k in sorted ( EVENT_CODES.keys ( ) ) ]
combo_al = ttk.Combobox ( f_top, values=sorted_events, width=38, state="readonly")
combo_al.pack ( side=tk.LEFT, padx=5 ) ; combo_al.set ( "INT (Internal Test)")


# 1. Fetch system clock 
now = datetime.datetime.now()

# 2. Check midnight boundary condition (between 23:46 and 23:59)
if now.hour == 23 and now.minute >= 46:
    target_date = now + datetime.timedelta(days=1)
else:
    target_date = now

# 3. Calculate next 15-minute interval for TM
minutes_to_add = 15 - (now.minute % 15)
if minutes_to_add == 15 and now.second == 0:
    minutes_to_add = 0
next_15 = now + datetime.timedelta(minutes=minutes_to_add)

# 4. Format strings
formatted_tm = next_15.strftime("%H%M+0000")
formatted_dt = target_date.strftime("%m%d")

# 5. Build and inject entry TM
entry_tm = ttk.Entry(f_top, width=12)
entry_tm.pack(side=tk.LEFT, padx=5)
entry_tm.insert(0, formatted_tm)

# 6. Build and inject entry DT
entry_dt = ttk.Entry(f_top, width=6)
entry_dt.pack(side=tk.LEFT, padx=5)
entry_dt.insert(0, formatted_dt)
# Scrollable Center Panel for Sector Targeting
f_middle = ttk.LabelFrame ( root, text=" Targeted Micronation Grid Sectors ", padding=5)
f_middle.pack ( fill=tk.BOTH, expand=True, padx=10, pady=5)

canvas = tk.Canvas ( f_middle, borderwidth=0, highlightthickness=0)
scrollbar = ttk.Scrollbar ( f_middle, orient="vertical", command=canvas.yview)
scroll_frame = ttk.Frame ( canvas)

scroll_frame.bind ( "<Configure>", lambda e: canvas.configure ( scrollregion=canvas.bbox ( "all" ) ) )
canvas.create_window ( ( 0, 0 ) , window=scroll_frame, anchor="nw")
canvas.configure ( yscrollcommand=scrollbar.set)

canvas.pack ( side="left", fill="both", expand=True)
scrollbar.pack ( side="right", fill="y")

# Renders the 52 distinct zones across the domestic map
zone_vars = {}
sorted_keys = sorted ( ZONES.keys ( ) , key=lambda x: int ( x ) )

for idx, key in enumerate ( sorted_keys ) :
    zone_vars[key] = tk.BooleanVar ( )
    r, c = idx // 2, idx % 2 # Double-column tactical arrangement
    cb = ttk.Checkbutton ( scroll_frame, text=ZONES[key], variable=zone_vars[key])
    cb.grid ( row=r, column=c, sticky=tk.W, padx=10, pady=2)

# Action Compile Button
ttk.Button ( root, text="⚡ TRANSMIT PACKET BURST", command=generate_purge ) .pack ( pady=5)

# High-Visibility Output Terminus
output_text = tk.Text ( root, height=2, width=70, font= ( "Courier", 11, "bold" ) , fg="#00FF00", bg="#111111")
output_text.pack ( padx=10, pady=10)

root.mainloop ( )