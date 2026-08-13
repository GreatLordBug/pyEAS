import tkinter as tk
from tkinter import ttk, messagebox
import queue
import threading
import subprocess
import os
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
CHUNKS_PER_BUFFER = 1024  # Size of audio blocks fed to sounddevice

# --- Core Audio Generation Helpers ---
def text_to_bits(text_string, include_preamble=True):
    """
    Converts string characters to an 8-bit stream sent LSB-first.
    Appends the true NWS/SAME preamble (16 bytes of 0xAB) if requested.
    """
    bit_stream = []
    
    if True:
        # Hex 0xAB in binary is 10101011. Sent LSB-First, this becomes: [1, 1, 0, 1, 0, 1, 0, 1]
        true_preamble_byte = [1, 1, 0, 1, 0, 1, 0, 1]
        if include_preamble:
            for _ in range(16):
                bit_stream.extend(true_preamble_byte)
        else:
            for _ in range(16):
                bit_stream.extend(true_preamble_byte)
            
    for char in text_string:
        byte_val = ord(char)
        # Standard EAS/SAME rule: Send the 8-bit byte out Least Significant Bit (LSB) first
        for i in range(8):
            bit_stream.append((byte_val >> i) & 1)
    if True:
        # Hex 0xAB in binary is 10101011. Sent LSB-First, this becomes: [1, 1, 0, 1, 0, 1, 0, 1]
        true_preamble_byte = [1, 1, 0, 1, 0, 1, 0, 1]
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
    """Generates an American-accented EAS robotic voice with tightened word pacing."""
    temp_tts = f"temp_live_tts_{threading.get_ident()}.wav"
    try:
        # -v en-us targets American pronunciation rules
        # -s 150 provides a natural, steady pace
        # -p 42 provides an authoritative emergency pitch
        # -g 5 shortens the structural pause duration between words
        subprocess.run(
            ["espeak-ng", "-w", temp_tts, "-v", "en-us", "-s", "150", "-p", "42", "-g", "0", text], 
            check=True, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        
        # Stream into memory array using your existing file processing engine
        audio = read_and_resample_wav(temp_tts)
        
        if os.path.exists(temp_tts):
            os.remove(temp_tts)
        return audio
        
    except Exception:
        # Safety clean sweep to keep temporary folder footprint empty
        if os.path.exists(temp_tts):
            try: os.remove(temp_tts)
            except: pass
        return np.array([], dtype=np.int16)



# --- State Management & Live Audio Loop ---
class BroadcastSystem:
    def __init__(self):
        self.loop_items = []       # List of np.arrays representing normal background rotation
        self.eas_queue = queue.Queue()  # Holds immediate high-priority alert arrays
        
        self.current_loop_idx = 0
        self.current_array = np.array([], dtype=np.int16)
        self.array_pointer = 0
        
        self.is_playing_eas = False
        self.lock = threading.Lock()
        
        # Audio device stream setup
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE, 
            channels=1, 
            dtype='int16', 
            blocksize=CHUNKS_PER_BUFFER,
            callback=self._audio_callback
        )
        self.stream.start()

    def update_loop(self, chunk_list):
        """Replaces standard loop content seamlessly or schedules it after current EAS finishes."""
        with self.lock:
            self.loop_items = chunk_list
            self.current_loop_idx = 0
            # If not in EAS, swap pointers immediately to reflect changes
            if not self.is_playing_eas:
                self.current_array = self.loop_items[0] if self.loop_items else np.array([], dtype=np.int16)
                self.array_pointer = 0

    def trigger_eas_interrupt(self, eas_audio_payload):
        """Forces the stream to dump its current position mid-buffer and inject EAS blocks immediately."""
        with self.lock:
            self.is_playing_eas = True
            # Empty current play-head instantly to break loop cycle
            self.current_array = eas_audio_payload
            self.array_pointer = 0

    def _audio_callback(self, outdata, frames, time_info, status):
        """Continuous hardware driver callback requesting chunks of audio frames."""
        with self.lock:
            bytes_needed = frames
            out_buffer = np.zeros(bytes_needed, dtype=np.int16)
            write_idx = 0

            while write_idx < bytes_needed:
                # Calculate what remains inside our running clip segment
                remaining_samples = len(self.current_array) - self.array_pointer

                if remaining_samples > 0:
                    take_samples = min(bytes_needed - write_idx, remaining_samples)
                    out_buffer[write_idx:write_idx+take_samples] = self.current_array[self.array_pointer:self.array_pointer+take_samples]
                    self.array_pointer += take_samples
                    write_idx += take_samples
                else:
                    # Current audio asset is exhausted. Find the next slice.
                    if self.is_playing_eas:
                        # Finished the emergency payload. Transition back to standard loops.
                        self.is_playing_eas = False
                        self.current_loop_idx = 0
                        if self.loop_items:
                            self.current_array = self.loop_items[0]
                        else:
                            self.current_array = np.array([], dtype=np.int16)
                        self.array_pointer = 0
                    else:
                        # Standard Rotation loop advancement
                        if self.loop_items:
                            self.current_loop_idx = (self.current_loop_idx + 1) % len(self.loop_items)
                            self.current_array = self.loop_items[self.current_loop_idx]
                        else:
                            # Total dead air silence loop placeholder
                            self.current_array = np.zeros(SAMPLE_RATE, dtype=np.int16)
                        self.array_pointer = 0
                    
                    # Prevent lock hangs if completely empty
                    if len(self.current_array) == 0:
                        self.current_array = np.zeros(SAMPLE_RATE, dtype=np.int16)
                        self.array_pointer = 0

            outdata[:] = out_buffer.reshape(-1, 1)


