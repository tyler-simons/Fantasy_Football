import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import altair as alt
from espn_data.get_espn_data import *

st.set_page_config(
    layout="wide",
    page_title="Fantasy Football Dashboard",
)
owners = [team.owner for team in our_league.teams]
teams = [team.team_name for team in our_league.teams]
owner_names = pd.DataFrame({"owners": owners, "teams": teams})

# Top of page
st.title("Purple Drank Fantasy Scoreboard")

# Build columns

# Year select

# year_selection = st.selectbox("Select Season", options=[2021, 2020])
year_selection = 2021
st.markdown("----")

st.header(f"{year_selection} Regular Season Summary")


# Read in data
def read_fantasy_data(year):
    season_dict = {
        2020: pd.read_csv("fantasy/fantasy_data_2020.csv"),
        2021: get_2021_season_data(),  # pd.read_csv("fantasy/fantasy_data_2021.csv"),
    }
    return season_dict[year]


# Read in the data
fantasy_data = read_fantasy_data(year_selection)

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

total_wins = summary_table_agg.assign(total_wins=summary_table_agg["h2h_win"] + summary_table_agg["top6_win"]).assign(
    total_losses=lambda x: weeks_since_start_season() * 2 - x["total_wins"]
)

# Add owners names
added_owners = total_wins.merge(owner_names, left_index=True, right_on="teams")
added_owners = added_owners.set_index("owners")

top_scorer_final = added_owners.merge(summed_tops, right_index=True, left_on="teams")["top_scorer_sum"]

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
top_six_teams = fantasy_data[["team_name", "week", "top6_win"]].drop_duplicates()
t6_added_owns = top_six_teams.merge(owner_names, left_on="team_name", right_on="teams")
t6_pivot = t6_added_owns[["owners", "top6_win", "week"]].pivot("owners", "week", "top6_win")
t6_pivot = t6_pivot.loc[top_scorer_final.index]


# Style the table
def highlight_true(s):
    """
    highlight the maximum in a Series yellow.
    """
    is_true = s == True
    return [
        "background-color: darkgreen; color: darkgreen" if v else "background-color: purple; color: purple"
        for v in is_true
    ]


format_dict = {"Points For": "{:.5}"}
# styled_wins = top_scorer_final.style(format_dict)
col1, col2 = st.columns(2)

records = (
    top_scorer_final.style.bar(subset="Points For", color="darkblue")
    # .highlight_min(axis=0, color="purple", subset=["points"])
    .format(format_dict).set_caption("Records and Points")
)

with col1:
    st.table(records)
with col2:
    st.table(t6_pivot.style.apply(highlight_true).set_caption("Top 6 Scoring by Week"))


st.markdown("----")

## Team selection


with st.expander("Teams"):
    teams = fantasy_data["team_name"].drop_duplicates().tolist()
    teams.sort()
    selected_team_name = st.selectbox("Select a team", teams)

    # Header
    st.header(f"Performance by: {selected_team_name}")

    # Selected team
    selected_team = fantasy_points.query("team_name == @selected_team_name")
    st.write(
        f"Max points: \
        {selected_team[selected_team.points == selected_team.points.max()]['points'].to_string(header=False, index=False)}\
            in Week {selected_team[selected_team.points == selected_team.points.max()]['week'].to_string(header=False, index=False)}"
    )

    # Min points
    st.write(
        f"Min points: \
        {selected_team[selected_team.points == selected_team.points.min()]['points'].to_string(header=False, index=False)}\
            in Week {selected_team[selected_team.points == selected_team.points.min()]['week'].to_string(header=False, index=False)}"
    )

    # SD points
    st.write(
        f"Standard deviation in points scored: \
        {round(selected_team.points.std())}"
    )

    # Team Table
    st.header("Team Table")
    st.dataframe(selected_team[["week", "points", "opponent", "points_against", "h2h_win", "top6_win"]])

    melted_points = selected_team[["week", "points", "points_against"]].melt(
        id_vars=["week"], value_vars=["points", "points_against"]
    )

    # Right column
    tp_df = fantasy_data.query("team_name == @selected_team_name")
    tp_df.tp_points = [float(i) for i in tp_df.tp_points.to_list()]
    top_scorers = tp_df.groupby("tp_names", group_keys=False).agg("count").reset_index()

    top_scorers_plot = (
        alt.Chart(top_scorers)
        .mark_bar(size=15)
        .encode(
            x=alt.X("tp_names:O", axis=alt.Axis(title="Player", labels=True, ticks=True), sort="-y"),
            y=alt.Y("tp_points:Q", axis=alt.Axis(title="Times a top performer")),
        )
        .properties(width=800)
    )

    st.markdown("## Top performers")
    st.markdown("#### How many times each player was in the top 3 performers on the team")

    st.altair_chart(top_scorers_plot)

    # Points per week
    st.markdown("## Points per week plot")
    st.markdown("#### Points scored for (green) vs points against (orange)")
    week_plot = (
        alt.Chart(melted_points)
        .mark_bar(size=15)
        .encode(
            x=alt.X("variable:O", axis=alt.Axis(title="", labels=False, ticks=False)),
            y=alt.Y("value", axis=alt.Axis(title="Points")),
            color=alt.Color("variable:N", scale=alt.Scale(scheme="dark2")),
            tooltip=alt.Tooltip(["variable", "value"]),
            column=alt.Column(
                "week:O", title="Week", align="all", header=alt.Header(titleOrient="bottom", labelOrient="bottom")
            ),
        )
        .properties(width=40)
    )

    st.altair_chart(week_plot)
