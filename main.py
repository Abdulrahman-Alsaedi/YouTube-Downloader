import tkinter as tk
from tkinter import ttk, Menu, simpledialog, messagebox
import os
import threading
import yt_dlp
from PIL import Image, ImageTk
import vlc
import re
from time import sleep
import json
from datetime import datetime
import ttkbootstrap as tb
from moviepy.video.io.VideoFileClip import VideoFileClip

class SmallVideoPlayer:
    def __init__(self, root, main_app, video_path, current_time):
        self.root = root
        self.main_app = main_app
        self.video_path = video_path
        self.current_time = current_time

        # Create small video player frame with the correct size
        self.small_player_frame = ttk.Frame(self.root, width=250, height=180)
        self.small_player_frame.place(relx=1.0, rely=0.85, anchor="se")
        self.small_player_frame.pack_propagate(False)  # Prevent resizing with the content

        # Initialize VLC player
        self.instance = vlc.Instance("--no-xlib --quiet")
        self.player = self.instance.media_player_new()

        # Embed VLC player
        self.player.set_hwnd(self.small_player_frame.winfo_id())

        # Load and play the video from the current position
        if os.path.exists(video_path):
            media = self.instance.media_new(video_path)
            self.player.set_media(media)
            self.player.play()
            self.player.set_time(current_time)  # Start from current position
            self.player.audio_set_volume(self.main_app.current_volume)
            self.player.set_rate(self.main_app.current_speed)

        # Playback controls container
        self.controls_container = ttk.Frame(self.root)
        self.controls_container.place(relx=1.0, rely=0.95, anchor="se")

        # Seek bar with video time
        self.seek_bar = ttk.Scale(self.controls_container, from_=0, to=self.player.get_length(), orient="horizontal", command=self.on_seek)
        self.seek_bar.pack(fill=tk.X, padx=5)
        self.time_label = ttk.Label(self.controls_container, text="00:00 / 00:00")
        self.time_label.pack(side=tk.LEFT, padx=5)

        # Playback controls

        self.skip_backward_button = ttk.Button(self.controls_container, text="⏪", command=lambda: self.skip_video(-5000))
        self.skip_backward_button.pack(side=tk.LEFT, padx=5)

        self.play_button = ttk.Button(self.controls_container, text="⏯️", command=self.toggle_play_pause)
        self.play_button.pack(side=tk.LEFT, padx=5)

        self.skip_forward_button = ttk.Button(self.controls_container, text="⏩", command=lambda: self.skip_video(5000))
        self.skip_forward_button.pack(side=tk.LEFT, padx=5)

        self.close_button = ttk.Button(self.controls_container, text="❌", command=self.close_video)
        self.close_button.pack(side=tk.LEFT, padx=5)

        # Maximize button with ↗️ icon
        self.maximize_button = ttk.Button(self.controls_container, text="↗️", command=self.switch_to_main_player)
        self.maximize_button.pack(side=tk.LEFT, padx=5)

        # Double-click to switch back to main player
        self.small_player_frame.bind("<Double-1>", self.switch_to_main_player)

        # Update seek bar and time label
        self.update_seek_bar()

    def toggle_play_pause(self):
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def skip_video(self, milliseconds):
        current_time = self.player.get_time()
        self.player.set_time(current_time + milliseconds)

    def close_video(self):
        self.player.stop()
        self.small_player_frame.destroy()
        self.controls_container.destroy()

    def switch_to_main_player(self, event=None):
        current_time = self.player.get_time()
        self.player.stop()
        self.small_player_frame.destroy()
        self.controls_container.destroy()
        self.main_app.play_video(self.video_path, current_time)

    def on_seek(self, value):
        """Seek to a specific position in the video."""
        self.player.set_time(int(float(value)))

    def update_seek_bar(self):
        """Update the seek bar and time label."""
        if self.player and self.seek_bar.winfo_exists():
            current_time = self.player.get_time()
            self.seek_bar.config(to=self.player.get_length(), value=current_time)
            self.time_label.config(text=f"{self.format_time(current_time)} / {self.format_time(self.player.get_length())}")
        self.root.after(1000, self.update_seek_bar)

    def format_time(self, milliseconds):
        """Convert milliseconds to a formatted time string (MM:SS)."""
        seconds = int(milliseconds / 1000)
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02}:{seconds:02}"
        
