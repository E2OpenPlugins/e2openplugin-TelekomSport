from Tools.BoundFunction import boundFunction

from twisted.web.client import Agent, BrowserLikeRedirectAgent, readBody, ResponseDone
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.internet import reactor
from twisted.web.http_headers import Headers

#==== workaround for TLSv1_2 with DreamOS =======
from OpenSSL import SSL
from twisted.internet.ssl import ClientContextFactory
try:
	# available since twisted 14.0
	from twisted.internet._sslverify import ClientTLSOptions
except ImportError:
	ClientTLSOptions = None
#================================================

try:
	from enigma import eMediaDatabase

	import ssl
	try:
		_create_unverified_https_context = ssl._create_unverified_context
	except AttributeError:
		pass
	else:
		ssl._create_default_https_context = _create_unverified_https_context
except:
	pass

class TelekomSportFileSaver(Protocol):

	def __init__(self, finished, callback, errorCallback, filename):
		self.finished = finished
		self.callback = callback
		self.errorCallback = errorCallback
		self.filename = filename
		self.f = open(filename, 'wb')

	def dataReceived(self, bytes):
		self.f.write(bytes)

	def connectionLost(self, reason):
		self.f.close()
		if reason.check(ResponseDone):
			self.callback()
		else:
			self.errorCallback(reason.getErrorMessage())


class TelekomSportFileDownloader:

	def __init__(self, isDreamOS):
		if isDreamOS == False:
			self.agent = BrowserLikeRedirectAgent(Agent(reactor))
		else:
			class WebClientContextFactory(ClientContextFactory):
				"A SSL context factory which is more permissive against SSL bugs."

				def __init__(self):
					self.method = SSL.SSLv23_METHOD

				def getContext(self, hostname=None, port=None):
					ctx = ClientContextFactory.getContext(self)
					# Enable all workarounds to SSL bugs as documented by
					# http://www.openssl.org/docs/ssl/SSL_CTX_set_options.html
					ctx.set_options(SSL.OP_ALL)
					if hostname and ClientTLSOptions is not None: # workaround for TLS SNI
						ClientTLSOptions(hostname, ctx)
					return ctx

			contextFactory = WebClientContextFactory()
			self.agent = BrowserLikeRedirectAgent(Agent(reactor, contextFactory))

	def start(self, url, filename, callback, errorCallback):
		self.filename = filename
		d = self.agent.request('GET', url, Headers({'user-agent': ['Twisted']}))
		d.addCallback(boundFunction(self.handleResponse, callback, errorCallback))
		d.addErrback(errorCallback)

	def handleResponse(self, callback, errorCallback, response):
		finished = Deferred()
		response.deliverBody(TelekomSportFileSaver(finished, callback, errorCallback, self.filename))
		return finished

