#!/usr/bin/env python
import sys
import os
import socket
import sys
import time
import select
import queue
import re
import subprocess
from threading import Thread, get_ident
import platform
import datetime
import traceback
import ipaddress
from struct import pack, unpack, calcsize
from configparser import ConfigParser
from ctypes import *
import mimetypes
from urllib.parse import urlparse, parse_qs

import rewrapper

version='4.04-remux'

def safe_int(s, default=0):
    """Convert string to int, return default if conversion fails."""
    try:
        return int(s)
    except:
        return default

def encipher(v, k):
    y = c_uint32(v[0])
    z = c_uint32(v[1])
    sum = c_uint32(0)
    delta = 0x61C88647
    n = 32
    w = [0,0]

    while(n>0):
        sum.value -= delta
        y.value += ( z.value << 4 ) + k[0] ^ z.value + sum.value ^ ( z.value >> 5 ) + k[1]
        z.value += ( y.value << 4 ) + k[2] ^ y.value + sum.value ^ ( y.value >> 5 ) + k[3]
        n -= 1

    w[0] = y.value
    w[1] = z.value
    return w

def decipher(v, k):
    y = c_uint32(v[0])
    z = c_uint32(v[1])
    sum = c_uint32(0xc6ef3720)
    delta = 0x9e3779b9
    n = 32
    w = [0,0]

    while(n>0):
        z.value -= ( y.value << 4 ) + k[2] ^ y.value + sum.value ^ ( y.value >> 5 ) + k[3]
        y.value -= ( z.value << 4 ) + k[0] ^ z.value + sum.value ^ ( z.value >> 5 ) + k[1]
        sum.value -= delta
        n -= 1

    w[0] = y.value
    w[1] = z.value
    return w

def Crypt( data, key ):
    bytes = b''
    info = [int.from_bytes(data[i:i+4],byteorder='little')  for i in range(0, len(data), 4)]
    for i in range(0, len(info), 2):
        chunk = [info[i], info[i+1]]
        ciphertext = encipher(chunk, key)
        bytes = bytes + ciphertext[0].to_bytes(4, byteorder='little') + ciphertext[1].to_bytes(4, byteorder='little')
    return bytes

def Decrypt( data, key ):
    bytes = b''
    info = [int.from_bytes(data[i:i+4],byteorder='little')  for i in range(0, len(data), 4)]
    for i in range(0, len(info), 2):
        chunk = [info[i], info[i+1]]
        cleartext = decipher(chunk, key)
        bytes = bytes + cleartext[0].to_bytes(4, byteorder='little') + cleartext[1].to_bytes(4, byteorder='little')
    return bytes

def ts(res=-3):
    return '%s ' % datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S.%f").rstrip('0')[:res]
    
def pbuf(s):
    s = ''.join('{:02x} '.format(x) for x in s).upper()
    cnt = 0
    out = ''
    for i in range(0, len(s), 48):
        ss = s[i:i+48].strip()
#           print( "%06d" % (cnt,), ss )
        out = out + "%06d " % (cnt,) + ss + '\r\n'
        cnt += 16
    return out
    
productIdDict ={
        "UNKNOWN": "Slingbox",
        0: "Classic",
        1: "PRO",
        2: "Classic",
        3: "AV",
        4: "TUNER",
        5: "Classic",
        6: "Sling MODEM",
        7: "SOLO",
        8: "PRO-HD",
        9: "922",
        12: "HDS-600RS",
        13: "120",
        14: "Sling Adapter",
        17: "350",
        18: "500",
        32: "M1",
        19762: "M2"
    }
    
def ip4_addresses():
    ips = []
    interfaces = netifaces.interfaces()
    for interface in interfaces:
        addresses = netifaces.ifaddresses(interface)
        for address in addresses:
            info = addresses[address][0]
            if 'broadcast' in info:
                ips.append((info['addr'],info['broadcast'], interface)) 
    return ips 
    
def find_slingbox_info(name):
    try:
        import netifaces
    except:
        print('ERROR. Cannot scan local network for slingboxes\nBecause the "netifaces" python modules has not been installed')
        return []


    boxes = []

    query =  [0x01, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00,
              0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
              0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
              0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
    ip = ''
    port = 0

    print(name, 'No valid slingbox ip info found in config.ini')
    for local_ip, broadcast, interface in ip4_addresses():
        if local_ip == '127.0.0.1': continue
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            try:
                s.bind((local_ip, 0))
            except Exception as e:
 #               print('Error binding socket to send broadcast', e )
                continue
                
            print(name,'Finding Slingboxes on local network. My IP Info = ', local_ip)
            s.sendto( bytearray(query), (broadcast, 5004 ))
            while True:
                try:
                    msg, source = s.recvfrom(128)
#                    print('MSG', len(msg), source, pbuf(msg))
                    if len(msg) == 124 :
                        port = msg[121] * 256 + msg[120]
                        net_name = ''
                        for char in msg[ 56:120]:
                            if char != 0: net_name = net_name + chr(char)
                        finderid = ''.join('{:02x}'.format(x) for x in msg[40:56])
                        pid = msg[38] * 256 + msg[39]
                        if pid in productIdDict.keys(): pname = productIdDict[pid] 
                        else: pname = 'Unknown slingbox type'
                        print( name, 'Found at', source[0], port, '"', net_name, '"', 
                        'FinderID', finderid.upper(), 'ProductID', pname)
                        boxes.append((source[0], port, name, pid))
                except Exception as e:
 #                   print(e, traceback.print_exc())
                    break
    return boxes    

def closeconn( s ):
    if s :
 #       print('Closing Connection')
        try:
            s.shutdown(socket.SHUT_RDWR)
        except: pass
        s.close()
    return None

def find_max_buffer_size( opt ):
    size = 1024*1024*8
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while size > 0 :
        try:
 #           print( 'trying', size )
            sock.setsockopt(socket.SOL_SOCKET, opt, size )
            break
        except : 
            size = size - (1024*1024)
            continue 
    if size < 1024*1024*8 :
        print('Warning TCP buffering might not be sufficent for reliable streaming')
    return size         
        

def sure_sendall(sock, data, timeout=10):
    # Ensure that all data is sent, even if the socket is non-blocking and raises an Exception

    end_time = time.time() + timeout
    leftover = data

    while leftover:
        try:
            sent = sock.send(leftover)
        except BlockingIOError:
            sent = 0
            print('client blocks')

        leftover = leftover[sent:]
        if time.time() > end_time:
            print('socket timeout', sock)
            break

def remux_video_stream(mp4wrapper, data):
    if remux_video_stream.timestamp:
        timedelta = time.time() - remux_video_stream.timestamp
        speed = 8 * len(data) / timedelta
#        print('Speed', speed, 'bits/sec', end='     \r')
    else:
        speed = 0
    remux_video_stream.timestamp = time.time()
    recoded = mp4wrapper.rewrite(data)
#    if recoded: print('remuxed',  len(recoded), end='    \r')
    return recoded

remux_video_stream.timestamp = None

def streamer(maxstreams, config_fn, forced_params, section_name, box_name, streamer_q, server_port):
    global streamer_qs, stati, num_streams
    smode = 0x2000               # basic cipher mode,
    sid = 0
    seq = 0
    tbd = 0
    dco = b''
    bco = 0
    bts = 0
    s_ctl = None
    stream = None
    dbuf = None
    skey = None
    stat = 0
    rccode = 0
    streams = []
    stream_header = None
    max_recv_tcp_buffer = find_max_buffer_size(socket.SO_RCVBUF)

    def new_key( sid, rand, challange ):    
        def bits2bytes(bits):
            def abyte( b ):
                n = 0
                for abit in b[::-1]:
                    n = (n << 1) + abit
                return n
                
            ba = bytearray()
            for i in range(0,len(bits), 8 ):
                ba.append(abyte(bits[i:i+8]))     
            return ba     
               
        def xor( b1, b2 ):
            br = bytearray()
            l = len(b2)
            for i in range(0,l):
                br.append( b1[i] ^ b2[i])  
            return br + b1[l:]
                
        def dynk( rand, sid, a, b ): # hash function for dynamic key 
           
            def p(ba):  # make string from bits
                z = ord('0')
                out = ''
                for b in ba : out = out + chr(z+b)
                return out

            def bytes2bits( buf ):
                t = ''
                for b in buf:
                    t = t + '{:08b}'.format(b)[::-1]
                ba = bytearray()
                for c in t:
                    ba.append( ord(c) & 1 )
                return ba
                
        #******************************
            t = bytes2bits(rand)  
            s = bytes2bits(pack('H', sid ))
            td = [a, b]
            v = bytearray()    
            for i in range(1,17):
                r = i * td[((sid >> (i - 1)) & 1)]
                z = t[r:] + t[0:r]
                t = xor(z,s)
                v = xor(t, v)
            return v

 #       rand = bytearray.fromhex('feedfacedeadbeef1111222233334444')
 #       c = bytearray.fromhex( challange )
        my_key = xor( dynk(rand, sid, 2, 3), dynk(challange, sid, -1, -4))
  #      print( 'SKEY', pbuf(bits2bytes(my_key)) )
        return list(unpack('IIII', bits2bytes(my_key)))
        
    def futf16(in_str):
        out_str = ''
        for c in in_str: out_str = out_str + c + chr(0)
        return bytes(out_str, 'utf-8')

    def sling_cmd( opcode, data, msg_type=0x0101 ):
        nonlocal sid, seq, s_ctl, dbuf, skey, stat, smode
        parity = 0
        if smode == 0x8000 :
            for x in data:
              parity ^= x
#        print( 'Sending to Slingbox ', hex(opcode), hex(parity), '\r\n')
        seq += 1
        try:
            cmd = pack("<HHHHH 6x HH 4x H 6x", msg_type, sid, opcode, 0, seq, len(data), smode, parity) + Crypt(data, skey)
            s_ctl.sendall( cmd )
        except Exception as e:
            print(name, 'Error Sending Command', e, hex(msg_type), sid, hex(opcode),  seq, len(data), hex(smode), hex(parity))
            return False

        if opcode == 0x66 : return True

        try:
            response = s_ctl.recv(32)
            if len(response) == 32:
                sid, stat, dlen = unpack("2x H 8x H 2x H", response[0:18] ) # "x2 v x8 v x2 v", $hbuf);
        #        print( 'Sent to Slingbox ', hex(opcode), hex(parity), hex(len(data)))
        #        print( 'Received from Slingbox', sid, hex(stat), dlen )
        #        print('RESP', pbuf(response))
                if opcode == 0x68 : return  # ignore logout errors
                if stat & stat != 0x0d & stat != 0x13 :
                    print( "cmd:", hex(opcode), "err:",  hex(stat), dlen )
                if dlen > 0 :
                    in_buf = s_ctl.recv( 512 )
                    dbuf = Decrypt(in_buf, skey)
        #            print('DBUF', hex(opcode), pbuf(dbuf))
                return True
            else: return False
        except Exception as e:
            print(name, 'Error Getting Response', e, hex(msg_type), sid, hex(opcode), seq)
            return False

    def sling_open(addr, connection_type):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, max_recv_tcp_buffer)
        s.settimeout(10)
        print('Connecting...', addr, connection_type )
        s.connect(addr)
        s.sendall(str.encode('GET /stream.asf HTTP/1.1\r\nAccept: */*\r\nPragma: Sling-Connection-Type=%s, Session-Id=%d\r\n\r\n' % (connection_type, sid)))
        return s

    def SetVideoParameters(resolution, FrameRate, VideoBandwidth, VideoSmoothness, IframeRate, AudioBitRate ):
        rand = bytearray.fromhex('feedfacedeadbeef1111222233334444') # 'random' challenge
        print('VideoParameters: Resolution=',resolution, 'FrameRate=', FrameRate,
              'VideoBandwidth=', VideoBandwidth, 'VideoSmoothness=', VideoSmoothness,
              'IframeRate=', IframeRate, 'AudioBitRate=', AudioBitRate)
        sling_cmd(0xb5, pack("11I 16s 2I 92x",
                         0xff,
                         0xff,
                         resolution, # Screen Size
                         1,
                         (IframeRate << 24 ) + (FrameRate << 16) + VideoBandwidth,
                          0x10001 + (VideoSmoothness << 8), #Video Smoothness
                         3, #fixed
                         1, #fixed
                         AudioBitRate,
#                         3,
                         0x4f,
                         1,
                         rand,
                         0x1012020,
                         1)); # set stream params
        if stat != 0:
            print(name, 'Slingbox returned error trying to set video parameters')
            print('Please validate parameters.')
            return False
        return True
     
    def start_slingbox_session(streams):
        nonlocal stream_header, stream_header_remuxed, sid, seq, s_ctl, dbuf, skey, stat, smode
        global stati, num_streams

        skey = [0xBCDEAAAA,0x87FBBBBA,0x7CCCCFFA,0xDDDDAABC]
 #       print('skey', skey )
        smode = 0x2000               # basic cipher mode,
        sid = seq = 0                # no session ID, seq 0
        print(name, 'Opening Control stream', hex(smode), sid, seq)
        s_ctl = sling_open(sling_net_address, 'Control') # open control connection to SB
 
        if not sling_cmd(0x67, pack('I 32s 32s 132x', 0, futf16('admin'), futf16(password))): # log in to SB
            print(name, 'Slingbox did not respond to login request. Please reset Slingbox and try again. NOT a factory reset') 
            return (s_ctl, None)
        if stat != 0:
            if stat == 0x2:
                print(name,'Error Starting Session. Check your admin password in config.ini file!')
            elif stat == 0x2b:
                print(name,'Error Starting Session. Slingbox might be Bricked')
            else:
                print(name,'Unknown Error Starting Session. Can''t Continue.')
            return s_ctl, None
            
        rand = bytearray.fromhex('feedfacedeadbeef1111222233334444') # 'random' challenge
        sling_cmd(0xc6, pack('I 16s 36x', 1, rand)) # setup dynamic key on SB
        if stat != 0:
            print(name,'Error Starting Session. Check your admin password in config.ini file!')
            return s_ctl, None
           
        skey = new_key(sid, rand, dbuf[0:16])
