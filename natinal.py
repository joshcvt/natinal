#!/usr/bin/python

# NATINAL
# (c) 2016 J. W. Crockett, Jr., josh.crockett@gmail.com

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

import notifiers

logLevel = logging.INFO		# .DEBUG
configFN = "config.ini"		# may be overridden by -c fn.ini

# MLB.com rolls to "today's" date at 1000 ET. This means you get a day's games until 10 AM ET the following day.
# I prefer 9 as a good rollover/announcement time.  This setting is overridden by config:[general]/rolloverTime.
defaultRolloverTime="0900"

teamDirectoryUrl = "http://mlb.com/lookup/xml/named.team_all.bam?sport_code=%27mlb%27&active_sw=%27Y%27&all_star_sw=%27N%27"
# http://mlb.mlb.com/properties/mlb_properties.xml is a less-good alternate

# exists unless there are no games scheduled that day
leagueAgnosticMasterScoreboardUrl = "http://gdx.mlb.com/gdcross/components/game/LEAGUEBLOCK/year_%Y/month_%m/day_%d/master_scoreboard.xml"
validLeagues = ["mlb","aaa","aax","afa","afx","asx","rok"]

LEAGUE_GAMES = 162	# obvs this has to be refactored if we ever do MiLB

# doesn't exist until the game starts
mobileHighlightsUrl = "http://gdx.mlb.com/gdcross${game_data_directory}/media/mobile.xml" 

standingsJsonUrl = "http://mlb.mlb.com/lookup/json/named.standings_schedule_date.bam?season=${year}&schedule_game_date.game_date=%27${slashDate}%27&sit_code=%27h0%27&league_id=103&league_id=104&all_star_sw=%27N%27&version=2"

mlbTvUrl = "http://m.mlb.com/tv/e${calendar_event_id}/"
mlbAudioUrl = "http://m.mlb.com/tv/e${calendar_event_id}/?media_type=audio&clickOrigin=MSB&team=mlb"

# don't exist until the lineups drop
boxscoreXmlUrl = "http://gdx.mlb.com/components/game/mlb/year_${year}/month_${month}/day_${day}/${game_id}/boxscore.xml"

# not using yet, but keeping for value
# highlightsOfficialPageTemplate = "http://m.mlb.com/video/v629584083/"
# playResultsByTimecodeUrl = "http://lwsa.mlb.com/tfs/tfs?file=/components/game/mlb/year_2016/month_04/day_30/gid_2016_04_30_wasmlb_slnmlb_1/plays.xml&timecode=20160430_182330"
# <game inning="1" inning_state="Top"...><score ar="1" hr="0" ah/hh/ae/he...>
# in mobile.xml, get home tz timecode from <media><keywords><keyword type="sv_id" value="160430_132609"/> ET.CT.MT.MST.PT; can infer UTC diff via msxml: <game time_date_hm_lg="2016/04/30 8:10" time_zone_hm_lg="-4" home_time="5:10" 

# oddball magic-number const(s)
BOTH = -99999

INACTIVE_GAME_STATUS_CODES = ["Postponed", "Pre-Game", "Preview", "Warmup"]
PREGAME_STATUS_CODES = ["Pre-Game", "Preview", "Warmup", "Delayed Start"]
UPCOMING_STATUS_CODES = ["Pre-Game", "Warmup"]
UNDERWAY_STATUS_CODES = ["In Progress", "Manager Challenge", "Review"]
FINAL_STATUS_CODES = ["Final", "Game Over", "Completed Early"]
ANNOUNCE_STATUS_CODES = ["Delayed Start", "Postponed", "Delayed"]


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


def divOrdinal(intStr):
	match = re.search(r'\d+',intStr)
	theInt = int(match.group())
	singleEnds = {1:"st",2:"nd",3:"rd"}
	# returns ordinal string for divisional position
	if theInt in (11,12,13) or ((theInt % 10) in [0,4,5,6,7,8,9]):
		return str(theInt) + "th"
	else:
		return str(theInt) + singleEnds[theInt % 10]

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

