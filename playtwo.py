import xml.dom, urllib, ConfigParser, json, logging, traceback, re, argparse
from datetime import timedelta, datetime, date
from string import Template
from xml.dom.minidom import parse
from os import sys

from consts import *

#desiredTeams = ["BUIES CREEK ASTROS","DOWN EAST WOOD DUCKS","WINSTON-SALEM DASH"]
#traveltime = 190	# minutes
desiredTeams = ["Carolina Mudcats","Down East Wood Ducks"]
traveltime = 70

gamelen = 180		# minutes

logLevel = logging.DEBUG
logFN = "playtwo_undated.log"

DUPE_TEAM_ID = -5555
USE_CURRENT = -5556
DH_SAME_DAY = -5557


# http://mlb.com/lookup/xml/named.schedule_team_sponsors.bam?start_date=%272017/03/01%27&end_date=%272017/11/30%27&team_id=119&season=2017&game_type=%27R%27&game_type=%27A%27&game_type=%27E%27&game_type=%27F%27&game_type=%27D%27&game_type=%27L%27&game_type=%27W%27&game_type=%27C%27
# http://mlb.com/lookup/xml/named.schedule_team_sponsors.bam?start_date=%272016/03/01%27&end_date=%272016/11/30%27&team_id=119&season=2016&game_type=%27R%27&game_type=%27A%27&game_type=%27E%27&game_type=%27F%27&game_type=%27D%27&game_type=%27L%27&game_type=%27W%27&game_type=%27C%27
# schedule_team_complete: game_type S is exhibition; R regular season; D division; L league for MLB, div for MiLB; W World Series for MLB, league for MiLB; A ASG; (in schedule_xref only)
# schedule_xref has one row for ASG
# schedule_sponsors is individual gameday sponsors if set.
# schedule_nongame has rows for spring training games with a different schema

def loadLeagues():
	leagues = {}
	teams = {}
	for league in validLeagues:	# note, a "league" is actually a classification here
		dirUrl = leagueAgnosticTeamDirectoryUrl.replace("{league}",league) 
		logging.debug("loading class " + league + " from " + dirUrl)
		usock = urllib.urlopen(dirUrl)
		if usock.getcode() != 200:
			logging.error("Get teamdir failed for league " + league + " on " + dirUrl)
			return None
		# so let's continue
		leagues[league] = {}
		try:
			dirTree = parse(usock)
			for row in dirTree.getElementsByTagName("row"):
				rowDict = dict(row.attributes.items())
				# team_id and team_code are unique. name_abbrev is not even unique within classifications: COL for Columbus and Colorado Springs AAA
				leagues[league][rowDict["team_id"]] = rowDict
				teams[rowDict["team_id"]] = rowDict
		except Exception as e:
			logging.error("XML directory get/decode failed for dir URL " + dir + ", " + traceback.format_exc(e))
			return None
		usock.close()
	return (leagues,teams)


def buildIndexes(teams):
	(cities, fullnames, dupes) = ({},{},{})
	for tid in teams:	
		team = teams[tid]
		upperFn = team["name_display_long"].upper()
		upperSn = team["name_display_short"].upper()
		fullnames[upperFn] = tid
		if upperSn in cities:	# dupe
			if upperSn in dupes:
				dupes[upperSn].append(tid)
			else:
				dupes[upperSn] = [cities[upperSn],tid]
				cities[upperSn] = DUPE_TEAM_ID
		else:
			cities[upperSn] = tid
	return (cities, fullnames, dupes)


def loadSchedule(tid,year=USE_CURRENT):
	
	if year == USE_CURRENT:
		year = datetime.now().strftime("%Y") 
	else:
		if isinstance(year,(int,long)):
			year = str(year)
	
	sched = []
	# OK, now that that's over with
	usock = urllib.urlopen(scheduleXmlUrl.replace("{year}",year).replace("{tid}",tid))
	if usock.getcode() != 200:
		logging.error("Get sched failed for tid " + tid + " on " + scheduleXmlUrl)
		return None
	# so let's continue
	try:
		schedTree = parse(usock)
		for stcomplete in schedTree.getElementsByTagName("schedule_team_complete"):	# should only be one
			logging.debug("got stcomplete for " + scheduleXmlUrl.replace("{year}",year).replace("{tid}",tid))
			for row in stcomplete.getElementsByTagName("row"):				# should be a lot
				#logging.debug("got row for tid " + tid)
				rowDict = dict(row.attributes.items())
				if rowDict["game_type"] in ("R","D","L","W"):
					sched.append(rowDict)
	except Exception as e:
		logging.error("Some kind of fail in parsing for tid " + tid)
		return None
	
	return sched

