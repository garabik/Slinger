import ffmpeg
import threading
import os
import time, subprocess

class Mp4Rewrapper:
    def __init__(self):
        # Start ffmpeg: read from pipe:0, write to pipe:1
        # - copy the codec (no re-encode): vcodec='copy'
        # - produce a fragmented MP4 (allows streaming): movflags='frag_keyframe+empty_moov+default_base_moof'
        print('Initialize mp4 remuxer')
        self.proc = (
            ffmpeg
            .input('pipe:0',
                   format="asf",
                   sample_fmt='fltp',
                   flags='low_delay',
                   fflags="nobuffer+discardcorrupt+flush_packets",
                   frame_drop_threshold=1,
#                   fps_mode='cfr',
                   vsync='vfr',
                   copyts=None,

#                   fflags="nobuffer+flush_packets",
                   )
           .output('pipe:1',
                    format='mp4',
                    vcodec='copy',
                    acodec='copy',
                    # these two options are not present in older ffmpeg versions
                    # drop_pkts_on_overflow=True,
                    # attempt_recovery=True,
                    fflags='nobuffer+genpts+discardcorrupt+flush_packets',
#                    fflags='nobuffer+genpts+flush_packets',


                    flags='+global_header+low_delay',
                    probesize=32,
                    analyzeduration=0,
                    frag_duration = 100000,
                    movflags='+empty_moov+default_base_moof+separate_moof+omit_tfhd_offset',
                    flush_packets=1,
                    max_interleave_delta=200000,
                    loglevel=24,
#                    absf='aac_adtstoasc',
                    )
            .run_async(quiet=False, pipe_stdin=True, pipe_stdout=True)#, pipe_stderr=True)
        )
        self.lock = threading.Lock()  # make thread-safe if you want to write/read from multiple threads
        os.set_blocking(self.proc.stdout.fileno(), False)

    def rewrite(self, in_chunk, read_chunk_size=65536):
        """
        Feed `in_chunk` of raw video frames into ffmpeg and return all the data so far produced.
        You can call this repeatedly, and it will keep producing
        valid MP4 fragments as soon as enough input has accumulated.
        """

        with self.lock:
            # send the next piece of raw stream
            self.proc.stdin.write(in_chunk)
            self.proc.stdin.flush()

            # read whatever MP4 data is available
            # this is nonblocking
            r = b''
            while True:
                read_in = self.proc.stdout.read(read_chunk_size)
                if read_in:
                    #print('read in', len(read_in), 'bytes')
                    r += read_in
                else:
                    break
#            if r:
#                print('==== end reading ====', len(r))
            return r


    def close(self):
        print('closing ffmpeg')
        # signal EOF to ffmpeg, let it finish writing final data
        with self.lock:
            self.proc.stdin.close()
        # drain ffmpeg's stdout
        out = b''
        while True:
            chunk = self.proc.stdout.read(65536)
            if not chunk:
                break
            out += chunk
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        print('ffmpeg closed')
        return out

    def __del__(self):
        print('del rewrap')
        self.close()

