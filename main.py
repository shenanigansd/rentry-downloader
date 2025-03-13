import tkinter

from tkinter import *

from tkinter.messagebox import showerror
from tkinter.filedialog import asksaveasfilename
from tkinter.ttk import *

from pathlib import Path

import requests, string, re


key_path = Path("./api-key.txt")

USER_AGENT = "Bast-Rentry-Raw-Fetcher/0.2"


def load_key():
    if not key_path.exists():
        return ""

    data = key_path.read_text()
    if not data.startswith("api-key:"):
        if data:
            showerror("API Key Read Error", "Something invalid is in the api key file!")
            exit(1)

        return ""

    return data.removeprefix("api-key:").strip()


def set_key():
    global api_key
    key = key_entry_var.get().strip()
    print(key)
    api_key = key

    key_path.write_text("api-key: " + key)

    key_entry_var.set("*"*len(key))


# Make sure to keep state alive, tkinter is bad about reference counting...
preview = 0
previews = {}

def do_download():
    global preview
    preview += 1
    target_page = link_entry.get().strip()
    print("Do download:", api_key, target_page)

    parsed = re.fullmatch(r"https?://rentry.co/(\w+)(/raw)?", target_page)
    if not parsed:
        if not set(target_page) - set(string.ascii_letters):
            parsed_id = target_page
        else:

            showerror("URL Invalid", repr(target_page) + " is not a valid rentry url")
            return
    else:
        parsed_id = parsed.group(1)

    to_fetch = "https://rentry.co/" + parsed_id + "/raw"

    r = requests.get(to_fetch, headers={"rentry-auth": api_key, "User-Agent": USER_AGENT})

    if r.status_code != 200:
        showerror("Rentry returned status code", str(r.status_code) + "for url " + to_fetch)
        return

    data = r.text

    if len(data.strip()) == 0:
        showerror("Empty download", "The fetched file is empty?")
        return

    file_name = get_first_line_filename(data) + ".md"


    preview_window = Toplevel(root, takefocus=True)
    preview_window.title("Preview of " + file_name)
    preview_frame = Frame(preview_window)
    preview_frame.pack()
    preview_text = Text(preview_frame)
    preview_text.pack()
    preview_text.insert("1.0", data[:2000])
    preview_text.config(state="disabled")

    def do_save():
        dest = asksaveasfilename(confirmoverwrite=True, defaultextension=".md", initialfile=file_name)
        if not dest:
            return

        written = Path(dest).write_text(data)
        print("Successful:", written, "bytes written")
        status_var.set(f"Saved {written} bytes!")
        preview_window.destroy()
        del previews[preview]

    def do_reject():
        status_var.set("Rejected")
        preview_window.destroy()
        del previews[preview]

    reject_button = Button(preview_frame, text="Reject", command=do_reject)
    reject_button.pack()
    save_button = Button(preview_frame, state="active", text="Save", command=do_save)
    save_button.pack()
    save_button.focus_set()

    preview_window.bind("<Return>", lambda e: do_save())
    preview_window.bind("<space>", lambda e: do_save())
    preview_window.bind("<Escape>", lambda e: do_reject())
    previews[preview] = [preview_window, preview_frame, preview_text, reject_button, save_button]

def get_first_line_filename(file_content: str) -> str:
    GOOD_CHARS = string.ascii_letters + string.digits
    # Characters that can't be on either end
    PERMISSIBLE_CHARS = "-_. "
    VALID_CHARS = GOOD_CHARS + PERMISSIBLE_CHARS

    for line in file_content.splitlines(False):
        if not line.strip():
            continue

        valid_chars = [i for i in line if i in GOOD_CHARS]

        if len(valid_chars) < 2:
            continue

        filename = ''.join(i if i in VALID_CHARS else "_" for i in line).strip(PERMISSIBLE_CHARS)
        return filename


api_key = load_key()


root = Tk()
root.title("Rentry Downloader")
# root.geometry("300x300")

frame = Frame(root, padding=10, width=400, height=600)
frame.grid()

Label(frame, text="Paste:", justify="left").grid(column=0, row=0)
link_entry = Entry(frame)
link_entry.grid(column=0, row=1)


status_var = StringVar()
status_var.set("ready")
Label(frame, textvariable=status_var, justify="left").grid(column=0, row=2)

Label(frame, text="API Key:", justify="left").grid(column=0, row=3)
key_entry_var = StringVar()
key_entry_var.set("*"*len(api_key))


key_entry = Entry(frame, textvariable=key_entry_var)
key_entry.grid(column=0, row=4)

Button(frame, text="🔒", command=set_key).grid(column=1, row=4)
key_entry.bind("<Return>", lambda e: set_key())


Button(frame, text="Download Raw", command=do_download).grid(column=0, row=6)
link_entry.bind("<Return>", lambda e: do_download())

root.mainloop()