#        print('New Key ', skey)
        smode = 0x8000                # use dynamic key from now on
        sling_cmd(0x7e, pack("I I", 1, 0)) # stream control
        retries = 0 
        while stat and retries < 3:
            retries += 1
            print(name,'Box in use! Kicking off other user.' )
            stati[server_port] = name + ' Slingbox in Use! Cannot start session, kicking off other user..'
            sling_cmd(0x93, pack('32s 32s 8x', futf16('admin'), futf16(password)))
            time.sleep(1)
            sling_cmd(0x6a, pack("I 172x", 1)); # unk fn
            sling_cmd(0x7e, pack("I I", 1, 0)) # stream control
        if stat:
            print(name, 'Cannot kick off other user, not starting session.')
            print( 'If this error persists, consider rebooting your slingbox')
            return (s_ctl, None)
        
        ## Select input
        if VideoSource :
            print(name,'Selecting Video Source', VideoSource)
            source = int(VideoSource)
            sling_cmd(0x85, pack('4h', source, 0, 0, 0 )) 
            if stat != 0 :
                print('Error trying to set VideoSource. Please make sure the supplied value is valid for your slingbox model')
                return ( s_ctl, None )
                
            try:    
                sling_cmd( 0x86, pack("h 254x", 0x0400 + source )) # Get Key Codes
                if len(dbuf) > 1 :
                    i = 1
                    codes = []
                    while dbuf[i] != 0 and i < len(dbuf): 
                        codes.append(dbuf[i])
                        i += 1
                    codes.sort()
                    if codes :
                        print(name, 'Keycodes=', codes)
                    elif not ( Solo and source == 0):
                        print( name, 'Warning: No remote keys configured, using correct VideoSource?')
            except:
                print('Error retreiving Keycodes. If this error persists consider rebooting your slingbox')
                return (s_ctl,None)
                    
            
        sling_cmd(0xa6, pack("10h 76x", 0x1cf, 0, 0x40, 0x10, 0x5000, 0x180, 1, 0x1e,  0, 0x3d))
        if not SetVideoParameters(resolution, FrameRate, VideoBandwidth, VideoSmoothness, IframeRate, AudioBitRate ) :
            return (s_ctl,None)
        stream = sling_open(sling_net_address, 'Stream')

        first_buffer = bytearray(stream.recv(pksize, socket.MSG_PEEK))
        magic = bytearray(u'Slingbox'.encode('utf-16le'))
        idx = first_buffer.find(magic)
        if idx > 0:
            sourceid = bytearray(16)
#            print('Fixup Media', name, section_name)
            source_name = name
            if source_name == 'SLINGBOX' : source_name = 'Slingbox'
            sourceid[:len(source_name)*2] = bytearray(source_name[0:8].encode('utf-16le'))
            first_buffer[idx:idx+16]= sourceid
