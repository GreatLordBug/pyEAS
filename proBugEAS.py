import tkinter as tk
from tkinter import ttk, messagebox
import queue
import threading
import subprocess
import os
import time
from pathlib import Path
import numpy as np
import soundfile as sf
import sounddevice as sd
import requests
import SAME
import OAME

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

# --- Constants ---
SAMPLE_RATE = 44100       
BAUD_RATE = 520.8333        
FREQ_MARK, FREQ_SPACE = 2083.33, 1562.50        
PREAMBLE_BITS = 128         
SAMPLES_PER_BIT = int(SAMPLE_RATE / BAUD_RATE)
CHUNKS_PER_BUFFER = 1024 

# FIPS/SAME Target Zones
TARGET_ZONES = {"042003", "142003", "242003", "342003", "442003", "542003", "642003", "742003", "842003", "942003", "000000", "042000"}
CONFIG_PATH = Path(__file__).with_name("config.toml")

DEFAULT_CONFIG = {
    "app": {
        "header": "OGZC-CRS-ADR-0000+0100-0101+00",
        "footer": "NNNN",
        "tone_seconds": 8.0,
        "siren_placement": "attached",
        "siren_goarounds": 16,
        "siren_length": 4,
        "use_file": False,
        "use_siren": True,
        "potato_siren": False,
        "external_target": "",
        "voice_text": "The National Weather Service has issued a severe statement.",
    },
    "same": {
        "event": "ADR - Administrative Message",
        "county_keys": ["allegheny_pa"],
        "duration": "0100",
        "originator": "WXR",
        "station_id": "KPBZ",
    },
    "auto": {
        "event_codes": ["TOR", "SVR", "FFW", "FLW", "WSW", "SVS"],
        "callsign": "WXR",
        "counties": ["042003", "000000", "042000"],
        "weather_text": True,
        "alert_text_template": "HAZ...{hazard} HAIL {hail} SRC...{source}",
    },
}


def _toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "\"\""
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return json_quote(value)


def json_quote(value):
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return '"' + escaped + '"'


def dump_toml(data, path):
    lines = []
    for section, section_values in data.items():
        lines.append(f"[{section}]")
        for key, value in section_values.items():
            if isinstance(value, dict):
                raise TypeError("Nested sections beyond one level are not supported.")
            if isinstance(value, list):
                rendered = ", ".join(_toml_value(v) for v in value)
                lines.append(f"{key} = [{rendered}]")
            else:
                lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def load_config(path=CONFIG_PATH):
    if not path.exists():
        dump_toml(DEFAULT_CONFIG, path)
        return DEFAULT_CONFIG.copy()
    try:
        with path.open("rb") as fh:
            loaded = tomllib.load(fh)
        merged = DEFAULT_CONFIG.copy()
        for top_key, top_value in loaded.items():
            if isinstance(top_value, dict):
                merged.setdefault(top_key, {})
                merged[top_key].update(top_value)
        return merged
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(data, path=CONFIG_PATH):
    dump_toml(data, path)


def apply_app_defaults(cfg):
    entry_header.delete(0, tk.END)
    entry_header.insert(0, cfg.get("app", {}).get("header", DEFAULT_CONFIG["app"]["header"]))
    entry_footer.delete(0, tk.END)
    entry_footer.insert(0, cfg.get("app", {}).get("footer", DEFAULT_CONFIG["app"]["footer"]))
    entry_tone_len.delete(0, tk.END)
    entry_tone_len.insert(0, str(cfg.get("app", {}).get("tone_seconds", DEFAULT_CONFIG["app"]["tone_seconds"])))
    siren_placement_var.set(cfg.get("app", {}).get("siren_placement", DEFAULT_CONFIG["app"]["siren_placement"]))
    entry_siren_goarounds.delete(0, tk.END)
    entry_siren_goarounds.insert(0, str(cfg.get("app", {}).get("siren_goarounds", DEFAULT_CONFIG["app"]["siren_goarounds"])))
    entry_siren_length.delete(0, tk.END)
    entry_siren_length.insert(0, str(cfg.get("app", {}).get("siren_length", DEFAULT_CONFIG["app"]["siren_length"])))
    var_use_file.set(bool(cfg.get("app", {}).get("use_file", DEFAULT_CONFIG["app"]["use_file"])))
    var_use_siren.set(bool(cfg.get("app", {}).get("use_siren", DEFAULT_CONFIG["app"]["use_siren"])))
    var_potato_siren.set(bool(cfg.get("app", {}).get("potato_siren", DEFAULT_CONFIG["app"]["potato_siren"])))
    entry_file_path.delete(0, tk.END)
    entry_file_path.insert(0, cfg.get("app", {}).get("external_target", DEFAULT_CONFIG["app"]["external_target"]))
    text_body.delete("1.0", tk.END)
    text_body.insert("1.0", cfg.get("app", {}).get("voice_text", DEFAULT_CONFIG["app"]["voice_text"]))
    same_county_entry.delete(0, tk.END)
    same_county_entry.insert(0, ", ".join(str(v) for v in cfg.get("same", {}).get("county_keys", DEFAULT_CONFIG["same"]["county_keys"])))
    same_duration_entry.delete(0, tk.END)
    same_duration_entry.insert(0, cfg.get("same", {}).get("duration", DEFAULT_CONFIG["same"]["duration"]))
    same_originator_entry.delete(0, tk.END)
    same_originator_entry.insert(0, cfg.get("same", {}).get("originator", DEFAULT_CONFIG["same"]["originator"]))
    same_station_entry.delete(0, tk.END)
    same_station_entry.insert(0, cfg.get("same", {}).get("station_id", DEFAULT_CONFIG["same"]["station_id"]))
    same_event_var.set(cfg.get("same", {}).get("event", DEFAULT_CONFIG["same"]["event"]))