def make_slotcal(game_year):

	caldate = date(game_year,1,1)
	yeardict = {}
	oneday = timedelta(days=1)
	while caldate.year == game_year:
		yeardict[caldate.strftime("%Y-%m-%d")] = []
		caldate += oneday

	return yeardict
	
def std_gamestr(rd):
	return rd["opponent_abbrev"] + "@" + rd["team_abbrev"] + ", " + rd["venue_name"] + ", " + rd["game_time_local"]

def dh_ok(gamelist):
	
	if len(gamelist) < 2:
		return None
	
	gamelist = sorted(gamelist,key=lambda game:datetime.strptime(game["game_time_local"],"%m/%d/%Y %I:%M:%S %p"))
	mindelta = timedelta(minutes=gamelen) + timedelta(minutes=traveltime)
	
	if len(gamelist) == 2:
		gamedelta = datetime.strptime(gamelist[1]["game_time_local"],"%m/%d/%Y %I:%M:%S %p") - datetime.strptime(gamelist[0]["game_time_local"],"%m/%d/%Y %I:%M:%S %p")
		if (gamedelta > mindelta):
			return "Good DH: " + std_gamestr(gamelist[0]) + " and " + std_gamestr(gamelist[1])
		else:
			return None
	else:
		basestr = "haven't implemented calculation for " + str(len(gamelist)) + " games:\n\t"
		n = 0
		for rd in gamelist:
			if n != 0:
				basestr + "; "
			basestr += std_gamestr(rd)
			n += 1
		return basestr

	return None

	
def do_dh(scheds):

	TIMESEP_FUDGEMIN = 10
	
	# get the year from the sched
	game_year = None
	for tn in scheds:
		if not game_year:
			for rd in scheds[tn]:
				try:
					game_year = re.search(r'^(\d+)',rd["game_date"]).group(0)
					if game_year:
						break
				except:
					None
	if not game_year:
		raise Exception("no games found, can't do this")
	else:
		game_year = int(game_year)
	
	yeardict = make_slotcal(game_year)
		
	# build game list by day, discarding road games
	for tn in scheds:
		for rd in scheds[tn]:
			if rd["home_away_sw"] == 'H':
				yeardict[rd["game_date"].split('T')[0]].append(rd)
	
	# run over list to find times six hours apart, minus gametime fudge factor 
	#print rd["game_date"], rd["team_abbrev"], rd["opponent_abbrev"], rd["game_time_local"]
	#2017-04-06T00:00:00 DE SAL 4/6/2017 3:33:00 AM
	for ymd in sorted(yeardict):
		#if len(yeardict[ymd]) < 2:
		#	continue
		#dstr = ymd
		#for rd in sorted(yeardict[ymd],key=lambda game:datetime.strptime(game["game_time_local"],"%m/%d/%Y %I:%M:%S %p")):
		#	dstr += ", " + std_gamestr(rd)
		#print dstr
		dstr = dh_ok(yeardict[ymd])
		if dstr:
			print dstr
	
	

def main():

	logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',filename=logFN, level=logLevel)

	(leagues,teams) = loadLeagues()
	#print json.dumps(leagues["afa"], indent=2)
	#print leagues
	(cities, fullnames, dupes) = buildIndexes(teams)
	#print cities
	#print fullnames
	#print dupes
	scheds = {}
	for tname in desiredTeams:
		if tname.upper() in fullnames:
			scheds[tname] = loadSchedule(fullnames[tname.upper()])
		elif tname.upper() in cities:
			if cities[tname.upper()] == DUPE_TEAM_ID:
				logging.error("team " + tname + " is ambiguous, must provide nickname")
		else:
			logging.error("team not found: " + tname)
			
	for tname in scheds:
		logging.debug("Yo, I got sked for " + tname + ", " + str(len(scheds[tname])) + " games")
		
	do_dh(scheds)


main()


