from NotifierClass import Notifier

import twitter
from datetime import datetime, timedelta
import time
import threading

class TFFPNotifier(Notifier):

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
		self.waitminutes = cfgParser.getint(insec,"waitminutes")
		try:
			self.hashtag = cfgParser.get(insec,"hashtag").strip()
		except:
			self.hashtag = "#tweetsfromfirstplace"
		try:
			self.viatag = cfgParser.get(insec,"viatag").strip()
		except:
			self.viatag = "/via bot"
	
	def pushResults(self,newres):
		# the only thing this cares about is the final, and *that* only matters once x minutes have passed.
		if "finals" in newres:
			for finalDict in newres["finals"]:
				if "result" in finalDict:
					if (finalDict["result"] == "win" and "1st" in finalDict["standings"]):
						waittweet = threading.Thread(target=self._wait_and_tweet,args=())
						#print "thread constructed"
						waittweet.start()
					
	def _wait_and_tweet(self):
		api = twitter.Api(consumer_key=self.conskey, consumer_secret=self.conssecret,
			access_token_key=self.acctokenkey, access_token_secret=self.acctokensecret)				
		#print "got api, waiting"
		if self.screenname == '':
			api.PostUpdate(self.hashtag + " " + self.viatag)
		else:
			time.sleep(60*self.waitminutes)
			#print "calling has_t"
			if not self._has_tweeted(api):
				#print "tweeting!"
				api.PostUpdate(self.hashtag + " " + self.viatag)
	
	def _has_tweeted(self,api):
		tl = api.GetUserTimeline(screen_name=self.screenname)
		curt = datetime.utcnow()
		for st in tl:
			st_datetime = datetime.strptime(st.created_at,"%a %b %d %H:%M:%S +0000 %Y")
			if ( (curt-st_datetime) > timedelta(minutes=self.waitminutes+10) ):
				# we're out of tweets within the range we have to care about
				break
			elif self.hashtag in st.text:
				# already tweeted, go home
				return True
		return False