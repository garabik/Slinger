# Slinger web player

**Beware**: this is in very early stage, it is not well tested, and it may not work for you. And this documentation is somewhat sketchy.

This is a forked version of the original Slinger, software that allows you to connect to Slingboxes. For details, please refer to the original README-original.md documentation.

This forked version implements remuxing the video stream into the mp4 container, with the sole purpose of allowing playback on web browsers.

This assumes you already have the original Slinger installed and working. 


## Installation


Please follow the original Slinger instructions, prepare the `config.ini` file.

You need ffmpeg and ffmpeg-python (*not* python-ffmpeg!)

On Debian, you can install them using following commands:

```
apt-get install ffmpeg
pip install --break-system-packages ffmpeg-python # or setup a venv -- this is out of scope of this documentation
```

On Fedora:

```
sudo dnf install python3-ffmpeg-python
```

On Android + Termux:

```
pkg install ffmpeg
pip install --break-system-packages ffmpeg-python
```

This should be a drop-in replacement for the original Slingerserver and by default, it should work in the same way.

The web player is in the file webplay.html, make sure it is in the same directory as the slingbox_server.py, and you need a python moddule rewrap.py (in the same directory).


## Usage

To connect to the Slinger server, point your web browser to http://localhost:8080/webplay.html (as usual, replace `localhost` and `8080` with your configured values, if different).

If you use multiple slingbox setup (in your config.ini), use http://localhost:8080/webplay.html?slingbox_id=nameofyourslingbox.

Clicking on the video (even if not playing) will toggle remote control and video controls (the ugly buttons at the bottom). This can be toggled also by the TAB key on the keyboard.

Double click will toggle fullscreen mode.

Since video autoplay is finicky, I opted for manual start with the Play button (in the ugly control area at the bottom). This will take a while (watch the slingbox_server.py output for any problems, especially the first time). Clicking Play again will pause the video, and clicking it once more will resume playing. Note that this will increase the remote control lag accordingly. To go back to live streaming, click on the Stop button and then again on the Play/pause one. If you encounter problems (disconnect etc.), repeat the Stop and Play sequence.

You can also force a resolution or a bitrate, by appending '?resolution=N' or '?bitrate=N' to the URL.
For example, to force resolution 320x240 and bitrate 500kbps, use `http://localhost:8080/webplay.html?slingbox_id=nameofyourslingbox&resolution=1&bitrate=500` (this will work only if there is no other stream playing). Or you can expand the `Opts` button and select the resolution and bitrate there (if playing, you have to Stop and Play the video to apply the changes).


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

These keys follow my remote, but they should be somewhat sensible for a range of remote types. If you need to change them, edit the keyMap.set definitions at the top of `webplay.html`.

For touchscreen devices, swiping your finger up/down sends the up/down events (i.e. switch channels). Because on some mobile browsers swiping down reloads the page, you can also (somewhat confusingly) swipe left/right to switch channels.

Dragging your finger along the right border will change the volume.

### Powering on

If your remote device is powered off and you need the remote to power it on, there is an interesting Catch-22 situation. This is not specific to this web player, but it happens with the Slinger player as well (just less pronounced).
`slingbox-server.py` will not send any remote events before the player connects, so if you just click on the Power button and then start the video, the Power button will be ignored. So the typical chain of events is:

1. You open the player (be it this web player or something else)
2. You start streaming (e.g. by clicking on the Play button)
3. Slingbox will deliver the stream without the video track
4. The player (usually powered by ffmpeg) will buffer some data, looking for the video, and then gives up and hangs
5. The player disconnects from the Slinger server
6. Any subsequent attempt to press the Power button will be ignored.

Fortunately, there is enough time (10 seconds or so) between the points 4. and 5. where you can use the remote... If you miss the window, hit the Stop button and then Play and try again. However, even if you powered on the device, the player has already ingested some packets without the video track, and will hang (and then disconnect) again. So you will have to repeat the Stop and Play sequence again, or even reload the webpage, and then it should work. Unfortunately, there is no visual feedback.



The modified slinger server is still backward compatible, you can use it the usual way, including Slinger player. You can also stream to several clients as usual.

The remuxed stream in mp4 container is available at `http://localhost:8080/slingbox?remux=1` (replace `localhost`, port and `slingbox` with your values, if different from the default and/or running the server remotely). You can connect to multiple streams, remuxed or not. Each remuxed stream will launch one `ffmpeg` process, because sharing a `mp4` header between streams is nontrivial (read: I was not able to implement it). Fortunately, `ffmpeg` muxing is cheap.

These are the parameters you can use:

 * `remux=1` - remux this stream into mp4 container
 * `dummy=anything` - will be ignored, this was my attempt at mitigating caching issues
 * `resolution=N` - force resolution number `N` (see README-slinger.md for the list of resolutions)
 * `bitrate=N` - force bitrate in kbps

Anything else will be interpreted as the initial channel, for backward compatibility. Selecting bitrate and resolution works only if there is no other stream playing (remuxed or no).

## Notes

What I intended to be a quick&dirty hack turned out to be more complicated and lead me through the rabbit hole of html5 `<video>` tag quirks and limitations. 

I had to modity the original `slingbox-server.py` somewhat more than I expected, and I had to put a lot of javascript to the web player to make it usable. The code is full of hacks and workarounds - it is not an elegant code, but at least it works for me.

Since the original stream is in h264+aac, remuxing is cheap and won't take much CPU time (I have no idea if Slingbox Classic is capable of h264, or just WM9). In particular, there are no resource problems with running it on any recent-ish Android mobile phone or tablet. On my old Intel Celeron N3050 1.60GHz notebook the `slingbox_server.py` takes about 20-30% CPU time, the browser playing the video takes another 20-30%, the remuxing less than 1%.

The latency is horrible - I used the standard tricks when remuxing the stream and pushing it to the client, but it still adds some latency, and on top of that web browser buffers the video quite a lot.

This has been tested only with Slingbox Pro HD.

