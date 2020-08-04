#!/usr/bin/python

# NATINAL
# (c) 2016-20 J. W. Crockett, Jr., josh.crockett@gmail.com

# Not
# Another
# Twit
# Issuing
# Notifications
# About the
# Lineups!

# yes, the acronym's a terrible stretch. ref: http://www.uni-watch.com/2009/04/18/natinal-joke/, and the daily race of Nationals beat writers for who tweets the starting lineup first

# Please note http://gdx.mlb.com/components/copyright.txt, which covers the data sources owned by MLB Advanced Media, L.P. ("MLBAM") that this application consumes. The developer of this application claims no rights to or control over these sources or the data contained within. Users of this application are themselves solely responsible for assuring that their use of this application, the sources and the data contained within complies with any and all terms and conditions set by MLBAM.

import xml.dom, urllib, ConfigParser, json, logging, traceback, re, argparse
from datetime import timedelta, datetime
from string import Template
from xml.dom.minidom import parse
from os import sys

from nat_lib import *

import notifiers

logLevel = logging.INFO		# .DEBUG
configFN = "config.ini"		# may be overridden by -c fn.ini

# MLB.com rolls to "today's" date at 1000 ET. This means you get a day's games until 10 AM ET the following day.
# I prefer 9 as a good rollover/announcement time.  This setting is overridden by config:[general]/rolloverTime.
defaultRolloverTime="0900"

# what kind of video should we pull? This one's OK, I think
# was "FLASH_1200K_640X360" until beginning of 2019 regular season. 
# We'll want to move this to config in a refactor
PREFERRED_PLAYBACK_LEVEL_NAME = "mp4Avc"	

# oddball magic-number const(s)
BOTH = -99999


def setupNotifiers(cfgParser):
	
	theSet = []
	# convenience
	availableNotifiers = {}
	for nclass in notifiers.NotifierClass.Notifier.__subclasses__():
		availableNotifiers[nclass.__name__] = nclass
	
	heads = cfgParser.get("notifiers","notifiers")
	for head in heads.split(","):
		if head != '':
			try:
				theSet.append(availableNotifiers[cfgParser.get(head,"class")](cfgParser,head))
			except Exception as e:
				logging.error("Notif construction failed for header " + head + "\n" + str(e))
	
	return theSet

def divShortName(teamDiv):
	try:
		divre = re.search(r'(\w)\w+ League (\w+)',teamDiv)
		divShort = divre.groups()[0] + "L " + divre.groups()[1]
		return divShort
	except Exception, e:
		return teamDiv
		
def gidizeGameId(gameId):
	if not re.match("gid_",gameId):
		gameId = re.sub(r"\-","_",gameId)
		gameId = re.sub(r"\/","_",gameId)
		gameId = "gid_" + gameId
	return gameId


def getScoreline(game):
	statusElement = game.getElementsByTagName("status")[0]
	statusAttr = statusElement.getAttribute("status")
	
	if statusAttr in POSTPONED_STATUS_CODES:
	
		statusStr = game.getAttribute("away_team_city") + " at " + game.getAttribute("home_team_city") + " postponed"
		try:
			makeup = game.getAttribute("description")
			if makeup and len(makeup.strip()) > 0:
				statusStr += " (" + makeup + ")"
		except Exception as e:
			pass
		return statusStr
		
	elif statusAttr in SUSPENDED_STATUS_CODES:
		statusStr = "Suspended game"
	else:
		statusStr = "Final"
	innings = int(statusElement.getAttribute("inning"))
	reason = statusElement.getAttribute("reason")
	if innings != 9 or reason != "":
		statusStr += " ("
		if innings != 9:
			statusStr += str(innings)
			if reason != "":
				statusStr += ", " + reason
		else:
			statusStr += reason
		statusStr += ")"
	
	statusStr += ": "
	runsElem = game.getElementsByTagName("linescore")[0].getElementsByTagName("r")[0]
	runs_home = runsElem.getAttribute("home")
	runs_away = runsElem.getAttribute("away")
	if int(runs_home) > int(runs_away):
		statusStr += game.getAttribute("home_team_city") + " " + runs_home + ", " + game.getAttribute("away_team_city") + " " + runs_away
	else:
		statusStr += game.getAttribute("away_team_city") + " " + runs_away + ", " + game.getAttribute("home_team_city") + " " + runs_home
		
	return statusStr

def textFromElem(elem):
	return (" ".join(t.nodeValue for t in elem.childNodes if t.nodeType in (t.CDATA_SECTION_NODE,t.TEXT_NODE))).strip()

