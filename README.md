# Slinger

This is a forked version of the original Slinger, software that allows you to connect to Slingboxes. For details, please refer to the original README-original.md documentation.

This forked version implements remuxing the video stream into the mp4 container, with the sole purpose of allowing playback on web browsers.

This assumes you already have the original Slinger installed and working. 


## Installation



Please install the original Slinger software first, especially the `config.ini file.

### Prerequisites

You need ffmpeg and ffmpeg-python (*not* python-ffmpeg!)

On Debian, you can install them using following commands:

    apt-get install ffmpeg
    pip install --break-system-packages ffmpeg-python # or setup a venv -- this is out of scope of this documentation

On Fedora:
    sudo dnf install python3-ffmpeg-python



