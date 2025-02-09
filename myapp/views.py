from django.shortcuts import render
from django.http import JsonResponse

from nba_api.stats.static import teams

from nba_api.stats.endpoints.scoreboardv2 import ScoreboardV2
from nba_api.stats.endpoints.leaguegamelog import LeagueGameLog

from nba_api.stats.endpoints.teaminfocommon import TeamInfoCommon
from nba_api.stats.endpoints.leaguedashteamstats import LeagueDashTeamStats

from nba_api.stats.endpoints.teamplayerdashboard import TeamPlayerDashboard
from nba_api.stats.endpoints.playergamelogs import PlayerGameLogs
from nba_api.stats.endpoints.playerindex import PlayerIndex

import pandas as pd
import time

# Create your views here.


def home(request):
    return render(request, 'home.html')


def game_list(request):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # Throttle API calls to avoid rate limiting (sleep for 0.6 seconds)
    time.sleep(0.6)

    games = ScoreboardV2(header=headers)
    games_dict = games.get_dict()
    data = games_dict['resultSets']

    game_header_data = data[0]
    line_score_data = data[1]

    game_header_df = pd.DataFrame(
        game_header_data['rowSet'], columns=game_header_data['headers'])
    line_score_df = pd.DataFrame(
        line_score_data['rowSet'], columns=line_score_data['headers'])

    # Convert GAME_DATE_EST to datetime objects
    game_header_df['GAME_DATE_EST'] = pd.to_datetime(
        game_header_df['GAME_DATE_EST'])
    line_score_df['GAME_DATE_EST'] = pd.to_datetime(
        line_score_df['GAME_DATE_EST'])

    # Extract Game Time
    game_header_df['GAME_TIME'] = game_header_df['GAME_STATUS_TEXT'].str.extract(
        r'(\d+:\d+ [ap]m ET)')

    # Merge for Home Team info
    home_df = pd.merge(game_header_df, line_score_df,  left_on=['GAME_DATE_EST', 'GAME_SEQUENCE', 'GAME_ID', 'HOME_TEAM_ID'], right_on=[
                       'GAME_DATE_EST', 'GAME_SEQUENCE', 'GAME_ID', 'TEAM_ID'], how='left')

    # Merge for Visitor Team info
    visitor_df = pd.merge(game_header_df, line_score_df, left_on=['GAME_DATE_EST', 'GAME_SEQUENCE', 'GAME_ID', 'VISITOR_TEAM_ID'], right_on=[
                          'GAME_DATE_EST', 'GAME_SEQUENCE', 'GAME_ID', 'TEAM_ID'], how='left', suffixes=('_home', '_visitor'))

    # Merge Home and Visitor DataFrames
    merged_df = pd.merge(home_df, visitor_df, on=['GAME_DATE_EST', 'GAME_SEQUENCE', 'GAME_ID', 'HOME_TEAM_ID', 'VISITOR_TEAM_ID', 'GAME_TIME', 'GAME_STATUS_TEXT', 'GAME_STATUS_ID', 'GAMECODE', 'SEASON', 'LIVE_PERIOD', 'LIVE_PC_TIME',
                         'NATL_TV_BROADCASTER_ABBREVIATION', 'HOME_TV_BROADCASTER_ABBREVIATION', 'AWAY_TV_BROADCASTER_ABBREVIATION', 'LIVE_PERIOD_TIME_BCAST', 'ARENA_NAME', 'WH_STATUS', 'WNBA_COMMISSIONER_FLAG'], suffixes=('_home', '_visitor'))

    # Select and rename columns
    final_df = merged_df[[
        'GAME_ID', 'GAME_DATE_EST', 'GAME_TIME', 'HOME_TEAM_ID', 'VISITOR_TEAM_ID',
        'TEAM_CITY_NAME_home', 'TEAM_NAME_home', 'TEAM_WINS_LOSSES_home',
        'TEAM_CITY_NAME_visitor', 'TEAM_NAME_visitor', 'TEAM_WINS_LOSSES_visitor'
    ]].rename(columns={
        'GAME_DATE_EST': 'GAME_DATE',
        'TEAM_WINS_LOSSES_home': 'HOME_TEAM_RECORD',
        'TEAM_WINS_LOSSES_visitor': 'VISITOR_TEAM_RECORD',
        'TEAM_CITY_NAME_home': 'HOME_TEAM_CITY_NAME',
        'TEAM_NAME_home': 'HOME_TEAM_NAME',
        'TEAM_CITY_NAME_visitor': 'VISITOR_TEAM_CITY_NAME',
        'TEAM_NAME_visitor': 'VISITOR_TEAM_NAME',
    })
    
    final_df = final_df.dropna(subset=['GAME_TIME'])

    return JsonResponse(final_df.to_dict(orient="records"), safe=False)