def pullHighlights(gamePk, highlightTeamId, prefsDict, pDict, newResults):
	
	if prefsDict["baghdadBob"] == None:
		return (pDict, newResults)
	
	thisHighlightsUrl = statsApiGameContentJsonUrl.replace("GAME_PK",gamePk)
	logging.debug("Getting highlights URL: " + thisHighlightsUrl)
	usock = urllib.urlopen(thisHighlightsUrl)
	if usock.getcode() != 200:
		# highlights file doesn't appear until there are highlights. fail softly.
		logging.debug("highlights get failed for " + thisHighlightsUrl)
	else:
		try:
			highlightsJson = json.load(usock)
			usock.close()
			logging.debug("got highlights for " + thisHighlightsUrl + " , teamId " + str(highlightTeamId))
			
			for media in highlightsJson["highlights"]["highlights"]["items"]:
				if (prefsDict["baghdadBob"] == False) or highlightIsOfTeam(media,highlightTeamId) or isCompressedGame(media):
					#  or media.getAttribute("media-type") == "C" compressed game still needs check TODO TODO TODO
					try:
						blurb = media["blurb"]
						if isCompressedGame(media):
							blurb = blurb + " (" + media["duration"] + ")"
						mp4 = ""
						for pb in media["playbacks"]:
							if pb["name"] == PREFERRED_PLAYBACK_LEVEL_NAME:
								mp4 = pb["url"]
								break
						
						if mp4 == "":
							# nothing of PREFERRED_PLAYBACK_LEVEL_NAME was found
							logging.info("Check blurb " + blurb + " for no highlight of " + PREFERRED_PLAYBACK_LEVEL_NAME)
						else:
							logging.debug("highlight: " + blurb + ", video: " + mp4)
 
							if media["mediaPlaybackId"] not in pDict["results"]["highlights"].keys():
								pDict["results"]["highlights"][media["mediaPlaybackId"]] = (blurb,mp4)
								if ((prefsDict["suppressStatcast"] == False) or (("statcast" in blurb.lower()) == False)):
									newResults["highlights"].append((blurb,mp4))
							else:
								logging.debug("I think this one's in pDict already")
					except Exception as e:
						logging.error("Error taking apart individual mediaNode: " + str(e))
		except Exception as e:
			logging.error("Exception parsing highlights JSON: " + str(e))
	
	return (pDict, newResults)

def highlightIsOfTeam(highlightItem,teamId):
	if teamId == BOTH:
		return True
	# now iterate if we're still here
	for kw in highlightItem["keywordsAll"]:
		if kw["type"] == "team_id" and str(teamId) == str(kw["value"]):
			return True
	# if we're still here:
	return False

##### TODO TODO TODO won't know if this is right until compressed games appear, but abstracting it out helps fix later
def isCompressedGame(mediaItem):
	return (mediaItem["type"] == "C")