def collect_current_config():
    return {
        "app": {
            "header": entry_header.get().strip() or DEFAULT_CONFIG["app"]["header"],
            "footer": entry_footer.get().strip() or DEFAULT_CONFIG["app"]["footer"],
            "tone_seconds": float(entry_tone_len.get() or DEFAULT_CONFIG["app"]["tone_seconds"]),
            "siren_placement": siren_placement_var.get() or DEFAULT_CONFIG["app"]["siren_placement"],
            "siren_goarounds": int(entry_siren_goarounds.get() or DEFAULT_CONFIG["app"]["siren_goarounds"]),
            "siren_length": int(entry_siren_length.get() or DEFAULT_CONFIG["app"]["siren_length"]),
            "use_file": bool(var_use_file.get()),
            "use_siren": bool(var_use_siren.get()),
            "potato_siren": bool(var_potato_siren.get()),
            "external_target": entry_file_path.get().strip(),
            "voice_text": text_body.get("1.0", tk.END).strip(),
        },
        "same": {
            "event": same_event_var.get() or DEFAULT_CONFIG["same"]["event"],
            "county_keys": [c.strip().lower() for c in same_county_entry.get().split(",") if c.strip()],
            "duration": (same_duration_entry.get() or DEFAULT_CONFIG["same"]["duration"]).strip(),
            "originator": (same_originator_entry.get() or DEFAULT_CONFIG["same"]["originator"]).strip(),
            "station_id": (same_station_entry.get() or DEFAULT_CONFIG["same"]["station_id"]).strip(),
        },
        "auto": {
            "event_codes": [c.strip().upper() for c in auto_event_codes_var.get().split(",") if c.strip()],
            "callsign": (auto_callsign_var.get() or DEFAULT_CONFIG["auto"]["callsign"]).strip().upper(),
            "counties": [c.strip() for c in auto_counties_var.get().split(",") if c.strip()],
            "weather_text": bool(auto_weather_text_var.get()),
            "alert_text_template": (auto_alert_template_var.get() or DEFAULT_CONFIG["auto"]["alert_text_template"]).strip(),
        },
    }


def _current_auto_config():
    cfg = load_config(CONFIG_PATH)
    return cfg.get("auto", DEFAULT_CONFIG["auto"])


def _parse_alert_text(event_name, headline, description, template=None):
    template = template or _current_auto_config().get("alert_text_template", DEFAULT_CONFIG["auto"]["alert_text_template"])
    text_blob = " ".join(part for part in [event_name, headline, description] if part)
    lower_text = text_blob.lower()

    if "severe thunderstorm" in lower_text:
        hazard_match = None
        for pattern in [r"(\d+)\s*mph", r"(\d+)\s*mi/h", r"(\d+)\s*mph\s*gusts"]:
            match = __import__('re').search(pattern, text_blob, __import__('re').IGNORECASE)
            if match:
                hazard_match = match.group(1) + "MPH"
                break
        hazard = hazard_match or "SEVERE THUNDERSTORM"
        hail = "0\"" if "no hail" in lower_text or "hail 0" in lower_text or "0\"" in text_blob else "OBSERVED"
        source = "OBSERVED" if "observed" in lower_text else "NWS"
    else:
        hazard = event_name.upper()
        hail = "0\"" if "no hail" in lower_text else "UNKNOWN"
        source = "OBSERVED" if "observed" in lower_text else "NWS"

    values = {
        "hazard": hazard,
        "hail": hail,
        "source": source,
        "event": event_name,
        "headline": headline,
        "description": description,
    }
    try:
        return template.format(**values)
    except Exception:
        return f"HAZ...{hazard} HAIL {hail} SRC...{source}"


def open_auto_config_window():
    win = tk.Toplevel(root)
    win.title("Auto Alert Configuration")
    win.geometry("640x420")
    win.minsize(560, 360)

    frame = ttk.Frame(win, padding=16)
    frame.pack(fill=tk.BOTH, expand=True)

    global auto_event_codes_var, auto_callsign_var, auto_counties_var, auto_weather_text_var, auto_alert_template_var
    auto_event_codes_var = tk.StringVar(value=", ".join(_current_auto_config().get("event_codes", DEFAULT_CONFIG["auto"]["event_codes"])))
    auto_callsign_var = tk.StringVar(value=_current_auto_config().get("callsign", DEFAULT_CONFIG["auto"]["callsign"]))
    auto_counties_var = tk.StringVar(value=", ".join(_current_auto_config().get("counties", DEFAULT_CONFIG["auto"]["counties"])))
    auto_weather_text_var = tk.BooleanVar(value=bool(_current_auto_config().get("weather_text", DEFAULT_CONFIG["auto"]["weather_text"])))
    auto_alert_template_var = tk.StringVar(value=_current_auto_config().get("alert_text_template", DEFAULT_CONFIG["auto"]["alert_text_template"]))

    ttk.Label(frame, text="Event codes to activate automatically:").pack(anchor=tk.W)
    ttk.Entry(frame, textvariable=auto_event_codes_var, width=80).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text="Callsign:").pack(anchor=tk.W)
    ttk.Entry(frame, textvariable=auto_callsign_var, width=30).pack(anchor=tk.W, pady=(0, 10))

    ttk.Label(frame, text="Counties/FIPS to activate for (comma-separated):").pack(anchor=tk.W)
    ttk.Entry(frame, textvariable=auto_counties_var, width=80).pack(fill=tk.X, pady=(0, 10))

    ttk.Checkbutton(frame, text="Participate in Alert Text section for valid alert types", variable=auto_weather_text_var).pack(anchor=tk.W, pady=(0, 10))

    ttk.Label(frame, text="Alert text template:").pack(anchor=tk.W)
    ttk.Entry(frame, textvariable=auto_alert_template_var, width=80).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text="Example: HAZ...{hazard} HAIL {hail} SRC...{source}", foreground="#666666").pack(anchor=tk.W)

    btns = ttk.Frame(frame)
    btns.pack(fill=tk.X, pady=(12, 0))

    def save_auto_cfg():
        try:
            cfg = {
                "auto": {
                    "event_codes": [c.strip().upper() for c in auto_event_codes_var.get().split(",") if c.strip()],
                    "callsign": (auto_callsign_var.get() or DEFAULT_CONFIG["auto"]["callsign"]).strip().upper(),
                    "counties": [c.strip() for c in auto_counties_var.get().split(",") if c.strip()],
                    "weather_text": bool(auto_weather_text_var.get()),
                    "alert_text_template": (auto_alert_template_var.get() or DEFAULT_CONFIG["auto"]["alert_text_template"]).strip(),
                }
            }
            existing = load_config(CONFIG_PATH)
            existing.update(cfg)
            save_config(existing, CONFIG_PATH)
            lbl_status.config(text="Auto alert config saved")
            win.destroy()
        except Exception as exc:
            messagebox.showerror("Config Error", str(exc))

    ttk.Button(btns, text="Save", command=save_auto_cfg).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side=tk.LEFT)


