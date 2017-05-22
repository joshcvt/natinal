#!/usr/bin/python

import re

leagueAgnosticTeamDirectoryUrl = "http://mlb.com/lookup/xml/named.team_all.bam?sport_code=%27{league}%27&active_sw=%27Y%27&all_star_sw=%27N%27"
# http://mlb.mlb.com/properties/mlb_properties.xml is a less-good alternate

# just do this so we don't have to rework the bot
teamDirectoryUrl = leagueAgnosticTeamDirectoryUrl.replace("{league}","mlb")

# exists unless there are no games scheduled that day
leagueAgnosticMasterScoreboardUrl = "http://gdx.mlb.com/gdcross/components/game/LEAGUEBLOCK/year_%Y/month_%m/day_%d/master_scoreboard.xml"
validLeagues = ["mlb","aaa","aax","afa","afx","asx","rok"] # in descending order


# doesn't exist until the game starts
mobileHighlightsUrl = "http://gdx.mlb.com/gdcross${game_data_directory}/media/mobile.xml" 

standingsJsonUrl = "http://mlb.mlb.com/lookup/json/named.standings_schedule_date.bam?season=${year}&schedule_game_date.game_date=%27${slashDate}%27&sit_code=%27h0%27&league_id=103&league_id=104&all_star_sw=%27N%27&version=2"

mlbTvUrl = "http://m.mlb.com/tv/e${calendar_event_id}/"
mlbAudioUrl = "http://m.mlb.com/tv/e${calendar_event_id}/?media_type=audio&clickOrigin=MSB&team=mlb"

# don't exist until the lineups drop
boxscoreXmlUrl = "http://gdx.mlb.com/components/game/mlb/year_${year}/month_${month}/day_${day}/${game_id}/boxscore.xml"

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
FINAL_STATUS_CODES = ["Final", "Game Over", "Completed Early"]
ANNOUNCE_STATUS_CODES = ["Delayed Start", "Postponed", "Delayed"]

# future stuff for resetter
codeToVariants = {
	"WSH":["Washington","Nationals","Washington Nationals","Nats"],
	"NYM":["Mets","New York Mets"],
	
	"NYY":["Yankees","New York Yankees"],
	
	"MIN":["Minnesota","Twins","Minnesota Twins"],
	"KC":["Kansas City","Royals","Kay Cee","KC","Kansas City Royals"],
	
	"SEA":["Seattle","Mariners","Seattle Mariners","M's","Ems"]
	#TODO: fill
	}
dabList = {
	"New York":["Mets","Yankees"],
	"Chicago":["Cubs","White Sox"]
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