#        print( 'FIRST', type(first_buffer), pbuf(first_buffer))
        h264_header = b'\x36\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c'
        h264_header_pos = first_buffer.find( h264_header ) + 50
 #       print( 'h246_header_pos', h264_header_pos, len( first_buffer ))
        if Solo:
            tbd = 0
            audio_header = b'\x91\x07\xDC\xB7\xB7\xA9\xCF\x11\x8E\xE6\x00\xC0\x0C\x20\x53\x65\x72'
            audio_header_pos = first_buffer.find( audio_header ) + 0x60 # find audio hdr
            first_buffer[audio_header_pos:audio_header_pos+10] = pack("H 8x", 0x9012)
        if SB240:
            tbd = 0
            audio_header = b'\xA1\xDC\xAB\x8C\x47\xA9\xCF\x11\x8E\xE6\x00\xC0\x0C\x20\x53\x65\x68'
            audio_header_pos = first_buffer.find( audio_header ) + 0x60 # find audio hdr
            first_buffer[audio_header_pos:audio_header_pos+10] = pack("H 8x", 0x9012)

        stream_header = first_buffer[0:h264_header_pos]
        #print( 'SH', type(stream_header), pbuf(stream_header))

        print(name,'Stream started at', ts(), len(stream_header), len(first_buffer[h264_header_pos:]))
        stream_header_remuxed = b''
        print('streams:', streams)
        for s in streams :
            do_remux_wrapper = remux_connections.get(s, False)
            if do_remux_wrapper:
                stream_header_remuxed = remux_video_stream(do_remux_wrapper, stream_header)
            try:
                if do_remux_wrapper:
                    if stream_header_remuxed:
                        s.sendall(stream_header_remuxed)
                else:
                    if stream_header:
                        s.sendall(stream_header)
            except:
                print(name, 'ERROR: Media Player closed connection immediately after receiving 200 OK')
                return (s_ctl, None )
        # flush header from socket
        stream.recv(h264_header_pos)

        return s_ctl, stream

    def parse_cmd(msg):
 #       print('Q',msg)
        if msg[0] == 0x00 :
            return msg[1:].decode('utf-8').split('=')
        else:
            return 'IR', msg      

    def check_ip( sling_net_address, retry_count ):
        print( name, 'Checking for slingbox at', sling_net_address, retry_count)
        cnt = 0
        while True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect(sling_net_address)
                print(name, sling_net_address, 'OK')
                closeconn(s)
                return True
            except Exception as e: 
                closeconn(s)
                time.sleep(1)
                cnt += 1
                if not cnt % 10 : print( name, 'Still waiting for', sling_net_address )
                if retry_count == -1 : continue  #Forever
                if cnt < retry_count: continue
                else: 
                    print(name, 'Error connecting to ', sling_net_address) 
                    closeconn(s)
                    return False
    
    def public_ip(ip):
        if ip == '' : return False
        if ip.startswith('192.168.'): return False            
        if ip.startswith('10.'): return False
        if ip.startswith('127.0.'): return False
        if ip.startswith('172.') :
            second_octet = int(ip.split('.')[1])
            if second_octet > 15 and second_octet < 33 : return False 
        return True
            
    def start_streaming_connection(ip):
        global num_streams
        if public_ip(ip) :
            if num_streams == maxstreams :
                print( 'Max remote streams', maxstreams, 'reached. Ignoring new streaming request')
                return False
                
            num_streams = num_streams + 1
            print('Starting remote stream', num_streams )
        return True
        
    def close_streaming_connection(s):
        global num_streams
        if s :
            if public_ip(stream_clients[s]) :
                num_streams = num_streams - 1
                print( num_streams, 'active remote connections')
                
            del stream_clients[s]
            streams.remove(s)
            if s in remux_connections:
                if remux_connections[s]:
                    print(name, 'Closing remux connection')
                    remux_connections[s].close()
                del remux_connections[s]
            return closeconn(s)
        return None
        
    def closecontrol(s):
        if s :
            print( name, 'Logging Out')
            try:
                if Solo: sling_cmd( 0x68, b'')
            except: pass
            return closeconn(s)

    ################## START of Streamer Execution
    print('Streamer Running: ', maxstreams, config_fn, section_name, box_name, server_port, max_recv_tcp_buffer)
    # without (fake) 'Accept-ranges: bytes', no seeking within buffered video will be possible in chrome based browsers
    OK = b'HTTP/1.0 200 OK\r\nContent-type: video/mp4\r\nCache-Control: no-cache\r\nConnection: keep-alive\r\nAccept-Ranges: bytes\r\n\r\n'

    ERROR =b'HTTP/1.0 503 ERROR\r\nContent-type: application/octet-stream\r\nCache-Control: no-cache\r\nConnection: close\r\n\r\n'
    stream_clients = {}
    cp = ConfigParser()
    cp.read(config_fn)
    slinginfo = cp[section_name]
    slingip =  slinginfo.get('ipaddress', '' )
    slingport = int(slinginfo.get('port', '5201'))
    name = slinginfo.get('name', box_name )
    finderid = slinginfo.get('finderid', '' )
    if finderid :
        # sanity checks
        finderid = finderid.strip().upper().split(':')
        ext_port = -1
        if len(finderid) == 2:
            try:
                ext_port = int(finderid[1], 10)
                if ext_port > 65535: raise
            except:
                print(name, 'ERROR: Finderid External Port must be between 0-65535')
                ext_port = -1
        else:
            ext_port = server_port
                
        if ext_port != -1:
            try:
                if (len(finderid[0]) == 32) and int(finderid[0],16): 
                    finderids[ finderid[0]] = ext_port
                else : print(name, 'ERROR: Invalid Finderid length. Must be 32 characters', finderid)
            except: print(name, 'ERROR: Finderid must only contain hexadecimal characters', finderid)
            
    bts = bco = runt = 0
    boxes = []
    sling_net_address = (slingip, slingport)
    if not check_ip(sling_net_address, int(slinginfo.get('ConnectRetries', '0' ))):   
        if not public_ip(sling_net_address[0]):
            time.sleep(1)
            boxes = find_slingbox_info(name)

            for box in boxes:
#                    print('checking', slingip, 'box', box)
                if box[0] == slingip:
                    print(name, 'Found matching IP Address', slingip, 'will use this box, check port number in your config file' )
                    boxes = [box]
                    break
                            
            if len(boxes) > 1: 
                print("""Found more than one slingbox on the local network.
    Please select the one you want to use and update the config file accordingly.
    \n%s Giving up. Sorry..""" % name)
                return
     
            if len(boxes) == 1: 
                slingip = boxes[0][0]
                slingport = boxes[0][1]
                sling_net_address = (slingip, slingport)  
                         
            if not boxes:
                msg =  "Can't find a slingbox on network. Please make sure it's plugged in and connected. Check config.ini"
                for port in stati.keys():
                    stati[port] = msg
                print(name, msg)
                time.sleep(5)
                print( name, 'Giving up. Sorry...')
                return

    def readnbytes(sock, n):
#        print( 'Reading', n )
        buff = b''
        try:
            while n > 0:
                b = sock.recv(n)
                if len(b) == 0:
                    return b          # peer socket has received a SH_WR shutdown
                buff += b
                n -= len(b)
        except Exception as e:
            print(name, 'Error Reading video stream')
            buff = b''
        return buff

    def process_solo_msg( msg, sock ):
    
        def cs( mybuf ):
            sum = 0
            for byte in mybuf:
                sum = sum + byte
            return sum
            
        nonlocal tbd, dco, bco, pc, bts, stream_header
#        if resolution == 0 : return msg
#        print('MSG', pbuf(msg[0:16]))
        msg = bytearray( msg )
        pmode = unpack(">I", msg[0:4])[0]
        pad, pktt, pcnt = unpack("<x I I 2x B", msg[4:16])
        header = b''        
#        print('pmode..', pc, hex(pmode), pad, pktt, pcnt)
        if ( pmode & 0xFFFFFFFE ) != 0x82000018 :  
            magic = bytes(u'Slingbox'.encode('utf-16le'))
 #           print('MAGIC', magic)
            if magic in msg:
                print(ts(), name, 'Solo/ProHD Input Video Format Changed. Stream Restarted')
                return b'Restart'

        off = 16
        if pmode == 0x82000018 :
            off = 15
            pcnt = 1
            
        p = 0
        while p < (pcnt & 63) :
 #           print( "loop", p, off, pcnt & 63); 
            fmt = "<B x I x I 4x H"
            if off > 2983 : break 
            sn, objoff, objsiz, length = unpack(fmt, msg[off:off+17]);
            off += 17
            if not pmode & 1 :
                off -= 2
                length = 2970 - pad   
            if ( sn == 0x82 or (sn & 63 == 1 )) : 
                if objoff == 0 : tbd = objsiz & ~15
                bts = (bco + length ) & 15
                cbd = (bco + length) & ~15
                if (cbd):
 #                  print( 'SN', sn, off, tbd, bts, objsiz, objoff, cbd, bco )

                   if (bco):
     #                  print('Decrypting',  bco, off, cbd)
                       buf = Decrypt(dco + msg[off:off + (cbd - bco)], skey); 
                       dco = buf[0:bco] # fix data carried over
                       msg[off:off+(cbd - bco)] = buf[bco:] # fix current packet
                       bco = 0;
                   else:
     #                  print('DEcrypting', off, cbd, len(msg), pbuf(msg[off:off+cbd]))
                       buf = Decrypt(msg[off:off+cbd], skey) # decrypt
    #                   print('DEcrypted', pbuf(buf))
                       msg[off:off+cbd] = buf
                tbd -= cbd
                if tbd == 0 : bts = 0
                if sn == 0x82 and objoff == 0:
                   break
               
            off += length
#            print('off', off, length, pad)
            p += 1 
        
