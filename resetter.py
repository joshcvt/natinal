#!/usr/bin/python

import urllib2, json, traceback # ConfigParser, argparse	     #, logging
from datetime import timedelta, datetime, date
from string import join
import xml.etree.ElementTree as ET
from os import sys

from nat_lib import *
from reset_lib import NoGameException, NoTeamException, DabException

intRolloverLocalTime = 1000

#logLevel = logging.DEBUG
#logFN = "resetter.log"

def findGameNodes(msTree,team):
	return (msTree.getroot().findall("./game[@away_name_abbrev='" + team + "']") + msTree.getroot().findall("./game[@home_name_abbrev='" + team + "']"))


def buildVarsToCode():
	vtoc = {}
	for k in codeToVariants:
		for var in codeToVariants[k]:
			if var in vtoc:
				raise Exception("OOPS: trying to duplicate pointer " + var + " as " + k + ", it's already " + vtoc[var])
			else:
				vtoc[var] = k
				vtoc[var.lower()] = k
				vtoc[var.upper()] = k
		# and before we go, do k = k too
		vtoc[k] = k
		vtoc[k.lower()] = k	# it's already upper
		
	return vtoc

def placeAndScore(g):

	loc = g.get("location").split(",")[0]
	if not loc:
		reset = "at " + g.get("venue") 
	elif loc == "Bronx":
		reset = "in the Bronx"
	else:
		reset = "in " + loc

	reset +=  ", "
	
	# score
	hruns = g.find("linescore/r").attrib["home"]
	aruns = g.find("linescore/r").attrib["away"]
	if int(hruns) > int(aruns):
		reset += (g.attrib["home_team_name"] + " " + hruns + ", " + g.attrib["away_team_name"] + " " + aruns)
	else:
		reset += (g.attrib["away_team_name"] + " " + aruns + ", " + g.attrib["home_team_name"] + " " + hruns)
	
	return reset


def getReset(g,team,fluidVerbose):
	if g == None:
		return "No game today."

	statNode = g.find("status")
	stat = statNode.get("status")
	reset = ""
	
	if stat in PREGAME_STATUS_CODES:
		if fluidVerbose:
			reset += getProbables(g,team)
		else:
			reset += g.attrib["away_team_name"] + " at " + g.attrib["home_team_name"] + " starts at " + g.attrib["time"] + " " + g.attrib["time_zone"] + "."
		if stat in ANNOUNCE_STATUS_CODES:	# delayed start
			reset = reset[:-1] + " (" + stat.lower() + ")."
	
	if stat in UNDERWAY_STATUS_CODES:
		
		inningState = statNode.get("inning_state").lower()
		reset = placeAndScore(g) + ", " + inningState + " of the " + divOrdinal(statNode.get("inning")) + ". "
		
		# might have at, might have in as the front.		
		if g.get("double_header_sw") in ("Y","S"):
			reset = "Game " + g.get("game_nbr") + " " + reset
		else:
			reset = reset[0].upper() + reset[1:]
						
		if inningState in ("top","bottom"): 	#in play
			obstrs = { "0": "",	# don't need to say anything
						"1": "Runner on first. ",
						"2": "Runner on second. ",
						"3": "Runner on third. ",
						"4": "Runners on first and second. ",
						"5": "Runners on first and third. ",
						"6": "Runners on second and third. ",
				 		"7": "Bases loaded. "}
			onBaseStatus = g.find("runners_on_base").attrib["status"]
			reset += obstrs[onBaseStatus]
			
			outs = statNode.get("o")
			if outs == "0":
				reset += "No outs. "
			elif outs == "1":
				reset += outs + " out. "
			else:
				reset += outs + " outs. "
	
	if stat in FINAL_STATUS_CODES:
		reset += "Final "
		if g.get("double_header_sw") in ("Y","S"):	# S is for makeups
			reset += "of game " + g.get("game_nbr") + " "
		reset += placeAndScore(g)
		if (int(statNode.get("inning")) != 9):
			reset += " in " + statNode.get("inning") + " innings"
		reset += ". "
	
	if (len(reset) == 0):
		# give up
		reset = g.attrib["away_team_name"] + " at " + g.attrib["home_team_name"] + " is " + stat.lower() + "."
		
	return reset
	
	