system_engine = BroadcastSystem()

# --- GUI Application Logic ---
def append_to_loop():
    """Generates an asset and appends it onto the ongoing continuous list array rotation."""
    # 1. Fetch values on the MAIN thread before starting the background worker
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
                    # Run on main thread to show error safely
                    root.after(0, lambda: messagebox.showerror("Error", f"Siphon path invalid or missing:\n{f_path}"))
                    return
            else:
                if r_body:
                    chunks.append(run_tts(r_body))

            if chunks:
                # Pull current sequence, add the new item, send it back down line
                new_rotation = system_engine.loop_items + chunks
                system_engine.update_loop(new_rotation)
                # Update UI elements safely using root.after
                root.after(0, lambda: lbl_status.config(text=f"Rotation Updated ({len(new_rotation)} Items in Loop)"))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", str(e)))
            
    threading.Thread(target=worker, daemon=True).start()

def clear_active_loop():
    """Wipes standard loop down to dead air. Will not stop an active EAS signal currently running."""
    system_engine.update_loop([])
    lbl_status.config(text="Loop Cleared. Playing Dead Air...")

def deploy_eas_priority():
    """Instantly builds and injects an EAS block, snapping off any current loop mid-syllable."""
    # 1. Fetch ALL UI values safely on the MAIN thread first
    r_head = entry_header.get().strip().upper()
    r_foot = entry_footer.get().strip().upper()
    r_body = text_body.get("1.0", tk.END).strip()
    f_path = entry_file_path.get().strip().replace("'", "").replace('"', "")
    use_file = var_use_file.get()

    try:
        t_len = float(entry_tone_len.get() or 0.0)
    except ValueError:
        return messagebox.showerror("Error", "Invalid attention tone duration value!")

    # REMOVED: The mandatory check that required r_head to have text.

    # Verify siphon path instantly if checked
    if use_file and (not f_path or not os.path.exists(f_path)):
        return messagebox.showerror("Error", f"Siphon path invalid or missing:\n{f_path}")

    # Update status safely on main thread
    lbl_status.config(text="⚠️ COMPILING & INJECTING EAS ALERT...")

    def worker():
        try:
            eas_chunks = []
            silence_1s = np.zeros(SAMPLE_RATE, dtype=np.int16)

            # 3x Header Sends - ONLY runs if a header string is provided
            if r_head:
                h_audio = generate_afsk_chunk(text_to_bits(r_head + "\r\n", True))
                for _ in range(3):
                    eas_chunks.append(h_audio)
                    eas_chunks.append(silence_1s)

            # Attention Dual Tones
            if t_len > 0:
                eas_chunks.append(generate_eas_attention_signal(t_len))
                eas_chunks.append(silence_1s)

            # --- Siphon or TTS Routing for Voice Payload ---
            if use_file:
                eas_chunks.append(read_and_resample_wav(f_path))
            elif r_body:
                eas_chunks.append(run_tts(r_body))

            # Post-voice short pause
            eas_chunks.append(np.zeros(int(SAMPLE_RATE * 1.5), dtype=np.int16))

            # 3x Footer Sends - ONLY runs if a footer string is provided
            if r_foot:
                f_audio = generate_afsk_chunk(text_to_bits(r_foot + "\r\n", False))
                for _ in range(3):
                    eas_chunks.append(f_audio)
                    eas_chunks.append(silence_1s)

            # Safeguard: only process if we actually added audio layers
            if eas_chunks:
                full_eas_audio = np.concatenate(eas_chunks)
                # Fire structural interrupt routine immediately 
                system_engine.trigger_eas_interrupt(full_eas_audio)
            
            # Update UI text safely via root.after from background thread
            root.after(0, lambda: lbl_status.config(text="⚠️ TRANSMITTING EAS INTERRUPTION LIVE"))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", str(e)))

    threading.Thread(target=worker, daemon=True).start()