def get_teams_data(home_team_id: str, away_team_id: str):
    home_team = TeamInfoCommon(team_id=home_team_id)
    away_team = TeamInfoCommon(team_id=away_team_id)
    home_team = home_team.get_dict()
    away_team = away_team.get_dict()

    # Extract TeamInfoCommon data
    team_info = home_team['resultSets'][0]['rowSet'][0]
    # Extract TeamSeasonRanks data
    season_ranks = home_team['resultSets'][1]['rowSet'][0]
    team_df_home = pd.DataFrame(
        [team_info], columns=home_team['resultSets'][0]['headers'])
    ranks_df_home = pd.DataFrame(
        [season_ranks], columns=home_team['resultSets'][1]['headers'])
    merged_df_home = pd.merge(team_df_home, ranks_df_home, on=['TEAM_ID'])

    # Extract TeamInfoCommon data
    team_info = away_team['resultSets'][0]['rowSet'][0]
    # Extract TeamSeasonRanks data
    season_ranks = away_team['resultSets'][1]['rowSet'][0]
    team_df_away = pd.DataFrame(
        [team_info], columns=away_team['resultSets'][0]['headers'])
    ranks_df_away = pd.DataFrame(
        [season_ranks], columns=away_team['resultSets'][1]['headers'])
    merged_df_away = pd.merge(team_df_away, ranks_df_away, on=['TEAM_ID'])

    merged_df_teams = pd.concat([merged_df_home, merged_df_away])
    final_df = merged_df_teams[[
        'TEAM_ID', 'TEAM_CITY', 'TEAM_NAME', 'W', 'L', 'PCT',
        'PTS_RANK', 'PTS_PG', 'OPP_PTS_RANK', 'OPP_PTS_PG'
    ]]
    final_df['TEAM_ID'] = final_df['TEAM_ID'].astype(str)

    team_list = teams.get_teams()
    nba_team_df = pd.DataFrame.from_dict(team_list)
    nba_team_df['LOGO_PATH'] = nba_team_df['full_name'].apply(lambda team: f"/media/{team}.png")
    nba_team_df = nba_team_df.rename(columns={'id':'TEAM_ID'})
    nba_team_df = nba_team_df[['TEAM_ID','LOGO_PATH']]
    nba_team_df['TEAM_ID'] = nba_team_df['TEAM_ID'].astype(str)
    final_df = pd.merge(final_df, nba_team_df, on=['TEAM_ID'])

    print(final_df)

    #Fetch the advanced analytics like 3-points allowed, points allowed in paind 
    return final_df.to_dict(orient="records")


