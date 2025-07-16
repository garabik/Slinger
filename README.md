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

The web player is in the file webplay.html, make sure it is in the same directory as the slingbox-server.py, and you need a python moddule rewrap.py (in the same directory).


## Usage

To connect to the Slinger server, point your web browser to http://localhost:8080/webplay.html.

If you use multiple slingbox setup (in your config.ini), use http://localhost:8080/webplay.html?slingbox_id=nameofyourslingbox

Clicking on the video (even if not playing) will toggle remote control and video controls (the ugly buttons at the bottom).
So will pressing the TAB key.

Double click will toggle fullscreen mode.

The remote can be controlled by a keyboard, using the following keys:

 * digits 0-9
 * Enter or Space - select (OK)
 * Arrow keys
 * M - mute (remote)
 * g - EPG
 * s - satellite
 * f - favorite group
 * i - info
 * x - exit
 * p - power on/off
 * m - menu
 * PageUp, PageDown
 * R, G, B, Y (capital letters, with Shift) - red, green, blue, yellow buttons on the remote

These keys should be somewhat sensible for a range of remotes, if you need to change them, edit the keyMap.set definitions at the top of `webplay.html`.

For touchscreen devices, swiping your finger up/down sends the up/down events (i.e. switch channels); because on some mobile browsers, swiping down reloads the page, you can also swipe left/right to switch channels.

Dragging your finger along the right border will change the volume.

