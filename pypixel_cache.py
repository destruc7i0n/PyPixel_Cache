"""
PyPixel Cache wrapper by @WireSegal and TheDestruc7i0n
You may use this code, as long as you give credit
http://pypixel.thedestruc7i0n.ca/
Allows you to make calls to the Hypixel API through python.


Updated by TheDestruc7i0n to be able to Cache files
"""

#Old imports

import json
#import urllib2
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


class FallbackCachedSession(CachedSession):
	"""Cached session that'll reuse expired cache data on timeouts

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
	'HypixelAPI', backend='sqlite', expire_after=999999999999,
	session_factory=FallbackCachedSession)

#Begin old code, with changes

def expandUrlData(data):
	"""
	dict -> a param string to add to a url
	"""
	string = "?" # the base for any url
	dataStrings = []
	for i in data:
		dataStrings.append(i+"="+data[i])
	string += "&".join(dataStrings)
	return string


def urlopen(url, t, params={}):
	"""
	string, dict -> data from the url
	"""
	url += expandUrlData(params)
	res = requests.get(url, headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36' }, timeout = t).text
	html = json.loads(res)
	#html = urllib2.urlopen(req).read()
	html["Cached"] = res.from_cache
	return html

class HypixelAPI:
	"""
	A class that allows you to make hypixel api calls.
	string -> api class
		"""
	base = "https://api.hypixel.net/"
	def __init__(self, key, timeout = 3):
		self.key = key
		self.timeout = timeout
		self.baseParams = {"key": self.key}

	def keyRequest(self):
		"""
		nothing -> dict of stats for your api key
		"""
		url = self.base + "key"
		params = self.baseParams
		timeout = self.timeout
		return urlopen(url, timeout, params)
		
	def boosters(self):
		"""
		nothing -> gets list of boosters
		"""
		url = self.base + "boosters"
		params = self.baseParams
		timeout = self.timeout
		return urlopen(url, timeout, params)

	def friends(self, username):
		"""
		string -> dict of friends of the player USERNAME
		"""
		url = self.base + "friends"
		params = self.baseParams
		timeout = self.timeout
		params["player"] = username
		return urlopen(url, timeout, params)

	def guildByMember(self, username):
		"""
		string -> dict of a hypixel guild containing player USERNAME
		"""
		url = self.base + "findGuild"
		params = self.baseParams
		timeout = self.timeout
		params["byPlayer"] = username
		return urlopen(url, timeout, params)

	def guildByName(self, name):
		"""
		string -> dict of a hypixel guild named NAME
		"""
		url = self.base + "findGuild"
		params = self.baseParams
		timeout = self.timeout
		params["byName"] = name
		return urlopen(url, timeout, params)

	def guildByID(self, guildID):
		"""
		string -> dict of a hypixel guild with id GUILDID
		"""
		url = self.base + "guild"
		params = self.baseParams
		timeout = self.timeout
		params["id"] = guildID
		return urlopen(url, timeout, params)

	def session(self, username):
		"""
		string -> dict of USERNAME's session
		"""
		url = self.base + "session"
		params = self.baseParams
		timeout = self.timeout
		params["player"] = username
		return urlopen(url, timeout, params)

	def userByUUID(self, uuid):
		"""
		string -> information about player with uuid UUID
		"""
		url = self.base + "player"
		params = self.baseParams
		timeout = self.timeout
		params["uuid"] = uuid
		return urlopen(url, timeout, params)
		
	def userByName(self, name):
		"""
		string -> information about player with name NAME
		"""
		url = self.base + "player"
		params = self.baseParams
		timeout = self.timeout
		params["name"] = name
		return urlopen(url, timeout, params)


class MultiKeyAPI:
	"""
	A class that handles using multiple keys for more requests-per-minute. 
	Acts exactly like HypixelAPI for making API calls.
	list -> api class
	list, int -> api class with delay of int seconds
	list, int, bool -> api with delay of int seconds with debug mode in bool
	"""
	def __init__(self, keys, delay = 5, debug = False, timeout = 3):
		self.apis = [HypixelAPI(i, timeout = timeout) for i in keys]
		self.apii = 0
		self.api = self.apis[self.apii]
		self.delay = delay
		self.debug = debug

	def _changeInstance(self):
		self.apii += 1
		if self.apii >= len(self.apis):
			self.apii = 0
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
