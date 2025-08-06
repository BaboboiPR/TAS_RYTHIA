import struct
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

def read_null_terminated_string(f):
    bytes_list = []
    while True:
        b = f.read(1)
        if b == b'\n' or b == b'':
            break
        bytes_list.append(b)
    return b''.join(bytes_list).decode('utf-8')

def read_variable_string(f, four_bytes=False):
    length = struct.unpack('<I' if four_bytes else '<H', f.read(4) if four_bytes else f.read(2))[0]
    data = f.read(length)
    return data.decode('utf-8')

def fix_id(s):
    return s

def parse_sspm(path, speed_multiplier=1.0):
    with open(path, 'rb') as f:
        signature = f.read(4).decode('ascii')
        if signature != 'SS+m':
            raise ValueError("Unsupported file format")

        version = struct.unpack('<H', f.read(2))[0]
        output = {}

        if version == 1:
            f.read(2)
            map_id = fix_id(read_null_terminated_string(f))
            map_name = read_null_terminated_string(f)
            mappers = read_null_terminated_string(f)
            output['map_id'] = map_id
            output['map_name'] = map_name
            output['mappers'] = mappers

            last_ms = struct.unpack('<I', f.read(4))[0]
            note_count = struct.unpack('<I', f.read(4))[0]
            difficulty = struct.unpack('<B', f.read(1))[0]

            contains_cover = f.read(1)[0]
            if contains_cover == 0x02:
                cover_length = struct.unpack('<Q', f.read(8))[0]
                f.read(cover_length)

            contains_audio = struct.unpack('<?', f.read(1))[0]
            if contains_audio:
                audio_length = struct.unpack('<Q', f.read(8))[0]
                f.read(audio_length)

            notes = []
            for _ in range(note_count):
                ms = struct.unpack('<I', f.read(4))[0]
                is_quantum = struct.unpack('<?', f.read(1))[0]

                if is_quantum:
                    x = struct.unpack('<f', f.read(4))[0]
                    y = struct.unpack('<f', f.read(4))[0]
                else:
                    x = struct.unpack('<B', f.read(1))[0]
                    y = struct.unpack('<B', f.read(1))[0]

                notes.append((x,y, int(ms / speed_multiplier)))

        elif version == 2:
            f.read(4)
            f.read(20)
            last_ms = struct.unpack('<I', f.read(4))[0]
            note_count = struct.unpack('<I', f.read(4))[0]
            marker_count = struct.unpack('<I', f.read(4))[0]

            difficulty = struct.unpack('<B', f.read(1))[0]
            map_rating = struct.unpack('<H', f.read(2))[0]
            contains_audio = struct.unpack('<?', f.read(1))[0]
            contains_cover = struct.unpack('<?', f.read(1))[0]
            requires_mod = struct.unpack('<?', f.read(1))[0]

            custom_data_offset = struct.unpack('<Q', f.read(8))[0]
            custom_data_length = struct.unpack('<Q', f.read(8))[0]
            audio_offset = struct.unpack('<Q', f.read(8))[0]
            audio_length = struct.unpack('<Q', f.read(8))[0]
            cover_offset = struct.unpack('<Q', f.read(8))[0]
            cover_length = struct.unpack('<Q', f.read(8))[0]
            marker_definitions_offset = struct.unpack('<Q', f.read(8))[0]
            marker_definitions_length = struct.unpack('<Q', f.read(8))[0]
            marker_offset = struct.unpack('<Q', f.read(8))[0]
            marker_length = struct.unpack('<Q', f.read(8))[0]

            def read_varstr(four_bytes=False):
                length = struct.unpack('<I' if four_bytes else '<H', f.read(4) if four_bytes else f.read(2))[0]
                return f.read(length).decode('utf-8')

            map_id = fix_id(read_varstr())
            map_name = read_varstr()
            song_name = read_varstr()
            mapper_count = struct.unpack('<H', f.read(2))[0]
            mappers = [read_varstr() for _ in range(mapper_count)]

            output['map_id'] = map_id
            output['map_name'] = map_name
            output['mappers'] = "\n".join(mappers)

            f.seek(marker_definitions_offset)
            num_defs = struct.unpack('<B', f.read(1))[0]

            has_notes = False
            for i in range(num_defs):
                definition = read_varstr()
                if i == 0 and definition == "ssp_note":
                    has_notes = True
                num_values = struct.unpack('<B', f.read(1))[0]
                while True:
                    data = f.read(1)[0]
                    if data == 0:
                        break

            if not has_notes:
                output['notes'] = []
                return output

            f.seek(marker_offset)
            notes = []
            for _ in range(note_count):
                ms = struct.unpack('<I', f.read(4))[0]
                marker_type = struct.unpack('<B', f.read(1))[0]
                is_quantum = struct.unpack('<?', f.read(1))[0]

                if is_quantum:
                    x = struct.unpack('<f', f.read(4))[0]
                    y = struct.unpack('<f', f.read(4))[0]
                else:
                    x = struct.unpack('<B', f.read(1))[0]
                    y = struct.unpack('<B', f.read(1))[0]

                notes.append((x, y, int(ms / speed_multiplier)))

        else:
            raise ValueError("Unsupported SSPM version")

        notes.sort(key=lambda note: note[2])
        output['notes'] = notes
        return output

def save_as_txt(data, txt_path):
    with open(txt_path, 'w', encoding='utf-8') as f:
        for x, y, ms in data.get('notes', []):
            f.write(f"{x}|{y}|{ms}\n")
        f.write("\n\n")
        f.write(f"# Total Notes: {len(data.get('notes', []))}\n")

# UI section
def browse_file():
    filepath = filedialog.askopenfilename(filetypes=[("SSPM files", "*.sspm")])
    if filepath:
        entry_file.delete(0, tk.END)
        entry_file.insert(0, filepath)

def convert_file():
    sspm_path = entry_file.get()
    try:
        speed = float(entry_speed.get())
    except ValueError:
        messagebox.showerror("Invalid Speed", "Please enter a valid number for speed.")
        return

    if not sspm_path.endswith(".sspm"):
        messagebox.showerror("Invalid File", "Please choose a .sspm file.")
        return

    txt_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
    if not txt_path:
        return

    try:
        data = parse_sspm(Path(sspm_path), speed)
        save_as_txt(data, Path(txt_path))
        messagebox.showinfo("Success", f"Converted and saved to:\n{txt_path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# Build UI
root = tk.Tk()
root.title("SSPM to TXT Converter with Speed Modifier")

tk.Label(root, text="SSPM File:").grid(row=0, column=0, sticky="w")
entry_file = tk.Entry(root, width=40)
entry_file.grid(row=0, column=1)
tk.Button(root, text="Browse", command=browse_file).grid(row=0, column=2)

tk.Label(root, text="Speed Multiplier:").grid(row=1, column=0, sticky="w")
entry_speed = tk.Entry(root)
entry_speed.insert(0, "1.0")
entry_speed.grid(row=1, column=1)

tk.Button(root, text="Convert", command=convert_file).grid(row=2, column=1, pady=10)

root.mainloop()