def pullHighlights(game, highlightTeamId, baghdadBob, pDict, newResults):
	
	if baghdadBob == None:
		return (pDict, newResults)
		
	gameDataDir = game.getAttribute("game_data_directory")
	thisHighlightsUrl = Template(mobileHighlightsUrl).substitute(game_data_directory=gameDataDir)
	usock = urllib.urlopen(thisHighlightsUrl)
	if usock.getcode() != 200:
		# highlights file doesn't appear until there are highlights. fail softly.
		logging.debug("highlights get failed for " + game.getAttribute("game_id") + "/ " + thisHighlightsUrl + " , " + game.getAttribute("home_lg_time") + " local " + thisHighlightsUrl)
	else:
		highlightsXml = parse(usock)
		usock.close()
		logging.debug("got highlights for " + game.getAttribute("game_id") + "/ " + thisHighlightsUrl + " , teamId " + str(highlightTeamId))
		mediaNodes = highlightsXml.getElementsByTagName("media")
		for media in mediaNodes:
			if (baghdadBob == False) or (highlightTeamId == BOTH or highlightTeamId == media.getAttribute("team_id") or media.getAttribute("media-type") == "C"):
				try:
					#blurb = media.getElementsByTagName("blurb")[0].firstChild.childNodes[0].data
					blurbElem = media.getElementsByTagName("blurb")[0]
					blurb = " ".join(t.nodeValue for t in blurbElem.childNodes if t.nodeType == t.TEXT_NODE)
					durationElem = media.getElementsByTagName("duration")[0]
					if media.getAttribute("media-type") == "C":
						blurb = blurb + " (" + (" ".join(t.nodeValue for t in durationElem.childNodes if t.nodeType == t.TEXT_NODE)) + ")"
					urls = media.getElementsByTagName("url")
					mp4 = ""
					for urlNode in urls:
						if urlNode.getAttribute("playback-scenario") == "FLASH_1200K_640X360":
							mp4 = " ".join(t.nodeValue for t in urlNode.childNodes if t.nodeType == t.TEXT_NODE).strip()
							break
					logging.debug("highlight: " + blurb + ", video: " + mp4)
					
					mp4split = re.split("\/",mp4)
					playkey = mp4split[len(mp4split)-3]
					if playkey not in pDict["results"]["highlights"].keys():
						pDict["results"]["highlights"][playkey] = (blurb,mp4)
						newResults["highlights"].append((blurb,mp4))
					else:
						logging.debug("I think this one's in pDict already")
				except Exception as e:
					logging.error(e)

	return (pDict, newResults)
		
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
			logging.debug("Exiting pullLineupsXml with usock.getcode() == " + usock.getcode())
			return None
		boxscoreXml = parse(usock)
	except Exception, e:
		logging.debug("Exiting pullLineupsXml with exception " + traceback.format_exc(e))
		return None
	
	bxElem = boxscoreXml.getElementsByTagName("boxscore")[0]
	
	lups = [{"team_name_full":bxElem.getAttribute("home_fname"),"team_short":bxElem.getAttribute("home_sname")},
		{"team_name_full":bxElem.getAttribute("away_fname"),"team_short":bxElem.getAttribute("away_sname")}]
		
	# now I have a boxscoreXml, ho ho ho.
	for team in boxscoreXml.getElementsByTagName("batting"):
		which = team.getAttribute("team_flag")	# "home" or "away"
		lup = [1,2,3,4,5,6,7,8,9]	# prepare the array
		for batter in team.getElementsByTagName("batter"):
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
		
