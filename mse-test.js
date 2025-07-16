// some js code to test MSE (does not quite work)

const video = document.getElementById('video');
const mediaSource = new MediaSource();
video.src = URL.createObjectURL(mediaSource);

var video_src = 'slingbox?remux=1&dummy=test';

mediaSource.addEventListener('sourceopen', onSourceOpen);

// fetches MP4 as a streaming response and pumps into MSE
async function fetchAndStream(url, sb, queue) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const reader = resp.body.getReader();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    // queue the chunk; append if possible
    queue.push(value);
    if (!sb.updating && queue.length) {
      sb.appendBuffer(queue.shift());
    }
    // tiny pause to give the video a chance to start playing
    await new Promise(r => setTimeout(r, 0));
  }
}

async function onSourceOpen() {
  const mime = 'video/mp4; codecs="avc1.64000D, mp4a.40.2"'; // for slingbox

  const sourceBuffer = mediaSource.addSourceBuffer(mime);

  // queue to hold incoming chunks when the buffer is busy
  const queue = [];

  sourceBuffer.addEventListener('updateend', () => {
    // whenever the buffer is free, append next chunk
    if (queue.length && !sourceBuffer.updating) {
      sourceBuffer.appendBuffer(queue.shift());
    }
    // trim away anything older than 5 seconds behind current playhead
    const buffered = sourceBuffer.buffered;
    if (buffered.length && video.currentTime - buffered.start(0) > 5) {
        console.log(`Trimming buffer: ${buffered.start(0)} to ${video.currentTime - 5}`);
  //    sourceBuffer.remove(buffered.start(0), video.currentTime - 5);
    }
  });

    // start fetching and appending
    await fetchAndStream(video_src, sourceBuffer, queue);
