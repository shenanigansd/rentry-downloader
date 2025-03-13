from __future__ import annotations

import logging
import tkinter

from tkinter import *

from tkinter.messagebox import showerror
from tkinter.filedialog import asksaveasfilename
from tkinter.ttk import *

from pathlib import Path

import requests, string, re


KEY_PATH = "./api-key.txt"
USER_AGENT = "Bast-Rentry-Raw-Fetcher/0.3"


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)



class KeyManager:
    def __init__(self, key_path: str):
        self.key_path = Path(key_path)
        self.api_key = None


    def load_key(self):
        if not self.key_path.exists():
            return ""

        data = self.key_path.read_text()
        if not data.startswith("api-key:"):
            if data:
                showerror("API Key Read Error", "Something invalid is in the api key file!")
                exit(1)

            return ""

        self.api_key = data.removeprefix("api-key:").strip()
        logger.info("Loaded api_key: %s", self.api_key)
        return self.api_key


    def set_key(self, key: str):
        # Ignore attempt to set key to placeholder value
        if set(key) == set("*"):
            logger.warning("Refusing to set api key to placeholder asterisks")
            return "*"*len(self.api_key)

        logger.info("Set api_key: %s", self.api_key)
        self.api_key = key.strip()
        self.key_path.write_text("api-key: " + self.api_key)
        return "*"*len(self.api_key)


class PreviewWindow:
    def __init__(self, main: RentryDownloader, file_name: str, data: str):
        self.root = main.root
        self.file_name = file_name
        self.data = data
        self.main = main
        self.init_gui()

    def init_gui(self):
        self.window = Toplevel(self.root, takefocus=True)
        self.window.title("Preview of " + self.file_name)

        self.frame = Frame(self.window)
        self.frame.pack()

        self.text = Text(self.frame)
        self.text.pack()
        self.text.insert("1.0", self.preview_data())
        self.text.config(state="disabled")

        self.reject_button = Button(self.frame, text="Reject", command=self.do_reject)
        self.reject_button.pack()

        self.save_button = Button(self.frame, state="active", text="Save", command=self.do_save)
        self.save_button.pack()
        self.save_button.focus_set()

        self.window.bind("<Return>", lambda e: self.do_save())
        self.window.bind("<space>", lambda e: self.do_save())
        self.window.bind("<Escape>", lambda e: self.do_reject())

    def do_save(self):
        dest = asksaveasfilename(confirmoverwrite=True, defaultextension=".md", initialfile=self.file_name)
        if not dest:
            return

        written = Path(dest).write_text(self.data)
        logger.info("Successfully wrote: %s bytes to %s", written, dest)
        self.main.set_status(f"Saved {written} bytes!")
        self.window.destroy()
        self.main.destroy_preview(self)

    def do_reject(self):
        logger.info("Preview closed without saving")
        self.main.set_status("Rejected")
        self.window.destroy()
        self.main.destroy_preview(self)

    def preview_data(self):
        return self.data[:2000]


class RentryDownloader:
    GOOD_CHARS = string.ascii_letters + string.digits
    PERMISSIBLE_CHARS = "-_. "  # Characters that can't be on either end of a filename
    VALID_CHARS = GOOD_CHARS + PERMISSIBLE_CHARS

    def __init__(self, key_path: str, user_agent: str):
        self.key_manager = KeyManager(key_path)
        self.user_agent = user_agent
        self.init_gui()
        self.preview_windows = []

    def init_gui(self):
        self.root = Tk()
        self.root.title("Rentry Downloader")
        # root.geometry("300x300")

        self.frame = Frame(self.root, padding=10, width=400, height=600)
        self.frame.grid()

        self.paste_label = Label(self.frame, text="Paste:", justify="left")
        self.paste_label.grid(column=0, row=0)

        self.link_entry = Entry(self.frame)
        self.link_entry.grid(column=0, row=1)
        self.link_entry.bind("<Return>", lambda e: self.do_download())

        self.status_var = StringVar()
        self.status_var.set("ready")

        self.status_label = Label(self.frame, textvariable=self.status_var, justify="left")
        self.status_label.grid(column=0, row=2)

        self.api_key_label = Label(self.frame, text="API Key:", justify="left")
        self.api_key_label.grid(column=0, row=3)

        self.key_entry_var = StringVar()
        self.key_entry_var.set("*"*len(self.key_manager.load_key()))

        self.key_entry = Entry(self.frame, textvariable=self.key_entry_var)
        self.key_entry.grid(column=0, row=4)
        self.key_entry.bind("<Return>", lambda e: self.set_key())

        self.lock_button = Button(self.frame, text="🔒", command=self.set_key)
        self.lock_button.grid(column=1, row=4)

        self.download_button = Button(self.frame, text="Download Raw", command=self.do_download)
        self.download_button.grid(column=0, row=6)

    def set_status(self, status: str):
        self.status_var.set(status)

    def set_key(self):
        self.key_entry_var.set(self.key_manager.set_key(self.key_entry_var.get()))

    def do_download(self):
        target_page = self.link_entry.get().strip()
        logger.info("Doing download of %s with api_key %s", target_page, self.key_manager.api_key)

        parsed = re.fullmatch(r"https?://rentry.co/(\w+)(/raw)?", target_page)
        if not parsed:
            if not set(target_page) - set(string.ascii_letters):
                parsed_id = target_page
            else:
                logger.info("Download attempt rejected: invalid/non-rentry url")
                showerror("URL Invalid", repr(target_page) + " is not a valid rentry url")
                return
        else:
            parsed_id = parsed.group(1)

        to_fetch = "https://rentry.co/" + parsed_id + "/raw"

        r = requests.get(to_fetch, headers={"rentry-auth": self.key_manager.api_key, "User-Agent": self.user_agent})

        if r.status_code != 200:
            logger.error("Download failed: rentry returned status code %s for url %s", r.status_code, to_fetch)
            showerror("Rentry returned status code", str(r.status_code) + "for url " + to_fetch)
            return

        data = r.text

        if len(data.strip()) == 0:
            logger.error("Download failed: fetched file was empty")
            showerror("Empty download", "The fetched file is empty?")
            return

        file_name = self.get_first_line_filename(data) + ".md"
        logger.info("Download successful, showing accept/reject dialog")
        self.show_preview(file_name, data)

    def show_preview(self, file_name: str, data: str):
        self.preview_windows.append(PreviewWindow(self, file_name, data))

    def destroy_preview(self, preview: PreviewWindow):
        """
        Deallocate a preview window

        This is needed because tkinter doesn't reference-count/keepalive some objects if the python
        references get garbage collected, so we ensure a root-to-leaf tether until the preview
        is no longer neccessary.
        """
        self.preview_windows.remove(preview)

    def get_first_line_filename(self, file_content: str) -> str:
        """
        Generate a filename from the beginning of the file's content
        """
        for line in file_content.splitlines(False):
            if not line.strip():
                continue

            valid_chars = [i for i in line if i in self.GOOD_CHARS]

            if len(valid_chars) < 2:
                continue

            filename = ''.join(i if i in self.VALID_CHARS else "_" for i in line).strip(self.PERMISSIBLE_CHARS)
            return filename

        return "untitled"

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    RentryDownloader(KEY_PATH, USER_AGENT).run()