# initialize default app values from TOML before the rest of the widgets are populated
app_defaults = load_config(CONFIG_PATH)


def save_current_config():
    try:
        cfg = collect_current_config()
        save_config(cfg, CONFIG_PATH)
        lbl_status.config(text=f"Defaults saved to {CONFIG_PATH.name}")
    except Exception as exc:
        messagebox.showerror("Config Error", str(exc))


def load_current_config():
    try:
        cfg = load_config(CONFIG_PATH)
        apply_app_defaults(cfg)
        lbl_status.config(text=f"Defaults loaded from {CONFIG_PATH.name}")
    except Exception as exc:
        messagebox.showerror("Config Error", str(exc))


def text_to_bits(text_string, include_siren=True, siren_gothroughs=4, siren_length=16, siren_only=False):
    bit_stream = []
    endamble_byte_1 = [0, 0, 0, 0, 0, 0, 0, 0]
    endamble_byte_2 = [1, 1, 1, 1, 1, 1, 1, 1]
    endamble_byte_3 = [1, 1, 0, 1, 0, 1, 0, 1]
    
    # 1. Standalone Pure Siren Mode (Returns early to prevent header protocol leaking)
    if siren_only:
        for i in range(int(siren_gothroughs)):
            for j in range(int(siren_length)):
                bit_stream.extend(endamble_byte_2)
            for J in range(int(siren_length)):
                bit_stream.extend(endamble_byte_1)
        return bit_stream

    # 2. Standard Protocol Data Blocks
    true_preamble_byte = [1, 1, 0, 1, 0, 1, 0, 1]
    if include_siren:
        for i in range(int(siren_gothroughs)):
            for j in range(int(siren_length)):
                bit_stream.extend(endamble_byte_2)
            for J in range(int(siren_length)):
                bit_stream.extend(endamble_byte_1)
    for i in range(2):
        bit_stream.extend(endamble_byte_2)
    for i in range(1):
        bit_stream.extend(endamble_byte_1)
    for i in range(16):
        bit_stream.extend(true_preamble_byte)
            
    for char in text_string:
        byte_val = ord(char)
        for i in range(8):
            bit_stream.append((byte_val >> i) & 1)

    bit_stream.extend(endamble_byte_3)
    bit_stream.extend(endamble_byte_2)
    bit_stream.extend(endamble_byte_2)
    return bit_stream

def generate_afsk_chunk(bit_stream):
    chunks = []
    phase = 0.0
    for b in bit_stream:
        f = FREQ_MARK if b == 1 else FREQ_SPACE
        t = np.arange(SAMPLES_PER_BIT) / SAMPLE_RATE
        pd = 2 * np.pi * f * t
        wk = np.sin(phase + pd)
        phase = (phase + pd[-1]) % (2 * np.pi)
        chunks.append((wk * 32767).astype(np.int16))
    return np.concatenate(chunks) if chunks else np.array([], dtype=np.int16)

def generate_eas_attention_signal(duration):
    if duration <= 0: return np.array([], dtype=np.int16)
    t = np.arange(int(SAMPLE_RATE * duration)) / SAMPLE_RATE
    return ((np.sin(2 * np.pi * 853 * t) + np.sin(2 * np.pi * 960 * t)) / 2.0 * 32767).astype(np.int16)


def build_siren_audio(siren_gothroughs=4, siren_length=16, potato_mode=False):
    if potato_mode:
        potato_bits = text_to_bits("potato", include_siren=False, siren_gothroughs=0, siren_length=0, siren_only=False)
        return generate_afsk_chunk(potato_bits)

    siren_only_bits = text_to_bits("", include_siren=False, siren_gothroughs=siren_gothroughs, siren_length=siren_length, siren_only=True)
    return generate_afsk_chunk(siren_only_bits)


def read_and_resample_wav(filepath):
    if not os.path.exists(filepath):
        return np.array([], dtype=np.int16)
    data, native_rate = sf.read(filepath, dtype='int16')
    if len(data.shape) > 1:
        data = data[:, 0]
    if native_rate != SAMPLE_RATE:
        num_target_samples = int((len(data) / native_rate) * SAMPLE_RATE)
        data = np.interp(np.linspace(0, len(data) - 1, num_target_samples), np.arange(len(data)), data)
    return data.astype(np.int16)