def get_matchups(home_team_id: str, away_team_id: str):
    game_logs = LeagueGameLog()
    game_logs = game_logs.get_dict()
    data = game_logs['resultSets']
    game_logs_data = data[0]
    game_logs_df = pd.DataFrame(
        game_logs_data['rowSet'], columns=game_logs_data['headers'])

    home_stats = game_logs_df[game_logs_df['TEAM_ID'] == home_team_id].copy()
    away_stats = game_logs_df[game_logs_df['TEAM_ID'] == away_team_id].copy()

    stat_columns = ['WL', 'MIN', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT',
                    'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK',
                    'TOV', 'PF', 'PTS', 'PLUS_MINUS']

    home_stats = home_stats.rename(
        columns={col: f'HOME_{col}' for col in stat_columns})
    away_stats = away_stats.rename(
        columns={col: f'AWAY_{col}' for col in stat_columns})

    merged_stats = pd.merge(home_stats, away_stats,
                            on='GAME_ID', suffixes=('_HOME', '_AWAY'))
    merged_stats['TOTAL_POINTS'] = merged_stats['HOME_PTS'] + merged_stats['AWAY_PTS']
    return merged_stats.to_dict(orient="records")


def player_analysis(team_id: str, game_id: str):
    player_stats = TeamPlayerDashboard(team_id=team_id)
    player_stats = player_stats.get_dict()
    data = player_stats['resultSets']
    player_stats_data = data[1]
    player_stats_df = pd.DataFrame(
        player_stats_data['rowSet'], columns=player_stats_data['headers'])
    player_stats_df['MIN'] = (
        player_stats_df['MIN'] / player_stats_df['GP']).round(1)
    player_stats_df['FGM'] = (
        player_stats_df['FGM'] / player_stats_df['GP']).round(1)
    player_stats_df['FGA'] = (
        player_stats_df['FGA'] / player_stats_df['GP']).round(1)
    player_stats_df['FG3A'] = (
        player_stats_df['FG3A'] / player_stats_df['GP']).round(1)
    player_stats_df['FG3M'] = (
        player_stats_df['FG3M'] / player_stats_df['GP']).round(1)
    player_stats_df['REB'] = (
        player_stats_df['REB'] / player_stats_df['GP']).round(1)
    player_stats_df['AST'] = (
        player_stats_df['AST'] / player_stats_df['GP']).round(1)
    player_stats_df['TOV'] = (
        player_stats_df['TOV'] / player_stats_df['GP']).round(1)
    player_stats_df['STL'] = (
        player_stats_df['STL'] / player_stats_df['GP']).round(1)
    player_stats_df['BLK'] = (
        player_stats_df['BLK'] / player_stats_df['GP']).round(1)
    player_stats_df['PF'] = (player_stats_df['PF'] /
                             player_stats_df['GP']).round(1)
    player_stats_df['PTS'] = (
        player_stats_df['PTS'] / player_stats_df['GP']).round(1)
    player_stats_df['PLUS_MINUS'] = (
        player_stats_df['PLUS_MINUS'] / player_stats_df['GP']).round(1)
    player_stats_df = player_stats_df.drop(columns=['GROUP_SET', 'NICKNAME', 'W', 'L', 'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB', 'WNBA_FANTASY_PTS', 'GP_RANK', 'W_RANK', 'L_RANK',
                                                    'W_PCT_RANK', 'MIN_RANK', 'FGM_RANK', 'FGA_RANK', 'FG_PCT_RANK',
                                                    'FG3M_RANK', 'FG3A_RANK', 'FG3_PCT_RANK', 'FTM_RANK', 'FTA_RANK',
                                                    'FT_PCT_RANK', 'OREB_RANK', 'DREB_RANK', 'REB_RANK', 'AST_RANK',
                                                    'TOV_RANK', 'STL_RANK', 'BLK_RANK', 'BLKA_RANK', 'PF_RANK', 'PFD_RANK',
                                                    'PTS_RANK', 'PLUS_MINUS_RANK', 'NBA_FANTASY_PTS_RANK', 'DD2_RANK',
                                                    'TD3_RANK', 'WNBA_FANTASY_PTS_RANK', 'NBA_FANTASY_PTS', 'PFD', 'BLKA'])
    player_stats_df = player_stats_df.sort_values(by='MIN', ascending=False)
    player_stats_df['GAME_ID'] = game_id
    return player_stats_df.to_dict(orient="records")

