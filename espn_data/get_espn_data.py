from logging import debug
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st
from espn_api.football import League


def box_score_to_csv(box_match, week, year, our_league):
    our_league.refresh()
    box_match_1 = box_match
    name = ["tp1", "tp2", "tp3"]
    week_scores = our_league.box_scores(week)

    # Home team
    home_points = box_match_1.home_score
    home_team_name = (
        box_match_1.home_team.owners[0]["firstName"]
        + " "
        + box_match_1.home_team.owners[0]["lastName"]
    )

    home_player_points = []
    for player in box_match_1.home_lineup:
        home_player_points.append([player.name, player.points])
    player_df = pd.DataFrame(home_player_points, columns=["player", "points"]).sort_values(
        "points", ascending=False
    )
    home_top_3_players = player_df.head(3).player.to_list()
    home_top_3_player_points = player_df.head(3).points.to_list()

    # Away team
    away_points = box_match_1.away_score
    away_team_name = (
        box_match_1.away_team.owners[0]["firstName"]
        + " "
        + box_match_1.away_team.owners[0]["lastName"]
    )

    away_player_points = []
    for player in box_match_1.away_lineup:
        away_player_points.append([player.name, player.points])
    player_df = pd.DataFrame(away_player_points, columns=["player", "points"]).sort_values(
        "points", ascending=False
    )
    away_top_3_players = player_df.head(3).player.to_list()
    away_top_3_player_points = player_df.head(3).points.to_list()

    home_h2h_win = home_points > away_points
    away_h2h_win = home_points < away_points

    # Top 6 scores
    weekly_scores = []
    for match in week_scores:
        weekly_scores.extend([match.home_score, match.away_score])
    weekly_scores = np.array(weekly_scores)
    weekly_scores.sort()

    home_top6_win = home_points >= weekly_scores[-6]
    away_top6_win = away_points >= weekly_scores[-6]

    # Create the DF
    team_data = [
        [home_team_name] * 3 + [away_team_name] * 3,
        [week] * 6,
        [home_points] * 3 + [away_points] * 3,
        name + name,
        home_top_3_players + away_top_3_players,
        home_top_3_player_points + away_top_3_player_points,
        [away_team_name] * 3 + [home_team_name] * 3,
        [home_h2h_win] * 3 + [away_h2h_win] * 3,
        [away_points] * 3 + [home_points] * 3,
        [bool(home_top6_win)] * 3 + [bool(away_top6_win)] * 3,
        [year] * 6,
    ]
    # Columns
    team_cols = [
        "team_name",
        "week",
        "points",
        "name",
        "tp_names",
        "tp_points",
        "opponent",
        "h2h_win",
        "points_against",
        "top6_win",
        "year",
    ]
    team_dict = {key: value for key, value in zip(team_cols, team_data)}
    return pd.DataFrame(team_dict)


def full_week_data(week, year, league):
    match_data = []
    week_scores = league.box_scores(week)

    for match in week_scores:
        match_data.append(box_score_to_csv(match, week, year, league))
    combined_matches = pd.concat(match_data)
    return combined_matches


def weeks_since_start_season():
    d1 = datetime(2022, 9, 6)
    d2 = datetime.now()

    total_diff = d2 - d1
    return total_diff.days // 7


def get_season_data(year, league):
    our_league = league

    total_weeks = 14

    all_data = []
    for i in range(1, total_weeks + 1):
        weekly_data = full_week_data(i, year, our_league)
        print(i)
        if len(all_data) > 0:
            if (
                weekly_data.points_against.sum() == 0
                or weekly_data.points_against.sum() == all_data[-1].points_against.sum()
            ):
                break
            else:
                all_data.append(weekly_data)

        else:
            all_data.append(weekly_data)

    season_data = pd.concat(all_data).query("points_against > 1")
    return season_data
