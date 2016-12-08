teamDirectoryUrl = "http://mlb.com/lookup/xml/named.team_all.bam?sport_code=%27mlb%27&active_sw=%27Y%27&all_star_sw=%27N%27"
# http://mlb.mlb.com/properties/mlb_properties.xml is a less-good alternate

# exists unless there are no games scheduled that day
leagueAgnosticMasterScoreboardUrl = "http://gdx.mlb.com/gdcross/components/game/LEAGUEBLOCK/year_%Y/month_%m/day_%d/master_scoreboard.xml"
validLeagues = ["mlb","aaa","aax","afa","afx","asx","rok"]


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
