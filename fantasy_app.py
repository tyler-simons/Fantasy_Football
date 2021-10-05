import streamlit as st
import pandas as pd
import altair as alt
from espn_api.football import League
import espn_data.ff_probability as ff_probability
import espn_data.build_tables as build_tables
import os
from google.cloud import storage

st.set_page_config(
    layout="wide",
    page_title="Fantasy Football Dashboard",
)
st.title("Purple Drank Fantasy Scoreboard")
os.environ["GOOGLE_ACCOUNT_CREDENTIALS"] = st.secrets["GOOGLE_ACCOUNT_CREDENTIALS"]

year_selection = st.selectbox("Select Season", options=[2019, 2020, 2021], index=2)
year = year_selection
st.markdown("----")
st.header(f"{year_selection} Regular Season Summary")


# Read in data
# Get updated 2021 data


@st.experimental_memo(max_entries=1)
def get_2021_data():
    client = storage.Client()
    season_2021 = pd.read_csv("gs://fantasy-football-palo-alto-data/fantasy_data_2021.csv", encoding="utf-8")
    return season_2021


season_dict = {
    "2019": pd.read_csv("fantasy/fantasy_data_2019.csv"),
    "2020": pd.read_csv("fantasy/fantasy_data_2020.csv"),
    "2021": get_2021_data(),
}
# return season_dict[year]


# Read in the data
fantasy_data = season_dict[str(year_selection)]
our_league = League(
    league_id=st.secrets["league_id"], year=year_selection, espn_s2=st.secrets["espn_s2"], swid=st.secrets["swid"]
)
# Make a single table
cols_remove = ["name", "tp_names", "tp_points"]
fantasy_points = fantasy_data.drop(columns=cols_remove).drop_duplicates()

records, t6_pivot = build_tables.create_top6_and_record_table(fantasy_data)

format_dict = {"Points For": "{:.5}"}

records_final = records.style.bar(subset="Points For", color="darkblue").format(format_dict)


st.markdown("<br>Records and Total Points", unsafe_allow_html=True)
st.table(records_final)

st.markdown("----")
st.markdown("<br>Top 6 Scores per Week", unsafe_allow_html=True)
st.table(t6_pivot)


st.markdown("----")

## Team selection

with st.expander("Matchup Luck"):
    liklihood_table = (
        ff_probability.build_probability_distribution(fantasy_data)
        .sort_index(ascending=False)
        .cumsum(axis=0)
        .sort_index(ascending=True)
    )

    st.markdown("# How lucky have your matchups been?")
    st.markdown("We simulated 10,000 seasons with a random order of Head to Head matchups")
    st.markdown(
        "This table shows the cumulative probability that each team will have at least X wins thus far in the season. If your true number of wins is below 50%, you are lucky. <br> <span style='color:red'>Red</span> text denotes true number of wins",
        unsafe_allow_html=True,
    )

    # Select the liklihood wins
    num_wins = records["Standing"].str.extract("(^\d{,2})").astype("int").reset_index()  # .reset_index()
    num_wins.columns = ["team_name", "wins"]
    # Issue with the column names in the num wins section
    # print(num_wins)
    num_wins = list(zip(num_wins.team_name, num_wins.wins))
    # Color a cell if it the right number of wins
    def style_specific_cell(x, wins):

        color = "color: red"
        df1 = pd.DataFrame("", index=x.index, columns=x.columns)

        for row in wins:
            df1.loc[row[1], row[0]] = color
        return df1

    format_dict = {col: "{:,.1%}".format for col in liklihood_table.columns}
    formatted_liklihood = (
        liklihood_table.style.bar(color="darkblue")
        .format(format_dict)
        .apply(style_specific_cell, wins=num_wins, axis=None)
        .set_caption("Likelihood for having at least X wins so far")
    )
    st.table(formatted_liklihood)
with st.expander("Margin of Victory/Loss + Waiver Points"):
    col1_m, col2_m = st.columns(2)
    with col1_m:
        st.markdown("## Average margin of loss or victory")
        st.markdown("By how much did each team win or lose?")

        margins_wavier_pts = build_tables.calc_margins_waivers(fantasy_data, our_league)
        st.altair_chart(build_tables.avg_margin_chart(margins_wavier_pts))

    with col2_m:
        st.markdown("## Average points from waiver pickups")
        st.markdown("By how much did each team benefit from their additions?")
        st.altair_chart(
            alt.Chart(margins_wavier_pts.fillna(0))
            .mark_bar(filled=True, color="cyan", xOffset=1)
            .encode(
                y=alt.Y("team_name", title="Team Name", sort="-x"),
                x=alt.X("average_waiver_points", title="Avg. points added via waivers"),
                tooltip=[
                    alt.Tooltip("team_name", title="Team Name"),
                    alt.Tooltip("average_waiver_points", format=".2f", title="Avg. points from waivers"),
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
    st.markdown("## Team Table")
    st.dataframe(
        selected_team[["week", "points", "opponent", "points_against", "h2h_win", "top6_win"]].rename(
            columns={
                "week": "Week",
                "points": "Points For",
                "opponent": "Opponent Name",
                "points_against": "Points Against",
                "h2h_win": "Head2Head Win",
                "top6_win": "Top 6 Win",
            }
        )
    )

    melted_points = selected_team[["week", "points", "points_against"]].melt(
        id_vars=["week"], value_vars=["points", "points_against"]
    )

    team_col1, team_col2 = st.columns(2)
    # Right column
    with team_col1:
        tp_df = fantasy_data.query("team_name == @selected_team_name")
        tp_df.tp_points = [float(i) for i in tp_df.tp_points.to_list()]
        top_scorers = tp_df.groupby("tp_names", group_keys=False).agg("count").reset_index()

        top_scorers_plot = (
            alt.Chart(top_scorers)
            .mark_bar(size=15)
            .encode(
                x=alt.X("tp_names", axis=alt.Axis(title="Player", labels=True, ticks=True), sort="-y"),
                y=alt.Y(
                    "tp_points:Q",
                    axis=alt.Axis(title="Times a top performer"),
                ),
            )
            .properties(width=400, height=400)
        )

        st.markdown("## Top performers")
        st.markdown("#### How many times each player was in the top 3 performers on the team")

        st.altair_chart(top_scorers_plot)

    # Points per week
    # with team_col2:
    #     st.markdown("## Points per week plot")
    #     st.markdown("#### Points scored for (green) vs points against (orange)")
    #     st.dataframe(melted_points)
    #     week_plot = (
    #         alt.Chart(melted_points)
    #         .mark_bar(size=15)
    #         .encode(
    #             x=alt.X("variable:O", axis=alt.Axis(title="Week", labels=True, ticks=False)),
    #             y=alt.Y("value", axis=alt.Axis(title="Points")),
    #             color=alt.Color("variable:N", scale=alt.Scale(scheme="dark2"), title="Points"),
    #             column=alt.Column(
    #                 "week:O", title="Week", align="all", header=alt.Header(titleOrient="bottom", labelOrient="bottom")
    #             ),
    #         )
    #         .properties(width=100, height=300)
    #     )

    #     st.altair_chart(week_plot)