def pullStandings(msXML, standingsUrlTemplate, scheduleDT):
	
	baseStandingsUrl = Template(standingsUrlTemplate).substitute(year=scheduleDT.strftime("%Y"),slashDate=scheduleDT.strftime("%Y/%m/%d"))
	byTeam = {}
	byDivList = {}
	byLeagueList = {}
	usock = urllib.urlopen(baseStandingsUrl)
	if usock.getcode() != 200:
		logging.error("Get base standings failed for standings URL " + baseStandingsUrl)
		return None
	# so let's continue
	try:
		baseLeagues = json.load(usock)["standings_schedule_date"]["standings_all_date_rptr"]["standings_all_date"]
	except Exception as e:
		logging.error("JSON standings get/decode failed for standings URL " + baseStandingsUrl + ", " + traceback.format_exc(e))
		return None
	
	for lg in baseLeagues:
		lname = ("AL" if lg["league_id"] == "103" else "NL")
		for team in lg["queryResults"]["row"]:
			td = {}
			td["abbrev"] = team["team_abbrev"]
			td["league"] = lname
			td["div"] = team["division"]
			# we'll do pct math ourselves. one of these needs to be a float to do that in Python 2
			td["w"] = float(team["w"])
			td["l"] = int(team["l"])
			td["name"] = team["team_full"]
			byTeam[team["team_abbrev"]] = td
	
	# now it's time to iterate over msXml to update this with current W/L. Yay!
	for game in msXML.getElementsByTagName("game"):
		home = game.getAttribute("home_name_abbrev")
		away = game.getAttribute("away_name_abbrev")
		if (home not in ('AL','NL')):	# catch All-Star Game special case
			byTeam[home]["w"] = float(game.getAttribute("home_win"))
			byTeam[home]["l"] = int(game.getAttribute("home_loss"))
			byTeam[away]["w"] = float(game.getAttribute("away_win"))
			byTeam[away]["l"] = int(game.getAttribute("away_loss"))
	
	# and now build byDivList and byLeagueList with updated data
	for team in byTeam:
		if byTeam[team]["div"] not in byDivList:
			byDivList[byTeam[team]["div"]] = []
		byDivList[byTeam[team]["div"]].append(byTeam[team])
		if byTeam[team]["league"] not in byLeagueList:
			byLeagueList[byTeam[team]["league"]] = []
		byLeagueList[byTeam[team]["league"]].append(byTeam[team])
		# this leaves the structures pointing to the same team objects.  this will be useful.
	
	if (0 == 1):	
		for k in sorted(byDivList,key=lambda div: re.sub("Central","Middle",div)): # so we get E/C/W
	
			byDivList[k].sort(key=lambda team: ( -team["w"]/(team["w"]+team["l"]), -team["w"]) )
			firstW = None
			firstL = None
			rank = 0
		
			# do GB and position
			for team in byDivList[k]:
				rank += 1	
				if firstW == None:
					firstW = team["w"]
					firstL = team["l"]
					team["gb"] = 0.0
					team["pos"] = str(rank)
				else:
					team["gb"] = ((firstW - team["w"]) + (team["l"] - firstL)) / 2
					if team["gb"] == prev["gb"] and team["w"] == prev["w"]:
						if not re.match("T-\d",prev["pos"]):
							prev["pos"] = "T-" + prev["pos"]
						team["pos"] = prev["pos"]
					else:
						team["pos"] = str(rank)
				
				prev = team
	
			# now fill in games up for 1st place
			firstList = []
			topGB = 99999.0
			for team in byDivList[k]:
				if team["pos"] in ("1","T-1"):
					firstList.append(team)
				elif team["gb"] < topGB:
					topGB = team["gb"]
			if topGB == 99999.0:
				topGB = 0.0
			for team in firstList:
				team["gb"] = -topGB
			
			# start populating magic number at 81 games in for first-place
			if ((byDivList[k][0]["w"] + byDivList[k][0]["l"]) >= (LEAGUE_GAMES/2)):
				byDivList[k][0]["magic"] = (LEAGUE_GAMES+1) - (byDivList[k][0]["w"] + byDivList[k][1]["l"])
				for ln in range(1,len(byDivList[k])):
					if byDivList[k][ln]["pos"] == "T-1":
						byDivList[k][ln]["magic"] = (LEAGUE_GAMES+1) - (byDivList[k][ln]["w"] + byDivList[k][0]["l"])
	
	byDivList = doStandingsMagic(byDivList)

	for team in byTeam:
		byTeam[team]["text"] = byTeam[team]["abbrev"] + " " + divOrdinal(byTeam[team]["pos"]) + " " + divShortName(byTeam[team]["div"]) + " (" + ((str(byTeam[team]["gb"]) + " GB") if byTeam[team]["gb"] >= 0.0 else ("+" + str(-byTeam[team]["gb"]) + " GA")) + ")"
		if "magic" in byTeam[team]:
			if byTeam[team]["magic"] > 0:
				byTeam[team]["text"] = byTeam[team]["text"] + ", magic number: " + str(int(byTeam[team]["magic"]))
			else:
				byTeam[team]["text"] = byTeam[team]["text"] + ", CLINCHED"
	
	return byTeam

