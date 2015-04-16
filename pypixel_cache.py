"""
PyPixel Cache wrapper by @WireSegal and TheDestruc7i0n
You may use this code, as long as you give credit
http://pypixel.thedestruc7i0n.ca/
Allows you to make calls to the Hypixel API through python.


Updated by TheDestruc7i0n to be able to Cache files
"""

#Old imports

import json
import urllib2
import time

#Thanks http://stackoverflow.com/users/100297/martijn-pieters !

import requests_cache, requests

import logging


from datetime import (
	datetime,
	timedelta
)
from requests.exceptions import (
	ConnectionError,
	Timeout,
)
from requests_cache.core import (
	dispatch_hook,
	CachedSession,
)

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

class FallbackCachedSession(CachedSession):
	"""
	Cached session that'll reuse expired cache data on timeouts

	This allows survival in case the backend is down, living of stale
	data until it comes back.

	"""

	def send(self, request, **kwargs):
		# this *bypasses* CachedSession.send; we want to call the method
		# CachedSession.send() would have delegated to!
		session_send = super(CachedSession, self).send
		if (self._is_cache_disabled or
				request.method not in self._cache_allowable_methods):
			response = session_send(request, **kwargs)
			response.from_cache = False
			return response

		cache_key = self.cache.create_key(request)

		def send_request_and_cache_response(stale=None):
			try:
				response = session_send(request, **kwargs)
			except (Timeout, ConnectionError):
				if stale is None:
					raise
				log.warning('No response received, reusing stale response for '
							'%s', request.url)
				return stale

			if stale is not None and response.status_code == 500:
				log.warning('Response gave 500 error, reusing stale response '
							'for %s', request.url)
				return stale

			if response.status_code in self._cache_allowable_codes:
				self.cache.save_response(cache_key, response)
			response.from_cache = False
			return response

		response, timestamp = self.cache.get_response_and_time(cache_key)
		if response is None:
			return send_request_and_cache_response()

		if self._cache_expire_after is not None:
			is_expired = datetime.utcnow() - timestamp > self._cache_expire_after
			if is_expired:
				self.cache.delete(cache_key)
				# try and get a fresh response, but if that fails reuse the
				# stale one
				return send_request_and_cache_response(stale=response)

		# dispatch hook here, because we've removed it before pickling
		response.from_cache = True
		response = dispatch_hook('response', request.hooks, response, **kwargs)
		return response


def basecache_delete(self, key):
	# We don't really delete; we instead set the timestamp to
	# datetime.min. This way we can re-use stale values if the backend
	# fails
	try:
		if key not in self.responses:
			key = self.keys_map[key]
		self.responses[key] = self.responses[key][0], datetime.min
	except KeyError:
		return

from requests_cache.backends.base import BaseCache
BaseCache.delete = basecache_delete

requests_cache.install_cache(
	'HypixelAPI', backend='sqlite', expire_after=600,
	session_factory=FallbackCachedSession)

#Begin old code, with changes

def expandUrlData(data):
	string = "?" # the base for any url
	dataStrings = []
	for i in data:
		dataStrings.append(i+"="+data[i])
	string += "&".join(dataStrings)
	return string


def urlopen(url, t, ua, params={}):
	url += expandUrlData(params)
	res = requests.get(url, headers = { 'User-Agent': ua }, timeout = t)
	html = res.json()
	#html = urllib2.urlopen(req).read()
	try:
		html["Cached"] = res.from_cache
	except AttributeError:
		html["Cached"] = True
	#html["Timestamp"] = int(time.time()*1000)
	return html

def noncache_urlopen(url, t, ua, params={}):
	url += expandUrlData(params)
	req = urllib2.Request(url, headers = { 'User-Agent': ua })
	html = urllib2.urlopen(req, timeout = t).read()
	return json.loads(html)

class HypixelAPI:
	base = "https://api.hypixel.net/"
	def __init__(self, key, timeout = 3, ua = 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36'):
		self.key = key
		self.timeout = timeout
		self.ua = ua
		self.baseParams = {"key": self.key}

	def keyRequest(self):
		url = self.base + "key"
		params = self.baseParams
		timeout = self.timeout
		ua = self.ua
		return noncache_urlopen(url, timeout, ua, params)
		
	def boosters(self):
		url = self.base + "boosters"
		params = self.baseParams
		timeout = self.timeout
		ua = self.ua
		return urlopen(url, timeout, ua, params)

	def friends(self, username):
		url = self.base + "friends"
		params = self.baseParams
		timeout = self.timeout
		ua = self.ua
		params["player"] = username
		return urlopen(url, timeout, ua, params)

	def guildByMember(self, username):
		url = self.base + "findGuild"
		params = self.baseParams
		timeout = self.timeout
		ua = self.ua
		params["byPlayer"] = username
		return urlopen(url, timeout, ua, params)

	def guildByName(self, name):
		url = self.base + "findGuild"
		params = self.baseParams
		timeout = self.timeout
		ua = self.ua
		params["byName"] = name
		return urlopen(url, timeout, ua, params)

	def guildByID(self, guildID):
		url = self.base + "guild"
		params = self.baseParams
		timeout = self.timeout
		ua = self.ua
		params["id"] = guildID
		return urlopen(url, timeout, ua, params)

	def session(self, username):
		url = self.base + "session"
		params = self.baseParams
		timeout = self.timeout
		ua = self.ua
		params["player"] = username
		return noncache_urlopen(url, timeout, ua, params)

	def userByUUID(self, uuid):
		url = self.base + "player"
		params = self.baseParams
		timeout = self.timeout
		ua = self.ua
		params["uuid"] = uuid
		return urlopen(url, timeout, ua, params)
		
	def userByName(self, name):
		url = self.base + "player"
		params = self.baseParams
		timeout = self.timeout
		ua = self.ua
		params["name"] = name
		return urlopen(url, timeout, ua, params)


class MultiKeyAPI:
	def __init__(self, keys, delay = 5, debug = False, timeout = 3, ua = 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36'):
		self.apis = [HypixelAPI(i, timeout = timeout, ua = ua) for i in keys]
		self.apii = 0
		self.api = self.apis[self.apii]
		self.delay = delay
		self.debug = debug

	def _changeInstance(self):
		self.apii += 1
		self.apii %= len(self.apis)
		self.api = self.apis[self.apii]

	def _throttleproofAPICall(self, callType, *args):
		loaded = getattr(self.api, callType)(*args)
		while "throttle" in loaded:
			if self.debug: 
				print("Throttled, changing instance")
			time.sleep(self.delay)
			self._changeInstance()
			loaded = getattr(self.api, callType)(*args)
		return loaded

	def keyRequest(self):           return self._throttleproofAPICall("keyRequest")
	def boosters(self):             return self._throttleproofAPICall("boosters")
	def friends(self, username):        return self._throttleproofAPICall("friends", username)
	def guildByMember(self, username):  return self._throttleproofAPICall("guildByMember", username)
	def guildByName(self, name):        return self._throttleproofAPICall("guildByName", name)
	def guildByID(self, guildID):       return self._throttleproofAPICall("guildByID", guildID)
	def session(self, username):        return self._throttleproofAPICall("session", username)
	def userByUUID(self, uuid):         return self._throttleproofAPICall("userByUUID", uuid)
	def userByName(self, name):         return self._throttleproofAPICall("userByName", name)