#        print $out $dco if $dco ne '';
        msg = dco + msg
        bco = bts
        if bco > 0 : 
            dco = msg[-bts:]
            msg = msg[0:-bts]
 #           print('DCO', bts, pbuf(dco)[7:-2])
        else:
            dco = b''

        return header + msg
        
    def SendKeycode( key, rccode ):
        print('sending key', key, rccode )
        if '.' in key:
            code,chan,subchan = key.split('.')
            chan = int(chan)
            cmd = bytearray(8)
            cmd[0] = int(code)
            cmd[1] = 0
            cmd[2] = 0
            cmd[3] = 0
            cmd[4] = chan & 255
            cmd[5] = chan >> 8
            cmd[6] = int(subchan)
            cmd[7] = 0
            sling_cmd(0x89, cmd + pack('8x'), msg_type=0x0101)
        else:
            cmd = bytearray(4)
            cmd[0] = int(key)
            cmd[1] = 0
            cmd[2] = 0
            cmd[3] = rccode
            sling_cmd(0x87, cmd + pack('467x 4h', cmd[3], 0, 0, 0), msg_type=0x0101)
    
    def send_start_channel( channel, rccode ):
        if channel : 
            if channel != '0':
                print(ts(), name, 'Sending Start Channel', channel)
                if '+' in channel:
                    print('Split', channel.split('+'))
                    for keycode in channel.split('+'): 
                        if keycode : SendKeycode(keycode, rccode)
                elif '.' in channel:
                    SendKeycode( '2.' + channel, 0 )              
                else:
                    digits2buttons = ['18','9','10','11','12','13','14','15','16','17']
                    for digit in channel:
                        if digit in '0123456789' :
                            SendKeycode( digits2buttons[int(digit)], rccode)
        return None
                    
    def parse_stream( header ):
        bits = header.split(':')
        return ( bits[0]+':'+bits[1], bits[2] )
        
    def RemoteLocked(sender_ip):
        if RemoteLock and sender_ip != 'Server' and (sender_ip != primary_stream_client):
            print(name, 'Ignoring IR request from', sender_ip, 'Remote Locked by', primary_stream_client )
            return True
        else: return False

                                                          
    print(name, 'Using slingbox at ', sling_net_address)
    while True:
        stream_header = None
        streams = []
        # Wait for first stream request to arrive
        cp = ConfigParser()
        cp.read(config_fn)
        slinginfo = cp[section_name]
        name = slinginfo.get('name', box_name).strip()
        my_num_streams = 0
        my_max_streams = int(slinginfo.get('maxstreams', '10'))
        print('Streamer: ', name, 'Waiting for first stream, flushing any IR requests that arrive while not connected to slingbox')
        print('forced params', forced_params)
         
        #if box_name == '/' : stati_key = '/'
        #else: stati_key = '/'+ box_name
        stati[box_name] = 'Waiting for first client. Slingbox at ' + str(sling_net_address)
            
        while True:
            cmd, value = parse_cmd(streamer_q.get())
            if cmd == 'STREAM': break
            
        client_addr, channel = parse_stream(value)
        client_socket = (streamer_q.get()) ## Get the socket to stream on    
        if not start_streaming_connection(client_addr): 
            client_socket = closeconn(client_socket)
            continue 
            
        my_num_streams = 1
            
        cp.read(config_fn)
        slinginfo = cp[section_name]
        name = slinginfo.get('name', box_name).strip()
        sbtype = slinginfo.get('sbtype', "350/500").strip()
 #       print('DiscoveredSolo', DiscoveredSolo)
        if len(boxes) == 1 :  
            box_type = boxes[0][3]
            Solo = box_type < 9
            SB240 = box_type == 3 
            sbtype = productIdDict[box_type]
        else: 
            Solo = 'Solo' in sbtype or 'Pro' in sbtype
            SB240 = '240' in sbtype or 'AV' in sbtype           
 #       print('Is Solo', Solo)
        password = slinginfo.get('password', 'admin').strip()
        if password.upper().startswith('E1:'):
            print( name, 'Using encrypted password:', password)
            pw = password.upper().replace('E1:', '').strip()
            try:
                pw_bytes = bytearray.fromhex(pw)
                clear = Decrypt(pw_bytes, [0xBCDEAAAA,0x87FBBBBA,0x7CCCCFFA,0xDDDDAABC])
            except Exception as e:
                print('Bad E1: Password cannot decrypt. Missing/bad characters?', len(pw), e, traceback.print_exc())
                return (closeconn(s_ctl), None)
            eos = clear.find(b'\x00\x00')
            if eos > 0:
                password = clear[0:-2:2].decode("utf-8")
            else:
                print('name, Bad E1: Password Missing characters')
                continue             
        
        resolution = int(slinginfo.get('Resolution', 12))
        if resolution < 0 or resolution > 16 : 
            print(name, 'Invalid Resolution', resolution, 'Defaulting to 640x480')
            resolution = 5;
        if 'resolution' in forced_params:
            resolution = forced_params['resolution']
            print(name, 'Forced Resolution', resolution)
        FrameRate = int(slinginfo.get('FrameRate', 30 ))
        VideoBandwidth = int(slinginfo.get('VideoBandwidth', 2000 ))
        if 'bitrate' in forced_params:
            VideoBandwidth = forced_params['bitrate']
            print(name, 'Forced Video Bitrate', VideoBandwidth)
        VideoSmoothness = int(slinginfo.get('VideoSmoothness', 63 ))
        IframeRate = int(slinginfo.get('IframeRate', 5 ))
        AudioBitRate = int(slinginfo.get('AudioBitRate', 64 ))
        VideoSource = slinginfo.get('VideoSource', '' )
        if channel == '0': StartChannel = slinginfo.get('StartChannel', '' )
        else: StartChannel = channel
        RemoteLock = slinginfo.get('RemoteLock', '')
        if box_name in remotes.keys(): rccode = remotes[box_name][1][2]       
        if Solo : 
            if resolution : pksize = 3000
            else: pksize = 1636
        else: pksize = 3072
        print( '\r\nSlinginfo ', sbtype, resolution, FrameRate, slingip, slingport, pksize, my_max_streams, password )

        print(name, 'Starting Stream for ', client_addr)
        stream_clients[client_socket] = client_addr  
        primary_stream_client = client_addr.split(':')[0]       
        streams.append(client_socket)
        try:
            client_socket.sendall(OK)
            s_ctl, stream  = start_slingbox_session(streams)

        except Exception as e:
            print(name, 'Badness starting slingbox session ', e, traceback.print_exc())
            continue
        if s_ctl and stream :
            stati[box_name] = box_name + ' Streaming %d clients. Resolution=%d' % (len(streams), resolution )
            pc = 0
            stream.settimeout(15)
            tick = lasttick = laststatus = lastkeepalive = last_remote_command_time = startchanneltime = time.time()
            if not Solo : StartChannel = send_start_channel(StartChannel, rccode)
            speed_timestamp = time.time()
            cum_msg_len = 0
            while streams:
                msg = readnbytes(stream, pksize)
                if Solo and len(msg) > 0: 
                    try:
                        msg = process_solo_msg( msg, stream )
                        if not msg:
                            continue
                    except Exception as e:
                        print(name, 'Error Processing Solo Message. Stopping', e, traceback.print_exc())
                        break
                    if len(msg) < 10:
                        if len(msg) == 0 :
                            print(ts(), name, 'Bad or Corrupted Solo message')
                        # Restart    
                        break
                
                if len(msg) == 0 :
                    print(ts(), name, 'Stream Stopped Unexpectly. Kicked Off?')
                    break
                    
                pc += 1

                for stream_socket in streams:
                    do_remux_wrapper = remux_connections.get(stream_socket, False)
                    try:
                        if do_remux_wrapper:
                            msg_remuxed = remux_video_stream(do_remux_wrapper, msg)
                            if msg_remuxed:
                                sure_sendall(stream_socket, msg_remuxed)
                                cum_msg_len += len(msg_remuxed)
                        else:
                            if msg:
                                sure_sendall(stream_socket, msg)
                                cum_msg_len += len(msg)
                        timedelta = time.time() - speed_timestamp
                        if timedelta > 10: # averaged over 10s
                            speed_timestamp = time.time()
                            speed_raw = cum_msg_len / timedelta
                            cum_msg_len = 0
                            speed = int(8*speed_raw/1024)
                            print('streaming speed', speed, 'kbps', end='        \r')
                    except Exception as e:
                        if stream_socket in stream_clients.keys():
                            print(ts(), name, 'Stream Terminated for ', stream_clients[stream_socket])
                            print(traceback.print_exc())
                            print('closing stream')
                            close_streaming_connection(stream_socket)
                        else:
                            print(ts(), name, 'Stream Terminated', e, traceback.print_exc())
                            streams.remove(stream_socket)

                        my_num_streams = my_num_streams - 1
                        continue
                msg = b''
                
                if (not streamer_q.empty()):
                    cmd, data = parse_cmd(streamer_q.get())
                    print( name, 'Got Streamer Control Message', cmd )
                    if cmd == 'STREAM' :
                        new_stream = streamer_q.get()
                        #print(new_stream)
                        if my_num_streams == my_max_streams :
                            print( name, 'Max streams', my_max_streams, 'for this slingbox has been reached. Not starting connection')
                            new_stream.sendall(ERROR)
                            new_stream = closeconn(new_stream)
                        elif not start_streaming_connection(data) :
                            print(name, 'Video Stream Startup Error')
                            new_stream.sendall(ERROR)
                            new_stream = closeconn(new_stream)
                        else:
                            my_num_streams = my_num_streams + 1
                            sure_sendall(new_stream, OK)
                            stream_clients[new_stream], channel = parse_stream(data)
                            do_remux_wrapper = remux_connections.get(new_stream, False)
                            if do_remux_wrapper:# and stream_header_remuxed:
                                stream_header_remuxed = remux_video_stream(do_remux_wrapper, stream_header) # will return most likely b''
                                if stream_header_remuxed:
                                    print('sending remuxed header', len(stream_header_remuxed))
                                    sure_sendall(new_stream, stream_header_remuxed)
                            elif stream_header:
                                print('sending header')
                                sure_sendall(new_stream, stream_header)
                            print( name, 'New Stream Starting', channel)
                            if channel != '0':
                                if not RemoteLock : StartChannel = channel
                                else: print( name, 'RemoteLocked, ignoring channel request')
                            streams.append(new_stream) 

                    elif cmd == 'ProHD':
                        channel, sender_ip = data.split(':')
                        print(ts(), name, 'got ProHD', channel, sender_ip)
                        stream_ip = primary_stream_client
                        if not RemoteLocked(sender_ip):
                            SendKeycode( channel, rccode)                              
                    elif cmd == 'IR':
                        print('IR', data)
                        for key in data:
                            sender_ip = key[1:].decode('utf-8')
                            stream_ip = primary_stream_client                            
                            if not RemoteLocked( sender_ip ):
                                print(ts(), name,'Sending IR keycode', key[0], rccode, 'for', sender_ip)
                                SendKeycode(str(key[0]), rccode )

                curtime = time.time()
                if curtime - tick > 0.5: # Only check stuff every 
                    tick = curtime
                    
                    if curtime - lasttick > 10.0:
                        print('.', end='')
                        #print( stati_key, box_name )
                        stati[box_name] = box_name + ' Streaming %d clients. Resolution=%d Packets=%d' % (len(streams), resolution, pc)
                        lasttick = curtime
                        sys.stdout.flush()                  
                        if curtime - laststatus > 90.0 :
                            print(ts()[0:20].replace(' ', ''), name, '%d Clients.' % len(streams), end='')
                            for c in stream_clients.values(): print( c, end=' ')
                            print('')
                            laststatus = curtime
                            sys.stdout.flush()

                    if curtime - lastkeepalive > 10.0 :
        #                  print('Sending Keep Alive' )
                        sling_cmd(0x66, '') # send a keepalive
                        lastkeepalive = curtime
                        socket_ready, _, _ = select.select([s_ctl], [], [], 0.0 )
                        if socket_ready : s_ctl.recv(8192)
                          
                    if StartChannel : 
                        if curtime - startchanneltime > 10.0 :
                            StartChannel = send_start_channel(StartChannel, rccode)
                    

            ### No More Streams OR input stream stopped
            print(name, 'Shutting down connections')
            s_ctl = closecontrol(s_ctl)
            for s in streams : close_streaming_connection(s)
            for s, wrapper in list(remux_connections.items()):
                if wrapper:
                    wrapper.close()
                del remux_connections[s]
            streams = []
            stream_clients = {}
            my_num_streams = 0
        else:
            print(name,'ERROR: Slingbox session startup failed.')
            if s_ctl : s_ctl = closecontrol(s_ctl)
            if stream : 
                stream = close_streaming_connection(stream)
                client_socket.sendall(ERROR)
            else:
                if public_ip(client_addr.split(':')[0]) :
                    num_streams = num_streams - 1
                    print( num_streams, 'active remote connections')
            client_socket = closeconn(client_socket)
            my_num_streams = 0
            
            
    print(name, 'Streamer Exiting.. should never get here')
    s_ctl = closecontrol(s_ctl)
    stream = close_streaming_connection(stream)
    client_socket = closeconn(client_socket)