def get_defensive_stats(home_team_id, away_team_id):
    team_defence = LeagueDashTeamStats(measure_type_detailed_defense='Defense')
    team_defence_dict = team_defence.get_dict()
    data = team_defence_dict['resultSets']
    team_data = data[0]
    team_defence_df = pd.DataFrame(team_data['rowSet'],columns=team_data['headers'])
    team_defence_df = team_defence_df[team_defence_df['TEAM_ID'].isin([home_team_id, away_team_id])]
    team_defence_df = team_defence_df.drop(columns=['GP', 'W', 'L', 'W_PCT', 'MIN','DEF_RATING',
       'DREB', 'DREB_PCT', 'STL', 'BLK', 'OPP_PTS_OFF_TOV',
       'OPP_PTS_2ND_CHANCE', 'OPP_PTS_FB', 'OPP_PTS_PAINT', 'GP_RANK',
       'W_RANK', 'L_RANK', 'W_PCT_RANK', 'MIN_RANK', 'DREB_PCT_RANK', 'BLK_RANK'])



    team_opp_defence = LeagueDashTeamStats(measure_type_detailed_defense='Opponent')
    team_opp_defence_dict = team_opp_defence.get_dict()
    data = team_opp_defence_dict['resultSets']
    team_opp_data = data[0]
    team_opp_defence_df = pd.DataFrame(team_opp_data['rowSet'],columns=team_opp_data['headers'])
    team_opp_defence_df = team_opp_defence_df[['TEAM_ID','OPP_FG3_PCT_RANK','OPP_FG_PCT_RANK','OPP_REB_RANK']]


    defensive_stats = pd.merge(team_defence_df, team_opp_defence_df, on=['TEAM_ID'])
    
    return defensive_stats.to_dict(orient="records")

def get_offensive_stats(home_team_id, away_team_id):
    team_offence = LeagueDashTeamStats(measure_type_detailed_defense='Scoring')
    team_offence_dict = team_offence.get_dict()
    data = team_offence_dict['resultSets']
    team_data = data[0]
    team_offence_df = pd.DataFrame(team_data['rowSet'],columns=team_data['headers'])
    team_offence_df = team_offence_df[team_offence_df['TEAM_ID'].isin([home_team_id, away_team_id])]
    team_offence_df = team_offence_df.drop(columns=['GP', 'W', 'L', 'W_PCT', 'MIN', 'PCT_FGA_2PT',
       'PCT_FGA_3PT', 'PCT_PTS_2PT', 'PCT_PTS_2PT_MR', 'PCT_PTS_3PT',
       'PCT_PTS_FB', 'PCT_PTS_FT', 'PCT_PTS_OFF_TOV', 'PCT_PTS_PAINT',
       'PCT_AST_2PM', 'PCT_UAST_2PM', 'PCT_AST_3PM', 'PCT_UAST_3PM',
       'PCT_AST_FGM', 'PCT_UAST_FGM', 'GP_RANK', 'W_RANK', 'L_RANK',
       'W_PCT_RANK', 'MIN_RANK','PCT_PTS_2PT_RANK', 'PCT_PTS_2PT_MR_RANK', 
       'PCT_PTS_3PT_RANK','PCT_PTS_FT_RANK', 'PCT_PTS_OFF_TOV_RANK', 'PCT_AST_2PM_RANK', 'PCT_UAST_2PM_RANK',
       'PCT_AST_3PM_RANK', 'PCT_UAST_3PM_RANK', 'PCT_AST_FGM_RANK',
       'PCT_UAST_FGM_RANK'])

    team_basic_offence = LeagueDashTeamStats(measure_type_detailed_defense='Base')
    team_basic_offence_dict = team_basic_offence.get_dict()
    data = team_basic_offence_dict['resultSets']
    team_basic_data = data[0]
    team_basic_offence_df = pd.DataFrame(team_basic_data['rowSet'],columns=team_basic_data['headers'])
    team_basic_offence_df = team_basic_offence_df[['TEAM_ID','FG3_PCT_RANK','FG_PCT_RANK','REB_RANK','TOV_RANK','STL_RANK']]
    
    offensive_stats = pd.merge(team_offence_df, team_basic_offence_df, on=['TEAM_ID'])

    return offensive_stats.to_dict(orient="records")

