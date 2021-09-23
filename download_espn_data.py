import pandas as pd
from espn_data.get_espn_data import get_2021_season_data

all_data = get_2021_season_data()

all_data.to_csv("./fantasy/fantasy_data_2021.csv", index=False)
