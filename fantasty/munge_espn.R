library(tidyverse)
library(readxl)

# Data Processing Script

# Read in data
season12_scores <- read_excel("season12_scores.xlsx")

# Function to process a single game
build_tib <- function(matchup)
{game_pair <- matchup
team_names <- c(game_pair[1], game_pair[4])
week <- 1
points <- c(game_pair[3], game_pair[6])
top_performers_1 <- c(game_pair[8], game_pair[12])
top_performers_2 <- c(game_pair[9], game_pair[13])
top_performers_3 <- c(game_pair[10], game_pair[14])
win = as.numeric(as.numeric(points)[1] > as.numeric(points)[2])

make_tib <- tibble(team_name = team_names,
                   week = week,
                   points = points,
                   tp1 = top_performers_1,
                   tp2 = top_performers_2,
                   tp3 = top_performers_3,
                   opponent = rev(team_names),
                   h2h_win = c(win, !win),
                   points_against = rev(points)) %>% 
  pivot_longer(cols = -c(team_name, week, points, opponent, h2h_win, points_against)) %>%
  mutate(tp_names = str_extract(value, "^([A-Za-z\\. ])+"),
         tp_points = str_extract(value, "[0-9.]{2,5}")) %>%
  mutate(tp_points = as.numeric(str_remove(tp_points, "^\\.+"))) %>%
  select(team_name, week, points, name, tp_names, tp_points, opponent, h2h_win, points_against)

return(make_tib)
}

# Function to process a single week
melt_week <- function(single_week_raw){
  week_vec <- single_week_raw
  split_list <- split(week_vec, ceiling(seq_along(week_vec)/14))
  single_week <- split_list %>% map(~(.) %>% build_tib()) %>% bind_rows()
  top_6_wins <- single_week %>% select(team_name, points) %>% distinct() %>% 
    mutate(points = as.numeric(points)) %>% arrange(desc(points)) %>%
    mutate(top6_win = c(rep(TRUE, nrow(.)/2), rep(FALSE, nrow(.)/2))) %>%
    select(-points)
  final_week <- single_week %>% left_join(top_6_wins, by = "team_name")
  return(single_week)
}

# Map to entire dataset
season_12_data <- season12_scores %>% map(~(.) %>% melt_week()) %>% bind_rows() %>%
  mutate(week = rep(1:13, each = 36))

# Write out CSV
season_12_data %>% write_csv("./fantasy_data_2020.csv")

