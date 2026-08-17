import tkinter as tk
from tkinter import ttk, messagebox
import queue
import threading
import subprocess
import os
import time
import numpy as np
import soundfile as sf
import sounddevice as sd
import requests

# --- Constants ---
SAMPLE_RATE = 80000        
BAUD_RATE = 520.8333        
FREQ_MARK, FREQ_SPACE = 2083.33, 1562.50        
PREAMBLE_BITS = 128         
SAMPLES_PER_BIT = int(SAMPLE_RATE / BAUD_RATE)
CHUNKS_PER_BUFFER = 1024 

# FIPS/SAME Target Zones
TARGET_ZONES = {"042003", "142003", "242003", "342003", "442003", "542003", "642003", "742003", "842003", "942003", "000000", "042000"} 

def text_to_bits(text_string, include_preamble=True):
    bit_stream = []
    true_preamble_byte = [1, 1, 0, 1, 0, 1, 0, 1]
    
    if include_preamble:
        for _ in range(16):
            bit_stream.extend(true_preamble_byte)
    else:
        for _ in range(16):
            bit_stream.extend(true_preamble_byte)
            
    for char in text_string:
        byte_val = ord(char)
        for i in range(8):
            bit_stream.append((byte_val >> i) & 1)

    for _ in range(4):
        bit_stream.extend(true_preamble_byte)
    return bit_stream

def generate_afsk_chunk(bit_stream):
    audio_samples = []
    current_phase = 0.0
    for bit in bit_stream:
        freq = FREQ_MARK if bit == 1 else FREQ_SPACE
        t = np.arange(SAMPLES_PER_BIT) / SAMPLE_RATE
        phase_delta = 2 * np.pi * freq * t
        wave_chunk = np.sin(current_phase + phase_delta)
        current_phase = (current_phase + phase_delta[-1]) % (2 * np.pi)
        audio_samples.append((wave_chunk * 32767).astype(np.int16))
    return np.concatenate(audio_samples) if audio_samples else np.array([], dtype=np.int16)

def generate_eas_attention_signal(duration):
    if duration <= 0: return np.array([], dtype=np.int16)
    t = np.arange(int(SAMPLE_RATE * duration)) / SAMPLE_RATE
    return ((np.sin(2 * np.pi * 853 * t) + np.sin(2 * np.pi * 960 * t)) / 2.0 * 32767).astype(np.int16)

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
            try: os.remove(temp_tts)
            except: pass
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
                self.current_array = self.loop_items[0] if self.loop_items else np.array([], dtype=np.int16)
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
                            self.current_array = self.loop_items[0]
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

def append_to_loop():
    f_path = entry_file_path.get().strip().replace("'", "").replace('"', "")
    r_body = text_body.get("1.0", tk.END).strip()
    use_file = var_use_file.get()

    def worker():
        try:
            chunks = []
            if use_file:
                if f_path and os.path.exists(f_path):
                    chunks.append(read_and_resample_wav(f_path))
                else:
                    root.after(0, lambda: messagebox.showerror("Error", f"Siphon path invalid or missing:\n{f_path}"))
                    return
            else:
                if r_body:
                    chunks.append(run_tts(r_body))

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

    try:
        t_len = float(entry_tone_len.get() or 0.0)
    except ValueError:
        return messagebox.showerror("Error", "Invalid attention tone duration value!")
        
    if use_file and (not f_path or not os.path.exists(f_path)):
        return messagebox.showerror("Error", f"Siphon path invalid or missing:\n{f_path}")

    lbl_status.config(text="⚠️ COMPILING & INJECTING EAS ALERT...")

    def worker():
        try:
            eas_chunks = []
            silence_1s = np.zeros(SAMPLE_RATE, dtype=np.int16)

            if r_head:
                h_audio = generate_afsk_chunk(text_to_bits(r_head + "\r\n", True))
                for _ in range(3):
                    eas_chunks.append(h_audio)
                    eas_chunks.append(silence_1s)

            if t_len > 0:
                eas_chunks.append(generate_eas_attention_signal(t_len))
                eas_chunks.append(silence_1s)

            if use_file:
                eas_chunks.append(read_and_resample_wav(f_path))
            elif r_body:
                eas_chunks.append(run_tts(r_body))

            eas_chunks.append(np.zeros(int(SAMPLE_RATE * 1.5), dtype=np.int16))

            if r_foot:
                f_audio = generate_afsk_chunk(text_to_bits(r_foot + "\r\n", False))
                for _ in range(3):
                    eas_chunks.append(f_audio)
                    eas_chunks.append(silence_1s)
            if eas_chunks:
                full_eas_audio = np.concatenate(eas_chunks)
                system_engine.trigger_eas_interrupt(full_eas_audio)
            
            root.after(0, lambda: lbl_status.config(text="TRANSMITTING EAS INTERRUPTION LIVE"))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", str(e)))

    threading.Thread(target=worker, daemon=True).start()