def run_tts(text):
    temp_tts = f"temp_live_tts_{threading.get_ident()}.wav"
    try:
        subprocess.run(
            ["espeak-ng", "-w", temp_tts, "-v", "en-us", "-s", "150", "-p", "42", "-g", "0", text], 
            check=True, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        audio = read_and_resample_wav(temp_tts)
        if os.path.exists(temp_tts):
            os.remove(temp_tts)
        return audio
    except Exception:
        if os.path.exists(temp_tts):
            try:
                os.remove(temp_tts)
            except Exception:
                pass
        return np.array([], dtype=np.int16)

class BroadcastSystem:
    def __init__(self):
        self.loop_items = []  
        self.eas_queue = queue.Queue()  
        self.current_loop_idx = 0
        self.current_array = np.array([], dtype=np.int16)
        self.array_pointer = 0
        self.is_playing_eas = False
        self.lock = threading.Lock()
        
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE, 
            channels=1, 
            dtype='int16', 
            blocksize=CHUNKS_PER_BUFFER,
            callback=self._audio_callback
        )
        self.stream.start()

    def update_loop(self, chunk_list):
        with self.lock:
            self.loop_items = chunk_list
            self.current_loop_idx = 0
            if not self.is_playing_eas:
                if self.loop_items:
                    # Ensure current_array is a single ndarray from the rotation, not the list itself
                    self.current_array = self.loop_items[self.current_loop_idx]
                else:
                    self.current_array = np.array([], dtype=np.int16)
                self.array_pointer = 0

    def trigger_eas_interrupt(self, eas_audio_payload):
        with self.lock:
            self.is_playing_eas = True
            self.current_array = eas_audio_payload
            self.array_pointer = 0

    def _audio_callback(self, outdata, frames, time_info, status):
        with self.lock:
            bytes_needed = frames
            out_buffer = np.zeros(bytes_needed, dtype=np.int16)
            write_idx = 0

            while write_idx < bytes_needed:
                remaining_samples = len(self.current_array) - self.array_pointer

                if remaining_samples > 0:
                    take_samples = min(bytes_needed - write_idx, remaining_samples)
                    out_buffer[write_idx:write_idx+take_samples] = self.current_array[self.array_pointer:self.array_pointer+take_samples]
                    self.array_pointer += take_samples
                    write_idx += take_samples
                else:
                    if self.is_playing_eas:
                        self.is_playing_eas = False
                        self.current_loop_idx = 0
                        if self.loop_items:
                            # Resume from the first item in the loop rotation
                            self.current_array = self.loop_items[self.current_loop_idx]
                        else:
                            self.current_array = np.array([], dtype=np.int16)
                        self.array_pointer = 0
                    else:
                        if self.loop_items:
                            self.current_loop_idx = (self.current_loop_idx + 1) % len(self.loop_items)
                            self.current_array = self.loop_items[self.current_loop_idx]
                        else:
                            self.current_array = np.zeros(SAMPLE_RATE, dtype=np.int16)
                        self.array_pointer = 0
                    
                    if len(self.current_array) == 0:
                        self.current_array = np.zeros(SAMPLE_RATE, dtype=np.int16)
                        self.array_pointer = 0

            outdata[:] = out_buffer.reshape(-1, 1)

system_engine = BroadcastSystem()

def show_add_confirmation(parent):
    result = {'choice': 'cancel'}

    dlg = tk.Toplevel(parent)
    dlg.title('Confirm Add To Loop')
    dlg.transient(parent)
    dlg.grab_set()

    msg = tk.Label(dlg, text='Add current selection to the loop rotation?')
    msg.pack(padx=20, pady=(12, 8))

    btn_frame = ttk.Frame(dlg)
    btn_frame.pack(padx=12, pady=(0,12), fill=tk.X)

    def choose_yes():
        result['choice'] = 'yes'
        dlg.destroy()

    def choose_yes_without():
        result['choice'] = 'yes_without'
        dlg.destroy()

    def choose_cancel():
        result['choice'] = 'cancel'
        dlg.destroy()

    ttk.Button(btn_frame, text='Yes', command=choose_yes).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
    ttk.Button(btn_frame, text='Yes without Siren/Tone', command=choose_yes_without).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
    ttk.Button(btn_frame, text='Cancel', command=choose_cancel).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

    parent.wait_window(dlg)
    return result['choice']

def append_to_loop():
    f_path = entry_file_path.get().strip().replace("'", "").replace('"', "")
    r_body = text_body.get("1.0", tk.END).strip()
    use_file = var_use_file.get()
    use_siren_flag = var_use_siren.get()
    siren_placement = siren_placement_var.get()
    potato_mode = var_potato_siren.get()

    def worker():
        try:
            chunks = []
            try:
                t_goa = int(entry_siren_goarounds.get() or 0)
                t_slen = int(entry_siren_length.get() or 0)
                t_len = float(entry_tone_len.get() or 0.0)
            except ValueError:
                root.after(0, lambda: messagebox.showerror("Error", "Invalid siren or tone numeric input"))
                return
            if use_file:
                if f_path and os.path.exists(f_path):
                    chunks.append(read_and_resample_wav(f_path))
                else:
                    root.after(0, lambda: messagebox.showerror("Error", f"Siphon path invalid or missing:\n{f_path}"))
                    return
            else:
                if r_body:
                    chunks.append(run_tts(r_body))

            tone_audio = generate_eas_attention_signal(t_len) if t_len > 0 else np.array([], dtype=np.int16)
            siren_audio = build_siren_audio(t_goa, t_slen, potato_mode) if use_siren_flag else np.array([], dtype=np.int16)

            if siren_placement == "before":
                if siren_audio.size > 0:
                    chunks.insert(0, siren_audio)
                if tone_audio.size > 0:
                    chunks.insert(0, tone_audio)
            elif siren_placement == "after":
                if tone_audio.size > 0:
                    chunks.append(tone_audio)
                if siren_audio.size > 0:
                    chunks.append(siren_audio)
            elif siren_placement == "replace":
                if siren_audio.size > 0:
                    chunks.append(siren_audio)
            elif use_siren_flag and siren_audio.size > 0:
                chunks.insert(0, siren_audio)

            if chunks:
                new_rotation = system_engine.loop_items + chunks
                system_engine.update_loop(new_rotation)
                root.after(0, lambda: lbl_status.config(text=f"Rotation Updated ({len(new_rotation)} Items in Loop)"))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", str(e)))
            
    threading.Thread(target=worker, daemon=True).start()

