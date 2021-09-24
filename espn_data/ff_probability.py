import pandas as pd
import random
import numpy as np


def split(df, col):
    return [x for _, x in df.groupby(col)]


def create_top6_dict(ffdata):
    """Create a dictionary of team names and if they scored in the top 6"""
    top6_wins = ffdata[["team_name", "week", "top6_win"]].drop_duplicates()
    top6_wins.top6_win = top6_wins.top6_win.astype("int")
    top6_split = split(top6_wins, "team_name")

    top6_dict = {}
    for i in top6_split:
        top6_dict.update({i.team_name.unique()[0]: list(i.top6_win.values)})
    return top6_dict


def create_team_dict(raw_scores):
    """Create dictionary of team names and their scores"""
    team_scores = split(raw_scores, "team_name")
    team_dict = {}
    for i in team_scores:
        team_name = i.team_name.drop_duplicates().values[0]
        team_dict.update({team_name: i.points.values})
    return team_dict


def simulate_season(team_name, team_dict, top6_dict):
    """10,000 simulations of random opponents to see how many wins you'd get in the season"""
    opponents = [i for i in list(team_dict.keys()) if i != team_name]
    # Randomize order of opponents

    # Get maximum number of games so far
    games_count = len(team_dict[team_name])

    all_wins = []
    for i in range(10000):
        new_order = random.sample(opponents, games_count)
        wins = 0
        for j, opp in enumerate(new_order):
            my_points = team_dict[team_name][j]
            opp_points = team_dict[opp][j]
            if my_points > opp_points:
                wins += 1
            wins += top6_dict[team_name][j]
        all_wins.append(wins)
    return all_wins


def build_probability_distribution(ffdata):
    """Simulate the seasons for all of the teams"""
    raw_scores = ffdata[["team_name", "week", "points"]].drop_duplicates()

    team_dict = create_team_dict(raw_scores)
    top6_dict = create_top6_dict(ffdata)
    all_team_names = sorted(list(set(raw_scores.team_name.values)))
    simulated_wins = []
    for name in all_team_names:
        total_wins = pd.Series(simulate_season(name, team_dict, top6_dict))
        total_wins = total_wins.rename(name)
        simulated_wins.append(total_wins.value_counts() / total_wins.value_counts().sum())

    return pd.concat(simulated_wins, axis=1).fillna(0)
