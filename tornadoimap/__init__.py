# coding: utf-8
import socket
import tornado.iostream
import tornado.ioloop
import time
import ssl
import re

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
		self.has_select = False
		self.waiters = {}

		self._get_socket(host, port)

	def _id(self):
		return int(time.time())

	def _cmd(self, cmd, callback):
		_id = self._id()
		self.stream.write(bytes("{0} {1}\n".format(_id, cmd).encode("UTF-8")))
		self.waiters["^{0} ".format(str(_id))] = callback

	def _callback_process(self, data):
		has_literals = False

		def _call_waiter(data):
			match = re.match("(" + ")|(".join(self.waiters.keys()) + ")", str(data, "UTF-8"))
			if match:
				key = list(self.waiters.keys())[match.lastindex-1]
				self.waiters[key](data)

		# literals
		def _callback_process_append(ad, data):
			data += ad
			_call_waiter(data)

		if b"{" in data:
			has_literals = True
			literal = data.split(b"{")[1]
			literal = int(literal.split(b"}")[0])
			self.stream.read_bytes(literal, lambda ad: _callback_process_append(ad, data))

		# default stuff
		self.stream.read_until(b"\n", self._callback_process)
		if not has_literals:
			_call_waiter(data)

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
				self.has_select = True
				callback(0, "SELECT done.")
			else:
				callback(1, "SELECT failed.")
		self._cmd("SELECT {0}".format(mailbox), _callback)

	# SEARCH mailbox for matching messages. Look for criterias at
	# https://tools.ietf.org/html/rfc3501#section-6.4.4
	def search(self, criteria, callback=None):
		if not callback:
			callback = self.callback
		if not self.has_select:
			callback(1, "No mailbox selected!")
			return
		if self.has_login == False:
			callback(1, "Not logged-in!")
			return

		def _callback(data):
			resp = data.split(bytes(" ".encode("UTF-8")))
			if resp[1] != b"OK":
				callback(1, "SEARCH failed.")

		def _callback_results(data):
			data = data.split(b" ")
			del data[0]
			del data[0]
			data[-1] = data[-1].replace(b"\r\n", b"")
			callback(0, data)

		self.waiters["^\* SEARCH"] = _callback_results
		self._cmd("SEARCH {0}".format(criteria), _callback)

	# Retrieve data associated with the message /set/. Look at
	# https://tools.ietf.org/html/rfc3501#section-6.4.5 for
	# parts / item names
	def fetch(self, set, part, callback=None):
		if not callback:
			callback = self.callback
		if not self.has_select:
			callback(1, "No mailbox selected!")
			return
		if self.has_login == False:
			callback(1, "Not logged-in!")
			return

		def _callback(data):
			resp = data.split(bytes(" ".encode("UTF-8")))
			if resp[1] != b"OK":
				callback(1, "FETCH failed.")

		def _callback_results(data):
			callback(0, data)

		self.waiters["^\* [0-9+] FETCH"] = _callback_results
		self._cmd("FETCH {0} {1}".format(set, part), _callback)