def clear_active_loop():
    system_engine.update_loop([])
    lbl_status.config(text="Loop Cleared. Playing Dead Air...")

def deploy_eas_priority():
    r_head = entry_header.get().strip().upper()
    r_foot = entry_footer.get().strip().upper()
    r_body = text_body.get("1.0", tk.END).strip()
    f_path = entry_file_path.get().strip().replace("'", "").replace('"', "")
    use_file = var_use_file.get()
    use_siren = var_use_siren.get()
    siren_placement = siren_placement_var.get()
    potato_mode = var_potato_siren.get()

    try:
        t_len = float(entry_tone_len.get() or 0.0)
        t_goa = float(entry_siren_goarounds.get() or 0)
        t_slen = float(entry_siren_length.get() or 0)
    except ValueError:
        return messagebox.showerror("Error", "Invalid Number Input")

    if (t_goa * t_slen) > 96:
        confirm = messagebox.askyesno(
            "Warning: Excessive Siren Parameters",
            "The combined total of Siren Goarounds and Siren Length exceeds 96!\n\nDo you wish to proceed?"
        )
        if not confirm:
            return

    if use_file and (not f_path or not os.path.exists(f_path)):
        return messagebox.showerror("Error", f"Siphon path invalid or missing:\n{f_path}")

    lbl_status.config(text="⚠️ COMPILING & INJECTING EAS ALERT...")

    def worker():
        try:
            eas_chunks = []
            silence_1s = np.zeros(SAMPLE_RATE, dtype=np.int16)
            tone_audio = generate_eas_attention_signal(t_len) if t_len > 0 else np.array([], dtype=np.int16)
            siren_audio = build_siren_audio(int(t_goa), int(t_slen), potato_mode) if use_siren else np.array([], dtype=np.int16)

            if not r_head and use_siren and siren_placement == "attached":
                eas_chunks.append(siren_audio)
                eas_chunks.append(silence_1s)
            elif r_head and siren_placement == "attached":
                if potato_mode:
                    potato_audio = generate_afsk_chunk(text_to_bits("potato", include_siren=False, siren_gothroughs=0, siren_length=0, siren_only=False))
                    h_audio = generate_afsk_chunk(text_to_bits(r_head + "-", False, 0, 0, siren_only=False))
                    for _ in range(3):
                        eas_chunks.append(potato_audio)
                        eas_chunks.append(silence_1s)
                        eas_chunks.append(h_audio)
                        eas_chunks.append(silence_1s)
                else:
                    h_audio = generate_afsk_chunk(text_to_bits(r_head + "-", use_siren, t_goa, t_slen, siren_only=False))
                    for _ in range(3):
                        eas_chunks.append(h_audio)
                        eas_chunks.append(silence_1s)
            elif r_head:
                h_audio = generate_afsk_chunk(text_to_bits(r_head + "-", False, 0, 0, siren_only=False))
                for _ in range(3):
                    eas_chunks.append(h_audio)
                    eas_chunks.append(silence_1s)

            if siren_placement == "before":
                if siren_audio.size > 0:
                    eas_chunks.append(siren_audio)
                    eas_chunks.append(silence_1s)
                if tone_audio.size > 0:
                    eas_chunks.append(tone_audio)
                    eas_chunks.append(silence_1s)
            elif siren_placement == "after":
                if tone_audio.size > 0:
                    eas_chunks.append(tone_audio)
                    eas_chunks.append(silence_1s)
                if siren_audio.size > 0:
                    eas_chunks.append(siren_audio)
                    eas_chunks.append(silence_1s)
            elif siren_placement == "replace":
                if siren_audio.size > 0:
                    eas_chunks.append(siren_audio)
                    eas_chunks.append(silence_1s)
                elif tone_audio.size > 0:
                    eas_chunks.append(tone_audio)
                    eas_chunks.append(silence_1s)
            elif tone_audio.size > 0:
                eas_chunks.append(tone_audio)
                eas_chunks.append(silence_1s)

            if use_file:
                eas_chunks.append(read_and_resample_wav(f_path))
            elif r_body:
                eas_chunks.append(run_tts(r_body))

            eas_chunks.append(np.zeros(int(SAMPLE_RATE * 1.5), dtype=np.int16))

            if r_head and r_foot:
                f_audio = generate_afsk_chunk(text_to_bits(r_foot, False, siren_only=False))
                for _ in range(3):
                    eas_chunks.append(f_audio)
                    eas_chunks.append(silence_1s)

            if eas_chunks:
                full_eas_audio = np.concatenate(eas_chunks)
                system_engine.trigger_eas_interrupt(full_eas_audio)

            root.after(0, lambda: lbl_status.config(text="TRANSMITTING EAS INTERRUPTION LIVE"))
        except NameError as eRROR:
            root.after(0, lambda: messagebox.showerror("Error", str(eRROR)))

    threading.Thread(target=worker, daemon=True).start()

