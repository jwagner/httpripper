import atexit
from datetime import datetime
from os import path
import SocketServer
import shutil
import sys
import socket
import tempfile
import urllib2
from urlparse import urlparse


import logging
logger = logging

socket.setdefaulttimeout(30)


class HTTPProxyHandler(SocketServer.StreamRequestHandler):
    def handle(self):
        # that function is a bit nasty and complex and should be refactored..
        # parse request
        request = self.rfile.readline().strip()
        logger.debug("request %r", request)
        method, rawurl, version = request.split(" ")
        url = urlparse(rawurl)
        # open socket
        logger.debug("opening socket")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((url.hostname, int(url.port or 80)))
        # send request
        new_request = "%s %s?%s HTTP/1.0\r\n" % (method, url.path or "/", url.query)
        logger.debug("sending request %r", new_request)
        s.sendall(new_request)
        f = s.makefile("rw", 0)
        # forward headers
        logger.debug("processing headers")
        clen = 0
        for line in self.rfile:
            if not line.strip():
                break
            key, value = line.split(":", 1)
            if line.startswith("Connection:") or line.startswith("Proxy-") or line.startswith("Keep-Alive"):
                continue
            if key == "Content-Length":
                clen = int(value)
                logging.info("Got Content-Length: %r", clen)
            logger.debug("forwarding header %r", line)
            s.sendall(line)
        s.sendall("Connection: close\r\n\r\n")
        # send post data?
        if method == "POST":
            logger.debug("getting post data")
            data = self.rfile.read(clen)
            logger.debug("sending POST data %r", data)
            f.write(data)
            f.write("\r\n")
        if self.server.record:
            if sys.platform.startswith("win"):
                # screw windows
                name = tempfile.mktemp(prefix="proxpy-", dir=self.server.tempdir)
                data = open(name, "wb")
                data.name = name
            else:
                data = tempfile.NamedTemporaryFile(prefix="proxpy-", dir=self.server.tempdir)
                data.close_called = True
        # pass response headers
        for line in f:
            logger.debug("passig response header %r", line)
            self.wfile.write(line)
            if not line.strip():
                break
        logger.debug("passing request body")
        while 1:
            buf = f.read(1024)
            if not buf:
                break
            self.wfile.write(buf)
            if self.server.record:
                data.write(buf)
        if self.server.record:
            data.file.close()
            self.server.on_new_file(rawurl, data.name)
        logger.debug("closing connection")
        s.close()
        logger.debug("done")


class HTTPProxyServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr):
        self.tempdir = tempfile.mkdtemp(prefix="proxpy")
        atexit.register(shutil.rmtree, self.tempdir)
        self.record = False
        SocketServer.TCPServer.__init__(self, addr, HTTPProxyHandler)

    def on_new_file(self, url, path):
        print "new file", url, path

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    server = HTTPProxyServer(("localhost", 8080))
    server.record = True
    server.serve_forever()

