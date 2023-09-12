import streamlit as st
import pandas as pd
import altair as alt
from espn_api.football import League
from espn_data.get_espn_data import get_season_data
import espn_data.ff_probability as ff_probability
import espn_data.build_tables as build_tables
import numpy as np
from google.cloud import storage
from google.oauth2 import service_account
import json
import io
import hashlib

st.set_page_config(
    layout="wide",
    page_title="Fantasy Football Dashboard",
)
st.title("PA Fantasy Scoreboard")
st.markdown(
    """Dashboard displaying our scores from the past few years of ESPN Fantasy Football. 
        You can see the current scoreboard, top scores per week, how unlucky you've been, and a variety of other metrics. 
        \n Each week, two points are awarded -- one for winning your matchup and one for placing Top 6 in points scored"""
)

# Season Selection
year_selection = st.selectbox(
    "Start by selecting season", options=[2019, 2020, 2021, 2022, 2023], index=4
)
year = year_selection
st.markdown("----")
st.header(f"{year_selection} Regular Season Summary")


# Read in data helper functions
def push_pull_from_gcs(
    year: int,
    gcp_json_credentials_dict: dict,
    bucket_name: str,
    pull=True,
    upload_file=None,
    push=False,
) -> pd.DataFrame:
    """Push or pull the weekly top scores data from GCS. Either put it up or pull it down."""
    credentials = service_account.Credentials.from_service_account_info(gcp_json_credentials_dict)
    client = storage.Client(credentials=credentials)
    bucket = client.bucket(bucket_name)
    source_file_name = f"fantasy_data_{year}.csv"
    blob = bucket.blob(source_file_name)
    if pull:
        data = blob.download_as_string()
        df = pd.read_csv(io.BytesIO(data))
        return df
    elif push:
        blob.upload_from_string(upload_file.to_csv(index=False), "text/csv")
        return upload_file


# Read in data from GCS
def get_fantasy_data(
    season: int, refresh=False, bucket_name="fantasy-football-palo-alto-data"
) -> pd.DataFrame:
    """Get the data from the GCS bucket. Refresh if given the arg"""
    # Try to get the data from the bucket
    gcp_json_credentials_dict = json.load(open("fantasy_profile.json", "r"))
    gcp_json_credentials_dict.update(
        {
            "private_key": st.secrets["private_key"].replace("\\n", "\n"),
            "private_key_id": st.secrets["private_key_id"],
        }
    )
    if refresh:
        league = League(
            league_id=443750, year=season, espn_s2=st.secrets["espn_s2"], swid=st.secrets["swid"]
        )
        all_data = get_season_data(season, league)
        df = push_pull_from_gcs(
            season,
            gcp_json_credentials_dict,
            bucket_name,
            upload_file=all_data,
            pull=False,
            push=True,
        )
    else:
        df = push_pull_from_gcs(season, gcp_json_credentials_dict, bucket_name, pull=True)
    return df


# Read in the data
fantasy_data = get_fantasy_data(year_selection)
our_league = League(
    league_id=st.secrets["league_id"],
    year=year_selection,
    espn_s2=st.secrets["espn_s2"],
    swid=st.secrets["swid"],
)
# Make a single table
cols_remove = ["name", "tp_names", "tp_points"]
fantasy_points = fantasy_data.drop(columns=cols_remove).drop_duplicates()
records, t6_pivot = build_tables.create_top6_and_record_table(fantasy_data)

format_dict = {"Points For": "{:.5}"}

records_final = records.style.bar(subset="Points For", color="darkblue").format(format_dict)

c1, c2 = st.columns([2, 2])
c1.subheader(f"{records_final.index[0]} is winning")
c2.subheader(f"{records_final.index[-1]} is dead last")

st.markdown("<br>Records and Total Points", unsafe_allow_html=True)
st.table(records_final)

st.markdown("----")
st.markdown("<br>Top 6 Scores per Week", unsafe_allow_html=True)
st.markdown("Won matchup scores are in green with losses in red. Top weekly score is gold. ")
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
    num_wins = (
        records["Standing"].str.extract("(^\d{,2})").astype("int").reset_index()
    )  # .reset_index()
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
        st.altair_chart(build_tables.avg_margin_chart(margins_wavier_pts), use_container_width=True)

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
                    alt.Tooltip(
                        "average_waiver_points", format=".2f", title="Avg. points from waivers"
                    ),
                ],
            ),
            use_container_width=True,
        )

with st.expander("Teams"):
    teams = fantasy_data["team_name"].drop_duplicates().tolist()
    teams.sort()
    selected_team_name = st.selectbox("Select a team", teams)

    # Header
    st.header(f"Performance by: {selected_team_name}")

    # Selected team
    selected_team = fantasy_points.query("team_name == @selected_team_name")
    selected_team["points"] = selected_team["points"].round(2)
    selected_team["points_against"] = selected_team["points_against"].round(2)
    max_points, min_points = selected_team["points"].max(), selected_team["points"].min()
    avg_points = selected_team["points"].mean()

    a, b, c = st.columns(3)

    a.metric("Max points (up from average)", max_points, np.round(max_points - avg_points, 2))
    b.metric("Min points (down from average)", min_points, np.round(min_points - avg_points, 2))
    if len(selected_team.points) > 1:
        c.metric("Standard deviation of points", round(selected_team.points.std()))

    # Team Table
    st.markdown("## Team Table")
    st.dataframe(
        selected_team[
            ["week", "points", "opponent", "points_against", "h2h_win", "top6_win"]
        ].rename(
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
                x=alt.X(
                    "tp_names", axis=alt.Axis(title="Player", labels=True, ticks=True), sort="-y"
                ),
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

with st.form("refresh"):
    refresh_password = st.text_input("Refresh data code", type="password")
    # You found me! Now enter the truth...
    # This is obviously not best practice in production and I would use a salted hash system
    # for any kind of passwords
    if refresh_password == "tyler rules":
        st.success("Correct password...updating data")
        get_fantasy_data(year_selection, refresh=True)
        st.success("Data uploaded for this week")
    elif refresh_password:
        st.error("Wrong Password")
    st.form_submit_button("Submit")