teamRowXml = """<row team_id="3712" team_code="bca" file_code="t3712" franchise_code="" bis_team_code="" name_abbrev="BC" name_display_brief="Astros" name_display_short="Buies Creek" name_display_full="Buies Creek Astros" name_display_long="Buies Creek Astros" division_id="211" division="S" division_abbrev="CARS" division_full="Carolina League Southern" league_id="122" league="CAR" league_abbrev="CAR" league_full="Carolina League" sport_id="13" sport_code="afa" sport_abbrev="A (Adv)" sport_full="Class A Advanced" mlb_org_id="117" mlb_org_abbrev="HOU" mlb_org_brief="Astros" mlb_org_short="Houston" mlb_org="Houston Astros" spring_league_id="" spring_league="" spring_league_abbrev="" spring_league_full="" venue_id="5285" venue_name="Jim Perry Stadium" venue_short="" time_zone="ET" time_zone_alt="America/New_York" address="" address_line1="" address_line2="" address_line3="" address_intl="" address_city="" address_state="" address_zip="" address_province="" address_country="" phone_number="" city="Buies Creek" state="NC" website_url="" store_url="" base_url="" first_year_of_play="1987" last_year_of_play="2017" all_star_sw="N" active_sw="Y" name="Astros" name_short="Buies Creek" sport_code_display="Class A Advanced" sport_code_name="A (Adv)"/>
<row team_id="249" team_code="cmc" file_code="t249" franchise_code="" bis_team_code="" name_abbrev="CAR" name_display_brief="Mudcats" name_display_short="Carolina" name_display_full="Carolina Mudcats" name_display_long="Carolina Mudcats" division_id="211" division="S" division_abbrev="CARS" division_full="Carolina League Southern" league_id="122" league="CAR" league_abbrev="CAR" league_full="Carolina League" sport_id="13" sport_code="afa" sport_abbrev="A (Adv)" sport_full="Class A Advanced" mlb_org_id="158" mlb_org_abbrev="MIL" mlb_org_brief="Brewers" mlb_org_short="Milwaukee" mlb_org="Milwaukee Brewers" spring_league_id="" spring_league="" spring_league_abbrev="" spring_league_full="" venue_id="2625" venue_name="Five County Stadium" venue_short="" time_zone="ET" time_zone_alt="America/New_York" address="1501 N.C. Highway 39 Zebulon, NC	27597" address_line1="1501 N.C. Highway 39" address_line2="" address_line3="" address_intl="N" address_city="Zebulon" address_state="NC" address_zip="27597" address_province="" address_country="USA" phone_number="" city="Zebulon" state="NC" website_url="" store_url="" base_url="" first_year_of_play="1969" last_year_of_play="2017" all_star_sw="N" active_sw="Y" name="Mudcats" name_short="Carolina" sport_code_display="Class A Advanced" sport_code_name="A (Adv)"/>
<row team_id="485" team_code="dne" file_code="t485" franchise_code="" bis_team_code="" name_abbrev="DNE" name_display_brief="Wood Ducks" name_display_short="Down East" name_display_full="Down East Wood Ducks" name_display_long="Down East Wood Ducks" division_id="211" division="S" division_abbrev="CARS" division_full="Carolina League Southern" league_id="122" league="CAR" league_abbrev="CAR" league_full="Carolina League" sport_id="13" sport_code="afa" sport_abbrev="A (Adv)" sport_full="Class A Advanced" mlb_org_id="140" mlb_org_abbrev="TEX" mlb_org_brief="Rangers" mlb_org_short="Texas" mlb_org="Texas Rangers" spring_league_id="" spring_league="" spring_league_abbrev="" spring_league_full="" venue_id="2777" venue_name="Grainger Stadium" venue_short="" time_zone="ET" time_zone_alt="America/New_York" address="" address_line1="" address_line2="" address_line3="" address_intl="" address_city="" address_state="" address_zip="" address_province="" address_country="" phone_number="" city="Kinston" state="NC" website_url="" store_url="" base_url="" first_year_of_play="1962" last_year_of_play="2017" all_star_sw="N" active_sw="Y" name="Wood Ducks" name_short="Down East" sport_code_display="Class A Advanced" sport_code_name="A (Adv)"/>"""

