import ffmpeg
import threading
import os
import time

class Mp4Rewrapper:
    def __init__(self):
        # Start ffmpeg: read from pipe:0, write to pipe:1
        # - copy the codec (no re-encode): vcodec='copy'
        # - produce a fragmented MP4 (allows streaming): movflags='frag_keyframe+empty_moov+default_base_moof'
        print('*** Initializing mp4 remuxer')
        self.proc = (
            ffmpeg
            .input('pipe:0',
                   format="asf")
           .output('pipe:1',
                    format='mp4',
                    pix_fmt='yuv420p',
                    sample_fmt='fltp',
                    vcodec='copy',
                    acodec='copy',
                    # these two options are not present in older ffmpeg versions
                    # drop_pkts_on_overflow=True,
                    # attempt_recovery=True,
                    fflags='nobuffer+genpts+discardcorrupt+flush_packets',
                    #fflags='nobuffer+discardcorrupt+flush_packets',
                    flags='+global_header',
                    probesize=32,
                    frag_duration = 200000,  # 0.2 sec
                    movflags='frag_keyframe+empty_moov+default_base_moof+separate_moof',
                    absf='aac_adtstoasc',
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
        #print(self.lock)
        with self.lock:
            # send the next piece of raw stream
            self.proc.stdin.write(in_chunk)
            self.proc.stdin.flush()

            # read whatever MP4 data is available
            # this is nonblocking
            r = b''
            timestamp = time.time()
            while True:
                read_in =  self.proc.stdout.read(read_chunk_size)
                if read_in:
                    #print('read in', len(read_in), 'bytes')
                    r += read_in
                else:
                    # no data, assume EOF
                    break
#            if r:
#                print('==== end reading ====', len(r))
            return r


    def close(self):
        print('closing ffmpeg')
        # signal EOF to ffmpeg, let it finish writing final atoms
        with self.lock:
            self.proc.stdin.close()
        self.proc.wait()

    def __del__(self):
        print('del rewrap')
        self.close()

