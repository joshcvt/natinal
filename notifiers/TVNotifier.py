from .NotifierClass import Notifier

import twitter
import re

class TVNotifier(Notifier):

	def __init__(self,cfgParser,insec):
		self.header = insec
		self.conskey = cfgParser.get(insec,"conskey").strip()
		self.conssecret = cfgParser.get(insec,"conssecret").strip()
		self.acctokenkey = cfgParser.get(insec,"acctokenkey").strip()
		self.acctokensecret = cfgParser.get(insec,"acctokensecret").strip()
		try:
			self.tweetif = cfgParser.get(insec,"tweetif").strip().split(",")
		except:
			self.tweetif = None
		
	
	def pushResults(self,newres):
		# the only thing this cares about is the final, and *that* only matters once x minutes have passed.
		
		if "morningAnnounce" in list(newres.keys()) and len(newres["morningAnnounce"]) > 0:
			toTweet = []
			for game in newres["morningAnnounce"]:
				lines = game.split("\n")
				gameOn = []
				for line in lines:
					if re.search("^TV: ",line):
						channels = line.split("TV: ")[1].split(", ")
						for ch in channels:
							if ch in self.tweetif:
								gameOn.append(ch)
				if len(gameOn) > 0:
					toTweet.append(lines[0] + " on " + ", ".join(gameOn))
			
			for msg in toTweet:
				self._tweet(msg)
					
	def _tweet(self,message):
		api = twitter.Api(consumer_key=self.conskey, consumer_secret=self.conssecret,
			access_token_key=self.acctokenkey, access_token_secret=self.acctokensecret)	
		api.PostUpdate(message)
		