def start_alert_monitor():
    processed_alerts = set()

    def monitor_loop():
        headers = {'User-Agent': 'ProBugEASMonitor/2.0 (contact: test@example.com)'}
        url = "https://api.weather.gov/alerts/active?area=PA"

        while True:
            try:
                cfg = load_config(CONFIG_PATH).get("auto", DEFAULT_CONFIG["auto"])
                auto_codes = {str(code).strip().upper() for code in cfg.get("event_codes", [])}
                enabled_counties = {str(c).strip() for c in cfg.get("counties", [])}
                callsign = str(cfg.get("callsign", "WXR")).strip().upper() or "WXR"
                include_weather_text = bool(cfg.get("weather_text", False))
                alert_template = cfg.get("alert_text_template", DEFAULT_CONFIG["auto"]["alert_text_template"])

                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    features = data.get("features", [])

                    for feature in features:
                        properties = feature.get("properties", {})
                        alert_id = properties.get("id")

                        if alert_id in processed_alerts:
                            continue

                        geocode = properties.get("geocode", {})
                        same_codes = geocode.get("SAME", [])
                        ugc_codes = properties.get("UGC", [])

                        event_name = properties.get("event", "Weather Alert")
                        event_code = SAME.normalize_event_code(event_name)
                        if auto_codes and event_code not in auto_codes and event_name.upper() not in auto_codes:
                            continue

                        matched_counties = []
                        for zone in same_codes + ugc_codes:
                            if zone in enabled_counties or zone == "042003" or zone == "000000" or zone == "042000":
                                matched_counties.append(zone)

                        if enabled_counties and not matched_counties:
                            continue

                        processed_alerts.add(alert_id)

                        headline = properties.get("headline", "")
                        description = properties.get("description", "No details provided.")

                        target_counties = matched_counties or (['042003'] if '042003' in enabled_counties else ['000000'] if '000000' in enabled_counties else ['042000'] if '042000' in enabled_counties else ['042003'])

                        try:
                            generated_header = SAME.encode_same_string(
                                event_code=event_code,
                                target_counties=target_counties,
                                duration_hhmm="0100",
                                originator=callsign[:3],
                                station_id=callsign[:8].ljust(8, 'X')
                            )
                        except Exception:
                            generated_header = f"ZCZC-{callsign[:3]}-{event_code}-{target_counties[0]}+0100-{time.strftime('%j%H%M', time.gmtime())}-{callsign[:8].ljust(8, 'X')}-"

                        if include_weather_text:
                            generated_body = _parse_alert_text(event_name, headline, description, alert_template)
                        else:
                            generated_body = f"The National Weather Service has issued a {event_name}. {headline}. {description}"
                        generated_footer = "NNNN"

                        def update_gui_and_click():
                            entry_header.delete(0, tk.END)
                            entry_header.insert(0, generated_header)

                            text_body.delete("1.0", tk.END)
                            text_body.insert("1.0", generated_body)

                            entry_footer.delete(0, tk.END)
                            entry_footer.insert(0, generated_footer)

                            btn_eas.invoke()

                        root.after(0, update_gui_and_click)

            except Exception:
                pass

            time.sleep(30)

    threading.Thread(target=monitor_loop, daemon=True).start()

def build_event_menu_options():
    official = getattr(SAME, "ALL_EVENT_CODES", {})
    custom = getattr(OAME, "EVENT_CODES", {})
    combined = {}
    combined.update({code: label for code, label in official.items() if isinstance(code, str) and isinstance(label, str)})
    combined.update({code: label for code, label in custom.items() if isinstance(code, str) and isinstance(label, str)})
    return [f"{code} - {label}" for code, label in sorted(combined.items())]


def open_same_gui():
    subprocess.Popen(["python3", os.path.join(os.path.dirname(__file__), "SAME.py")], cwd=os.path.dirname(__file__))


def open_oame_gui():
    subprocess.Popen(["python3", os.path.join(os.path.dirname(__file__), "OAME.py")], cwd=os.path.dirname(__file__))


root = tk.Tk()
root.title("BUG Weatherbot Studio + OAME/SAME Functionality v2")
root.geometry("1200x900")
root.minsize(1000, 700)
root.resizable(True, True)

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True)

main_frame = ttk.Frame(notebook, padding="15")
notebook.add(main_frame, text="EAS Broadcast")

settings_frame = ttk.Frame(main_frame, padding=(0, 8, 0, 0))
settings_frame.pack(fill=tk.X)

config_buttons = ttk.Frame(settings_frame)
config_buttons.pack(fill=tk.X)
ttk.Button(config_buttons, text="Load Config Defaults", command=load_current_config).pack(side=tk.LEFT, padx=(0, 8))
ttk.Button(config_buttons, text="Save Current Values as Defaults", command=save_current_config).pack(side=tk.LEFT, padx=(0, 8))
ttk.Button(config_buttons, text="Auto Alert Config", command=open_auto_config_window).pack(side=tk.LEFT)

same_tab = ttk.Frame(notebook, padding="15")
notebook.add(same_tab, text="SAME")

auto_tab = ttk.Frame(notebook, padding="15")
notebook.add(auto_tab, text="Auto Config")

oame_tab = ttk.Frame(notebook, padding="15")
notebook.add(oame_tab, text="OAME")

# SAME tab content
same_label = ttk.Label(same_tab, text="SAME Header Generator", font=("Arial", 12, "bold"))
same_label.pack(anchor=tk.W, pady=(0, 10))