def loadMasterScoreboard(msURL,scheduleDT):
	
	#logging.debug( "Running scoreboard for " + scheduleDT.strftime("%Y-%m-%d"))
	scheduleUrl = scheduleDT.strftime(msURL)
	
	try:
		usock = urllib2.urlopen(scheduleUrl,timeout=10)
		msTree = ET.parse(usock)
		return msTree

	#except socket.timeout as e:
	except urllib2.HTTPError as e:
		print "HTTP " + str(e.code) + " on URL: " + scheduleUrl
		#if e.code in (404,403,500,410):
		#elif e.code != 200:
	#except urllib2.URLError as e:
	except Exception as e:
		print "WENT WRONG: " + e.__module__ + "." + e.__class__.__name__
	
	return None


def getProbables(g,tvTeam=None):
	if g == None:
		return None
	runningStr = ""
	subToken = "ZXZXCVCV"
	
	awayAbbr = g.attrib["away_name_abbrev"]
	homeAbbr = g.attrib["home_name_abbrev"]
	
	for (ptag,cattr) in [("away_probable_pitcher","away_team_city"),("home_probable_pitcher","home_team_city")]:
		try:
			pitcher = g.find(ptag)
			pstr = pitcher.get("name_display_roster")
		except:
			return None
		if "," in pstr:
			pstr = pstr + "."
		if pstr == "":
			pstr = "TBA"
		else:
			pstr = pstr + " " + pitcher.get("wins") + "-" + pitcher.get("losses") + ", " + pitcher.get("era")
		runningStr += (g.get(cattr) + " (" + pstr + ")" + subToken)
	# you now have awaypitcherSUBTOKENhomepitcherSUBTOKEN
	#runningStr = re.sub(subToken+"$"," starts at ",runningStr)
	#runningStr = re.sub(subToken," at ", runningStr)
	
	runningStr = runningStr.replace(subToken," at ",1).replace(subToken," starts at ") # do first, then second
	
	runningStr += g.attrib["time"] + " " + g.attrib["time_zone"] + "."
	
	if tvTeam:
		# lazy default here
		bc = "home"
		if tvTeam == awayAbbr:
			bc = "away"
		try:
			bcast = g.find("broadcast").find(bc).find("tv").text
			if bcast:
				runningStr += " TV broadcast is on " + bcast + "."
			else:
				runningStr += " No TV."
		except Exception, e:
			print "bcast exception:" + str(e)
			pass	
	
	return runningStr


def launch(team,fluidVerbose=True,rewind=False,ffwd=False):

	#logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',filename=logFN, level=logLevel)
	
	localRollover = intRolloverLocalTime
	
	if rewind:
		# force yesterday's games by making the rollover absurd.
		localRollover += 2400
	if ffwd:
		localRollover -= 2400
	
	vtoc = buildVarsToCode()

	if team.lower() in dabList:
		#return ["Did you mean " + join(dabList[team.lower()]," or ") + "?"]
		raise DabException(dabList[team.lower()])
	elif team.lower() not in vtoc:
		raise NoTeamException
	
	todayDT = datetime.now() - timedelta(minutes=((localRollover/100)*60+(localRollover%100)))
	todayStr = todayDT.strftime("%Y-%m-%d")

	#masterScoreboardUrl = re.sub("LEAGUEBLOCK","mlb",leagueAgnosticMasterScoreboardUrl)
	masterScoreboardUrl = leagueAgnosticMasterScoreboardUrl.replace("LEAGUEBLOCK","mlb")
	masterScoreboardTree = loadMasterScoreboard(masterScoreboardUrl,todayDT)
	
	if masterScoreboardTree:
		gns = findGameNodes(masterScoreboardTree,vtoc[team])
	else:
		gns = []
	
	if len(gns) == 0:
		raise NoGameException("No game today for " + team + ".")
	
	rv = []
	for gn in gns:
		rv.append(getReset(gn,vtoc[team],fluidVerbose))
	
	return rv