#<row team_id="119" team_file_code="la" team_city="LA Dodgers" team_full="Los Angeles Dodgers" team_brief="Dodgers" team_abbrev="LAD" league_id="104" league="NL" game_pk="490109" record_source="S" game_id="2017/04/03/sdnmlb-lanmlb-1" calendar_event_id="14-490109-2017-04-03" game_type="R" month="4" game_date="2017-04-03T00:00:00" month_abbrev="Apr" month_full="April" day="2" day_abbrev="Mon" day_full="Monday" home_away_sw="H" double_header_sw="N" game_nbr="1" game_time_et="2017-04-03T16:10:00" if_necessary="N" opponent_id="135" opponent_file_code="sd" opponent_city="San Diego" opponent_full="San Diego Padres" opponent_brief="Padres" opponent_abbrev="SD" opponent_league_id="104" opponent_league="NL" description="Dodgers home opener" split_squad="" opponent_split_squad="N" venue_name="Dodger Stadium" venue_city="Los Angeles" venue_twc_loc="USCA0638" game_time_local="4/3/2017 1:10:00 PM" time_zone_local="PDT" team_game_time="4/3/2017 1:10:00 PM" team_time_zone="PDT" opponent_game_time="4/3/2017 1:10:00 PM" opponent_time_zone="PDT" resumed_on="" resumed_at="" resumed_from="" rescheduled_to="" rescheduled_at="" rescheduled_from="" game_status_ind="S" game_status="Scheduled" reason="" gameday_sw="P" milbtv_sw="N" team_tunein="" team_tv="" opponent_tunein="" opponent_tv="" scheduled_innings="9" inning="" top_inning_sw="" probable_id="" probable="" probable_roster="" probable_wl="0-0" probable_era="-.--" opp_probable_id="" opp_probable="" opp_probable_roster="" opp_probable_wl="0-0" opp_probable_era="-.--" team_wl="0-0" opponent_wl="0-0" team_score="" opponent_score="" result="" win_pitcher_id="" win_pitcher="" win_pitcher_wl="0-0" win_pitcher_era="-.--" loss_pitcher_id="" loss_pitcher="" loss_pitcher_wl="0-0" loss_pitcher_era="-.--" save_pitcher_id="" save_pitcher="" save_pitcher_sv="" editorial_stats_type="R" editorial_stats_season="2017"/>
#<row team_id="119" team_file_code="la" team_city="Los Angeles" team_full="Los Angeles Dodgers" team_brief="Dodgers" team_abbrev="LAD" league_id="104" league="NL" game_pk="446871" record_source="S" game_id="2016/04/04/lanmlb-sdnmlb-1" calendar_event_id="14-446871-2016-04-04" game_type="R" month="4" game_date="2016-04-04T00:00:00" month_abbrev="Apr" month_full="April" day="2" day_abbrev="Mon" day_full="Monday" home_away_sw="A" double_header_sw="N" game_nbr="1" game_time_et="2016-04-04T19:05:00" if_necessary="N" opponent_id="135" opponent_file_code="sd" opponent_city="San Diego" opponent_full="San Diego Padres" opponent_brief="Padres" opponent_abbrev="SD" opponent_league_id="104" opponent_league="NL" description="Padres Home Opener" split_squad="N" opponent_split_squad="" venue_name="Petco Park" venue_city="San Diego" venue_twc_loc="USCA0982" game_time_local="4/4/2016 4:05:00 PM" time_zone_local="PDT" team_game_time="4/4/2016 4:05:00 PM" team_time_zone="PDT" opponent_game_time="4/4/2016 4:05:00 PM" opponent_time_zone="PDT" resumed_on="" resumed_at="" resumed_from="" rescheduled_to="" rescheduled_at="" rescheduled_from="" game_status_ind="F" game_status="Final" reason="" gameday_sw="P" milbtv_sw="N" team_tunein="" team_tv="SportsNet LA" opponent_tunein="" opponent_tv="FSSD" scheduled_innings="9" inning="9" top_inning_sw="N" probable_id="477132" probable="Kershaw, Clayton" probable_roster="Kershaw" probable_wl="0-0" probable_era="-.--" opp_probable_id="475115" opp_probable="Ross, Tyson" opp_probable_roster="Ross, T" opp_probable_wl="0-0" opp_probable_era="-.--" team_wl="1-0" opponent_wl="0-1" team_score="15" opponent_score="0" result="W" win_pitcher_id="477132" win_pitcher="Kershaw, Clayton" win_pitcher_wl="1-0" win_pitcher_era="0.00" loss_pitcher_id="475115" loss_pitcher="Ross, Tyson" loss_pitcher_wl="0-1" loss_pitcher_era="11.81" save_pitcher_id="" save_pitcher="" save_pitcher_sv="" editorial_stats_type="R" editorial_stats_season="2016"/>