def game_detail(request, game_id):

    # Game Data
    games = ScoreboardV2()
    games_dict = games.get_dict()
    data = games_dict['resultSets']

    game_header_data = data[0]

    game_header_df = pd.DataFrame(
        game_header_data['rowSet'], columns=game_header_data['headers'])
    game_header_df['GAME_ID'] = game_header_df['GAME_ID'].astype(str)

    game_header_df = game_header_df[game_header_df['GAME_ID'] == game_id]

    home_team_id = game_header_df.iloc[0]['HOME_TEAM_ID']
    away_team_id = game_header_df.iloc[0]['VISITOR_TEAM_ID']

    # Teams like City, Team Name, Record, Win Pct
    teams = get_teams_data(home_team_id, away_team_id)

    # Past Matchup Data
    matchups = get_matchups(home_team_id, away_team_id)

    home_player_stats = player_analysis(home_team_id, game_id)
    away_player_stats = player_analysis(away_team_id, game_id)

    team_defence_stats = get_defensive_stats(home_team_id, away_team_id)
    team_offence_stats = get_offensive_stats(home_team_id, away_team_id)

    return render(request, 'game_detail.html', {
        'game_data': game_header_df.to_dict(orient="records"),
        'team_data': teams,
        'previous_matchups': matchups,
        'home_team_players': home_player_stats,
        'away_team_players': away_player_stats,
        'defensive_stats': team_defence_stats,
        'offensive_stats': team_offence_stats
    })


def get_player_games(player_id, season='2024-25'):
    player_game_logs = PlayerGameLogs(season_nullable=season)
    player_stats = player_game_logs.get_dict()
    data = player_stats['resultSets']
    player_stats_data = data[0]
    player_stats_df = pd.DataFrame(
        player_stats_data['rowSet'], columns=player_stats_data['headers'])
    
    player_game_logs_2023 = PlayerGameLogs(season_nullable='2023-24')
    player_stats_2023 = player_game_logs_2023.get_dict()
    data_2023 = player_stats_2023['resultSets']
    player_stats_data_2023 = data_2023[0]
    player_stats_df_2023 = pd.DataFrame(
        player_stats_data_2023['rowSet'], columns=player_stats_data_2023['headers'])
    
    player_game_logs_2022 = PlayerGameLogs(season_nullable='2022-23')
    player_stats_2022 = player_game_logs_2022.get_dict()
    data_2022 = player_stats_2022['resultSets']
    player_stats_data_2022 = data_2022[0]
    player_stats_df_2022 = pd.DataFrame(
        player_stats_data_2022['rowSet'], columns=player_stats_data_2022['headers'])

    player_stats_df = pd.concat([player_stats_df, player_stats_df_2023, player_stats_df_2022], ignore_index=True)
    # Filter for player by player ID
    player_stats_df = player_stats_df[player_stats_df['PLAYER_ID'].astype(
        str) == player_id]
    player_stats_df['MATCHUP'] = player_stats_df['MATCHUP'].str[-3:]
    player_stats_df = player_stats_df.drop(columns=['SEASON_YEAR', 'NICKNAME', 'TEAM_ABBREVIATION', 'TEAM_NAME',
                                                    'WL', 'FTM',
                                                    'FTA', 'FT_PCT', 'OREB', 'DREB', 'BLKA','PFD', 'PLUS_MINUS', 'NBA_FANTASY_PTS', 'WNBA_FANTASY_PTS', 'GP_RANK', 'W_RANK', 'L_RANK', 'W_PCT_RANK',
                                                    'MIN_RANK', 'FGM_RANK', 'FGA_RANK', 'FG_PCT_RANK', 'FG3M_RANK',
                                                    'FG3A_RANK', 'FG3_PCT_RANK', 'FTM_RANK', 'FTA_RANK', 'FT_PCT_RANK',
                                                    'OREB_RANK', 'DREB_RANK', 'REB_RANK', 'AST_RANK', 'TOV_RANK',
                                                    'STL_RANK', 'BLK_RANK', 'BLKA_RANK', 'PF_RANK', 'PFD_RANK', 'PTS_RANK',
                                                    'PLUS_MINUS_RANK', 'NBA_FANTASY_PTS_RANK', 'DD2_RANK', 'TD3_RANK',
                                                    'WNBA_FANTASY_PTS_RANK', 'AVAILABLE_FLAG', 'MIN_SEC'])
    
    player_stats_df['MIN'] = player_stats_df['MIN'].round(1)
    player_stats_df['GAME_DATE'] = pd.to_datetime(player_stats_df['GAME_DATE'])
    player_stats_df['GAME_DATE'] = pd.to_datetime(player_stats_df['GAME_DATE']).dt.strftime('%Y-%m-%d')
    return player_stats_df.to_dict(orient="records")


