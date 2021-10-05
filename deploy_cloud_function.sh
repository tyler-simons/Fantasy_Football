#!/bin/bash
gcloud config set project fantasy-football-palo-alto 
gcloud config set compute/zone us-west2-a


gcloud functions deploy get_fantasy_data --entry-point save_season_data --runtime python38 --trigger-http --allow-unauthenticated --env-vars-file .env_vars.yaml --memory=2048MB --timeout=540s

gcloud scheduler jobs create http download_fantasy_data --schedule "30 23 * * 1" --uri "https://us-central1-fantasy-football-palo-alto.cloudfunctions.net/get_fantasy_data"