same_event_var = tk.StringVar(value=build_event_menu_options()[0] if build_event_menu_options() else "ADR - Administrative Message")
same_event_combo = ttk.Combobox(same_tab, textvariable=same_event_var, values=build_event_menu_options(), width=80, state="readonly")
same_event_combo.pack(fill=tk.X, pady=(0, 10))

same_county_label = ttk.Label(same_tab, text="County/FIPS codes (comma-separated; shortcuts: 042003, 000000, 042000):")
same_county_label.pack(anchor=tk.W)
same_county_entry = ttk.Entry(same_tab, width=80)
same_county_entry.insert(0, "042003")
same_county_entry.pack(fill=tk.X, pady=(0, 10))

same_duration_label = ttk.Label(same_tab, text="Duration (HHMM):")
same_duration_label.pack(anchor=tk.W)
same_duration_entry = ttk.Entry(same_tab, width=12)
same_duration_entry.insert(0, "0100")
same_duration_entry.pack(anchor=tk.W, pady=(0, 10))

same_originator_label = ttk.Label(same_tab, text="Originator (3 chars):")
same_originator_label.pack(anchor=tk.W)
same_originator_entry = ttk.Entry(same_tab, width=12)
same_originator_entry.insert(0, "WXR")
same_originator_entry.pack(anchor=tk.W, pady=(0, 10))

same_station_label = ttk.Label(same_tab, text="Station ID (up to 8 chars):")
same_station_label.pack(anchor=tk.W)
same_station_entry = ttk.Entry(same_tab, width=12)
same_station_entry.insert(0, "KPBZ")
same_station_entry.pack(anchor=tk.W, pady=(0, 10))

same_output = tk.Text(same_tab, height=12, width=90, font=("Courier", 10), wrap="none")
same_output.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

same_defaults_button = ttk.Button(same_tab, text="Save SAME defaults to config.toml", command=lambda: save_current_config())
same_defaults_button.pack(fill=tk.X, pady=(0, 8))

def generate_same_header_from_tab():
    try:
        code_text = same_event_var.get().split(" - ", 1)[0].strip()
        counties = [c.strip() for c in same_county_entry.get().split(",") if c.strip()]
        duration_value = (same_duration_entry.get() or "0100").strip()
        originator = same_originator_entry.get().strip() or "WXR"
        station_id = same_station_entry.get().strip() or "KPBZ"
        if not counties:
            raise ValueError("At least one county/FIPS code is required.")
        same_output.delete("1.0", tk.END)
        same_output.insert("1.0", SAME.encode_same_string(code_text, counties, duration_hhmm=duration_value, originator=originator, station_id=station_id))
    except Exception as exc:
        messagebox.showerror("Error", str(exc))

same_generate_btn = ttk.Button(same_tab, text="Generate SAME Header", command=generate_same_header_from_tab)
same_generate_btn.pack(fill=tk.X)

# Auto Config tab content
auto_event_codes_var = tk.StringVar(value=", ".join(_current_auto_config().get("event_codes", DEFAULT_CONFIG["auto"]["event_codes"])))
auto_callsign_var = tk.StringVar(value=_current_auto_config().get("callsign", DEFAULT_CONFIG["auto"]["callsign"]))
auto_counties_var = tk.StringVar(value=", ".join(_current_auto_config().get("counties", DEFAULT_CONFIG["auto"]["counties"])))
auto_weather_text_var = tk.BooleanVar(value=bool(_current_auto_config().get("weather_text", DEFAULT_CONFIG["auto"]["weather_text"])))
auto_alert_template_var = tk.StringVar(value=_current_auto_config().get("alert_text_template", DEFAULT_CONFIG["auto"]["alert_text_template"]))

auto_title = ttk.Label(auto_tab, text="Auto Alert Configuration", font=("Arial", 12, "bold"))
auto_title.pack(anchor=tk.W, pady=(0, 10))

auto_event_label = ttk.Label(auto_tab, text="Event codes to activate automatically:")
auto_event_label.pack(anchor=tk.W)
ttk.Entry(auto_tab, textvariable=auto_event_codes_var, width=80).pack(fill=tk.X, pady=(0, 10))

auto_callsign_label = ttk.Label(auto_tab, text="Callsign:")
auto_callsign_label.pack(anchor=tk.W)
ttk.Entry(auto_tab, textvariable=auto_callsign_var, width=30).pack(anchor=tk.W, pady=(0, 10))

auto_counties_label = ttk.Label(auto_tab, text="Counties/FIPS to activate for (comma-separated):")
auto_counties_label.pack(anchor=tk.W)
ttk.Entry(auto_tab, textvariable=auto_counties_var, width=80).pack(fill=tk.X, pady=(0, 10))

ttk.Checkbutton(auto_tab, text="Participate in Alert Text section for valid alert types", variable=auto_weather_text_var).pack(anchor=tk.W, pady=(0, 10))

auto_template_label = ttk.Label(auto_tab, text="Alert text template:")
auto_template_label.pack(anchor=tk.W)
ttk.Entry(auto_tab, textvariable=auto_alert_template_var, width=80).pack(fill=tk.X, pady=(0, 10))

auto_example = ttk.Label(auto_tab, text="Example: HAZ...{hazard} HAIL {hail} SRC...{source}", foreground="#666666")
auto_example.pack(anchor=tk.W)