def doStandingsMagic(byDivList,prefix=""):

	for k in sorted(byDivList,key=lambda div: re.sub("Central","Middle",div)): # so we get E/C/W
	
		byDivList[k].sort(key=lambda team: ( -team["w"]/(team["w"]+team["l"]), -team["w"]) )
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
			
		# start populating magic number at 81 games in for first-place
		if ((byDivList[k][0]["w"] + byDivList[k][0]["l"]) >= (LEAGUE_GAMES/2)):
			byDivList[k][0][prefix+"magic"] = (LEAGUE_GAMES+1) - (byDivList[k][0]["w"] + byDivList[k][1]["l"])
			for ln in range(1,len(byDivList[k])):
				if byDivList[k][ln][prefix+"pos"] == "T-1":
					byDivList[k][ln][prefix+"magic"] = (LEAGUE_GAMES+1) - (byDivList[k][ln]["w"] + byDivList[k][0]["l"])
	
	return byDivList
	
def loadMasterScoreboard(msURL, scheduleDT, msOverrideFN=None):
	
	if not msOverrideFN:
		logging.debug( "Running scoreboard for " + scheduleDT.strftime("%Y-%m-%d"))
		scheduleUrl = scheduleDT.strftime(msURL)

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

def rollGames(msXML,teams,baghdadBob,pDict):

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
							newResults["announce"].append(gameStr + " no longer " + pDict["announce"][gameId].lower() + ", " + gameNowStr)
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
				
				try:
					cevId = game.getElementsByTagName("media")[0].getAttribute("calendar_event_id")
					pDict["underway"].append(gameId)
					newResults["underway"].append( { "game": gameStr, 
						"audio": Template(mlbAudioUrl).substitute(calendar_event_id=cevId),
						"video": Template(mlbTvUrl).substitute(calendar_event_id=cevId) ,
						"foxExclusive": foxExclusive } )
				except:
					log.error("Game underway but couldn't get <media calendar_event_id=...> for " + gameId)
							
			if statusAttr not in INACTIVE_GAME_STATUS_CODES:	# only the ones with a game in progress or complete
				# moved all this out for clarity
				(pDict, newResults) = pullHighlights(game, highlightTeamId, baghdadBob, pDict, newResults)

			if statusAttr in FINAL_STATUS_CODES:
		
				statusStr = getScoreline(game)
				
				logging.debug(statusStr)
				if gameDataDir not in pDict["results"]["finals"].keys():
					pDict["results"]["finals"][gameDataDir] = (gameDataDir, statusStr, datetime.strftime(datetime.utcnow(),"%c"))
					finalDict = {"gamedir":gameDataDir,"final":statusStr,"reportTime":datetime.strftime(datetime.utcnow(),"%c")}
					
					if highlightTeamId == BOTH:
						finalDict["relevantteams"] = [home,away]
						finalDict["result"] = "neutral"
					else:
						runsElem = game.getElementsByTagName("r")[0]
						finalDict["relevantteams"] = [highlightTeamName]
						if (home in teams and int(runsElem.getAttribute("home")) > int(runsElem.getAttribute("away"))) or (away in teams and int(runsElem.getAttribute("away")) > int(runsElem.getAttribute("home"))):
							finalDict["result"] = "win"
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
			if (teamId in (home,away)) and (len(statuses) > 0) and (statuses[0].getAttribute("status") in PREGAME_STATUS_CODES) and (gameDir != afterGameDir) and afterGameDirReached:
				logging.debug( "next game for " + teamId + (("after " + afterGameDir) if afterGameDir else "") + " is " + game.getAttribute("game_data_directory"))
				return game
		
	return None