def start_alert_monitor():
    processed_alerts = set()

    def monitor_loop():
        headers = {'User-Agent': 'ProBugEASMonitor/2.0 (contact: test@example.com)'}
        url = "https://api.weather.gov/alerts/active?area=PA"

        while True:
            try:
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

                        is_target = any(zone in same_codes for zone in TARGET_ZONES)

                        if not is_target:
                            is_target = any("PAC003" in code for code in ugc_codes)

                        if is_target:
                            processed_alerts.add(alert_id)
                            
                            event_name = properties.get("event", "Weather Alert")
                            headline = properties.get("headline", "")
                            description = properties.get("description", "No details provided.")
                            tts_message = f"The National Weather Service has issued a {event_name}. {headline}. {description}"

                            root.after(0, lambda ev=event_name: lbl_status.config(
                                text=f"⚠️ AUTO EAS INJECTION: {ev}", bg="#990000", fg="white"
                            ))

                            eas_chunks = []
                            silence_1s = np.zeros(SAMPLE_RATE, dtype=np.int16)

                            header_text = "ZCZC-WXR-" + event_name[:3].upper() + "-042003+0100-2301500-WXR-STATION-"
                            h_audio = generate_afsk_chunk(text_to_bits(header_text + "\r\n", True))
                            for _ in range(3):
                                eas_chunks.append(h_audio)
                                eas_chunks.append(silence_1s)

                            eas_chunks.append(generate_eas_attention_signal(8.0))
                            eas_chunks.append(silence_1s)

                            eas_chunks.append(run_tts(tts_message))
                            eas_chunks.append(np.zeros(int(SAMPLE_RATE * 1.5), dtype=np.int16))

                            f_audio = generate_afsk_chunk(text_to_bits("NNNN" + "\r\n", False))
                            for _ in range(3):
                                eas_chunks.append(f_audio)
                                eas_chunks.append(silence_1s)

                            full_audio = np.concatenate(eas_chunks)
                            system_engine.trigger_eas_interrupt(full_audio)

                            root.after(0, lambda: lbl_status.config(
                                text="TRANSMITTING EAS INTERRUPTION LIVE", bg="#333", fg="#00FF00"
                            ))

            except Exception:
                pass

            time.sleep(30)

    threading.Thread(target=monitor_loop, daemon=True).start()

root = tk.Tk()
root.title("BUG Weatherbot Studio + OAME/SAME Functionality v2")
root.geometry("500x610")
root.resizable(False, False)

main_frame = ttk.Frame(root, padding="15")
main_frame.pack(fill=tk.BOTH, expand=True)

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

ttk.Label(main_frame, text="2. Attention Signal Duration (Seconds):").pack(anchor=tk.W, pady=2)
entry_tone_len = ttk.Entry(main_frame, width=15)
entry_tone_len.insert(0, "8.0")
entry_tone_len.pack(pady=2)

var_use_file = tk.BooleanVar()
ttk.Checkbutton(main_frame, text="Use External WAV Target instead of generating TTS", variable=var_use_file).pack(anchor=tk.W, pady=2)

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

start_alert_monitor()
root.mainloop()