def remote_control_stream( connection, client, request, server_port):
    def fix_host(request):
        start_host = request.find('Host:')
        start_port = request.find(':', start_host + 5 )+1
        end_port = request.find('\r\n', start_host)
#        print('Fixing', start_port, end_port, request[0:start_port] + str(server_port) + request[end_port:])
        return bytes(request[0:start_port] + str(server_port) + '\r\nFrom:%s'%client[0] + request[end_port:], 'utf-8')
     
    http_port = server_port + 1
#    print('\r\nStarting remote control stream handler for ', str(client), 'to port', http_port)
    remote_control_socket =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    remote_control_socket.connect(('127.0.0.1', http_port ))  ## Send Packets to Flask
    print('Remote Control Connected')
#    print('GOT', request )
    request = fix_host(request)
    remote_control_socket.sendall(request)
    sockets = [remote_control_socket, connection]
    POST = 'POST'.encode('utf-8')
    GET = 'GET'.encode('utf-8')
    
    while True:
 #       print('Waiting for data')
        read_sockets, _, _ = select.select(sockets, [], [])
        for sock in read_sockets:
            try: data = sock.recv(32768)
            except: break
            if len(data) == 0 :
                break
            if sock == connection: 
 #               print(data[0:10].decode("utf-8"))
                if POST in data or GET in data:
                    data = fix_host(data.decode("utf-8"))
                remote_control_socket.sendall(data)
            if sock == remote_control_socket: 
                connection.sendall(data)
        else:
            continue
        break
    connection = closeconn(connection)
    remote_control_socket = closeconn(remote_control_socket)
 #   print('Exiting Remote Control Stream Handler for', client )     
                
########################################################################
def ConnectionManager(config_fn):

    def SendIRKeycodes(data):
        print('SendIRKeycodes', data)
        try:
            sb, data = data.split('=')
            sb = sb.replace('SENDIRKEYCODES', '')
            keycodes = []
            for keycode in data.split('+'):
                if keycode.strip() == '-1':
                    print('Alert: Received Keycode -1. Restarting...')
                    killmyself()
                keycodes.append(
                int(keycode).to_bytes(1, byteorder='little') + bytes(client_address[0], 'utf-8'))
            if sb in streamer_qs.keys(): streamer_qs[sb].put(keycodes)
            else: print("Can't Send IR Keycodes. No streamer_q for", sb)
        except Exception as e: print('Error in SendIRKeycodes', e)
        
    def SendData( data ):
 #       print('Sending', len(data), data)
        return pack('!I', len(data) ) + data
 
    def GetSlingboxIds(cp):
        msg=''
        if cp.has_section('SLINGBOXES'):
            boxes = cp.items('SLINGBOXES')
            for id, name in boxes:
              msg = msg + id + '=' + name + ','
        elif cp.has_section('SLINGBOX'): 
            msg = msg + 'slingbox=/,'
        return msg[:-1].encode('UTF-8')
        
    def GetSlingboxInfo( request, cp):
        msg=''
        sbid = request.split('=')[1].strip() 
#        print('getdlingbox info', sbid)        
        if cp.has_section(sbid):
 #           print('found section')
            info = cp.items(sbid)
            for name, value in info:
                if name != 'password':
                    msg = msg + name + '=' + value + ','
        return msg[:-1].encode('UTF-8')
        
    def GetFile(request):
        data = b''
        try:
            fn = request.split('=')[1]
        except: 
            print('Bad GETFILE request. Missing "="', request)
            return data
        full_fn = os.path.abspath(fn)
        server_path = os.path.abspath('.')
        print('GetFile ', full_fn, )       
        if full_fn.startswith(server_path):
                if os.path.exists(full_fn):
                    f = open( fn, 'rb')
                    data = f.read()
                    f.close()
                else: print("Error: Can't find file", full_fn )
        else:
            print("Error: Error file path not Slingbox_Server folder", full_fn)
            
        return data 
        
    global streamer_qs
    global remux_connections # keeps track which connections (sockets) to remux to mp4, the values are instances of MP4Wrapper
    
    forced_params = {} # parameters forced by url
    streamer_q = None
    cp = ConfigParser()
    cp.read(config_fn)
    serverinfo = cp['SERVER']
    local_port = int(serverinfo.get('port', '8080'))
    maxstreams = serverinfo.get('maxremotestreams', '10')
    maxstreams = int(serverinfo.get('maxstreams', maxstreams))
    remoteenabled = serverinfo.get('enableremote', 'yes') == 'yes'
    URLbase = serverinfo.get('URLbase', 'slingbox')
    for c in " !*'();:@&=+$,/?%#[]" : 
        URLbase = URLbase.replace(c, '')
    print('Connection Manager Running on port %d with %d max streams using URL %s.' % (local_port,maxstreams, URLbase))

    server_address = ('', local_port)
    unified_config = True        
    if cp.has_section('SLINGBOXES'):
        boxes = cp.items('SLINGBOXES')
        print('BOXES', boxes)
        for _, box in boxes:
            if cp.has_section(box):
                if URLbase: box_url = '/'+URLbase+'/'+box                   
                else: box_url = '/'+ box                  
                print('BOX URL', box_url)
                streamer_qs[box_url] = queue.Queue()
                print('Building page for', box)
                remotes[box] = [box_url, BuildPage(cp, box)]
                Thread(target=streamer, args=(maxstreams, config_fn, forced_params, box, box, streamer_qs[box_url], local_port)).start()
            else:
                print('Missing [%s] section in config file' % box)
                continue
    elif cp.has_section('SLINGBOX'): 
        unified_config = False
        box = str(local_port)
        if URLbase: box_url = '/%s/%s' % (URLbase, box)
        else: box_url = box
        boxes = [('slingbox', box)]
        streamer_qs[box_url] = queue.Queue()
        print('Building page for Slingbox')
        remotes[box] = [box_url, BuildPage(cp, 'REMOTE')]
        print('Starting Streamer Thread for Slingbox')
        Thread(target=streamer, args=(maxstreams, config_fn, forced_params, 'SLINGBOX', box, streamer_qs[box_url], local_port)).start()

    # Create a TCP/IP socket
    max_send_tcp_size = find_max_buffer_size( socket.SO_SNDBUF )
    ConnectionManagerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ConnectionManagerSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print('starting up on %s port %s' % server_address, max_send_tcp_size )
    ConnectionManagerSocket.bind(server_address)
    ConnectionManagerSocket.listen()

    while True:
        # Wait for a connection
 #       print(ts(), 'waiting for a connection')
        try:
            connection, client_address = ConnectionManagerSocket.accept()
        except:
            print(ts(), 'Restarting ConnectionManager')
            ConnectionManagerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ConnectionManagerSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            print('starting up on %s port %s' % server_address )
            ConnectionManagerSocket.bind(server_address)
            ConnectionManagerSocket.listen(maxstreams)
            continue

        try:
            ready_read, ready_write, exceptional = select.select([connection], [], [], 0.4)
            if not ready_read:
                #print(ts(), 'No request in time, hacker?', str(client_address))
                #close silenty Chrome browers opens connection and then doesn't send anything
                connection = closeconn(connection)
                continue
            try:
                data = connection.recv(1024).decode("utf-8")
                data_lower = data.lower()
                data_1stline_lower = data_lower.split('\n',1)[0].strip().lower()