def getProbables(game,standings=None,stripDate=False):
	if game == None:
		return None
	runningStr = ""
	subToken = "ZXZXCVCV"
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
			pstr = pstr + " " + pitcher.getAttribute("wins") + "-" + pitcher.getAttribute("losses") + ", " + pitcher.getAttribute("era")
		runningStr += (game.getAttribute(cattr) + " (" + pstr + ")" + subToken)
	runningStr = re.sub(subToken+"$",", ",runningStr)
	runningStr = re.sub(subToken," at ", runningStr)
	runningStr += (re.sub("^(\d+)\/","",game.getAttribute("time_date")) + " " + game.getAttribute("time_zone"))
	if stripDate:
		runningStr = re.sub("\, \d+\/\d+",",",runningStr)
	
	if standings:
		sep = "; "
		sline = ""
		for abbr in (game.getAttribute("away_name_abbrev"), game.getAttribute("home_name_abbrev")):
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
	args = parser.parse_args()

	masterScoreboardOverride = args.file	# == None if not passed, which works

	config = ConfigParser.RawConfigParser()
	if args.config:
		print "running as config: " + args.config
		config.readfp(open(args.config))
	else:
		config.readfp(open(configFN))

	try:
		configRolloverTime = config.get("general","rolloverTime")
		intRolloverLocalTime = int(configRolloverTime,base=10)
	except Exception:
		intRolloverLocalTime = int(defaultRolloverTime,base=10)
	
	todayDT = datetime.now() - timedelta(minutes=((intRolloverLocalTime/100)*60+(intRolloverLocalTime%100)))
	todayStr = todayDT.strftime("%Y-%m-%d")

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
		masterScoreboardUrl = re.sub("LEAGUEBLOCK",config.get("general","league"),leagueAgnosticMasterScoreboardUrl)
		if config.get("general","league") not in validLeagues:
			raise ValueError("league not in permissible leagues")
	except (ConfigParser.NoOptionError, ValueError):
		masterScoreboardUrl = re.sub("LEAGUEBLOCK","mlb",leagueAgnosticMasterScoreboardUrl)

	try:
		baghdadBob = config.getboolean("general","baghdadBob")
	except ValueError:
		baghdadBob = None 	# if it's not binary, NO HIGHLIGHTS AT ALL
		logging.debug("baghdadBob is not binary, running with no highlights")

	persistDict = {}
	firstOfTheDay = False
	try:
		with open(persistFN) as opentest:
			persistDict = json.load(file(persistFN))
		if type(persistDict) != dict:
			raise ValueError("this went wrong")
	except IOError:
		pass	# persistFN doesn't exist
	except ValueError:
		logging.error("persistFN is corrupted, killing it and starting over")
		persistDict = {}

	if "todayStr" not in persistDict or ("todayStr" in persistDict and persistDict["todayStr"] != todayStr):
		for k in ("results","teamIdDir","announce","underway","upcoming"):
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

	if firstOfTheDay and masterScoreboardXml:
		standings = pullStandings(masterScoreboardXml,standingsJsonUrl,todayDT)
		for team in validTeams:
			try:
				game = nextGame(team,None,[masterScoreboardXml])
				while game != None:
					gddir = game.getAttribute("game_data_directory")
					gameProbs = getProbables(game,stripDate=True)
					if gameProbs and (gameProbs != ''):
						# put the simple one in pDict, because you'll compare that in rollGames for probables updates
						persistDict["results"]["probables"][game.getAttribute("game_data_directory")] = gameProbs
						gameProbsWithStandings = getProbables(game,standings,stripDate=True)
						if gameProbsWithStandings not in morningAnnounce:
							morningAnnounce.append(gameProbsWithStandings)
					game = nextGame(team,gddir,[masterScoreboardXml])
			except Exception as e:
				logging.error("firstOfTheDay failed for " + team + ", " + traceback.format_exc(e))
		logging.debug("it's firstOfTheDay, morningAnnounce looks like " + str(morningAnnounce))
	
	if masterScoreboardXml:
		(newResults,persistDict) = rollGames(masterScoreboardXml,validTeams,baghdadBob,persistDict)
	
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
			if tomorrowScoreboardXml == None:
				tomorrowScoreboardXml = loadMasterScoreboard(masterScoreboardUrl,(todayDT + timedelta(days=1)))
				standings = pullStandings(masterScoreboardXml,standingsJsonUrl,todayDT)
			for teamId in newFinal["relevantteams"]:
				probablesStr = getProbables(nextGame(teamId,newFinal["gamedir"],[masterScoreboardXml,tomorrowScoreboardXml],masterScoreboardUrl,6))
				sTeam = standings[teamId]
				if probablesStr == None:
					newFinal["probables"] = "No next game for " + teamId + " currently scheduled."
				else:
					newFinal["probables"] = probablesStr
				newFinal["standings"] = re.sub(r'^(\w+)',r'\g<1> currently',sTeam["text"])

	for vn in validNotifiers:
		# inherent assumption here: OK to resend whole package on notifier failure 
		# (i.e. partial repeat is OK / full failure is more likely than partial)
		try:
			if "staleResults" in persistDict:
				if vn.header in persistDict["staleResults"]:
					logging.error("haz a staleResult for " + vn.header + " " + str(persistDict["staleResults"][vn.header]))
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
