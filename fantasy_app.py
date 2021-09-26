import streamlit as st
import pandas as pd
import altair as alt
from espn_data.get_espn_data import *
from espn_data import ff_probability
from espn_data.build_tables import *

st.set_page_config(
    layout="wide",
    page_title="Fantasy Football Dashboard",
)
st.title("Purple Drank Fantasy Scoreboard")

# year_selection = st.selectbox("Select Season", options=[2021, 2020])
year_selection = 2021
st.markdown("----")
st.header(f"{year_selection} Regular Season Summary")


# Read in data
def read_fantasy_data(year):
    season_dict = {
        2020: pd.read_csv("fantasy/fantasy_data_2020.csv"),
        2021: pd.read_csv("fantasy/fantasy_data_2021.csv"),
    }
    return season_dict[year]


# Read in the data
fantasy_data = read_fantasy_data(year_selection)

# Make a single table
cols_remove = ["name", "tp_names", "tp_points"]
fantasy_points = fantasy_data.drop(columns=cols_remove).drop_duplicates()

records, t6_pivot = create_top6_and_record_table(fantasy_data)


col1, col2 = st.columns(2)

with col1:
    st.table(records)
with col2:
    st.table(t6_pivot.style.apply(highlight_true).set_caption("Top 6 Scoring by Week"))


st.markdown("----")

## Team selection

with st.expander("Matchup Luck"):
    liklihood_table = (
        ff_probability.build_probability_distribution(fantasy_data)
        .sort_index(ascending=False)
        .cumsum(axis=0)
        .sort_index(ascending=True)
    )
    format_dict = {col: "{:,.1%}".format for col in liklihood_table.columns}

    st.markdown("# How lucky have your matchups been?")
    st.markdown("We simulated 10,000 seasons with a random order of Head to Head matchups")
    st.markdown(
        "This table shows the cumulative probability that each team will have at least X wins thus far in the season. If you have MORE wins than the 50% line, you are lucky. "
    )

    st.table(
        liklihood_table.style.bar(color="darkblue")
        .format(format_dict)
        .set_caption("Likelihood for having at least X wins so far")
    )
with st.expander("Margin of Victory/Loss + Waiver Points"):
    col1_m, col2_m = st.columns(2)
    with col1_m:
        st.markdown("## Average margin of loss or victory")
        st.markdown("By how much did each team win or lose?")

        margins_wavier_pts = calc_margins_waivers(fantasy_data, our_league)
        st.altair_chart(avg_margin_chart(margins_wavier_pts))

    with col2_m:
        st.markdown("## Average points from waiver pickups")
        st.markdown("By how much did each team benefit from their additions?")
        st.altair_chart(
            alt.Chart(margins_wavier_pts.fillna(0))
            .mark_bar(filled=True, color="darkblue", xOffset=1)
            .encode(
                y=alt.Y("team_name", title="Team Name", sort="-x"),
                x=alt.X("average_waiver_points", title="Avg. points added via waivers"),
                tooltip=[
                    alt.Tooltip("team_name", title="Team Name"),
                    alt.Tooltip("average_waiver_points", format=".2f", title="Avg. points added via waivers"),
                ],
            )
        )

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