#                print('DATA ', data);
#                print('1stline', data_1stline_lower)
            except:
 #               print('bad data')
                data = 'Bad Request' 
            
            if 'GET' in data and 'HTTP' in data \
                 and not ('/remote' in data_1stline_lower or '/webplay' in data_1stline_lower or 'favicon.ico' in data_1stline_lower or '.php' in data_1stline_lower or '.html' in data_1stline_lower):
                start_uri = data.find('GET') + 3
                end_uri = data.find('HTTP', start_uri)
                uri = data[start_uri:end_uri]
                print(ts(), ' Streaming request from', str(client_address), uri)
                connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, max_send_tcp_size )
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                connection.setblocking(False)
                do_remux = False
                channel = 0

                if '?' in uri:
                    parsed_uri = urlparse(uri)
                    streamer_name = parsed_uri.path
                    parsed_qs = parse_qs(parsed_uri.query)
                    print('Parsed qs', parsed_qs)
                    if parsed_qs:
                        if 'remux' in parsed_qs:
                            do_remux = parsed_qs['remux'][0].strip().lower() in ('yes', 'true', '1')
                            del parsed_qs['remux']
                        if 'dummy' in parsed_qs:
                            del parsed_qs['dummy']
                        if 'resolution' in parsed_qs:
                            forced_resolution = parsed_qs['resolution'][0].strip().lower()
                            forced_resolution = safe_int(forced_resolution, -1)
                            if forced_resolution>=0:
                                forced_params['resolution'] = forced_resolution
                            del parsed_qs['resolution']
                        else:
                            if 'resolution' in forced_params:
                                del forced_params['resolution']
                        if 'bitrate' in parsed_qs:
                            forced_bitrate = parsed_qs['bitrate'][0].strip().lower()
                            forced_bitrate = safe_int(forced_bitrate, -1)
                            if forced_bitrate >= 0:
                                forced_params['bitrate'] = forced_bitrate
                            del parsed_qs['bitrate']
                        else:
                            if 'bitrate' in forced_params:
                                del forced_params['bitrate']
                    if parsed_qs:
                        # for backward compatibility, anything can be a key, and the value is the channel number
                        arbitrary_key = list(parsed_qs.keys())[0]
                        channel = parsed_qs[arbitrary_key][0]
                        channel = safe_int(channel, 0)
                else:
                    streamer_name = data[start_uri:end_uri]
                    channel = 0
                streamer_name = streamer_name.strip()
                if not unified_config:
                    if streamer_name == '/' : streamer_name = str(local_port)
                    else: streamer_name += '/%d' % (local_port)
                print('URI', streamer_name, channel )
                
                print('Streamer Name', streamer_name, channel)
                if streamer_name in streamer_qs.keys():
                    print('STREAM=%s:%d:%s' % (client_address[0], client_address[1], channel))
                    streamer_q = streamer_qs[streamer_name]
                    streamer_q.put( bytearray(1) + bytes('STREAM=%s:%d:%s' % (client_address[0], client_address[1], channel), 'utf-8'))
                    if do_remux:
                        remux_connections[connection] = rewrapper.Mp4Rewrapper()
                    else:
                        remux_connections[connection] = False
                    streamer_q.put(connection)
                else:
                    print("Error: Can't find streamer for", streamer_name, 'in', streamer_qs.keys())
                    connection = closeconn(connection)
                    continue
            elif 'GET' in data or 'POST' in data and 'HTTP' in data:
                print(ts(), ' RemoteControl connection from', str(client_address))
                Thread(target=remote_control_stream, args=(connection, client_address, data, local_port)).start()
            elif data == 'GETSLINGBOXIDS': 
                print('GETSLINGBOXIDS Request' );
                connection.send(SendData(GetSlingboxIds(cp)))
                connection = closeconn(connection)
                continue            
            elif data.startswith('GETSLINGBOXINFO='): 
                print(data, 'Request' );
                connection.send(SendData(GetSlingboxInfo(data,cp)))
                connection = closeconn(connection)
                continue
            elif data == 'GETSERVERCONFIG': 
                print('GETSERVERCONFIG Request' );
                connection.send(SendData(GetServerConfig()))
                connection = closeconn(connection)
                continue
 #           elif data.startswith('GETFILE='):
 #               connection.send(SendData(GetFile(data)))
 #               connection = closeconn(connection)
 #               continue
            elif data.startswith('SENDIRKEYCODES=') :
                SendIRKeycodes(data)
                connection = closeconn(connection)
                continue
            elif data == 'GETVERSION':
                connection.send(SendData(version.encode('UTF-8')))
                connection = closeconn(connection)
                continue
            elif data != 'PINGER':
                print('Hacker Alert. Invalid Request from ', client_address, data )
                connection = closeconn(connection)
                continue
            else:
                # Ping
                connection = closeconn(connection)
                continue
                
        except Exception as e:
            print( 'Program Bug? Please report. ', client_address, data, e, traceback.print_exc())
            connection = closeconn(connection)
            continue
    
def GetServerConfig():
    response = ''
#    print('GettingServer Config')
    for config_fn in sys.argv[1:] :
        if os.path.exists( config_fn ): 
            cp = ConfigParser()
            cp.read(config_fn)
 #           print(config_fn);
            serverinfo = cp['SERVER']
            msg = ''
            for key, value in serverinfo.items():
                msg = msg + key + '=' + value + ','
            if 'port' not in msg: msg += 'port=8080,'
            if 'urlbase' not in msg: msg += 'urlbase=slingbox,'
            msg = msg[:-1] + '|' 
 #           print('end', config_fn, msg)
            response += msg
    print('ServerConfig', response);
    return response[:-1].encode('utf-8')     
 
def BroadcastResponder(): 
    print('Broadcast Responder Running')
    while True:
        try:
            sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            sock.bind(('0.0.0.0', 50005 ))
            msg, sender = sock.recvfrom(1024)
#            print('BCM=', msg)
            if msg == b'GETSERVERCONFIG':
                print('Received GETSERVERCONFIG Request', msg, sender)
                sock.sendto(GetServerConfig(), sender)  
            sock.close()
        except Exception as e:
            print('ERROR While handling GETPORTNUMBERS request', e)
            time.sleep(10)

def killmyself():
    print('Shutting Down')
    os._exit(100)

def parse_buttons(buttons, lineno):
    lines = buttons.split('\n')
#        print('LINES=', lines)
    cmds = []
    for line in lines:
        try:
            lineno += 1
            if line.strip().startswith(';'): continue
#            print('Line=', line)
            name, value = line.split(':', 1)
#               print( name, value)
            name = name.replace("'", '').strip()
            cmds.append((name, value.strip()))
        except:
            print('ERROR parsing buttons in remote control file.\r\n Line number %d Contents %s' % (lineno, line))
#       print(cmds)
    return cmds
    
def parse_html(page):
    cmds = []
 #   re.search(r'pattern1(.*?)pattern2', page)
    result = re.findall('<button(.*?)/button>', page)
    for r in result:
#        print(r)
        start = r.find('name="') + 6
        if start > 6 :
            end = r.find('"', start)
            name = r[start:end]
        else: continue
        start = r.find('value="') + 7
        if start > 7:
            end = r.find('"', start)
            value = r[start:end]  
        else: continue
 #       print(name, value)
        cmds.append((name,value))
    return cmds