def get_player_matchups(player_id, game_id):
    # Game Data
    games = ScoreboardV2()
    games_dict = games.get_dict()
    data = games_dict['resultSets']

    game_header_data = data[0]

    game_header_df = pd.DataFrame(
        game_header_data['rowSet'], columns=game_header_data['headers'])
    game_header_df['GAME_ID'] = game_header_df['GAME_ID'].astype(str)

    game_header_df = game_header_df[game_header_df['GAME_ID'] == game_id]

    player_games = pd.DataFrame.from_dict(get_player_games(player_id))
    print(player_games)

    home_team_id = game_header_df.iloc[0]['HOME_TEAM_ID']
    away_team_id = game_header_df.iloc[0]['VISITOR_TEAM_ID']

    player_data = PlayerIndex(season='2024-25')
    player_dict = player_data.get_dict()
    player_data = player_dict['resultSets']
    player_data = player_data[0]
    player_data_df = pd.DataFrame(player_data['rowSet'], columns=player_data['headers'])
    player_data_df = player_data_df[player_data_df['PERSON_ID'] == int(player_id)]
    
    if not player_data_df.empty:
        player_team_id = player_data_df.iloc[0]['TEAM_ID']
    else:
        return {}
    
    #Now that we have the team ID of the player, and the home and visitor team id, we just need to figure out which team ID is not the player's
    if player_team_id != home_team_id and player_team_id != away_team_id:
        opponent_id = {}
    else:
        if player_team_id != home_team_id:
            opponent_id = home_team_id
        elif player_team_id != away_team_id:
            opponent_id = away_team_id

    #After we do that, we use the opponent team ID to search nba_team_df to get their team abbreviation
    team_list = teams.get_teams()
    nba_team_df = pd.DataFrame.from_dict(team_list)
    
    #Using that, we fetch all of the matchups in the past 3 seasons between that player and the opponent
    opponent_team_df = nba_team_df[nba_team_df['id'] == opponent_id]
    if not player_data_df.empty:
        opponent_team_abbreviation = opponent_team_df.iloc[0]['abbreviation']
    else:
        return {}


    #Now that we have the home and away team ID's, we need to fetch the matchups:
    matchups = player_games[player_games['MATCHUP'] == opponent_team_abbreviation]
    print(matchups)
    if len(matchups) == 0:
        return {}

    return matchups.to_dict(orient="records")

def player_stats_view(request, player_id):
    stats = get_player_games(player_id)
    return JsonResponse(stats, safe=False)

def player_matchups_view(request, player_id, game_id):
    stats = get_player_matchups(player_id, game_id)
    return JsonResponse(stats, safe=False)
    
