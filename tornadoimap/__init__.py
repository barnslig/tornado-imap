# coding: utf-8
import socket
import tornado.iostream
import tornado.ioloop
import time
import ssl

class AsyncIMAPClient:
	# Don't forget to specify callback function(s). All methods are
	# able to have their own callback or use the default one that is
	# required. They always look like the following example. /err/ is
	# True if there was an error or False if not. /msg/ is a string.
	#
	#    def callback(err, msg):
	#        (do something)
	#
	def __init__(self, host, callback, ioloop=None, port=143):
		self.ioloop = ioloop or tornado.ioloop.IOLoop.current()
		self.callback = callback
		self.has_login = False
		self.waiters = {}

		self._get_socket(host, port)

	def _id(self):
		return int(time.time())

	def _cmd(self, cmd, callback):
		_id = self._id()
		self.stream.write(bytes("{0} {1}\n".format(_id, cmd).encode("UTF-8")))
		self.waiters[str(_id)] = callback

	def _callback_process(self, data):
		self.stream.read_until(b"\n", self._callback_process)
		data = data.split(b" ")
		tag = str(data[0], "UTF-8")
		if tag in self.waiters.keys():
			self.waiters[tag](b" ".join(data))

	def _get_socket(self, host, port):
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
		self.stream = tornado.iostream.IOStream(s)

		self.stream.connect((host, port))
		self.stream.read_until(b"\n", self._callback_process)


	# Send STARTTLS command and initiates the SSL socket. Add an
	# ssl_context for specific SSL options like own certificates or so
	def starttls(self, ssl_context=None, callback=None):
		if not callback:
			callback = self.callback
		if not ssl_context:
			ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

		def _callback(data):
			resp = data.split(bytes(" ".encode("UTF-8")))
			if resp[1] == b"OK":
				self.ioloop.remove_handler(self.stream.socket.fileno())
				s = ssl_context.wrap_socket(self.stream.socket, do_handshake_on_connect=False)
				self.stream = tornado.iostream.SSLIOStream(s)
				self.stream.read_until(b"\n", self._callback_process)
				callback(0, "STARTTLS done.")
			else:
				callback(1, "STARTTLS failed.")
		self._cmd("STARTTLS", _callback)

	# Identify the client
	def login(self, username, password, callback=None):
		if not callback:
			callback = self.callback
		if self.has_login == True:
			callback(1, "Already logged-in!")
			return

		def _callback(data):
			resp = data.split(bytes(" ".encode("UTF-8")))
			if resp[1] == b"OK":
				self.has_login = True
				callback(0, "LOGIN done.")
			else:
				callback(1, "LOGIN failed.")
		self._cmd("LOGIN {0} {1}".format(username, password), _callback)

	# SELECTs a mailbox so that messages in the mailbox can be accessed.
	def select(self, mailbox="INBOX", callback=None):
		if not callback:
			callback = self.callback
		if self.has_login == False:
			callback(1, "Not logged-in!")
			return

		def _callback(data):
			resp = data.split(bytes(" ".encode("UTF-8")))
			if resp[1] == b"OK":
				callback(0, "SELECT done.")
			else:
				callback(1, "SELECT failed.")
		self._cmd("SELECT {0}".format(mailbox), _callback)