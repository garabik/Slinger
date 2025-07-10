# Slinger

This is a forked version of the original Slinger, software that allows you to connect to Slingboxes. For details, please refer to the original README-original.md documentation.

This forked version implements remuxing the video stream into the mp4 container, with the sole purpose of allowing playback on web browsers.

This assumes you already have the original Slinger installed and working. 


## Installation


Please follow the original Slinger instructions, prepare the `config.ini file.

You need ffmpeg and ffmpeg-python (*not* python-ffmpeg!)

On Debian, you can install them using following commands:

    apt-get install ffmpeg
    pip install --break-system-packages ffmpeg-python # or setup a venv -- this is out of scope of this documentation

On Fedora:
    sudo dnf install python3-ffmpeg-python


This should be a drop-in replacement and by default, it should work in the same way.

The web player is in the file webplay.html, make sure it is in the same directory as the slingbox-server.py.

Now, point your web browser to http://localhost:8080/webplay.html
