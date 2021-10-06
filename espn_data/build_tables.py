import pandas as pd
from .get_espn_data import weeks_since_start_season
from datetime import datetime
import streamlit as st
import altair as alt
import pickle
import json
from google.cloud import storage
from google.oauth2 import service_account


# Style the table
def highlight_true(s):
    """
    highlight the maximum in a Series yellow.
    """

    final_format = []
    for v in s:
        if v == s.max():
            final_format.append("background-color: gold; color: black")
        elif v > s.median():
            final_format.append("background-color: darkgreen; color: white")
        # elif v == s.min():
        #     final_format.append("background-color: saddlebrown; color: white")
        else:
            final_format.append("background-color: tomato; color: black")
    return final_format


def format_2_dec(x):
    return {col: "{:,.2}".format for col in x.columns}


def create_top6_and_record_table(fantasy_data):
    """Build the scoreboard starting from raw fantasy data"""

    # Top points per week
    top_scorers = fantasy_data.iloc[fantasy_data.reset_index().groupby(["week"])["points"].idxmax(), :]
    summed_tops = top_scorers.groupby("team_name").count()["week"]
    summed_tops = summed_tops.rename("top_scorer_sum")

    # Make a single table
    cols_remove = ["name", "tp_names", "tp_points"]
    fantasy_points = fantasy_data.drop(columns=cols_remove).drop_duplicates()

    # Scoreboard Table
    summary_table_agg = (
        fantasy_points[["team_name", "points", "points_against", "h2h_win", "top6_win"]]
        .groupby("team_name", group_keys=False)
        .agg("sum")
        .round(2)
    )

    total_wins = summary_table_agg.assign(
        total_wins=summary_table_agg["h2h_win"] + summary_table_agg["top6_win"]
    ).assign(total_losses=lambda x: fantasy_points["week"].max() * 2 - x["total_wins"])

    # Add owners names
    added_owners = total_wins
    top_scorer_final = added_owners.merge(summed_tops, right_index=True, left_index=True)["top_scorer_sum"]

    # Create the records
    added_owners["record"] = [
        f"{i}-{j}" for i, j in zip(added_owners.total_wins.to_list(), added_owners.total_losses.to_list())
    ]
    added_owners = added_owners.sort_values(["total_wins", "points"], ascending=False)
    sub_owners = added_owners[["record", "points"]]

    # Add the times top scorer
    top_scorer_final = sub_owners.merge(top_scorer_final, how="left", left_index=True, right_index=True).fillna(0)
    top_scorer_final["top_scorer_sum"] = top_scorer_final["top_scorer_sum"].astype("int")
    top_scorer_final.rename(
        columns={"record": "Standing", "points": "Points For", "top_scorer_sum": "# Times Top Scorer"}, inplace=True
    )
    # Top 6 table
    t6_pivot = (
        fantasy_points.pivot("team_name", "week", "points")
        .loc[top_scorer_final.index]
        .style.apply(highlight_true)
        .format("{:.5}")
    )

    return top_scorer_final, t6_pivot


def player_df_from_line(lineup, first_matchup, week, home_team):
    """Given a played lineup, return the player information"""
    team_info_list = []
    for player in lineup:
        player_info_list = []

        # Set team name
        if home_team:
            player_info_list.append(first_matchup.home_team.owner)
        else:
            player_info_list.append(first_matchup.away_team.owner)

        # Set player info
        player_info_list.append(week)
        player_info_list.append(player.name)
        player_info_list.append(player.position)
        player_info_list.append(player.slot_position)
        player_info_list.append(player.projected_points)
        player_info_list.append(player.points)

        if home_team:
            player_info_list.append(first_matchup.away_team.owner)
        else:
            player_info_list.append(first_matchup.home_team.owner)

        team_info_list.append(player_info_list)

    player_df_single_week = pd.DataFrame(team_info_list)
    player_df_cols = [
        "team_name",
        "week",
        "player_name",
        "player_pos",
        "player_slot",
        "player_proj_points",
        "player_points",
        "opponent",
    ]
    player_df_single_week.columns = player_df_cols
    sorted_players = player_df_single_week.sort_values("player_points", ascending=False).reset_index(drop=True)

    return sorted_players


# Calcualte the maximum points given the following allowed positions


def position_sorter(column):
    """Custom Sort function to put them in the way ESPN displays them"""
    positions = ["QB", "RB", "WR", "TE", "FLEX", "D/ST"]
    correspondence = {team: order for order, team in enumerate(positions)}
    return column.map(correspondence)


def add_ideal_to_player_df(player_df):
    """Add a tag to the player to determine if they were an ideal pick for that week"""
    positions = ["QB", "RB1", "RB2", "WR1", "WR2", "TE", "FLEX", "D/ST"]
    ordered_played = player_df.iterrows()

    found_positions = []
    for i, pos in ordered_played:
        for set_pos in positions:
            if pos.player_pos in set_pos:
                found_positions.append(pos)
                positions.remove(set_pos)
                break
            elif set_pos == "FLEX" and pos.player_pos in ["WR", "RB", "TE"]:
                found_positions.append(pos)
                positions.remove(set_pos)
                break

    ideal_lineup = pd.concat(found_positions, axis=1).transpose().sort_values(by="player_pos", key=position_sorter)
    ideal_lineup["ideal_player"] = True
    comb_player_ideal = player_df.merge(ideal_lineup[["team_name", "player_name", "ideal_player"]], how="left").fillna(
        False
    )
    comb_player_ideal["played"] = comb_player_ideal.player_slot != "BE"
    return comb_player_ideal


