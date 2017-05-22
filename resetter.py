#!/usr/bin/python

import urllib2, ConfigParser, json, logging, traceback, re, argparse
from datetime import timedelta, datetime, date
from string import Template
#from xml.dom.minidom import parse
import xml.etree.ElementTree as ET
from os import sys

from nat_lib import *

intRolloverLocalTime = 1000

logLevel = logging.DEBUG
logFN = "resetter.log"

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
		# and before we go, do k = k too
		vtoc[k] = k
		
	return vtoc

def placeAndScore(g):

	reset = g.get("location").split(",")[0] + ", "
	# score
	hruns = g.find("linescore/r").attrib["home"]
	aruns = g.find("linescore/r").attrib["away"]
	if int(hruns) > int(aruns):
		reset += (g.attrib["home_team_name"] + " " + hruns + ", " + g.attrib["away_team_name"] + " " + aruns)
	else:
		reset += (g.attrib["away_team_name"] + " " + aruns + ", " + g.attrib["home_team_name"] + " " + hruns)
	
	return reset


def getReset(g):
	if g == None:
		return "No game today."

	statNode = g.find("status")
	stat = statNode.get("status")
	reset = ""
	
	if stat in UNDERWAY_STATUS_CODES:
		if g.get("double_header_sw") == "Y":
			reset += "Game " + g.get("game_nbr") + " in "
		else:
			reset += "In "
		
		inningState = statNode.get("inning_state").lower()
		reset += placeAndScore(g) + ", " + inningState + " of the " + divOrdinal(statNode.get("inning")) + ". "
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
			if outs == "1":
				reset += outs + " out. "
			else:
				reset += outs + " outs. "
	
	if stat in FINAL_STATUS_CODES:
		reset += "Final "
		if g.get("double_header_sw") == "Y":
			reset += "of game " + g.get("game_nbr") + " "
		reset += "in " + placeAndScore(g) + ". "
			
	return reset
	
	
def loadMasterScoreboard(msURL,scheduleDT):
	
	logging.debug( "Running scoreboard for " + scheduleDT.strftime("%Y-%m-%d"))
	scheduleUrl = scheduleDT.strftime(msURL)
	
	try:
		usock = urllib2.urlopen(scheduleUrl,timeout=10)
		msTree = ET.parse(usock)
		return msTree

	#except socket.timeout as e:
	#except urllib2.HTTPError as e:
		#if e.code in (404,403,500,410):
		#elif e.code != 200:
	#except urllib2.URLError as e:
	except Exception as e:
		print "WENT WRONG: " + e.__module__ + "." + e.__class__.__name__
	
	return None
	

def main():

	logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',filename=logFN, level=logLevel)
	
	vtoc = buildVarsToCode()

	todayDT = datetime.now() - timedelta(minutes=((intRolloverLocalTime/100)*60+(intRolloverLocalTime%100)))
	todayStr = todayDT.strftime("%Y-%m-%d")

	masterScoreboardUrl = re.sub("LEAGUEBLOCK","mlb",leagueAgnosticMasterScoreboardUrl)
	masterScoreboardTree = loadMasterScoreboard(masterScoreboardUrl,todayDT)

	gns = findGameNodes(masterScoreboardTree,vtoc["Texas"])
	#text = getReset(gn)
	for gn in gns:
		print getReset(gn)
	

main()