class VideoDownloaderApp:
    # Initialize volume_label in __init__
    def __init__(self, root):
        self.root = root
        self.root.title("Video Downloader")
        self.root.geometry("1000x700")
        
        # Load settings
        self.settings_file = "settings.json"
        self.settings = self.load_settings()
        self.is_dark_mode = self.settings.get("dark_mode", False)

        # Apply ttkbootstrap theme
        self.style = tb.Style(theme="darkly" if self.is_dark_mode else "cosmo")

        # Default download folder
        self.download_folder = "Downloads"
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)

        # VLC player instance
        self.instance = vlc.Instance("--no-xlib --quiet")
        self.player = None
        self.is_playing = False
        self.video_length = 0
        self.current_volume = 100
        self.current_speed = self.settings.get("playback_speed", 1.0) # Default playback speed
        self.skip_seconds = self.settings.get("skip_seconds", 5000) # Default skip duration in milliseconds (5 seconds)

        # Download history
        self.history_file = "download_history.json"
        self.load_history()

        # Navigation bar
        self.create_navigation_bar()

        # Main content area
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Show home page by default
        self.show_home_page()

        # Keyboard shortcuts
        self.add_keyboard_shortcuts()
        
        # Initialize volume_label here
        self.volume_label = ttk.Label(self.main_frame, text=f"🔊 {self.current_volume}%")

    def load_settings(self):
        """Load settings from a JSON file."""
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as f:
                return json.load(f)
        else:
            return {"dark_mode": False, "playback_speed": 1.0, "skip_seconds": 5000}

    def save_settings(self):
        """Save settings to a JSON file."""
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f, indent=4)

    # def toggle_dark_mode(self):
    #     """Toggle between light and dark mode."""
    #     self.is_dark_mode = not self.is_dark_mode
    #     self.settings["dark_mode"] = self.is_dark_mode
    #     self.save_settings()

    #     # Apply the dark mode theme or light mode theme
    #     if self.is_dark_mode:
    #         # Dark mode colors
    #         self.style.theme_use("darkly")  # Use a dark theme as a base
    #         self.style.configure('TFrame', background='#3A3B3C')  # Main background
    #         self.style.configure('TLabel', background='#3A3B3C', foreground='white')  # Labels
    #         self.style.configure('TButton', background='#4A4B4C', foreground='white')  # Buttons
    #         self.style.configure('TEntry', fieldbackground='#4A4B4C', foreground='white')  # Entry fields
    #         self.style.configure('TCombobox', fieldbackground='#4A4B4C', foreground='white')  # Dropdowns
    #         self.style.configure('TProgressbar', background='#4A4B4C')  # Progress bars
    #     else:
    #         # Light mode colors
    #         self.style.theme_use("cosmo")  # Use a light theme as a base
    #         self.style.configure('TFrame', background='white')  # Main background
    #         self.style.configure('TLabel', background='white', foreground='black')  # Labels
    #         self.style.configure('TButton', background='#3498DB', foreground='black')  # Buttons
    #         self.style.configure('TEntry', fieldbackground='white', foreground='black')  # Entry fields
    #         self.style.configure('TCombobox', fieldbackground='white', foreground='black')  # Dropdowns
    #         self.style.configure('TProgressbar', background='#3498DB')  # Progress bars

    #     # Update the UI to reflect the new theme
    #     self.update_theme()

    def update_theme(self):
        """Update the theme for all widgets without resetting the page."""
        # Update the main frame and its children
        for widget in self.main_frame.winfo_children():
            self.update_widget_colors(widget)

    def update_widget_colors(self, widget):
        """Recursively update widget colors."""
        if isinstance(widget, (ttk.Label, ttk.Button, ttk.Radiobutton, ttk.Entry, ttk.Combobox)):
            widget.configure(style="TLabel" if isinstance(widget, ttk.Label) else "TButton")
        elif isinstance(widget, ttk.Frame):
            for child in widget.winfo_children():
                self.update_widget_colors(child)

    def create_navigation_bar(self):
        """Create the navigation bar at the top of the application."""
        nav_frame = ttk.Frame(self.root)
        nav_frame.pack(side=tk.TOP, fill=tk.X)

        # Navigation buttons
        self.home_button = ttk.Button(nav_frame, text="🏠 Home", command=self.show_home_page)
        self.home_button.pack(side=tk.LEFT, padx=10, pady=5)

        self.downloads_button = ttk.Button(nav_frame, text="📂 Downloads", command=self.show_downloads_page)
        self.downloads_button.pack(side=tk.LEFT, padx=10, pady=5)

        self.history_button = ttk.Button(nav_frame, text="📜 History", command=self.show_history_page)
        self.history_button.pack(side=tk.LEFT, padx=10, pady=5)

        self.settings_button = ttk.Button(nav_frame, text="⚙️ Settings", command=self.show_settings_page)
        self.settings_button.pack(side=tk.LEFT, padx=10, pady=5)

    def show_home_page(self):
        """Display the home page with URL input, quality options, and download controls."""
        self.current_page = "home"  # Track the current page
        # Clear the main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # URL input
        self.url_label = ttk.Label(self.main_frame, text="Enter Video URL:", style="TLabel")
        self.url_label.pack(pady=5)

        self.url_entry = ttk.Entry(self.main_frame, width=70, style="TEntry")
        self.url_entry.pack(pady=5)

        self.search_button = ttk.Button(self.main_frame, text="🔍 Search", command=self.search_video, style="TButton")
        self.search_button.pack(pady=10)

        # Video quality options
        self.quality_frame = ttk.Frame(self.main_frame, style="TFrame")
        self.quality_frame.pack(pady=10)

        self.quality_label = ttk.Label(self.quality_frame, text="Select Quality:", style="TLabel")
        self.quality_label.pack()

        self.quality_var = tk.StringVar(value="720p")
        self.quality_options = ["480p", "720p", "1080p", "Audio Only"]
        for option in self.quality_options:
            ttk.Radiobutton(self.quality_frame, text=option, variable=self.quality_var, value=option, style="TRadiobutton").pack()

        # Download button
        self.download_button = ttk.Button(self.main_frame, text="⬇️ Download", command=self.start_download, style="TButton")
        self.download_button.pack(pady=10)

        # Progress bar
        self.progress_bar = ttk.Progressbar(self.main_frame, orient="horizontal", length=400, mode="determinate", style="TProgressbar")
        self.progress_bar.pack(pady=10)

        # Status label
        self.status_label = ttk.Label(self.main_frame, text="Status: Ready", style="TLabel")
        self.status_label.pack(pady=5)

    def search_video(self):
        """Search for video information using the provided URL."""
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "Please enter a valid URL.")
            return

        try:
            ydl_opts = {}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                video_title = info_dict.get('title', None)
                formats = info_dict.get('formats', None)

                if video_title:
                    self.status_label.config(text=f"Found: {video_title}")
                else:
                    self.status_label.config(text="No video found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch video info: {e}")

    def start_download(self):
        """Start downloading the video with the selected quality."""
        url = self.url_entry.get()
        quality = self.quality_var.get()

        if not url:
            messagebox.showerror("Error", "Please enter a valid URL.")
            return

        def download_thread():
            try:
                ydl_opts = {
                    'format': 'bestvideo[height<=?1080]+bestaudio/best' if quality != "Audio Only" else 'bestaudio/best',
                    'outtmpl': os.path.join(self.download_folder, '%(title)s.%(ext)s'),
                    'progress_hooks': [self.progress_hook],
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)
                    video_title = info_dict.get('title', 'video')
                    video_ext = info_dict.get('ext', 'mp4')
                    video_path = os.path.join(self.download_folder, f"{video_title}.{video_ext}")

                    # Generate thumbnail
                    thumbnail_path = os.path.join(self.download_folder, f"{video_title}.jpg")
                    self.generate_thumbnail(video_path, thumbnail_path)

                    # Add to history
                    self.add_to_history(video_title, url, quality)

                self.status_label.config(text="Download complete!")
                self.progress_bar['value'] = 0
            except Exception as e:
                messagebox.showerror("Error", f"Download failed: {e}")

        threading.Thread(target=download_thread).start()

    def generate_thumbnail(self, video_path, thumbnail_path):
        """Generate a thumbnail from a video."""
        try:
            clip = VideoFileClip(video_path)
            clip.save_frame(thumbnail_path, t=1)  # Save a frame at 1 second
            clip.close()
        except Exception as e:
            print(f"Failed to generate thumbnail: {e}")

    def progress_hook(self, d):
        """Update progress bar based on download progress."""
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            if total_bytes > 0:
                progress = (downloaded_bytes / total_bytes) * 100
                self.progress_bar['value'] = progress
                self.status_label.config(text=f"Downloading: {progress:.2f}%")

    def show_downloads_page(self):
        """Display the downloads page with thumbnails of downloaded videos."""
        self.current_page = "downloads"  # Track the current page
        # Clear the main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # Refresh button
        refresh_button = ttk.Button(self.main_frame, text="🔄 Refresh", command=self.load_downloaded_videos)
        refresh_button.pack(pady=10)

        # Sort dropdown
        self.sort_var = tk.StringVar(value="Sort by Date")  # Default sort option
        sort_options = ["Sort by Name", "Sort by Date", "Sort by Size"]
        sort_dropdown = ttk.Combobox(self.main_frame, textvariable=self.sort_var, values=sort_options, state="readonly")
        sort_dropdown.bind("<<ComboboxSelected>>", self.update_sort)
        sort_dropdown.pack(pady=5)

        # Thumbnails frame
        self.thumbnails_frame = ttk.Frame(self.main_frame)
        self.thumbnails_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Load downloaded videos
        self.load_downloaded_videos()

    def update_sort(self, event=None):
        """Update the sort method and reload the videos."""
        sort_by = self.sort_var.get().split(" ")[-1].lower()
        self.load_downloaded_videos(sort_by)

    def rename_video(self, old_path, new_name):
        """Rename a video file and update the display."""
        new_path = os.path.join(self.download_folder, new_name + os.path.splitext(old_path)[1])
        old_thumbnail = os.path.splitext(old_path)[0] + ".jpg"
        new_thumbnail = os.path.splitext(new_path)[0] + ".jpg"
        
        try:
            os.rename(old_path, new_path)
            if os.path.exists(old_thumbnail):
                os.rename(old_thumbnail, new_thumbnail)
            self.load_downloaded_videos()  # Reload videos after renaming
            self.show_notification("Video renamed successfully!", "green")
        except Exception as e:
            self.show_notification(f"Failed to rename video: {e}", "red")




    from tkinter import Label  # Import tk.Label

    def load_downloaded_videos(self, sort_by="date"):
        """Load and display thumbnails of downloaded videos."""
        # Clear the thumbnails frame
        for widget in self.thumbnails_frame.winfo_children():
            widget.destroy()

        # Load downloaded videos and sort them
        videos = []
        for file in os.listdir(self.download_folder):
            if file.endswith((".mp4", ".mkv", ".webm")):
                video_path = os.path.join(self.download_folder, file)
                thumbnail_path = os.path.join(self.download_folder, os.path.splitext(file)[0] + ".jpg")
                video_info = {
                    "name": file,
                    "path": video_path,
                    "thumbnail": thumbnail_path,
                    "date": os.path.getmtime(video_path),
                    "size": os.path.getsize(video_path)
                }
                videos.append(video_info)

        # Sort videos based on the selected criteria
        if sort_by == "name":
            videos.sort(key=lambda x: x["name"])
        elif sort_by == "size":
            videos.sort(key=lambda x: x["size"], reverse=True)
        else:  # Default is by date
            videos.sort(key=lambda x: x["date"], reverse=True)

        # Display sorted videos
        for video in videos:
            video_frame = ttk.Frame(self.thumbnails_frame, style="TFrame")
            video_frame.pack(side=tk.LEFT, padx=10, pady=10)

            try:
                if os.path.exists(video["thumbnail"]):
                    thumbnail = ImageTk.PhotoImage(Image.open(video["thumbnail"]).resize((160, 90)))
                    thumbnail_label = ttk.Label(video_frame, image=thumbnail, style="TLabel")
                    thumbnail_label.image = thumbnail  # Keep a reference
                    thumbnail_label.pack()
                else:
                    thumbnail_label = None

                # Add fallback for the thumbnail_label if it's None
                if thumbnail_label is None:
                    placeholder_frame = ttk.Frame(video_frame, height=90, width=160, style="TFrame")
                    placeholder_frame.pack_propagate(False)
                    placeholder_frame.pack()
                    placeholder = ttk.Label(placeholder_frame, text="No Thumbnail", style="TLabel")
                    placeholder.pack(fill=tk.BOTH, expand=True)
                    thumbnail_label = placeholder

                video_name = os.path.splitext(video["name"])[0]
                name_label = ttk.Label(video_frame, text=video_name, style="TLabel")
                name_label.pack()

                # Bind context menu and play video events
                thumbnail_label.bind("<Button-3>", lambda e, path=video["path"]: self.show_context_menu(e, path))
                thumbnail_label.bind("<Button-1>", lambda e, path=video["path"]: self.play_video(path))

            except Exception as e:
                print(f"Failed to load thumbnail: {e}")
                placeholder_frame = ttk.Frame(video_frame, height=90, width=160, style="TFrame")
                placeholder_frame.pack_propagate(False)
                placeholder_frame.pack()
                placeholder = ttk.Label(placeholder_frame, text="No Thumbnail", style="TLabel")
                placeholder.pack(fill=tk.BOTH, expand=True)

                video_name = os.path.splitext(video["name"])[0]
                name_label = ttk.Label(video_frame, text=video_name, style="TLabel")
                name_label.pack()

                # Bind context menu and play video events
                placeholder.bind("<Button-3>", lambda e, path=video["path"]: self.show_context_menu(e, path))
                placeholder.bind("<Button-1>", lambda e, path=video["path"]: self.play_video(path))



    def show_context_menu(self, event, video_path):
        """Show the context menu for video options."""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Rename", command=lambda: self.prompt_rename(video_path))
        menu.add_command(label="Delete", command=lambda: self.delete_video(video_path))
        menu.tk_popup(event.x_root, event.y_root)

    def prompt_rename(self, video_path):
        """Prompt the user to enter a new name for the video."""
        new_name = simpledialog.askstring("Rename Video", "Enter new video name:", parent=self.root)
        if new_name:
            self.rename_video(video_path, new_name)

    def delete_video(self, video_path):
        """Delete the selected video."""
        try:
            os.remove(video_path)
            self.load_downloaded_videos()  # Reload videos after deletion
            self.show_notification("Video deleted successfully!", "green")
        except Exception as e:
            self.show_notification(f"Failed to delete video: {e}", "red")


    def show_history_page(self):
        """Display the download history page."""
        self.current_page = "history"  # Track the current page
        # Clear the main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # Display history
        for entry in self.download_history:
            history_label = ttk.Label(self.main_frame, text=f"{entry['title']} - {entry['quality']} - {entry['timestamp']}")
            history_label.pack(pady=5)

    def show_settings_page(self):
        """Display the settings page."""
        self.current_page = "settings"  # Track the current page
        # Clear the main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # # Dark mode toggle button
        # self.dark_mode_button = ttk.Button(self.main_frame, text="🌙 Dark Mode", command=self.toggle_dark_mode)
        # self.dark_mode_button.pack(pady=20)

        # Skip seconds dropdown
        self.skip_seconds_label = ttk.Label(self.main_frame, text="Skip Seconds:")
        self.skip_seconds_label.pack(pady=5)

        self.skip_seconds_var = tk.StringVar(value=f"{self.skip_seconds // 1000}s")  # Default value
        self.skip_seconds_options = ["5s", "10s", "15s", "20s", "30s"]
        self.skip_seconds_dropdown = ttk.Combobox(self.main_frame, textvariable=self.skip_seconds_var, values=self.skip_seconds_options)
        self.skip_seconds_dropdown.pack(pady=5)

        # Save skip seconds button
        self.save_skip_seconds_button = ttk.Button(self.main_frame, text="Save Skip Seconds", command=self.save_skip_seconds)
        self.save_skip_seconds_button.pack(pady=10)


    def save_skip_seconds(self):
        """Save the selected skip seconds value."""
        selected_value = self.skip_seconds_var.get()
        if selected_value.endswith("s"):
            try:
                seconds = int(selected_value[:-1])  # Remove 's' and convert to integer
                self.skip_seconds = seconds * 1000  # Convert to milliseconds
                self.settings["skip_seconds"] = self.skip_seconds
                self.save_settings()
                self.show_notification(f"Skip seconds set to {selected_value}", "green")
            except ValueError:
                self.show_notification("Invalid skip seconds value", "red")
        else:
            self.show_notification("Invalid skip seconds format", "red")

    def save_playback_speed(self):
        """Save the selected playback speed."""
        selected_value = self.speed_var.get()
        if selected_value == "Normal":
            speed = 1.0  # Default speed for "Normal"
        else:
            # Remove 'x' and convert to float (e.g., "0.5x" -> 0.5)
            speed = float(selected_value.rstrip("x"))

        # Update playback speed
        self.current_speed = speed
        self.settings["playback_speed"] = self.current_speed
        self.save_settings()
        if self.player:
            self.player.set_rate(self.current_speed)
        self.show_notification(f"Playback speed set to {selected_value}", "green")

    def play_video(self, video_path, current_time=0):
        """Play the selected video using VLC."""
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        self.player_frame = ttk.Frame(self.main_frame)
        self.player_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.player = self.instance.media_player_new()

        if os.name == 'nt':  # Windows
            self.player.set_hwnd(self.player_frame.winfo_id())
        else:  # Linux/Mac
            self.player.set_xwindow(self.player_frame.winfo_id())

        if os.path.exists(video_path):  
            media = self.instance.media_new(video_path)
            self.player.set_media(media)
            self.player.play()
            self.player.set_time(current_time)  # Start from current position
            self.player.audio_set_volume(self.current_volume)  
            self.player.set_rate(self.current_speed)  
            self.is_playing = True

            sleep(0.5)  
            self.video_length = self.player.get_length()

            self.seek_bar = ttk.Scale(self.main_frame, from_=0, to=self.video_length, orient="horizontal", command=self.on_seek)
            self.seek_bar.pack(fill=tk.X, padx=10, pady=10)

            self.time_label = ttk.Label(self.main_frame, text="00:00 / 00:00")
            self.time_label.pack()

            control_frame = ttk.Frame(self.main_frame)
            control_frame.pack(pady=10)


            self.skip_backward_button = ttk.Button(control_frame, text=f"⏪ {self.skip_seconds // 1000}s", command=lambda: self.skip_video(-self.skip_seconds))
            self.skip_backward_button.pack(side=tk.LEFT, padx=5)

            self.play_button = ttk.Button(control_frame, text="⏯️", command=self.toggle_play_pause)
            self.play_button.pack(side=tk.LEFT, padx=5)

            self.skip_forward_button = ttk.Button(control_frame, text=f"⏩ {self.skip_seconds // 1000}s", command=lambda: self.skip_video(self.skip_seconds))
            self.skip_forward_button.pack(side=tk.LEFT, padx=5)

            self.volume_slider = ttk.Scale(control_frame, from_=0, to=100, orient="horizontal", command=self.update_volume)
            self.volume_slider.set(self.current_volume)
            self.volume_slider.pack(side=tk.LEFT, padx=5)

            self.volume_label = ttk.Label(control_frame, text=f"🔊 {self.current_volume}%")
            self.volume_label.pack(side=tk.LEFT, padx=5)

            self.speed_dropdown_var = tk.StringVar(value="Normal" if self.current_speed == 1.0 else f"{self.current_speed}x")
            self.speed_dropdown_options = ["0.25x", "0.5x", "0.75x", "Normal", "1.25x", "1.5x", "2.0x"]
            self.speed_dropdown = ttk.Combobox(control_frame, textvariable=self.speed_dropdown_var, values=self.speed_dropdown_options, state="readonly")
            self.speed_dropdown.pack(side=tk.LEFT, padx=5)
            self.speed_dropdown.bind("<<ComboboxSelected>>", lambda e: self.update_speed(self.speed_dropdown_var.get()))

            self.back_button = ttk.Button(control_frame, text="⬅️ Back", command=lambda: self.switch_to_small_player(video_path, self.player.get_time()))
            self.back_button.pack(side=tk.LEFT, padx=5)

            self.close_button = ttk.Button(control_frame, text="❌", command=self.close_video)
            self.close_button.pack(side=tk.LEFT, padx=5)

            self.update_seek_bar()
        else:
            self.show_notification("Video file not found!", "red")

    def switch_to_small_player(self, video_path, current_time):
        self.player.stop()
        self.small_player = SmallVideoPlayer(self.root, self, video_path, current_time)
        self.show_downloads_page()

    def update_volume(self, value):
        """Update volume based on slider position."""
        self.current_volume = int(float(value))
        
        # Ensure volume is within 0-100% range
        if self.current_volume < 0:
            self.current_volume = 0
        elif self.current_volume > 100:
            self.current_volume = 100

        if self.player:
            self.player.audio_set_volume(self.current_volume)
        
        if hasattr(self, 'volume_label') and self.volume_label.winfo_exists():
            self.volume_label.config(text=f"🔊 {self.current_volume}%")

    def close_video(self):
        """Close the video and reset the player."""
        if self.player:
            self.player.stop()
            self.player = None
            self.is_playing = False
        self.show_downloads_page()

    def on_mouse_move(self, event):
        """Show the back button when the mouse moves inside the video."""
        self.back_button.pack(side=tk.LEFT, padx=5)
        self.close_button.pack(side=tk.LEFT, padx=5)
        self.root.after(3000, self.hide_controls)

    def hide_controls(self):
        """Hide the back and close buttons."""
        self.back_button.pack_forget()
        self.close_button.pack_forget()

    def show_notification(self, message, color):
        """Show a notification in the app."""
        self.notification_label = ttk.Label(self.main_frame, text=message, foreground=color)
        self.notification_label.pack(pady=5)
        self.root.after(3000, self.notification_label.destroy)  # Hide after 3 seconds

    def update_speed(self, value):
        """Update playback speed based on the selected value."""
        try:
            if value == "Normal":
                speed = 1.0  # Default speed for "Normal"
            else:
                # Remove 'x' and convert to float (e.g., "0.5x" -> 0.5)
                speed = float(value.rstrip("x"))

            # Update playback speed
            self.current_speed = speed
            if self.player:
                self.player.set_rate(self.current_speed)
            self.show_notification(f"Playback speed set to {value}", "green")
        except ValueError:
            self.show_notification("Invalid speed value", "red")

    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self.is_playing:
            self.player.pause()
            self.is_playing = False
        else:
            self.player.play()
            self.is_playing = True

    def skip_video(self, milliseconds):
        """Skip forward or backward in the video."""
        if self.player:
            current_time = self.player.get_time()
            self.player.set_time(current_time + milliseconds)

    def on_seek(self, value):
        """Seek to a specific position in the video."""
        if self.player:
            self.player.set_time(int(float(value)))

    def update_seek_bar(self):
        """Update the seek bar and time label."""
        if self.player and self.is_playing and self.seek_bar.winfo_exists():
            current_time = self.player.get_time()
            self.seek_bar.config(value=current_time)
            self.time_label.config(text=f"{self.format_time(current_time)} / {self.format_time(self.video_length)}")
        self.root.after(1000, self.update_seek_bar)

    def format_time(self, milliseconds):
        """Convert milliseconds to a formatted time string (MM:SS)."""
        seconds = int(milliseconds / 1000)
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02}:{seconds:02}"

    def show_settings(self):
        """Display the settings page."""
        # Clear the main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # Add settings options
        self.download_path_label = ttk.Label(self.main_frame, text="Download Path:")
        self.download_path_label.pack(pady=5)

        self.download_path_entry = ttk.Entry(self.main_frame, width=50)
        self.download_path_entry.insert(0, self.download_folder)
        self.download_path_entry.pack(pady=5)

        self.save_settings_button = ttk.Button(self.main_frame, text="Save Settings", command=self.save_settings)
        self.save_settings_button.pack(pady=10)

    def save_settings(self):
        """Save user settings."""
        if hasattr(self, 'download_path_entry'):
            self.download_folder = self.download_path_entry.get()
            if not os.path.exists(self.download_folder):
                os.makedirs(self.download_folder)
            messagebox.showinfo("Success", "Settings saved!")

    def show_history_page(self):
        """Display the download history page."""
        # Clear the main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # Display history
        for entry in self.download_history:
            history_label = ttk.Label(self.main_frame, text=f"{entry['title']} - {entry['quality']} - {entry['timestamp']}")
            history_label.pack(pady=5)

    def load_history(self):
        """Load download history from a JSON file."""
        if not os.path.exists(self.history_file):
            self.download_history = []  # Initialize an empty list if the file doesn't exist
            return

        try:
            with open(self.history_file, "r") as f:
                self.download_history = json.load(f)
        except json.JSONDecodeError:
            # If the file is corrupted, initialize an empty list
            self.download_history = []
            print("Warning: download_history.json is corrupted. Initializing an empty history.")
        except Exception as e:
            # Handle other exceptions (e.g., file permissions)
            self.download_history = []
            print(f"Failed to load history: {e}")

    def add_to_history(self, title, url, quality):
        """Add a download to the history."""
        entry = {
            "title": title,
            "url": url,
            "quality": quality,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.download_history.append(entry)
        self.save_history()

    def save_history(self):
        """Save download history to a JSON file."""
        try:
            with open(self.history_file, "w") as f:
                json.dump(self.download_history, f, indent=4)
        except Exception as e:
            print(f"Failed to save history: {e}")

    def add_keyboard_shortcuts(self):
        """Add keyboard shortcuts."""
        self.root.bind("<space>", lambda e: self.toggle_play_pause())
        self.root.bind("<Left>", lambda e: self.skip_video(-5000))
        self.root.bind("<Right>", lambda e: self.skip_video(5000))
        
        # Ensure volume does not exceed 100 or fall below 0
        self.root.bind("<Up>", lambda e: self.update_volume(min(self.current_volume + 10, 100)))
        self.root.bind("<Down>", lambda e: self.update_volume(max(self.current_volume - 10, 0)))


if __name__ == "__main__":
    root = tb.Window(themename="cosmo")  # Initialize ttkbootstrap window
    app = VideoDownloaderApp(root)
    root.mainloop()