def save_auto_cfg_tab():
    try:
        cfg = {
            "auto": {
                "event_codes": [c.strip().upper() for c in auto_event_codes_var.get().split(",") if c.strip()],
                "callsign": (auto_callsign_var.get() or DEFAULT_CONFIG["auto"]["callsign"]).strip().upper(),
                "counties": [c.strip() for c in auto_counties_var.get().split(",") if c.strip()],
                "weather_text": bool(auto_weather_text_var.get()),
                "alert_text_template": (auto_alert_template_var.get() or DEFAULT_CONFIG["auto"]["alert_text_template"]).strip(),
            }
        }
        existing = load_config(CONFIG_PATH)
        existing.update(cfg)
        save_config(existing, CONFIG_PATH)
        lbl_status.config(text="Auto alert config saved")
    except Exception as exc:
        messagebox.showerror("Config Error", str(exc))

ttk.Button(auto_tab, text="Save Auto Config", command=save_auto_cfg_tab).pack(fill=tk.X, pady=(12, 0))

# OAME tab content
same_launch_btn = ttk.Button(oame_tab, text="Open OAME standalone generator", command=open_oame_gui)
same_launch_btn.pack(anchor=tk.W, pady=(0, 10))
oame_info = tk.Label(
    oame_tab,
    text="The OAME generator lives in its own script but is now reachable from the main tabbed window.",
    justify=tk.LEFT,
    wraplength=700,
    padx=8,
    pady=8
)
oame_info.pack(anchor=tk.W, fill=tk.X)

launcher_frame = ttk.Frame(main_frame)
launcher_frame.pack(fill=tk.X, pady=(0, 10))
ttk.Button(launcher_frame, text="Open SAME Tool", command=open_same_gui).pack(side=tk.LEFT, padx=(0, 8))
ttk.Button(launcher_frame, text="Open OAME Tool", command=open_oame_gui).pack(side=tk.LEFT)

lbl_status = tk.Label(
    main_frame, 
    text="System Idle (Monitoring NWS API)", 
    bg="#333", 
    fg="#00FF00", 
    font=("Courier", 11, "bold"), 
    anchor="w", 
    padx=10, 
    pady=5
)
lbl_status.pack(fill=tk.X, pady=5)

ttk.Label(main_frame, text="1. EAS Header Code String:").pack(anchor=tk.W, pady=2)
entry_header = ttk.Entry(main_frame, width=55, font=("Courier", 10))
entry_header.insert(0, "OGZC-CRS-ADR-0000+0100-0101+00")
entry_header.pack(pady=2)

ttk.Label(main_frame, text="Manual Siren Config").pack(anchor=tk.W, pady=(8,2))

siren_placement_var = tk.StringVar(value="attached")
ttk.Label(main_frame, text="Siren placement:").pack(anchor=tk.W, pady=(2,0))
placement_combo = ttk.Combobox(main_frame, textvariable=siren_placement_var, values=["attached", "before", "after", "replace"], state="readonly", width=22)
placement_combo.pack(anchor=tk.W, pady=2)

ttk.Label(main_frame, text="Siren Goarounds").pack(anchor=tk.W, pady=2)
entry_siren_goarounds= ttk.Entry(main_frame, width=15)
entry_siren_goarounds.insert(0, "16")
entry_siren_goarounds.pack(pady=2)

ttk.Label(main_frame, text="Siren Length").pack(anchor=tk.W, pady=2)
entry_siren_length= ttk.Entry(main_frame, width=15)
entry_siren_length.insert(0, "4")
entry_siren_length.pack(pady=2)

ttk.Label(main_frame, text="2. Attention Signal Duration (Seconds):").pack(anchor=tk.W, pady=2)
entry_tone_len = ttk.Entry(main_frame, width=15)
entry_tone_len.insert(0, "8.0")
entry_tone_len.pack(pady=2)

var_use_file = tk.BooleanVar()
ttk.Checkbutton(main_frame, text="Use External WAV Target instead of generating TTS", variable=var_use_file).pack(anchor=tk.W, pady=2)

var_use_siren = tk.BooleanVar()
ttk.Checkbutton(main_frame, text="Use Siren", variable=var_use_siren).pack(anchor=tk.W, pady=2)

var_potato_siren = tk.BooleanVar()
ttk.Checkbutton(main_frame, text="Potato siren: replace siren with lowercase 'potato' encoded payload", variable=var_potato_siren).pack(anchor=tk.W, pady=2)

ttk.Label(main_frame, text="External Target Filepath (.wav):").pack(anchor=tk.W, pady=2)
entry_file_path = ttk.Entry(main_frame, width=55, font=("Courier", 9))
entry_file_path.pack(pady=2)

ttk.Label(main_frame, text="3. Voice Announcement / Text Input (TTS Engine):").pack(anchor=tk.W, pady=2)
text_body = tk.Text(main_frame, height=4, width=60, font=("Arial", 10))
text_body.insert("1.0", "The National Weather Service has issued a severe statement.")
text_body.pack(pady=2)

ttk.Label(main_frame, text="4. EAS End of Message Footer Code:").pack(anchor=tk.W, pady=2)
entry_footer = ttk.Entry(main_frame, width=55, font=("Courier", 10))
entry_footer.insert(0, "OGNN")
entry_footer.pack(pady=2)

apply_app_defaults(load_config(CONFIG_PATH))

btn_frame = ttk.Frame(main_frame, padding="5")
btn_frame.pack(fill=tk.X, pady=10)

ttk.Button(btn_frame, text="➕ Add to Loop Rotation", command=append_to_loop).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
ttk.Button(btn_frame, text="🛑 Clear Loop", command=clear_active_loop).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

btn_eas = tk.Button(
    main_frame, 
    text="INTERRUPT LIVE WITH EAS ALERT", 
    command=deploy_eas_priority, 
    bg="#990000", 
    fg="white", 
    font=("Arial", 11, "bold"), 
    height=2
)
btn_eas.pack(fill=tk.X, pady=5)

if __name__ == "__main__":
    start_alert_monitor()
    root.mainloop()
