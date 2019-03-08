from NotifierClass import Notifier

class ConsoleTextNotifier(Notifier):
	
	def __init__(self,cfgParser,insec): 
		self.header = insec
		# in a real notifier, you'd do some cfgParser.get(sec,"service_specific_value") = value action here
		
	def pushResults(self,newres):

		if "morningAnnounce" in newres.keys():
			print("TODAY'S GAMES:")
			try:
				for g in newres["morningAnnounce"]:
					print g
			except:
				pass
		
		# everything else, we're just gonna try and pass on KeyErrors
		try:
			for prob in newres["probables"]:
				print "PROBABLES UPDATE: " + prob
		except:
			pass
		try:
			for ann in newres["announce"]:
				print "GAME STATUS UPDATE: " + ann
		except:
			pass
		try:
			for (blurb, mp4) in newres["highlights"]:
				print(blurb + ": " + mp4)
		except:
			pass
		
		for finalDict in newres["finals"]:
			textOut = finalDict["final"]
			if "standings" in finalDict:
				if finalDict["standings"] != "":
					textOut += ", " + finalDict["standings"]
			print textOut
			if finalDict["probables"]:
				print "Next: "+finalDict["probables"]

		try:
			for underwayDict in newres["underway"]:
				print underwayDict["game"] + " now underway. Radio: " + underwayDict["audio"] + ", TV: " + underwayDict["video"]
		except:
			pass
			