def send_network_emergency_alert():
    # Replace with your Linux machine's local network IP address
    SERVER_IP = "192.168.1.169" 
    TOPIC = "network_alerts"
    URL = f"http://{SERVER_IP}/{TOPIC}"
    
    header_string = entry_header.get()
    announcement_text = text_body.get("1.0", tk.END).strip()
    
    try:
        # Send HTTP POST request with NTFY-specific configuration headers
        response = requests.post(
            URL,
            data=announcement_text.encode('utf-8'),
            headers={
                "Title": header_string,
                "Priority": "5",  # 5 = Max/Urgent priority (triggers loud sounds/lights)
                "Tags": "warning,rotating_light"  # Adds functional visual emojis
            },
            timeout=5
        )
        response.raise_for_status()
        
        lbl_status.config(
            text="ALERT PUSHED NATIONWIDE TO LOCAL NETWORK", 
            bg="#003300", 
            fg="#00FF00"
        )
    except Exception as e:
        lbl_status.config(
            text=f"Network Error: {str(e)}", 
            bg="#440000", 
            fg="#FF3333"
        )


root = tk.Tk()
root.title("BUG Weatherbot Studio + OAME/SAME Functionality v2")
root.geometry("500x610") # Expanded height slightly from 560 to cleanly anchor the new button
root.resizable(False, False)

# Main container
main_frame = ttk.Frame(root, padding="15")
main_frame.pack(fill=tk.BOTH, expand=True)

# Status Monitor display banner
lbl_status = tk.Label(
    main_frame, 
    text="System Idle (Dead Air)", 
    bg="#333", 
    fg="#00FF00", 
    font=("Courier", 11, "bold"), 
    anchor="w", 
    padx=10, 
    pady=5
)
lbl_status.pack(fill=tk.X, pady=5)

# Framing Codes Controls
ttk.Label(main_frame, text="1. EAS Header Code String:").pack(anchor=tk.W, pady=2)
entry_header = ttk.Entry(main_frame, width=55, font=("Courier", 10))
entry_header.insert(0, "OGZC-CRS-ADR-0000+0100-0101+00")
entry_header.pack(pady=2)

ttk.Label(main_frame, text="2. Attention Signal Duration (Seconds):").pack(anchor=tk.W, pady=2)
entry_tone_len = ttk.Entry(main_frame, width=15)
entry_tone_len.insert(0, "8.0")
entry_tone_len.pack(pady=2)

# Source Routing Toggles
var_use_file = tk.BooleanVar()
ttk.Checkbutton(main_frame, text="Siphon External WAV Target instead of generating TTS", variable=var_use_file).pack(anchor=tk.W, pady=2)

ttk.Label(main_frame, text="External Target Filepath (.wav):").pack(anchor=tk.W, pady=2)
entry_file_path = ttk.Entry(main_frame, width=55, font=("Courier", 9))
entry_file_path.pack(pady=2)

# Core Body message processing unit
ttk.Label(main_frame, text="3. Voice Announcement / Text Input (TTS Engine):").pack(anchor=tk.W, pady=2)
text_body = tk.Text(main_frame, height=4, width=60, font=("Arial", 10))
text_body.insert("1.0", "The National Weather Service has issued a severe statement.")
text_body.pack(pady=2)

ttk.Label(main_frame, text="4. EAS End of Message Footer Code:").pack(anchor=tk.W, pady=2)
entry_footer = ttk.Entry(main_frame, width=55, font=("Courier", 10))
entry_footer.insert(0, "OGNN")
entry_footer.pack(pady=2)

# Execution Action buttons block
btn_frame = ttk.Frame(main_frame, padding="5")
btn_frame.pack(fill=tk.X, pady=10)

ttk.Button(btn_frame, text="➕ Add to Loop Rotation", command=append_to_loop).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
ttk.Button(btn_frame, text="🛑 Clear Loop", command=clear_active_loop).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

btn_eas = tk.Button(
    main_frame, 
    text="🚨 INTERRUPT LIVE WITH EAS ALERT", 
    command=deploy_eas_priority, 
    bg="#990000", 
    fg="white", 
    font=("Arial", 11, "bold"), 
    height=2
)
btn_eas.pack(fill=tk.X, pady=5)

# --- NEW ADDITION: Dedicated Network Emergency Button ---
btn_net_emergency = tk.Button(
    main_frame,
    text="⚠️ Network Emergency Alerts - EMERGENCIES AND TESTS ONLY!",
    command=send_network_emergency_alert,
    bg="#CC6600",       # Noticeable warning orange
    fg="white",
    font=("Arial", 10, "bold"),
    height=1
)
btn_net_emergency.pack(fill=tk.X, pady=5)

root.mainloop()