def pullLineupsXml(gameId,xmlUrl):

	try:
		# first have to pull YMD from gameId, which is unfortunate.
		(yr,mo,dy) = re.search(r'(\d{4})\D(\d\d)\D(\d\d).*',gameId).groups()
		# and if it's not a "gid_" version of gameId, convert it
		gameId = gidizeGameId(gameId)
		exactXmlUrl = Template(xmlUrl).substitute(year=yr,month=mo,day=dy,game_id=gameId)
		logging.debug("getting lineup for " + gameId + " from " + exactXmlUrl)
		usock = urllib.urlopen(exactXmlUrl)
		if usock.getcode() != 200:
			logging.debug("Exiting pullLineupsXml with usock.getcode() == " + str(usock.getcode()) + " " + exactXmlUrl)
			return None
		boxscoreXml = parse(usock)
	except Exception, e:
		logging.info("Exiting pullLineupsXml during parse with exception " + traceback.format_exc(e)+ " " + exactXmlUrl)
		return None
	
	bxElem = boxscoreXml.getElementsByTagName("boxscore")[0]
	
	lups = [{"team_name_full":bxElem.getAttribute("home_fname"),"team_short":bxElem.getAttribute("home_sname")},
		{"team_name_full":bxElem.getAttribute("away_fname"),"team_short":bxElem.getAttribute("away_sname")}]
		
	# now I have a boxscoreXml, ho ho ho.
	for team in boxscoreXml.getElementsByTagName("batting"):
		which = team.getAttribute("team_flag")	# "home" or "away"
		lup = [1,2,3,4,5,6,7,8,9]	# prepare the array
		batters = team.getElementsByTagName("batter")
		if (len(batters) < 9):
			# possible they're posting lineupsXml before actual batters now in 2019. That ain't gonna work.
			logging.info("Exiting pullLineupsXml at len(batters) < 9 on url " + exactXmlUrl)
			return None
		for batter in batters:
			bo = batter.getAttribute("bo")
			if bo == "":
				# DH game pitcher
				bo = "1000"
				if len(lup) == 9:
					lup.append(10)
			bd = {}
			bd["name"] = batter.getAttribute("name")
			bd["position"] = batter.getAttribute("pos")
			lup[(int(bo)//100)-1] = bd
		if which == "home":
			lups[0]["players"] = lup
		else:
			lups[1]["players"] = lup

	logging.debug("returning from pullLineupsXml: " + str(lups))
	return lups
		
def pullStandings(msXML, standingsUrlTemplate, scheduleDT, newFinal=None):
	
	baseStandingsUrl = scheduleDT.strftime(standingsUrlTemplate)
	logging.debug("Getting standings URL " + baseStandingsUrl)
	byTeam = {}
	byDivList = {}
	byLeagueList = {}
	usock = urllib.urlopen(baseStandingsUrl)
	print baseStandingsUrl
	if usock.getcode() != 200:
		logging.error("Get base standings failed for standings URL " + baseStandingsUrl)
		return None
	# so let's continue
	try:
		baseDivisions = json.load(usock)["records"]
	except Exception as e:
		logging.error("JSON standings get/decode failed for standings URL " + baseStandingsUrl + ", " + traceback.format_exc(e))
		return None
	
	seasonGames = int(baseDivisions[0]["league"]["numGames"])
	
	if newFinal:    
	    gameToFinalize = int(newFinal["gamePk"])
	else:
	    gameToFinalize = None
	gameToAdd = None
    	
	for div in baseDivisions:
		
		lname = div["league"]["abbreviation"]   # AL or NL
		if (int(div["league"]["numGames"]) != seasonGames):
		    logging.error("We got variable season lengths (div/league/numGames) in standings URL " + baseStandingsUrl + ": " + str(seasonGames) + ", " + str(div["league"]["numGames"]))
		for rec in div["teamRecords"]:
			td = {}
			td["abbrev"] = rec["team"]["abbreviation"]
			td["league"] = lname
			td["div"] = div["division"]["nameShort"]    # "AL West" form
			# we'll do pct math ourselves. one of these needs to be a float to do that in Python 2
			td["w"] = float(rec["wins"])
			td["l"] = int(rec["losses"])
			td["name"] = rec["team"]["name"]
			byTeam[td["abbrev"]] = td
			
	# and now build byDivList and byLeagueList with updated data
	for team in byTeam:
		if byTeam[team]["div"] not in byDivList:
			byDivList[byTeam[team]["div"]] = []
		byDivList[byTeam[team]["div"]].append(byTeam[team])
		if byTeam[team]["league"] not in byLeagueList:
			byLeagueList[byTeam[team]["league"]] = []
		byLeagueList[byTeam[team]["league"]].append(byTeam[team])
		# this leaves the structures pointing to the same team objects.  this will be useful.

	byDivList = doStandingsMagic(byDivList,seasonGames)
	byLeagueList = doStandingsMagic(byLeagueList,seasonGames,prefix="league")
	
	for team in byTeam:
	    if gameToAdd:
	        
		if byTeam[team]["div"] not in byDivList:
			byDivList[byTeam[team]["div"]] = []
		byDivList[byTeam[team]["div"]].append(byTeam[team])
		if byTeam[team]["league"] not in byLeagueList:
			byLeagueList[byTeam[team]["league"]] = []
		byLeagueList[byTeam[team]["league"]].append(byTeam[team])
		# this leaves the structures pointing to the same team objects.  this will be useful.
		
	byDivList = doStandingsMagic(byDivList,seasonGames)

	byLeagueList = doStandingsMagic(byLeagueList,seasonGames,prefix="league")
	
	for team in byTeam:
		byTeam[team]["text"] = byTeam[team]["abbrev"] + " " + str(int(byTeam[team]["w"])) + "-" + str(byTeam[team]["l"]) + ", " + divOrdinal(byTeam[team]["pos"]) + " " + divShortName(byTeam[team]["div"]) + " (" + ((str(byTeam[team]["gb"]) + " GB") if byTeam[team]["gb"] >= 0.0 else ("+" + str(-byTeam[team]["gb"]) + " GA")) + ")"
		if "magic" in byTeam[team]:
			if byTeam[team]["magic"] > 0:
				byTeam[team]["text"] = byTeam[team]["text"] + ", magic number: " + str(int(byTeam[team]["magic"]))
			else:
				byTeam[team]["text"] = byTeam[team]["text"] + ", CLINCHED"
		if "leaguemagic" in byTeam[team]:
			if byTeam[team]["leaguemagic"] > 0:
				byTeam[team]["text"] = byTeam[team]["text"] + ", league magic number: " + str(int(byTeam[team]["leaguemagic"]))
			else:
				byTeam[team]["text"] = byTeam[team]["text"] + ", CLINCHED LEAGUE"
				
	return byTeam

def doStandingsMagic(byDivList,seasonGames,prefix=""):

	for k in sorted(byDivList,key=lambda div: re.sub("Central","Middle",div)): # so we get E/C/W
	
		byDivList[k].sort(key=lambda team: ( -team["w"]/( (team["w"]+team["l"]) if ((team["w"]+team["l"]) > 0) else 1), -team["w"]) )
		firstW = None
		firstL = None
		rank = 0
		
		# do GB and position
		for team in byDivList[k]:
			rank += 1	
			if firstW == None:
				firstW = team["w"]
				firstL = team["l"]
				team[prefix+"gb"] = 0.0
				team[prefix+"pos"] = str(rank)
			else:
				team[prefix+"gb"] = ((firstW - team["w"]) + (team["l"] - firstL)) / 2
				if team[prefix+"gb"] == prev[prefix+"gb"] and team["w"] == prev["w"]:
					if not re.match("T-\d",prev[prefix+"pos"]):
						prev[prefix+"pos"] = "T-" + prev[prefix+"pos"]
					team[prefix+"pos"] = prev[prefix+"pos"]
				else:
					team[prefix+"pos"] = str(rank)
				
			prev = team
	
		# now fill in games up for 1st place
		firstList = []
		topGB = 99999.0
		for team in byDivList[k]:
			if team[prefix+"pos"] in ("1","T-1"):
				firstList.append(team)
			elif team[prefix+"gb"] < topGB:
				topGB = team[prefix+"gb"]
		if topGB == 99999.0:
			topGB = 0.0
		for team in firstList:
			team[prefix+"gb"] = -topGB
			
		# start populating magic number at 2/3 mark for first-place
		if ((byDivList[k][0]["w"] + byDivList[k][0]["l"]) >= (2*seasonGames/3.0)):
			byDivList[k][0][prefix+"magic"] = (seasonGames+1) - (byDivList[k][0]["w"] + byDivList[k][1]["l"])
			for ln in range(1,len(byDivList[k])):
				if byDivList[k][ln][prefix+"pos"] == "T-1":
					byDivList[k][ln][prefix+"magic"] = (seasonGames+1) - (byDivList[k][ln]["w"] + byDivList[k][0]["l"])
	
	return byDivList
	
def loadMasterScoreboard(msURL, scheduleDT, msOverrideFN=None):
	
	if not msOverrideFN:
		logging.debug( "Running scoreboard for " + scheduleDT.strftime("%Y-%m-%d"))
		scheduleUrl = scheduleDT.strftime(msURL)
		
		logging.debug("Opening scheduleUrl: " + scheduleUrl)
		usock = urllib.urlopen(scheduleUrl)
		if (usock.getcode() == 404):
			logging.info("Schedule not found. Either there are no games today or MLBAM has changed the master scoreboard URL.\n")
			return None
		elif (usock.getcode() != 200):
			logging.error("HELP! Get schedule failed with HTTP code " + str(usock.getcode()) + " on URL:\n\t" + scheduleUrl + "\n")
			raise Exception("Get schedule failed (non-404) with HTTP code " + str(usock.getcode()) + " on URL:\n\t" + scheduleUrl + "\n")
	else:
		logging.debug("Running file scoreboard from " + msOverrideFN)
		usock = open(msOverrideFN)
		
	try:
		masterScoreboardXml = parse(usock)
		usock.close()
	except Exception as e:
		logging.error("MSXML parse failed on " + (msOverrideFN if msOverrideFN else ("URL:\n\t" + scheduleUrl)) + "\n" + traceback.format_exc(e))
		usock.close()
		return None

	return masterScoreboardXml

def isRegularSeason(msXML):
	# we want to bomb out if *any* game is not RS.
	for game in msXML.getElementsByTagName("game"):
		if game.getAttribute("game_type") != "R":
			return False
	return True

def pullValidTeams(cfgParser,teamDirUrl,pDict):
	teams = {}
	strTeams = cfgParser.get("general","teams")
	for i in strTeams.split(","):
		if i != '':
			teams[i.upper()] = ""	# let's sanity-check the requested teams first.  to do that, need all the valid teams.
	
	teamIdDir = {}
	if "teamIdDir" not in pDict:
		usock = urllib.urlopen(teamDirUrl)
		if (usock.getcode() != 200):
			logging.error("Master team directory not found, error " + str(usock.getcode()) + ", URL:\n\t" + teamDirUrl)
			quit
		masterDirXml = parse(usock)
		usock.close()
	
		for teamRow in masterDirXml.getElementsByTagName("row"):
			teamIdDir[teamRow.getAttribute("name_abbrev")] = teamRow.getAttribute("team_id")
		
		pDict["teamIdDir"] = teamIdDir
	else:
		teamIdDir = pDict["teamIdDir"]

	teamsBad = []
	for key in teams:
		if not (key in teamIdDir):
			teamsBad.append(key)
		else:
			teams[key] = teamIdDir[key]
			
	if len(teamsBad) > 0:
		logging.error("Bad team[s] requested: " + str(teamsBad) + ", quitting.")
		quit()
	if len(teams.keys()) == 0:
		logging.info("No team[s] requested. Only scanning league results (if that's even been written yet).")
	return (teams,pDict)

def rollGames(msXML,teams,prefsDict,pDict):

	newResults = { "highlights":[],"finals":[],"probables":[],"backtalk":[],"announce":[],"underway":[], "lineups": [] }
	
	for game in msXML.getElementsByTagName("game"):

		statuses = game.getElementsByTagName("status")		
		if len(statuses) == 0:
			continue	# can't do anything with this one yet.
			
		home = game.getAttribute("home_name_abbrev")
		away = game.getAttribute("away_name_abbrev")
		gameStr = away + " at " + home
		gameDataDir = game.getAttribute("game_data_directory")
		gameId = game.getAttribute("id")
		gamePk = game.getAttribute("game_pk")

		statusElement = statuses[0]
		statusAttr = statusElement.getAttribute("status")
	
		if away in teams or home in teams:
			logging.debug("looking at " + gameId + " status " + statusAttr)
			
			highlightTeamId = 0	#declaration for scoping
			highlightTeamSingleKey = "" # same, for return in relevantteams ONLY
			if (away in teams and home in teams):
				highlightTeamId = BOTH
			elif (away in teams):
				highlightTeamId = teams[away]
				highlightTeamName = away
			else:	# home in teams
				highlightTeamId = teams[home]
				highlightTeamName = home

			# now, toss out games that are completed and not today. 
			dateStr = "-".join(gameId.split("/")[0:3])
			if dateStr != pDict["todayStr"]:
				if statusAttr in FINAL_STATUS_CODES:
					logging.info("tossing out completed nontoday game " + gameId)
					continue
				else:
					backtalk = "Incomplete non-today game found: " + gameId + " in msxml"
					logging.warn(backtalk)
					if "backtalk" not in pDict:
						pDict["backtalk"] = [backtalk]
					if backtalk not in pDict["backtalk"]:
						pDict["backtalk"].append(backtalk)
						newResults["backtalk"].append(backtalk)
					# else it's already in
		
			# if it's in probables and probables are still relevant:
			if gameDataDir in pDict["results"]["probables"].keys():
				if statusAttr in UNDERWAY_STATUS_CODES:
					del pDict["results"]["probables"][gameDataDir]
				elif statusAttr in PREGAME_STATUS_CODES and not gameProbablesNull(game):
					curProbs = getProbables(game,stripDate=True)
					if curProbs and pDict["results"]["probables"][gameDataDir] != curProbs:
						newResults["probables"].append(curProbs)
						pDict["results"]["probables"][gameDataDir] = curProbs
			
			if statusAttr in UPCOMING_STATUS_CODES:
				if gameId not in pDict["upcoming"]:
					lineups = pullLineupsXml(gameId,boxscoreXmlUrl)
					if lineups != None:
						pDict["upcoming"].append(gameId)
						newResults["lineups"].append(lineups)
			
			if statusAttr in ANNOUNCE_STATUS_CODES or ("announce" in pDict and gameId in pDict["announce"]):
				gameNowStr = " now " + statusAttr.lower()
				if statusElement.getAttribute("reason") != "":
					gameNowStr = gameNowStr + " (" + statusElement.getAttribute("reason") + ")"
				if "announce" not in pDict:
					pDict["announce"] = {}
				if gameId in pDict["announce"]:
					if statusAttr != pDict["announce"][gameId]:
						# we've transitioned out of something.
						if statusAttr in ANNOUNCE_STATUS_CODES:
							pDict["announce"][gameId] = statusAttr
							newResults["announce"].append(gameStr + gameNowStr)
						else:
							newResults["announce"].append(gameStr + " no longer " + pDict["announce"][gameId].lower() + "," + gameNowStr)
							del pDict["announce"][gameId]
				else:
					# simply a new announcement
					pDict["announce"][gameId] = statusAttr
					newResults["announce"].append(gameStr + gameNowStr)
			
			if statusAttr in UNDERWAY_STATUS_CODES and gameId not in pDict["underway"]:
				
				# test for Fox exclusive, but don't fail if the element isn't there
				try:
					foxExclusive = (game.getElementsByTagName("links")[0].getAttribute("tv_station") == "FOX")
				except:
					foxExclusive = False
				
				pDict["underway"].append(gameId)
				newResults["underway"].append( { "game": gameStr, 
					"audio": mlbTvBaseUrl.format(pk=gamePk) + "?mediatype=audio",
					"video": mlbTvBaseUrl.format(pk=gamePk) ,
					"gameday": gamedayBaseUrl.format(pk=gamePk),
					"foxExclusive": foxExclusive } )
							
			if statusAttr not in INACTIVE_GAME_STATUS_CODES:	# only the ones with a game in progress or complete
				# moved all this out for clarity
				(pDict, newResults) = pullHighlights(gamePk, highlightTeamId, prefsDict, pDict, newResults)

			if statusAttr in FINAL_STATUS_CODES:
		
				statusStr = getScoreline(game)
				
				logging.debug(statusStr)
				if gameDataDir not in pDict["results"]["finals"].keys():
					pDict["results"]["finals"][gameDataDir] = (gameDataDir, statusStr, datetime.strftime(datetime.utcnow(),"%c"))
					finalDict = {"gamedir":gameDataDir,"gamePk":gamePk,"final":statusStr}
					
					if highlightTeamId == BOTH:
						finalDict["relevantteams"] = [home,away]
						finalDict["result"] = "neutral"
					else:
						runsElem = game.getElementsByTagName("r")[0]
						finalDict["relevantteams"] = [highlightTeamName]
						if (home in teams and int(runsElem.getAttribute("home")) > int(runsElem.getAttribute("away"))) or (away in teams and int(runsElem.getAttribute("away")) > int(runsElem.getAttribute("home"))):
							finalDict["result"] = "win"
						elif (int(runsElem.getAttribute("home")) == int(runsElem.getAttribute("away"))):
							finalDict["result"] = "tie"
						else:
							finalDict["result"] = "loss"
						
					logging.debug(finalDict)
					newResults["finals"].append(finalDict)

	return (newResults,pDict)

def nextGame(teamId, afterGameDir, xmlList, masterScoreboardUrl=None, maxMoreDays=0):
	# if afterGameDir = None, start from top of xmlList
	# otherwise return first one you see after reaching afterGameDir that isn't afterGameDir
	# returns next game that has not yet reached start time
	# if maxMoreDays is None, xmlList is fixed. Else it'll go from latest date in xmlList and add up to maxMoreDays
	gameNodes = []
	maxDT = None	# will eventually hold back-constructed latest master XML date
	moreDayCount = 0
	
	while moreDayCount <= maxMoreDays:
		if moreDayCount > 0:
			maxDT = maxDT + timedelta(days=1)
			xmlList = [loadMasterScoreboard(masterScoreboardUrl,maxDT)]
		
		for xml in xmlList:
			if xml != None:
				gameNodes += xml.getElementsByTagName("game")
				if moreDayCount == 0:
					constructedDstr = xml.getElementsByTagName("games")[0].getAttribute("year") + xml.getElementsByTagName("games")[0].getAttribute("month") + xml.getElementsByTagName("games")[0].getAttribute("day")
					backDT = datetime.strptime(constructedDstr,"%Y%m%d")
					if maxDT == None or backDT > maxDT:
						maxDT = backDT

		moreDayCount += 1
	
		if afterGameDir == None:
			afterGameDirReached = True
		else:
			afterGameDirReached = False

		# now that we have all those in one list, we can do a for loop and break out of it clearly once found.
		for game in gameNodes:
			# attributes: (away_|home_)(name_abbrev = MIL|code = mil|team_city = Milwaukee|team_name = Brewers)(league_id = 104 (NL)/103 (AL))
			home = game.getAttribute("home_name_abbrev")
			away = game.getAttribute("away_name_abbrev")
			gameDir = game.getAttribute("game_data_directory")
			statuses = game.getElementsByTagName("status")
			teamId = teamId.upper()
			if gameDir == afterGameDir:
				afterGameDirReached = True
				
			#if (teamId in (home,away)) and (len(statuses) > 0) and (statuses[0].getAttribute("status") in (PREGAME_STATUS_CODES + SUSPENDED_STATUS_CODES)) and (gameDir != afterGameDir) and afterGameDirReached:
			if (teamId in (home,away)) and (len(statuses) > 0) and (gameDir != afterGameDir) and afterGameDirReached:
				logging.debug( "next game for " + teamId + ((" after " + afterGameDir) if afterGameDir else "") + " is " + game.getAttribute("game_data_directory"))
				return game
		
	return None

def getProbables(game,standings=None,stripDate=False,tvTeam=None):
	if game == None:
		return None
	runningStr = ""
	subToken = "ZXZXCVCV"
	
	awayAbbr = game.getAttribute("away_name_abbrev")
	homeAbbr = game.getAttribute("home_name_abbrev")
	
	for (ptag,cattr) in [("away_probable_pitcher","away_team_city"),("home_probable_pitcher","home_team_city")]:
		try:
			pitcher = game.getElementsByTagName(ptag)[0]
			pstr = pitcher.getAttribute("name_display_roster")
		except:
			return None
		if "," in pstr:
			pstr = pstr + "."
		if pstr == "":
			pstr = "TBA"
		else:
			pstr = pstr + " " + pitcher.getAttribute("wins") + "-" + pitcher.getAttribute("losses") + ", " 
			# 2018: for some reason it switches a null ERA from "-.--" to "-" 10 minutes before game start. 
			# don't let that change the string
			era = pitcher.getAttribute("era")
			if era == "-":
				era = "-.--"	
			pstr += era
		runningStr += (game.getAttribute(cattr) + " (" + pstr + ")" + subToken)
	runningStr = re.sub(subToken+"$",", ",runningStr)
	runningStr = re.sub(subToken," at ", runningStr)
	gtime = re.sub("^(\d+)\/","",game.getAttribute("time_date"))
	if gtime.endswith("3:33"):
		gtime = gtime[:-5] + " time TBA"
	else:
		gtime += " " + game.getAttribute("time_zone")
	runningStr += gtime
	if stripDate:
		runningStr = re.sub("\, \d+\/\d+",",",runningStr)
	
	if tvTeam:
		# lazy default here
		bc = "home"
		if tvTeam == awayAbbr:
			bc = "away"
		try:
			bcast = game.getElementsByTagName("broadcast")[0].getElementsByTagName(bc)[0].getElementsByTagName("tv")[0].childNodes[0].data
			runningStr += "\nTV: " + bcast
		except Exception, e:
			logging.debug("bcast takeapart failed, probably means no TV: " + str(e))
				
	if standings:
		sep = "; "
		sline = ""
		for abbr in (awayAbbr,homeAbbr):
			sline = sline + sep + standings[abbr]["text"]
		sline = re.sub("^"+sep,"",sline)
		runningStr = runningStr + "\n" + sline
	
	return runningStr

def gameProbablesNull(game):
	# check a single probables set -- GH-#3
	try:
		return (game.getElementsByTagName("away_probable_pitcher")[0].getAttribute("name_display_roster") == "" and game.getElementsByTagName("home_probable_pitcher")[0].getAttribute("name_display_roster") == "")
	except:
		return None


def main():

	parser = argparse.ArgumentParser()
	parser.add_argument("-c","--config")
	parser.add_argument("-f","--file")
	parser.add_argument("-d","--date",help="Get results for a past date, in YYYY-mm-dd format")
	args = parser.parse_args()

	masterScoreboardOverride = args.file	# == None if not passed, which works

	config = ConfigParser.RawConfigParser()
	if args.config:
		print "running as config: " + args.config
		config.readfp(open(args.config))
	else:
		config.readfp(open(configFN))

	try:
		persistFN = config.get("general","persist_dict_fn")
		logFN = config.get("general","log_fn")
	except Exception as e:
		quit("Couldn't get critical file paths: " + traceback.format_exc(e))

	global logLevel
	try:
		llstr = config.get("general","logLevel")
		if llstr != "":
			logLevel = eval(llstr)
	except Exception:
		pass # leave logLevel alone if that doesn't work in one shot
	
	logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',filename=logFN, level=logLevel)
	
	try:
		configRolloverTime = config.get("general","rolloverTime")
		intRolloverLocalTime = int(configRolloverTime,base=10)
	except Exception:
		intRolloverLocalTime = int(defaultRolloverTime,base=10)
	
	if args.date:
		sp = args.date.split('-')
		todayDT = datetime(year=int(sp[0]),month=int(sp[1]),day=int(sp[2]),hour=23,minute=59)
		persistFN = persistFN + "." + args.date
		logging.info("Running against date " + args.date)
	else:
		todayDT = datetime.now() - timedelta(minutes=((intRolloverLocalTime/100)*60+(intRolloverLocalTime%100)))
	
	todayStr = todayDT.strftime("%Y-%m-%d")

	try:
		masterScoreboardUrl = re.sub("LEAGUEBLOCK",config.get("general","league"),leagueAgnosticMasterScoreboardUrl)
		if config.get("general","league") not in validLeagues:
			raise ValueError("league not in permissible leagues")
	except (ConfigParser.NoOptionError, ValueError):
		masterScoreboardUrl = re.sub("LEAGUEBLOCK","mlb",leagueAgnosticMasterScoreboardUrl)

	prefsDict = {}
	try:
		prefsDict["baghdadBob"] = config.getboolean("general","baghdadBob")
	except ValueError:
		prefsDict["baghdadBob"] = None 	# if it's not binary, NO HIGHLIGHTS AT ALL
		logging.debug("baghdadBob is not binary, running with no highlights")
		
	try:
		prefsDict["suppressStatcast"] = config.getboolean("general","suppressStatcast")
	except ValueError:
		prefsDict["suppressStatcast"] = false

	persistDict = {}
	firstOfTheDay = False
	try:
		with open(persistFN) as opentest:
			persistDict = json.load(file(persistFN))
		if type(persistDict) != dict:
			raise ValueError("persistFN has invalid data type")
	except IOError:
		pass	# persistFN doesn't exist
	except ValueError:
		logging.error("persistFN is corrupted, killing it and starting over")
		persistDict = {}

	if "todayStr" not in persistDict or ("todayStr" in persistDict and persistDict["todayStr"] != todayStr):
		for k in persistDict.keys():
			if k != "teamIdDir":
				# clear everything but the team ID directory in the morning
				persistDict.pop(k,None)
		firstOfTheDay = True
			
	persistDict["todayStr"] = todayStr
	# now set up the architecture
	if "results" not in persistDict:
		persistDict["results"] = {}	
	for resType in ("highlights","probables","finals"):
		if resType not in persistDict["results"]:
			persistDict["results"][resType] = {}
	for annType in ("underway","upcoming"):
		if annType not in persistDict:
			persistDict[annType] = []

	# load requested teams and sanity-check. if we make it back from this call, we're good to go forward and have at least one specified team
	(validTeams,persistDict) = pullValidTeams(config,teamDirectoryUrl,persistDict)

	# get master scoreboard DOM doc. Confirms that there are games today too.
	masterScoreboardXml = loadMasterScoreboard(masterScoreboardUrl,todayDT,masterScoreboardOverride)
	
	newResults = {}
	morningAnnounce = []
	
	validNotifiers = setupNotifiers(config)

	if firstOfTheDay and masterScoreboardXml and (not args.date):
		if isRegularSeason(masterScoreboardXml):
			standings = pullStandings(masterScoreboardXml,statsApiStandingsUrl,todayDT)
		else:
			standings = None
		for team in validTeams:
			try:
				game = nextGame(team,None,[masterScoreboardXml])
				while game != None:
					gddir = game.getAttribute("game_data_directory")
					logging.debug("got a game for " + team + ": " + gddir)
					if game.getElementsByTagName("status")[0].getAttribute("status") in SUSPENDED_STATUS_CODES:
						morningAnnounce.append(getScoreline(game) + " resumes " + game.getAttribute("time") + " " + game.getAttribute("home_ampm") + ".")
					elif game.getElementsByTagName("status")[0].getAttribute("status") in POSTPONED_STATUS_CODES:
						morningAnnounce.append(getScoreline(game))
					else:
						logging.debug("in the got a game else branch")
						gameProbs = getProbables(game,stripDate=True)
						if gameProbs and (gameProbs != ''):
							# put the simple one in pDict, because you'll compare that in rollGames for probables updates
							persistDict["results"]["probables"][game.getAttribute("game_data_directory")] = gameProbs
							gameProbsWithStandings = getProbables(game,standings,stripDate=True,tvTeam=team)
							if gameProbsWithStandings not in morningAnnounce:
								morningAnnounce.append(gameProbsWithStandings)
					game = nextGame(team,gddir,[masterScoreboardXml])
			except Exception as e:
				logging.error("firstOfTheDay failed for " + team + ", " + traceback.format_exc(e))
		logging.debug("it's firstOfTheDay, morningAnnounce looks like " + str(morningAnnounce))
	
	elif masterScoreboardXml: # args.date will hit here
		(newResults,persistDict) = rollGames(masterScoreboardXml,validTeams,prefsDict,persistDict)
	
	isNew = False
	for i in newResults:
		if newResults[i] != "" and newResults[i] != [] and newResults[i] != {} and newResults[i] != ():
			isNew = True
	if isNew:
		logging.info("newResults: " + str(newResults))
	else:
		logging.debug("newResults: " + str(newResults))
	
	if len(morningAnnounce) > 0:
		newResults["morningAnnounce"] = morningAnnounce # which is a list
	
	# we want to know next game for teamId in newResults["finals"][*]["relevantTeams"]
	# declare it outside, then load it once inside if there's anything in newResults["finals"]
	# anything farther forward, we'll make nextGame request out on the spot
	tomorrowScoreboardXml = None
	standings = None
	
	if "finals" in newResults:
		for newFinal in newResults["finals"]:
			if args.date:
				# empty populate probables and standings
				newFinal["probables"] = ''
				newFinal["standings"] = ''
			else:
				if tomorrowScoreboardXml == None:
					tomorrowScoreboardXml = loadMasterScoreboard(masterScoreboardUrl,(todayDT + timedelta(days=1)))
					if isRegularSeason(masterScoreboardXml):
						standings = None #pullStandings(masterScoreboardXml,statsApiStandingsUrl,todayDT,newFinal)
				for teamId in newFinal["relevantteams"]:
					probablesStr = getProbables(nextGame(teamId,newFinal["gamedir"],[masterScoreboardXml,tomorrowScoreboardXml],masterScoreboardUrl,6),tvTeam=teamId)
					if probablesStr == None:
						if "result" in newFinal and (newFinal["result"] == "win") and not isRegularSeason(masterScoreboardXml):
							newFinal["probables"] = "Next game for " + teamId + " TBA."
						else:
							newFinal["probables"] = "No next game for " + teamId + " currently scheduled."
					else:
						newFinal["probables"] = probablesStr
					if standings:
						newFinal["standings"] = re.sub(r'^(\w+)',r'\g<1> currently',standings[teamId]["text"])
					else:
						newFinal["standings"] = ""

	for vn in validNotifiers:
		# inherent assumption here: OK to resend whole package on notifier failure 
		# (i.e. partial repeat is OK / full failure is more likely than partial)
		try:
			if "staleResults" in persistDict:
				if vn.header in persistDict["staleResults"]:
					logging.error("got a staleResult for " + vn.header + " " + str(persistDict["staleResults"][vn.header]))
					stillStale = []
					for rset in persistDict["staleResults"][vn.header]:
						try:
							vn.pushResults(rset)
						except Exception:
							stillStale.append(rset)
					if len(stillStale) == 0:
						del persistDict["staleResults"][vn.header]
					else:
						persistDict["staleResults"][vn.header] = stillStale
			vn.pushResults(newResults)			
		except Exception, e:
			if "staleResults" not in persistDict:
				persistDict["staleResults"] = {}
			if vn.header not in persistDict["staleResults"]:
				persistDict["staleResults"][vn.header] = []
			persistDict["staleResults"][vn.header].append(newResults)
			logging.error(traceback.format_exc(e))

	try:
		json.dumps(persistDict)
		json.dump(persistDict,file(persistFN,'w'),indent=2)
	except TypeError as e:
		# dumps will trip this, keeping us from blowing away the persistFN
		logging.error("persistDict failed serialization. what's up? " + traceback.format_exc(e))
		logging.error(persistDict)
