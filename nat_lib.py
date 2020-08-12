#!/usr/bin/python

import re

leagueAgnosticTeamDirectoryUrl = "http://mlb.com/lookup/xml/named.team_all.bam?sport_code=%27{league}%27&active_sw=%27Y%27&all_star_sw=%27N%27"
# http://mlb.mlb.com/properties/mlb_properties.xml is a less-good alternate

# just do this so we don't have to rework the bot
teamDirectoryUrl = leagueAgnosticTeamDirectoryUrl.replace("{league}","mlb")

# exists unless there are no games scheduled that day
leagueAgnosticMasterScoreboardUrl = "http://gd2.mlb.com/components/game/LEAGUEBLOCK/year_%Y/month_%m/day_%d/master_scoreboard.xml"
validLeagues = ["mlb","aaa","aax","afa","afx","asx","rok"] # in descending order

statsApiScheduleUrl = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=%Y-%m-%d&leagueId=103,104&hydrate=team,linescore(runners),flags,liveLookin,review,game(content(summary,media(epg)),tickets),seriesStatus(useOverride=true),broadcasts(all)&useLatestGames=false&language=en"

# replaces mobilexml highlights
statsApiGameContentJsonUrl = "https://statsapi.mlb.com/api/v1/game/GAME_PK/content?language=en" 

statsApiStandingsUrl = "https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season=%Y&date=%Y-%m-%d&standingsTypes=regularSeason,springTraining,firstHalf,secondHalf&hydrate=division,conference,sport,league,team(nextSchedule(team,gameType=[R,F,D,L,W,C],inclusive=false),previousSchedule(team,gameType=[R,F,D,L,W,C],inclusive=true))"

mlbTvBaseUrl = "https://www.mlb.com/tv/g{pk}"
gamedayBaseUrl = "https://www.mlb.com/gameday/{pk}"

# don't exist until the lineups drop
boxscoreXmlUrl = "http://gd2.mlb.com/components/game/mlb/year_${year}/month_${month}/day_${day}/${game_id}/boxscore.xml"

scheduleXmlUrl = "http://mlb.com/lookup/xml/named.schedule_team_sponsors.bam?start_date=%27{year}/02/01%27&end_date=%27{year}/11/30%27&team_id={tid}&season={year}&game_type=%27R%27&game_type=%27A%27&game_type=%27E%27&game_type=%27F%27&game_type=%27D%27&game_type=%27L%27&game_type=%27W%27&game_type=%27C%27"
#game_type S is exhibition; R regular season; D division; L league; W World Series; A ASG; (in schedule_xref only); don't know what E or C are

gameTimeLocalTBAPlaceholder = "3:33:00 AM"

# not using yet, but keeping for value
# highlightsOfficialPageTemplate = "http://m.mlb.com/video/v629584083/"
# playResultsByTimecodeUrl = "http://lwsa.mlb.com/tfs/tfs?file=/components/game/mlb/year_2016/month_04/day_30/gid_2016_04_30_wasmlb_slnmlb_1/plays.xml&timecode=20160430_182330"
# <game inning="1" inning_state="Top"...><score ar="1" hr="0" ah/hh/ae/he...>
# in mobile.xml, get home tz timecode from <media><keywords><keyword type="sv_id" value="160430_132609"/> ET.CT.MT.MST.PT; can infer UTC diff via msxml: <game time_date_hm_lg="2016/04/30 8:10" time_zone_hm_lg="-4" home_time="5:10" 

INACTIVE_GAME_STATUS_CODES = ["Postponed", "Pre-Game", "Preview", "Warmup"]
PREGAME_STATUS_CODES = ["Pre-Game", "Preview", "Warmup", "Delayed Start"]
UPCOMING_STATUS_CODES = ["Pre-Game", "Warmup"]
UNDERWAY_STATUS_CODES = ["In Progress", "Manager Challenge", "Review"]
FINAL_STATUS_CODES = ["Final", "Game Over", "Completed Early", "Completed Early: Rain"]
ANNOUNCE_STATUS_CODES = ["Delayed Start", "Postponed", "Delayed"]
POSTPONED_STATUS_CODES = ["Postponed"]
SUSPENDED_STATUS_CODES = ["Suspended"]
SUSPENDED_LEADER = "Suspended"

