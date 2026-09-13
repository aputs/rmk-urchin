#!/usr/bin/env python3
# Robust RMKurchin firmware log capture from the USB-serial (CDC-ACM) port.
#
# A short-lived CHILD process owns the serial port (termios via ctypes) and
# writes raw bytes to a pipe. The PARENT reads the pipe and prints text.
#
# Why child + parent:
#   - ctypes/libc termios segfaults at Python interpreter shutdown on this
#     macOS + CPython setup. Keeping that code in a child makes the crash
#     invisible: the parent already streamed the bytes through the pipe.
#   - If the child dies mid-run (segfault, USB drop, etc.), the parent sees the
#     pipe close and re-spawns automatically, so --follow keeps streaming.
import os
import select
import subprocess
import sys
import time

CHILD_SRC = r"""
import ctypes, ctypes.util, glob, os, sys, time
CBAUD = 0o060000
CSTOPB = 0x00000400
CS8 = 0x00000300
CLOCAL = 0x00040000
CREAD = 0x00000080
CRTSCTS = 0x00080000
PARENB = 0x00004000
IXON = 0x00000200
IXOFF = 0x00001000
IXANY = 0x00000400
INLCR = 0x00000004
ICRNL = 0x00000100
ICANON = 0x00000002
ECHO = 0x00000008
ECHOE = 0x00000004
ISIG = 0x00000001
OPOST = 0x00000001
class T(ctypes.Structure):
    _fields_ = [('c_iflag', ctypes.c_uint32), ('c_oflag', ctypes.c_uint32),
                ('c_cflag', ctypes.c_uint32), ('c_lflag', ctypes.c_uint32),
                ('c_cc', ctypes.c_uint8 * 20)]
cands = sorted(glob.glob('/dev/cu.usbmodem*') + glob.glob('/dev/cu.usbserial*'))
if not cands:
    sys.exit(2)
port = cands[0]
baud = int(sys.argv[1]) if len(sys.argv) > 1 else 115200
fd = os.open(port, os.O_RDONLY)
lib = ctypes.CDLL(ctypes.util.find_library('C') or 'libSystem.B.dylib')
t = T()
lib.tcgetattr(fd, ctypes.byref(t))
t.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG)
t.c_oflag &= ~OPOST
t.c_iflag &= ~(IXON | IXOFF | IXANY | INLCR | ICRNL)
t.c_cflag &= ~(CSTOPB | PARENB | CRTSCTS)
t.c_cflag |= (CS8 | CLOCAL | CREAD)
t.c_cflag = (t.c_cflag & ~CBAUD) | baud
# VMIN=1, VTIME=0: block until >=1 byte so an idle port costs no CPU.
# (VMIN=0/VTIME=1 returns empty reads every 0.1s, which this reader mistook
#  for a disconnect and re-opened the port on -> a ~10Hz busy loop.)
t.c_cc[6] = 1
t.c_cc[7] = 0
lib.tcsetattr(fd, 0, ctypes.byref(t))
while True:
    try:
        data = os.read(fd, 65536)
    except OSError:
        data = b''
    if data:
        try:
            os.write(1, data)
        except BrokenPipeError:
            break
    else:
        time.sleep(0.25)  # empty read/disconnect: backoff, don't spin
"""
NO_PORT = 2  # child exit code when no USB-serial device is found


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    follow = '--follow' in sys.argv[1:]
    baud = int(args[0]) if len(args) > 0 else 115200
    duration = float(args[1]) if len(args) > 1 else 8.0
    deadline = time.time() + duration
    sys.stderr.write('logging rmk-urchin firmware (baud=%d, %s); Ctrl-C to stop\n'
                     % (baud, 'follow' if follow else str(duration) + 's'))
    proc = None
    try:
        while True:
            if not follow and time.time() >= deadline:
                break
            proc = subprocess.Popen(
                [sys.executable, '-c', CHILD_SRC, str(baud)],
                stdout=subprocess.PIPE,
            )
            fd = proc.stdout.fileno()
            deadline_reached = False
            while True:
                if not follow and time.time() >= deadline:
                    deadline_reached = True
                    break
                ready, _, _ = select.select([fd], [], [], 0.2)
                if ready:
                    try:
                        chunk = os.read(fd, 4096)
                    except OSError:
                        chunk = b''
                    if not chunk:
                        break  # child closed the pipe (it ended)
                    sys.stdout.write(chunk.decode('utf-8', 'replace'))
                    sys.stdout.flush()
            # inner loop done: child ended, or deadline ended it
            if deadline_reached:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                break  # duration mode: we are done
            code = proc.wait()
            if code == NO_PORT:
                sys.stderr.write('no USB-serial device; waiting...\n')
                time.sleep(0.5)
                continue
            # any other exit (segfault / USB drop): brief backoff, then respawn
            time.sleep(0.25)
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == '__main__':
    main()
