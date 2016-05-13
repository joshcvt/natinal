from NotifierClass import Notifier

class ConsoleTextNotifier(Notifier):
	
	def __init__(self,cfgParser,insec): 
		self.header = insec
		# in a real notifier, you'd do some cfgParser.get(sec,"service_specific_value") = value action here
		
	def pushResults(self,newres):
		if "morningAnnounce" in newres.keys():
			print("TODAY'S GAMES:")
			for g in newres["morningAnnounce"]:
				print g
		for prob in newres["probables"]:
			print "PROBABLES UPDATE: " + prob
		for ann in newres["announce"]:
			print "GAME STATUS UPDATE: " + ann
		for (blurb, mp4) in newres["highlights"]:
			print(blurb + ": " + mp4)
		for finalDict in newres["finals"]:
			print finalDict["final"] + ", " + finalDict["standings"]
			print "Next: "+finalDict["probables"]
		for underwayDict in newres["underway"]:
			print underwayDict["game"] + " now underway. Radio: " + underwayDict["audio"] + ", TV: " + underwayDict["video"]
			