def BuildPage(cp, section_name):
    BasePage = '''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"><html>
<head>
  <meta http-equiv="content-type" content="text/html; charset=UTF-8">
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
  <meta http-equiv="Pragma" content="no-cache" />
  <meta http-equiv="Expires" content="0" />
  <title>Remote</title>
  <style>
     %s
  </style>
</head>
<body>
     <form method="post" action="/Remote%s">
        %s
     </form>
</body>
</html>
'''
    default_style='''style=
.button {
  box-shadow: 0.5em 0.5em 1em 0px #222;
  background:linear-gradient(to bottom, #999 5%, #222 100%);
  background-color:#555;
  border-radius:1.25em 1.25em 1.25em 1.25em;
  min-width: 2.5em;
  max-width: 6.5em;
  height: 2.5em;
  border:1px solid #999;
  display:block;
  margin: auto;
  margin-top: 0.4ex;
  margin-bottom: 0.4ex;
  cursor:pointer;
  color:white;
  font-family:sans;
  font-weight:bold;
  text-decoration:none;
  text-shadow:0px 1px 0px #58c;
  text-align: center;
  display: inline;
}


'''
    default_remote_html = '''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Default Remote</title>

<style>

body {
 margin: 0;
}

.container {
  display: flex;
  flex-wrap: wrap;
  flex-direction: column;
  height: 100vh;
  align-content: flex-start;
  column-gap: 0.5em;
  margin-left: 1em;
}

.statusline {
  position: absolute;
  bottom: 1ex;
  font-family:sans;
  font-size: smaller;
}

.button {
  box-shadow: 0.5em 0.5em 1em 0px #222;
  background:linear-gradient(to bottom, #999 5%, #222 100%);
  background-color:#555;
  border-radius:1.25em 1.25em 1.25em 1.25em;
  min-width: 2.5em;
  max-width: 4.5em;
  height: 2.5em;
  border:1px solid #999;
  display:block;
  margin: auto;
  margin-top: 0.4ex;
  margin-bottom: 0.4ex;
  cursor:pointer;
  color:white;
  font-family:sans;
  font-weight:bold;
  text-decoration:none;
  text-shadow:0px 1px 0px #58c;
  text-align: center;
}

.wide {
  min-width: 4.5em;
  max-width: 4.5em;
  width: 4.5em;
}

.buttonred {
  background:linear-gradient(to bottom, red 5%, #600 100%);
  background-color: red;
}

.buttongreen {
  background:linear-gradient(to bottom, green 5%, #030 100%);
  background-color: green;
}

.buttonyellow {
  background:linear-gradient(to bottom, yellow 5%, #505 100%);
  background-color: yellow;
}

.buttonblue {
  background:linear-gradient(to bottom, blue 5%, #006 100%);
  background-color: blue;
}

.bigbutton {
  width: 4em;
  height: 4em;
  border-radius:2em;
}

.disabled {
  background:linear-gradient(to bottom, #ddd 5%, #888 100%);
  background-color:#ddd;
  display: none;
}

.button:hover {
  background:linear-gradient(to bottom, #222 5%, #999 100%);
  background-color:#222;
}

.button:active {
  position:relative;
  top:1px;
}

table {
  margin-left:auto;
  margin-right: auto;
  margin-top: 1ex;
  margin-bottom: 1ex;
  border-collapse:collapse;
  background-color: rgba(176, 176, 176, 0.3);
  border-radius:0.5em;
}

.squeeze {
  transform: scaleX(0.7);
}

.hidden {
  display: none;
}

#ir {
  color: white;
  padding-left: 1em;
  padding-right: 0.5em;
  display: inline-block;
}

</style>
</head>

<body>

<form id="remoteform" class="container" method='post' action='#'>

<input class="hidden" type="submit" name="dummy" >

<table>
  <tr>
  <td><button class="button buttonred" type="submit" value="1"  name="power" >O</button></td>
  <td><button class="button squeeze" type="submit" value="8" name="mute"             >MUTE</button></td>
  <td><span id="ir">⇈ </span></td><!-- to signal IR code is being sent -->
  </tr>
</table>


<table>
  <tr>
  <td><button class="button wide" style="margin-right: -2em" type="submit" value="33" name="menu" >MENU</button></td>
  <td></td>
  <td><button class="button" style="border-radius: 1.25em 1.25em 0 0"  type="submit" value="38" name="up"   >↑</button></td>
  <td></td>
  <td><button class="button wide" style="margin-left: -2em" type="submit" value="36" name="exit" >EXIT</button></td>
  </tr>
  <tr>
  <td></td>
  <td><button class="button" style="border-radius: 1.25em 0 0 1.25em" type="submit" value="40" name="left"  >←</button></td>
  <td><button class="button bigbutton"  type="submit" value="42" name="sel"   >OK</button></td>
  <td><button class="button" style="border-radius: 0 1.25em 1.25em 0"  type="submit" value="41" name="right" >→</button></td>
  <td></td>
  </tr>
  <tr>
  <td><button class="button wide" style="margin-right: -2em" type="submit" value="21" name="last"  >()</button></td>
  <td></td>
  <td><button class="button" style="border-radius: 0 0 1.25em 1.25em" type="submit" value="39" name="down"  >↓</button></td>
  <td></td>
  <td><button class="button wide" style="margin-left: -2em" type="submit" value="35" name="guide" >EPG</button></td>
</table>

<table>
  <tr>
  <td><button class="button"  type="submit" value="6" name="volup" >V+</button></td>
  <td><button class="button wide"  type="submit" value="46" name="info"  >INFO</button></td>
  <td><button class="button"  type="submit" value="4"  name="chup"  >P+</button></td>
  </tr>
  <tr>
  <td><button class="button"  type="submit" value="7" name="voldown"   >V−</button></td>
  <td><button class="button wide"  type="submit" value="63" name="FAV" >FAV</button></td>
  <td><button class="button"  type="submit" value="5"  name="chdown"   >P−</button></td>
  </tr>
</table>

<table>
  <tr>
  <td><input class="text" type="text" name="Digits" id="Digits" placeholder="channel" maxlength="4" size="4" value=""><input type="submit" value="↲" ></td>
  </tr>
</table>

<table>
  <tr>
  <td><button class="button"  type="submit" value="9" name="one"    >1</button></td>
  <td><button class="button"  type="submit" value="10" name="two"   >2</button></td>
  <td><button class="button"  type="submit" value="11" name="three" >3</button></td>
  </tr>
  <tr>
  <td><button class="button"  type="submit" value="12" name="four"  >4</button></td>
  <td><button class="button"  type="submit" value="13" name="five"  >5</button></td>
  <td><button class="button"  type="submit" value="14" name="six"   >6</button></td>
  </tr>
  <tr>
  <td><button class="button"  type="submit" value="15" name="seven" >7</button></td>
  <td><button class="button"  type="submit" value="16" name="eight" >8</button></td>
  <td><button class="button"  type="submit" value="17" name="nine"  >9</button></td>
  </tr>
  <tr>
  <td><button class="button"  type="submit" value="44" name="pgup"   >Pg+</button></td>
  <td><button class="button"  type="submit" value="18" name="zero"   >0</button></td>
  <td><button class="button"  type="submit" value="43" name="pgdown" >Pg−</button></td>
  </tr>
</table>

<table>
  <tr>
  <td><button class="button buttonred"  type="submit" value="74" name="red"      >R</button></td>
  <td><button class="button buttongreen" type="submit" value="75" name="green"   >G</button></td>
  <td><button class="button buttonyellow" type="submit" value="76" name="yellow" >Y</button></td>
  <td><button class="button buttonblue" type="submit" value="77" name="blue"     >B</button></td>
  </tr>
</table>


<table>
  <tr>
  <td><button class="button" type="submit" value="26" name="pause"    >II</button></td>
  <td><button class="button"  type="submit" value="27" name="rewind"  >«</button></td>
  <td><button class="button"  type="submit" value="28" name="forward" >»</button></td>
  </tr>
  <tr>
  <td><button class="button" style="color:red" type="submit" value="29" name="record" >●</button></td>
  <td><button class="button"  type="submit" value="24" name="play" >▶</button></td>
  <td><button class="button"  type="submit" value="25" name="stop" >■</button></td>
  </tr>
</table>

<table>
  <tr>
  <td><button class="button wide squeeze" type="submit" value="64" name="sat"     >SAT</button></td>
  <td><button class="button wide squeeze" type="submit" value="71" name="sub"     >SUB</button></td>
  <td><button class="button wide squeeze" type="submit" value="69" name="tvradio" >TV/R</button></td>
  </tr>
</table>

<table>
  <tr>
  <td><button class="button"  type="submit" value="65" name="search" >🔍</button></td>
  <td><button class="button"  type="submit" value="62" name="audio"  >A/B</button></td>
  <td><button class="button"  type="submit" value="66" name="txt"    >TXT</button></td>
  </tr>
</table>

<table>
  <tr>
  <td><button class="button" style="color:red" type="submit" value="-1" name="killmyself" >☠</button></td>
  </tr>
</table>


<script>

const irFlash = [
  { color: "red" },
  { color: "white" },
];

const irFlashTiming = {
  duration: 100,
  iterations: 1,
};

function sendCode(buttonName, buttonValue) {
    const dataString = encodeURIComponent(buttonName) + '=' + encodeURIComponent(buttonValue);
    const xhr = new XMLHttpRequest(); // Create XHR object
    xhr.open('POST', ''); // Set request method and URL
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.onload = () => {
      if (xhr.status === 200) {
        // console.log('Button code submitted successfully:', buttonName, buttonValue);
        document.getElementById('ir').animate(irFlash, irFlashTiming);
      } else {
        console.error('Error submitting:', xhr.statusText);
      }
    };
    xhr.send(dataString);
}

function addButtonListeners(buttons) {
    for (let submitButton of buttons)  {
        submitButton.addEventListener('click', (event) => {
            event.preventDefault();
            const buttonName = submitButton.getAttribute('name');
            const buttonValue = submitButton.getAttribute('value');
            sendCode(buttonName, buttonValue);
        });
    }
}


/* create a table of all possible keycodes */
var isFilled = false;

function autoFill () {
    if (isFilled) {
      return;
    }
    let table = document.getElementById('autofill');
    for (let row = 0; row <= 8; row++) {
        let rowNode = document.createElement('tr');
        for (let column = 0; column <= 9; column++) {
            let cellNode = document.createElement('td');
            let buttonNode = document.createElement('button');
            let code = 10*row+column;
            if (code > 81) {
                break;
            }
            buttonNode.textContent = code;
            buttonNode.setAttribute('name', `C${code}`);
            buttonNode.setAttribute('value', code);
            buttonNode.classList.add('button');
            cellNode.appendChild(buttonNode);
            rowNode.appendChild(cellNode);
            addButtonListeners([buttonNode]);
        }
        table.appendChild(rowNode);
    }
    isFilled = true;
}

const submitButtons = document.querySelectorAll('button[type="submit"]');
addButtonListeners(submitButtons);
</script>


<details ontoggle="autoFill()">
<summary>codes</summary>
<table id="autofill">
</table>
</details>

<div class="statusline">Status:%s</div>

</form>
</body>
</html>

'''
    default_buttons='''
        buttons=
        '7' : 15
        :&nbsp;&nbsp;
        '8' : 16
        :&nbsp;&nbsp;
        '9' : 17
        :&nbsp;&nbsp;
        :<br>
        '4' : 12
        :&nbsp;&nbsp;
        '5' : 13
        :&nbsp;&nbsp;
        '6' : 14
        :&nbsp;&nbsp;
        :<br>
        '1' : 9
        :&nbsp;&nbsp;
        '2' : 10
         :&nbsp;&nbsp;
        '3' : 11
        :&nbsp;&nbsp;
        :<br>
        '0' : 18
        :<br><br>
        'OK' : 42
         :&nbsp;&nbsp;
        '↑' : 38
        :&nbsp;&nbsp;
        '↓' : 39
        :&nbsp;&nbsp;
        '←' : 40
        :&nbsp;&nbsp;
        '→': 41
        :<br><br>
        :&nbsp;&nbsp;
        'Guide' : 35
        :&nbsp;&nbsp;
        'Last' : 56
        :&nbsp;&nbsp;
        'Exit' : 37
        :&nbsp;&nbsp;
        'DVR' : 23
        :<br><br>
        'FF' : 28
        :&nbsp;&nbsp;
        'Rew' : 27
        :&nbsp;&nbsp;
        'Play' : 24
        :&nbsp;&nbsp;
        'Pause' : 26
        : <br><br>
        'Ch+' : 4
        :&nbsp;&nbsp;
        'Ch-' : 5
        :&nbsp;&nbsp;
        'Pg-' : 43
        :&nbsp;&nbsp;
        'Pg+' : 44
        : <br><br>
        'Day-' : 59
        :&nbsp;&nbsp;
        'Day+' : 60
        :<br><br>
        'Rec' : 29
        :&nbsp;&nbsp;
        'OnDemand': 34
        :&nbsp;&nbsp;
        'Menu' : 33
        :<br><br>
        'Power' : 1
        'Restart': -1
        :<br><br>
        'Channel': Channel
        :&nbsp;&nbsp;'''

    data = default_remote_html
