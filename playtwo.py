import xml.dom, urllib, ConfigParser, json, logging, traceback, re, argparse
from datetime import timedelta, datetime
from string import Template
from xml.dom.minidom import parse
from os import sys

from consts import *

DUPE_TEAM_ID = -5555
# http://mlb.com/lookup/xml/named.schedule_team_sponsors.bam?start_date=%272017/03/01%27&end_date=%272017/11/30%27&team_id=119&season=2017&game_type=%27R%27&game_type=%27A%27&game_type=%27E%27&game_type=%27F%27&game_type=%27D%27&game_type=%27L%27&game_type=%27W%27&game_type=%27C%27
# http://mlb.com/lookup/xml/named.schedule_team_sponsors.bam?start_date=%272016/03/01%27&end_date=%272016/11/30%27&team_id=119&season=2016&game_type=%27R%27&game_type=%27A%27&game_type=%27E%27&game_type=%27F%27&game_type=%27D%27&game_type=%27L%27&game_type=%27W%27&game_type=%27C%27
# schedule_team_complete: game_type S is exhibition; R regular season; D division; L league; W World Series; A ASG (in schedule_xref only)
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


def createIndexes(teams):
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


def main():
	(leagues,teams) = loadLeagues()
	#print json.dumps(leagues["afa"], indent=2)
	#print leagues
	(cities, fullnames, dupes) = createIndexes(teams)
	#print cities
	#print fullnames
	print dupes


main()


teamRowXml = """<row team_id="3712" team_code="bca" file_code="t3712" franchise_code="" bis_team_code="" name_abbrev="BC" name_display_brief="Astros" name_display_short="Buies Creek" name_display_full="Buies Creek Astros" name_display_long="Buies Creek Astros" division_id="211" division="S" division_abbrev="CARS" division_full="Carolina League Southern" league_id="122" league="CAR" league_abbrev="CAR" league_full="Carolina League" sport_id="13" sport_code="afa" sport_abbrev="A (Adv)" sport_full="Class A Advanced" mlb_org_id="117" mlb_org_abbrev="HOU" mlb_org_brief="Astros" mlb_org_short="Houston" mlb_org="Houston Astros" spring_league_id="" spring_league="" spring_league_abbrev="" spring_league_full="" venue_id="5285" venue_name="Jim Perry Stadium" venue_short="" time_zone="ET" time_zone_alt="America/New_York" address="" address_line1="" address_line2="" address_line3="" address_intl="" address_city="" address_state="" address_zip="" address_province="" address_country="" phone_number="" city="Buies Creek" state="NC" website_url="" store_url="" base_url="" first_year_of_play="1987" last_year_of_play="2017" all_star_sw="N" active_sw="Y" name="Astros" name_short="Buies Creek" sport_code_display="Class A Advanced" sport_code_name="A (Adv)"/>
<row team_id="249" team_code="cmc" file_code="t249" franchise_code="" bis_team_code="" name_abbrev="CAR" name_display_brief="Mudcats" name_display_short="Carolina" name_display_full="Carolina Mudcats" name_display_long="Carolina Mudcats" division_id="211" division="S" division_abbrev="CARS" division_full="Carolina League Southern" league_id="122" league="CAR" league_abbrev="CAR" league_full="Carolina League" sport_id="13" sport_code="afa" sport_abbrev="A (Adv)" sport_full="Class A Advanced" mlb_org_id="158" mlb_org_abbrev="MIL" mlb_org_brief="Brewers" mlb_org_short="Milwaukee" mlb_org="Milwaukee Brewers" spring_league_id="" spring_league="" spring_league_abbrev="" spring_league_full="" venue_id="2625" venue_name="Five County Stadium" venue_short="" time_zone="ET" time_zone_alt="America/New_York" address="1501 N.C. Highway 39 Zebulon, NC	27597" address_line1="1501 N.C. Highway 39" address_line2="" address_line3="" address_intl="N" address_city="Zebulon" address_state="NC" address_zip="27597" address_province="" address_country="USA" phone_number="" city="Zebulon" state="NC" website_url="" store_url="" base_url="" first_year_of_play="1969" last_year_of_play="2017" all_star_sw="N" active_sw="Y" name="Mudcats" name_short="Carolina" sport_code_display="Class A Advanced" sport_code_name="A (Adv)"/>
<row team_id="485" team_code="dne" file_code="t485" franchise_code="" bis_team_code="" name_abbrev="DNE" name_display_brief="Wood Ducks" name_display_short="Down East" name_display_full="Down East Wood Ducks" name_display_long="Down East Wood Ducks" division_id="211" division="S" division_abbrev="CARS" division_full="Carolina League Southern" league_id="122" league="CAR" league_abbrev="CAR" league_full="Carolina League" sport_id="13" sport_code="afa" sport_abbrev="A (Adv)" sport_full="Class A Advanced" mlb_org_id="140" mlb_org_abbrev="TEX" mlb_org_brief="Rangers" mlb_org_short="Texas" mlb_org="Texas Rangers" spring_league_id="" spring_league="" spring_league_abbrev="" spring_league_full="" venue_id="2777" venue_name="Grainger Stadium" venue_short="" time_zone="ET" time_zone_alt="America/New_York" address="" address_line1="" address_line2="" address_line3="" address_intl="" address_city="" address_state="" address_zip="" address_province="" address_country="" phone_number="" city="Kinston" state="NC" website_url="" store_url="" base_url="" first_year_of_play="1962" last_year_of_play="2017" all_star_sw="N" active_sw="Y" name="Wood Ducks" name_short="Down East" sport_code_display="Class A Advanced" sport_code_name="A (Adv)"/>"""