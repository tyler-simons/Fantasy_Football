from altair.vegalite.v4.schema.core import Legend
import streamlit as st
import pandas as pd
import numpy as np
import time
import altair as alt


# Read in data
def read_fantasy_data():
    return pd.read_csv("fantasty/fantasy_data_2020.csv")

fantasy_data = read_fantasy_data()

# Make a single table
cols_remove = ["name", "tp_names", "tp_points"]
fantasy_points = fantasy_data.drop(columns = cols_remove).drop_duplicates()


# Top of page
st.title("Purple Drank Season 12")

st.header("2020 Regular Season Summary")

# Summary Table
summary_table_agg = fantasy_points[['team_name', 'points', 'points_against', 'h2h_win', 'top6_win']].\
    groupby('team_name', group_keys=False).agg('sum')
total_wins = summary_table_agg.\
    assign(total_wins = summary_table_agg['h2h_win'] + summary_table_agg['top6_win']).\
    assign(total_losses = lambda x: 26 - x['total_wins'] )    
st.write(total_wins)


st.markdown("----")

## Team selection


st.title("Select a team")
teams = fantasy_data['team_name'].drop_duplicates().tolist()
teams.sort()
selected_team_name = st.selectbox("Select a team", teams)



# Header
st.header(f"Performance by: {selected_team_name}")


# Selected team
selected_team = fantasy_points.query('team_name == @selected_team_name')
st.write(f"Max points: \
    {selected_team[selected_team.points == selected_team.points.max()]['points'].to_string(header=False, index=False)}\
        in Week {selected_team[selected_team.points == selected_team.points.max()]['week'].to_string(header=False, index=False)}")

# Min points
st.write(f"Min points: \
    {selected_team[selected_team.points == selected_team.points.min()]['points'].to_string(header=False, index=False)}\
        in Week {selected_team[selected_team.points == selected_team.points.min()]['week'].to_string(header=False, index=False)}")

# SD points
st.write(f"Standard deviation in points scored: \
    {round(selected_team.points.std())}")


# Team Table
st.header("Team Table")
st.dataframe(selected_team[['week', 'points', 'opponent', 'points_against', 'h2h_win', 'top6_win']])

melted_points = selected_team[['week', 'points', 'points_against']].\
    melt(id_vars = ['week'], value_vars=['points', 'points_against'])


# Points per week
st.markdown("## Points per week plot")
st.markdown("#### Points scored for (green) vs points against (orange)")
week_plot = alt.Chart(melted_points).\
    mark_bar(size=15).\
    encode(
        x=alt.X('variable:O', axis=alt.Axis(title="", labels=False, ticks=False)), 
        y = alt.Y('value', axis = alt.Axis(title="Points")), 
        color = alt.Color('variable:N', scale=alt.Scale(scheme='dark2')),
        tooltip = alt.Tooltip(['variable', 'value']),
        column=alt.Column("week:O", title = "Week", align='all', header=alt.Header(titleOrient="bottom", labelOrient='bottom'))).\
    properties(
        width = 40
    )

st.altair_chart(week_plot)

# Right column
tp_df = fantasy_data.query("team_name == @selected_team_name")
tp_df.tp_points = [float(i) for i in tp_df.tp_points.to_list()]
top_scorers = tp_df.groupby('tp_names', group_keys=False).agg('count').reset_index()

top_scorers_plot = alt.Chart(top_scorers).\
    mark_bar(size=15).\
    encode(
        x=alt.X('tp_names:O', axis=alt.Axis(title="Player", labels=True, ticks=True), sort = '-y'), 
        y = alt.Y('tp_points:Q', axis = alt.Axis(title="Times a top performer"))).\
    properties(width =800)

st.markdown("## Top performers")
st.markdown("#### How many times each player was in the top 3 performers on the team")

st.altair_chart(top_scorers_plot)