def build_matchup_player_dfs(matchup, week):
    """Create a dataframe that contains all the players and their ideal status for each matchup"""

    home_lineup = matchup.home_lineup
    away_lineup = matchup.away_lineup

    home_player_df = player_df_from_line(home_lineup, matchup, week, True)
    away_player_df = player_df_from_line(away_lineup, matchup, week, False)

    home_player_added_ideals = add_ideal_to_player_df(home_player_df)
    away_player_added_ideals = add_ideal_to_player_df(away_player_df)

    combined_set = pd.concat([home_player_added_ideals, away_player_added_ideals])
    return combined_set


## Build the player DF
def build_full_player_df(our_league):
    """Build a dataframe of teams and player information on each team"""
    full_player_df = []
    for week in range(1, weeks_since_start_season() + 1):
        matchups = our_league.box_scores(week)
        for match in matchups:
            full_player_df.append(build_matchup_player_dfs(match, week))

    return pd.concat(full_player_df)


@st.experimental_memo(ttl=50000)
def get_waiver_data(year, bucket_name="fantasy-football-palo-alto-data"):
    """Get the waiver dictionary from GCP"""
    # Set GCP creds
    gcp_json_credentials_dict = json.load(open("fantasy_profile.json", "r"))
    gcp_json_credentials_dict.update(
        {"private_key": st.secrets["private_key"].replace("\\n", "\n"), "private_key_id": st.secrets["private_key_id"]}
    )
    credentials = service_account.Credentials.from_service_account_info(gcp_json_credentials_dict)
    storage_client = storage.Client(credentials=credentials)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"wd_{year}.pickle")
    pickle_in = blob.download_as_string()
    my_dictionary = pickle.loads(pickle_in)

    return my_dictionary


def waiver_table(league):
    """Create a table of teams, transaction, and player_names"""
    activities = get_waiver_data(league.year)
    fa_adds = []
    for activity in activities:
        row = []
        transaction_date = datetime.fromtimestamp(activity.date / 1000).strftime("%Y-%m-%d %H:%M:%S.%f")
        for step in activity.actions:
            if "FA ADDED" in step or "WAIVER ADDED" in step:
                row.append(transaction_date)
                row.append(step[0].owner)
                row.append(step[1])
                row.append(step[2].name)
                fa_adds.append(row)

    return pd.DataFrame(fa_adds, columns=["date", "team_name", "action", "player_name"])


# Average waiver points by team
def calc_avg_waiver_points_by_team(our_league):
    """Create a dataframe of team_name and average points for waiver addition"""
    full_player_table = build_full_player_df(our_league)
    transaction_table = waiver_table(our_league)

    full_player_df_waivers = full_player_table.merge(
        transaction_table[["team_name", "player_name", "action"]], how="left"
    ).fillna("DRAFTED")

    avg_waiver_points = (
        full_player_df_waivers.query('(action == "WAIVER ADDED" | action == "FA ADDED") & played == True')
        .groupby(["team_name"], as_index=False)
        .mean()[["team_name", "player_points"]]
    )
    avg_waiver_points = avg_waiver_points.rename(columns={"player_points": "average_waiver_points"}).fillna(0)
    return avg_waiver_points


# Calculate win vs loss point differential
def win_loss_marings(ffdata):
    """Create a dataframe of team, avg win margin, and avg loss margin"""
    ffdata["point_diff"] = ffdata.points - ffdata.points_against
    win_loss_diff_table = ffdata.groupby(["team_name", "h2h_win"], as_index=False)["point_diff"].mean()
    win_loss_pivot = win_loss_diff_table.pivot("team_name", "h2h_win", "point_diff").fillna(0)
    win_loss_pivot = win_loss_pivot.reset_index().rename_axis(None, axis=1)
    win_loss_pivot.columns = ["team_name", "avg_margin_of_loss", "avg_margin_of_victory"]
    return win_loss_pivot


# Joined teams, margins, and waiver points
def calc_margins_waivers(fantasy_data, our_league):
    """Create a dataframe of teams, avg_loss_margin, avg_waiver_points"""
    win_loss_pivot = win_loss_marings(fantasy_data)
    avg_waiver_points = calc_avg_waiver_points_by_team(our_league)
    combined = win_loss_pivot.merge(avg_waiver_points, how="outer")
    for col in ["avg_margin_of_loss", "avg_margin_of_victory", "average_waiver_points"]:
        combined[col] = pd.to_numeric(combined[col])
    return combined


def avg_margin_chart(margins_wavier_pts):
    """Make a chart for the average margin of victory or loss"""
    loss_points = (
        alt.Chart(margins_wavier_pts)
        .mark_point(filled=True, size=50, color="tomato")
        .encode(
            y=alt.Y("team_name", title="Team Name"),
            x=alt.X("avg_margin_of_loss", title="Avg. Margin of Victory/Loss"),
            tooltip=[
                alt.Tooltip("team_name", title="Team Name"),
                alt.Tooltip("avg_margin_of_loss", title="Avg. Margin of Loss", format=".2f"),
            ],
        )
    )
    win_points = (
        alt.Chart(margins_wavier_pts)
        .mark_point(filled=True, size=50, color="lime")
        .encode(
            y=alt.Y("team_name", title=""),
            x=alt.X("avg_margin_of_victory", title=""),
            tooltip=[
                alt.Tooltip("team_name", title="Team Name"),
                alt.Tooltip("avg_margin_of_victory", title="Avg. Margin of Victory", format=".2f"),
            ],
        )
    )
    return loss_points + win_points
