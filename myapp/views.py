from django.shortcuts import render
from django.http import JsonResponse

from nba_api.stats.endpoints.scoreboardv2 import ScoreboardV2
from nba_api.stats.endpoints.leaguegamelog import LeagueGameLog

from nba_api.stats.endpoints.teaminfocommon import TeamInfoCommon
from nba_api.stats.endpoints.teamgamelogs import TeamGameLogs

import pandas as pd

# Create your views here.


def home(request):
    return render(request, 'home.html')


def game_list(request):
    games = ScoreboardV2()
    games_dict = games.get_dict()
    data = games_dict['resultSets']

    game_header_data = data[0]
    line_score_data = data[1]

    game_header_df = pd.DataFrame(game_header_data['rowSet'], columns=game_header_data['headers'])
    line_score_df = pd.DataFrame(line_score_data['rowSet'], columns=line_score_data['headers'])

    # Convert GAME_DATE_EST to datetime objects
    game_header_df['GAME_DATE_EST'] = pd.to_datetime(game_header_df['GAME_DATE_EST'])
    line_score_df['GAME_DATE_EST'] = pd.to_datetime(line_score_df['GAME_DATE_EST'])

    # Extract Game Time
    game_header_df['GAME_TIME'] = game_header_df['GAME_STATUS_TEXT'].str.extract(r'(\d+:\d+ [ap]m ET)')

    # Merge for Home Team info
    home_df = pd.merge(game_header_df, line_score_df,  left_on=['GAME_DATE_EST', 'GAME_SEQUENCE', 'GAME_ID', 'HOME_TEAM_ID'], right_on=['GAME_DATE_EST', 'GAME_SEQUENCE', 'GAME_ID', 'TEAM_ID'], how='left')

    # Merge for Visitor Team info
    visitor_df = pd.merge(game_header_df, line_score_df, left_on=['GAME_DATE_EST', 'GAME_SEQUENCE', 'GAME_ID', 'VISITOR_TEAM_ID'], right_on=['GAME_DATE_EST', 'GAME_SEQUENCE', 'GAME_ID', 'TEAM_ID'], how='left', suffixes=('_home', '_visitor'))


    # Merge Home and Visitor DataFrames
    merged_df = pd.merge(home_df, visitor_df, on=['GAME_DATE_EST', 'GAME_SEQUENCE', 'GAME_ID', 'HOME_TEAM_ID', 'VISITOR_TEAM_ID', 'GAME_TIME', 'GAME_STATUS_TEXT', 'GAME_STATUS_ID', 'GAMECODE','SEASON', 'LIVE_PERIOD', 'LIVE_PC_TIME', 'NATL_TV_BROADCASTER_ABBREVIATION', 'HOME_TV_BROADCASTER_ABBREVIATION', 'AWAY_TV_BROADCASTER_ABBREVIATION', 'LIVE_PERIOD_TIME_BCAST', 'ARENA_NAME', 'WH_STATUS', 'WNBA_COMMISSIONER_FLAG'], suffixes=('_home', '_visitor'))

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

    print(final_df.columns)

    return JsonResponse(final_df.to_dict(orient="records"),safe=False)

def game_detail(request, game_id):

    #Game Data
    games = ScoreboardV2()
    games_dict = games.get_dict()
    data = games_dict['resultSets']

    game_header_data = data[0]
    
    game_header_df = pd.DataFrame(game_header_data['rowSet'], columns=game_header_data['headers'])
    game_header_df['GAME_ID'] = game_header_df['GAME_ID'].astype(str)


    game_header_df = game_header_df[game_header_df['GAME_ID'] == game_id]
    
    home_team_id = game_header_df.iloc[0]['HOME_TEAM_ID']
    away_team_id = game_header_df.iloc[0]['VISITOR_TEAM_ID']

    #Teams like City, Team Name, Record, Win Pct
    home_team = TeamInfoCommon(team_id=home_team_id)
    away_team = TeamInfoCommon(team_id=away_team_id)
    home_team = home_team.get_dict()
    away_team = away_team.get_dict()

    team_info = home_team['resultSets'][0]['rowSet'][0]  # Extract TeamInfoCommon data
    season_ranks = home_team['resultSets'][1]['rowSet'][0] # Extract TeamSeasonRanks data
    team_df_home = pd.DataFrame([team_info], columns=home_team['resultSets'][0]['headers'])
    ranks_df_home = pd.DataFrame([season_ranks], columns=home_team['resultSets'][1]['headers'])
    merged_df_home = pd.merge(team_df_home, ranks_df_home, on=['TEAM_ID'])

    team_info = away_team['resultSets'][0]['rowSet'][0]  # Extract TeamInfoCommon data
    season_ranks = away_team['resultSets'][1]['rowSet'][0] # Extract TeamSeasonRanks data
    team_df_away = pd.DataFrame([team_info], columns=away_team['resultSets'][0]['headers'])
    ranks_df_away = pd.DataFrame([season_ranks], columns=away_team['resultSets'][1]['headers'])
    merged_df_away = pd.merge(team_df_away, ranks_df_away, on=['TEAM_ID'])

    merged_df_teams = pd.concat([merged_df_home,merged_df_away])
    final_df = merged_df_teams[[
        'TEAM_ID', 'TEAM_CITY', 'TEAM_NAME', 'W', 'L', 'PCT',
        'PTS_RANK', 'PTS_PG', 'OPP_PTS_RANK', 'OPP_PTS_PG'
    ]]

    #Past Matchup Data
    # Filter for games where the teams played against each other (both home/away combinations)

    game_logs = LeagueGameLog()
    game_logs = game_logs.get_dict()
    data = game_logs['resultSets']
    game_logs_data = data[0]
    game_logs_df = pd.DataFrame(game_logs_data['rowSet'], columns=game_logs_data['headers'])

    home_stats = game_logs_df[game_logs_df['TEAM_ID'] == home_team_id].copy()
    away_stats = game_logs_df[game_logs_df['TEAM_ID'] == away_team_id].copy()

    stat_columns = ['WL', 'MIN', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 
                'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 
                'TOV', 'PF', 'PTS', 'PLUS_MINUS']

    home_stats = home_stats.rename(columns={col: f'HOME_{col}' for col in stat_columns})
    away_stats = away_stats.rename(columns={col: f'AWAY_{col}' for col in stat_columns})

    merged_stats = pd.merge(home_stats, away_stats, on='GAME_ID', suffixes=('_HOME', '_AWAY'))


    return render(request, 'game_detail.html', {
        'game_data': game_header_df.to_dict(orient="records"),
        'team_data': final_df.to_dict(orient="records"),
        'previous_matchups': merged_stats.to_dict(orient="records")
    })

