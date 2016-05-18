from NotifierClass import Notifier
import urllib, urllib2, traceback, logging, json, re, random
from urlparse import urlsplit

class SlackNotifier(Notifier):
	
	def __init__(self,cfgParser,insec): 
		self.header = insec
		self.webhook = cfgParser.get(insec,"webhook_url").strip()
		try:
			self.useEasterEggs = cfgParser.get("general","useEasterEggs")
		except Exception:
			self.useEasterEggs = False
		self.channels = { }
		for chan in ("backtalk_channel", "announce_channel", "highlight_channel"):
			try:
				self.channels[chan] = "#" + cfgParser.get(insec,chan).strip()
			except Exception as e:
				self.channels[chan] = ""	
		try:
			self.backtalk_atuser = "@" + cfgParser.get(insec,"backtalk_atuser").strip()
		except Exception as e:
			self.backtalk_atuser = ""
		
	def pushResults(self,newres):
		for (blurb, mp4) in newres["highlights"]:
			payloadDict = {"text": (blurb + ": [<" + mp4 + "|mp4>]")}
			self._sendSlack(payloadDict,self.channels["highlight_channel"])
		for finalDict in newres["finals"]:
			whereAreHighlights = ""
			if self.useEasterEggs and re.search("Washington 0",finalDict["final"]):
				random.seed()
				if random.randint(0,3) == 0:
					whereAreHighlights = "You're right, Chris, there are no highlights. Screw this. "
			elif (self.channels["announce_channel"] != self.channels["highlight_channel"]) and (self.channels["highlight_channel"] != ""):
				whereAreHighlights = "Highlights in " + self.channels["highlight_channel"] + ". "
			payloadDict = {"text": "*"+finalDict["final"]+".* "+whereAreHighlights+finalDict["standings"]+"\nNext: "+finalDict["probables"], "link_names" : 1}
			if self.useEasterEggs:
				if re.search(", Washington",finalDict["final"]):
					payloadDict["icon_emoji"] = ":l:"
				else:
					payloadDict["icon_emoji"] = ":w:"
			self._sendSlack(payloadDict,self.channels["announce_channel"])
		if "backtalk" in newres.keys():
			for backtalk in newres["backtalk"]:
				payloadDict = {"text": self.backtalk_atuser + " " + backtalk, "link_names" : 1}
				if self.channels["backtalk_channel"] != "":
					self._sendSlack(payloadDict, self.channels["backtalk_channel"])
				elif self.backtalk_atuser != "":
					self._sendSlack(payloadDict,self.backtalk_atuser)
		if "morningAnnounce" in newres.keys() and len(newres["morningAnnounce"]) > 0:
			text = "Good morning. *TODAY'S GAME*:"
			if (len(newres["morningAnnounce"]) > 1):
				text = re.sub("GAME","GAMES",text)
			for g in newres["morningAnnounce"]:
				text += ("\n" + g)
			payloadDict = {"text":text}
			self._sendSlack(payloadDict,self.channels["announce_channel"])
		for prob in newres["probables"]:
			payloadDict = {"text":"*PROBABLES UPDATE:* " + prob}
			self._sendSlack(payloadDict,self.channels["announce_channel"])
		for ann in newres["announce"]:
			payloadDict = {"text":"*GAME STATUS UPDATE:* " + ann}
			self._sendSlack(payloadDict,self.channels["announce_channel"])
		for underwayDict in newres["underway"]:
			payloadDict = { "text": "*" + underwayDict["game"] + " now underway: <" + underwayDict["audio"] + "|radio> / <" + underwayDict["video"] + "|TV>*" }
			self._sendSlack(payloadDict,self.channels["announce_channel"])
		for lineupsList in newres["lineups"]:
			# home comes first for some reason
			payloadDict = {"attachments" : [{ "mrkdwn_in":["text"],"text":"*Lineups for " + lineupsList[1]["team_name_full"] + " at " + lineupsList[0]["team_name_full"] + "*", "fallback" : "Lineups set for " + lineupsList[1]["team_file_code"].upper() + " at " + lineupsList[0]["team_file_code"].upper(), "fields" : [] }] }
			for tln in reversed(lineupsList): 
				field = {"short":True, "title":tln["team_file_code"].upper(), "value":""}
				for player in tln["players"]:
					field["value"] = field["value"] + ("\n" + player["last_name"] + ", " + player["position"])
				field["value"] = re.sub(r"^\n","",field["value"])
				payloadDict["attachments"][0]["fields"].append(field)
			self._sendSlack(payloadDict,self.channels["announce_channel"])
		
	
	def _sendSlack(self,payloadDict,channel=None):
		try:
			if channel != None and channel != "":
				payloadDict["channel"] = channel
			if self.useEasterEggs and re.search("Roark",payloadDict["text"]) and re.search("Washington|WSH",payloadDict["text"]):
				random.seed()
				if random.randint(0,9) == 0:
					payloadDict["text"] = re.sub("(Tanner |)Roark","STAFF ACE Tanner Roark",payloadDict["text"])
			data = urllib.urlencode({"payload": json.dumps(payloadDict)})
			logging.debug("about to request " + json.dumps(payloadDict) + "\n" + data + "\nat " + self.webhook)
			req = urllib2.Request(self.webhook, data)
			response = urllib2.urlopen(req)
			logging.debug(response.read())
		except Exception, e:
			logging.error("Couldn't post for some reason:\n" + traceback.format_exc(e))
			return