# for resetter.  gives various ways the team can be addressed
# including more phonetic representations for Alexa possibility
# And some inside jokes.
# code is actually name_abbrev, not code. 
codeToVariants = {
	"WSH":["Washington","Nationals","Washington Nationals","Nats","Natinals"],
	"NYM":["Mets","New York Mets"],
	"ATL":["Braves","Barves","Atlanta","Atlanta Braves","A-Braves","Eh Braves"],
	"MIA":["Marlins","Miami","Miami Marlins"],
	"PHI":["Phillies","Philadelphia","Philly","Phils","Philadelphia Phillies"],
	
	"PIT":["Pirates","Pittsburgh","Pittsburgh Pirates","Bucs","Bucks"],
	"CIN":["Cincinnati","Reds","Cincinnati Reds","Sin-see","Cincy"],
	"MIL":["Milwaukee","Brewers","Brew Crew","Crew","Milwaukee Brewers"],
	"CHC":["Cubs","Chicago Cubs","Cubbies","Shy Cubs","ChiCubs"],
	"STL":["Cardinals","Cards","Redbirds","St. Louis","St. Louis Cardinals","Evil","Satan"],
	
	"SF":["San Francisco","S.F.","Giants","San Fran","San Francisco Giants"],
	"LAD":["Los Angeles","L.A.","LA","Dodgers","Los Angeles Dodgers","L.A. Dodgers"],
	"SD":["San Diego","S.D.","Padres","Pods","San Diego Padres","Friars"],
	"ARI":["Arizona","Diamondbacks","D-Backs","Dee Backs","Arizona Diamondbacks","Snakes"],
	"COL":["Colorado","Rockies","Colorado Rockies","Rocks","Garbage Franchise","GarbageFranchise","#GarbageFranchise"],
	
	"NYY":["Yankees","New York Yankees","Yanks"],
	"BOS":["Red Sox","Boston","BoSox","Bo Socks","Boston Red Sox"],
	"BAL":["Baltimore","Orioles","Oreos","Baltimore Orioles","O's"],
	"TB":["Tampa Bay","Tampa","Rays","Tampa Bay Rays","D-Rays"],
	"TOR":["Toronto","Blue Jays","Jays","Toronto Blue Jays"],
	
	"DET":["Detroit","Tigers","Detroit Tigers"],
	"MIN":["Minnesota","Twins","Minnesota Twins"],
	"KC":["Kansas City","Royals","Kay Cee","KC","Kansas City Royals"],
	"CLE":["Cleveland","Wahoos","Indians","Cleveland Indians"],
	"CWS":["Chicago White Sox","White Sox","ChiSox","Shy Sox"],
	
	"LAA":["Angels","Los Angeles Angels","L.A. Angels of Anaheim","Anaheim"],
	"OAK":["Oakland","Athletics","A's","Oakland Athletics","Oakland A's"],
	"TEX":["Texas","Rangers","Texas Rangers"],
	"HOU":["Houston","Astros","Stros","Houston Astros"],
	"SEA":["Seattle","Mariners","Seattle Mariners","M's","Ems","6org","Six org","6 org","#6org"]
	}
dabList = {
	"new york":["Mets","Yankees"],
	"ny":["Mets","Yankees"],
	"chicago":["Cubs","White Sox"],
	"sox":["Red Sox","White Sox"]
	# I'm not disambiguating LA as Dodgers/Angels. LA is the Dodgers.
	}
	
def divOrdinal(intStr):
	match = re.search(r'\d+',intStr)
	theInt = int(match.group())
	singleEnds = {1:"st",2:"nd",3:"rd"}
	# returns ordinal string for divisional position
	if theInt in (11,12,13) or ((theInt % 10) in [0,4,5,6,7,8,9]):
		return str(theInt) + "th"
	else:
		return str(theInt) + singleEnds[theInt % 10]