#    print(section_name)
    remoteinfo = cp[section_name]
    rccode = remoteinfo.get('code', '')
#    print('rccode1', rccode)
    if not rccode: 
        remoteinfo.get('RemoteCode', '')
#        print('rccode2', rccode)
    if not rccode :
        if section_name == 'REMOTE' :
            rccode = cp['SLINGBOX'].get('RemoteCode', '')
            if not rccode : rccode = cp['SLINGBOX'].get('VideoSource', '')
        else:
            rccode = remoteinfo.get('RemoteCode', '')
            if not rccode: rccode = remoteinfo.get('VideoSource', '')
 #   print('rccode3', rccode)        
    if not rccode:
        print('WARNING: Remote Control Code not set. Set RemoteCode or VideoSource\r\nDefaulting to 0 which is probably wrong')
        rccode = '0'
    rccode = int(rccode)   
          
    if cp.has_option(section_name, 'Remote'):
        fn= remoteinfo.get('Remote', '')
    else:
        fn = remoteinfo.get('include', '')

    if fn:  # Get form data myself
        print('Reading Custom Remote definition from', fn)
        try:
            f = open(fn, 'rb')
            data = f.read()
            f.close()
            data = data.decode('UTF-8', errors='ignore')
#            print('STYLE', style,'BUTTONS', buttons)
        except Exception as e:
            print('Error reading remote definition file, using defaults', e, traceback.print_exc())
    else:
        print('Using built in default remote page definition.')

    if fn.lower().endswith('.html') or fn=='':
        page = data
        cmds = parse_html(page)
    else:
        start_style = data.find('style=')
        start_buttons = data.find('buttons=')
        style=data[start_style+6:start_buttons].strip()
        buttons = data[start_buttons+8:].strip()
        style = style.replace('%', '%%')
        linecount = data[0:start_buttons].count('\n')
        cmds = parse_buttons(buttons, linecount)
 #       print(cmds)
        formstr = ''
        for key, data in cmds:
            if key == '':
                formstr = formstr + data
            else:
    #            print('BUTTON', data)
                try: btn_class = data.split(':')[1].strip()
                except: btn_class = 'button'
 #               <button class=round type="submit" name="1" value="9 : round"
                formstr = formstr + '<button class="%s" type="submit" name="%s" value="%s">%s</button>' % (btn_class, key, str(data).split(':')[0].strip(), key)
                if 'Channel' == data:
                    formstr = formstr + '<input class="text" type="text" name="Digits" maxlength="4" size="4" id="" value=""></input>'
        if section_name == 'REMOTE':
            uri = ''
        else: 
            uri = '/' + section_name
        page = BasePage % ( style, uri, formstr )
    return page, cmds, rccode
 
def get_streamer( request, text ):
    port = request.headers.get('Host').split(':')[1]
    try: box = text.split('/')[1]
    except : box = str(port)
#    print('URI', text, 'Remote', box, port, remotes.keys())
    for remote in remotes.keys(): 
#        print('checking ', remote, box)        
        if (box == remote): 
          return (remotes[box][0], request.headers['From'], box)         
    print('Error: Remote URL needs to be one of:')
    for remote in remotes.keys():
        print( '/Remote/%s' % remote.split('/')[-1])
    return (None, None, None)
 
###############################################################################
###########   START OF EXECUTION #####################################
mypid = os.getpid()
print( 'Version :', version, 'Running on', platform.platform(), 'pid=', mypid, sys.argv[0])

streamer_qs = {}
remux_connections = {} # keeps track which connections (sockets) to remux to mp4
stati = {}
remotes = {}
finderids = {}
tcode = 0
num_streams = 0
if len(sys.argv) == 1 : sys.argv.append('config.ini')
for config_fn in sys.argv[1:] :
    if os.path.exists( config_fn ):
        print( 'Using config file', config_fn )
    else:
        print( "Can't find specified config file", config_fn, 'Ignoring' )
        find_slingbox_info('')
        continue

    Thread(target=ConnectionManager, args=(config_fn,)).start()

    cp = ConfigParser()
    cp.read(config_fn)
    serverinfo = cp['SERVER']
    port = int(serverinfo.get('port', '8080'))
    
    http_port = port + 1
    cmds = None
    if serverinfo.get('enableremote', 'yes') == 'yes' :
        try:
            from flask import Flask, render_template, request, render_template_string, abort, send_file
        except:
               print('ERROR. Cannot use Remote Control\nBecause the "Flask" python module has not been installed')
               continue
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
            
        app = Flask(__name__)

        @app.route('/<path:text>', methods=["GET"])
        def index(text):
            print('GET', text)
            if text[1:].startswith('emote'):
                streamer, client, remote = get_streamer( request, text )
 #               print('GetStreamerResult', streamer, client, remote)
                if streamer :
                    page = remotes[remote][1][0]
                   # print(page)
                    if 'Status:%s' in page:
                        #print('Updating Status')
                        return render_template_string( page.replace('Status:%s', stati[remote]))
                    else:
                        #print('Returning page')
                        return render_template_string( page )
                else:
                    abort(404)
            else:
                text = os.getcwd() + '/' + text
                if text.endswith('.php') :
                    if os.path.exists(text):
                        print('Running PHP script', text)
                        out = subprocess.run(["php", text], stdout=subprocess.PIPE)
      #                  print(out.stdout)
                        return out.stdout
                    else: abort(404)
                elif text.endswith('.html'):
                    if os.path.exists(text):
                        print('Returning HTML file', text)
                        return send_file(text, mimetype='text/html')
                    else: abort(404)
                else:
                    print(text)
                    if os.path.exists(text):
                        mime = mimetypes.guess_type(text)[0]
 #                       print('Returning', text, mime)
                        return send_file(text, mime)
                    else: abort(404)

        @app.route('/<path:text>', methods=["POST"])
        def button(text):
            global streamer_qs, tcode, stati
            
            def send_pro_control(keyid):
                msg = bytearray(1) + bytes('ProHD=%s:%s' % (keyid,client), 'utf-8')
                print('ProHD', keyid)
                streamer_q.put(msg)
            
            def SendChannelDigits(channel):
                print('Sending Channel Digits', channel)
                if '.' in channel: # ProHD
                    if channel.endswith('.') : channel = channel + '0'
                    send_pro_control('2.' + channel)
                else:
                    keylist = []
                    for digit in channel:
                        if digit in '0123456789' :
                            keylist.append(
                       digits2buttons[int(digit)].to_bytes(1, byteorder='little')+ bytes(client, 'utf-8'))
                    streamer_q.put(keylist)

            streamer, client, remote = get_streamer( request, text )
#            print('GetStreamer', streamer, client, remote)
            if not streamer : abort(404)
            streamer_q = streamer_qs[streamer]
            Page, cmds, rccode = remotes[remote][1]          
            digits2buttons = [18,9,10,11,12,13,14,15,16,17]
 #           print('Button Clicked', request.form, client, cmds)
  #          for x in request.form.items() : print('Key Data', x)
            if request.form.get('Digits'):
                channel = request.form.get('Digits').strip()
                if channel[0] == '?' :
                    print('Sending test keycode', channel[1:] )
                    if '.' in channel:  # ProHD
                        send_pro_control(channel[1:] + '.0')
                    else:
                        kc = int(channel[1:])
                        streamer_q.put([kc.to_bytes(1, byteorder='little')])
                else: SendChannelDigits(channel)
            else:
 #               print('POST', request.form)
                for keyname, keycode in request.form.items():
  #                  print('key data', keyname, keycode)                   
                    if keyname == 'Digits': continue
                    else:
                        if keyname == 'RCtest':
                            stati[streamer] = 'Remote Code testing is depreicated. Please use VideoSource'
                        elif keyname == 'Restart' :
                            print('Restarting, killing myself')
                            killmyself()
                        elif keyname == 'Channel' : pass # Channel request with no digits
                        else:
                            data = keycode.split(':')[0].strip()
                            print( 'Remote', keyname, data )
                            if data.startswith('?') : 
                                SendChannelDigits(data[1:])
                            elif '.' in data:
                                send_pro_control(data + '.0')
                            else:
                                keycodes = []
                                for keycode in data.split(','):
                                    if keycode.strip()=='-1': 
                                        print('Alert:Received keycode -1. Restarting...')
                                        killmyself()
                                    keycodes.append(
                                    int(keycode).to_bytes(1, byteorder='little') + bytes(client, 'utf-8'))
                                streamer_q.put(keycodes)
                             
            if 'Status:%s' in Page:
                return render_template_string(Page.replace('Status:%s', stati[remote]))
            else:                   
                return render_template_string(Page)

        Thread(target=lambda: app.run(host='127.0.0.1', port=http_port, debug=False, use_reloader=False)).start()
        time.sleep(1) # give Flask sometime to start up makes logs easier to read

Thread(target=BroadcastResponder).start() 


try:
    import netifaces
    ips = ip4_addresses()
    for local_ip,x,x in ips:
        if local_ip == '127.0.0.1': continue
        if local_ip.startswith('169.254.') : continue
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try: s.bind((local_ip, 0))
            except Exception as e: continue
            print('Server IP address is', local_ip)
except:
    pass
    
#print(streamer_qs.keys(), remotes.keys(), stati.keys())
try: 
  while True: time.sleep(1)
except: os._exit(200)
