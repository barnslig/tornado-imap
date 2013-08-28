# coding: utf-8
import tornadoimap
import tornado.ioloop

def callback(err, msg):
	print(err)
	print(msg)

def searchCB(e, m):
	callback(e, m)
	for s in m:
		M.fetch(str(s, "UTF-8"), "(RFC822)")

def selectCB(e, m):
	callback(e, m)
	M.search("ALL", callback=searchCB)

def loginCB(e, m):
	callback(e, m)
	if e == 0:
		M.select(callback=selectCB)

def starttlsCB(e, m):
	callback(e, m)
	if e == 0:
		M.login("leonard", "supersicher", loginCB)

M = tornadoimap.AsyncIMAPClient("localhost", callback)
M.starttls(callback=starttlsCB)

tornado.ioloop.IOLoop.instance().start()