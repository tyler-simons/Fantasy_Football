from espn_api.football import League
import pickle
import streamlit as st
from espn_data.get_espn_data import get_season_data
from google.cloud import storage
import pandas as pd
import gcsfs
import logging
import os

# Only need this if you're running this code locally.
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"/your_GCP_creds/credentials.json"


def save_season_data(request):
    """Save the data for 2021 on GCP"""

    for year in [2025]:
        BUCKET_NAME = "fantasy-football-palo-alto-data"
        PROJECT_NAME = "fantasy-football-palo-alto"

        # Initalize league
        our_league = League(
            league_id=os.environ.get("league_id"),
            year=year,
            espn_s2=os.environ.get("espn_s2"),
            swid=os.environ.get("swid"),
        )
        logging.info("League connected")

        # Download data
        season_data_2021 = get_season_data(year, our_league)
        logging.info("Data downloaded")

        # Connect to the client
        client = storage.Client()
        bucket = client.get_bucket(BUCKET_NAME)

        # Save the data
        bucket.blob(f"fantasy_data_{year}.csv").upload_from_string(
            season_data_2021.to_csv(index=False), "text/csv"
        )
        logging.info("Data saved to GCS")

        # Download the waiver data
        ra = our_league.recent_activity(2000)
        fs = gcsfs.GCSFileSystem(project=PROJECT_NAME)

        logging.info("Waiver data downloaded")

        filename = f"{BUCKET_NAME}/wd_{year}.pickle"
        with fs.open(filename, "wb") as handle:
            pickle.dump(ra, handle, protocol=pickle.HIGHEST_PROTOCOL)
        logging.info("Waiver data saved")

    return "Finished"
