from NotifierClass import Notifier

import twitter
from datetime import datetime, timedelta
import time
import threading

class TwitterNotifier(Notifier):

	def __init__(self,cfgParser,insec):
		self.header = insec
		try:
			self.screenname = cfgParser.get(insec,"username").strip()
		except:
			self.screenname = ''
		self.conskey = cfgParser.get(insec,"conskey").strip()
		self.conssecret = cfgParser.get(insec,"conssecret").strip()
		self.acctokenkey = cfgParser.get(insec,"acctokenkey").strip()
		self.acctokensecret = cfgParser.get(insec,"acctokensecret").strip()
		try:
			self.tweeton = cfgParser.get(insec,"tweeton").strip().split(",")
		except:
			self.tweeton = ["win","loss"]
		try:
			self.wintext = cfgParser.get(insec,"wintext").strip()
		except:
			self.wintext = ""
		try:
			self.losstext = cfgParser.get(insec,"wintext").strip()
		except:
			self.losstext = ""
		try:
			self.gamelink = cfgParser.getboolean(insec,"link")
		except:
			self.gamelink = False
		try:
			self.scoretext = cfgParser.get(insec,"scoretext").strip().lower()
			if not (self.scoretext in ["before","after"]):
				raise Exception("scoretext not before or after")
		except:
			self.scoretext = "before"
	
	def pushResults(self,newres):
		# the only thing this cares about is the final, and *that* only matters once x minutes have passed.
		if "finals" in newres:
			for finalDict in newres["finals"]:
				if "result" in finalDict:
					if (finalDict["result"] == "win" and "win" in self.tweeton):
						restext = self.wintext
					elif (finalDict["result"] == "loss" and "loss" in self.tweeton):
						restext = self.losstext
					else:
						restext = "TIE GAME (somehow)"
					
					if (self.scoretext == "before"):
						msg = finalDict["final"] + ". " + restext
						if self.gamelink:
							msg += " " + "GAMELINK"
					else:
						msg = restext
						if self.gamelink:
							msg += "GAMELINK" + " "
						msg += finalDict["final"]
					
					self._tweet(msg)
					
	def _tweet(self,message):
		api = twitter.Api(consumer_key=self.conskey, consumer_secret=self.conssecret,
			access_token_key=self.acctokenkey, access_token_secret=self.acctokensecret)	
		api.PostUpdate(message)
		