import os
import shutil
import json
import requests
import time
import math
import datetime
import random
import statistics
import re
import sys

from collections import defaultdict
from zoneinfo import ZoneInfo

from gamer import Gamer
import synergies

from config import base_api, base_api_v2, headers, current_season, profile_dir, rate_limiter, time_zone, role_lock, gamer_card_hero_count
from config import TOAST_MESSAGES, ROAST_MESSAGES, NEUTRAL_MESSAGES, BELOW_MESSAGES, ABOVE_MESSAGES, CATEGORY_MAX_POINTS
from config import MAX_STAT_VALUES, MAX_STEPS, STAR_ICONS, performances, matchup_threshold, MAX_STAT_VALUES, ROLE_SCORING_CATEGORIES
from config import player_max_score, ai_enabled, minimum_time_played_to_count_match, stack_score_count, Bcol, match_limit, game_mode
from config import gamerlist, gamerlist_bronze, average_match_time, squadname, API_RETRIES, RETRY_DELAY_SECONDS


class Gamer_master():

	def __init__(self, gamerlist, game_nights_folder="./game_nights/"):
		self.gamers = []
		for nickname in gamerlist:
			g = Gamer(nickname)
			self.gamers.append(g)
		self.get_comp_heroes()
		self.load_and_sort_recent_match_data()
		self.get_latest_match_night()
		self.get_hero_matches()
		self.get_hero_stats()
		self.game_nights_folder = game_nights_folder


	def initiate(self):
		self.calculate_hero_scores()
		self.calculate_scores()
		self.export_data_objects()
		self.set_matchups()
		self.aggregate_game_night_data()
		self.generate_hero_feedbacks()
		self.classify_performances()
		self.set_synergies()

	def secure_name(self,name):
		if name == "Dagger":
			return "Cloak & Dagger"
		if name == "Bruce Banner":
			return "Hulk"
		return name

	def get_player_matches(self):
	    bcol = Bcol()
	    # Define profile_dir within the method or ensure it's accessible via self.profile_dir or globally
	    # profile_dir = "path/to/your/profiles" # Make sure this is defined

	    # --- Part 1: Process existing match history for each gamer ---
	    print(f"{bcol.HEADER}--- Processing existing match history ---{bcol.ENDC}")
	    for gamer in self.gamers:
	        print(f"Processing {gamer.nickname}'s known history...")
	        gamer_dir = os.path.join(profile_dir, gamer.nickname)
	        os.makedirs(gamer_dir, exist_ok=True) # Ensure directory exists

	        if "match_history" not in gamer.data or not gamer.data["match_history"]:
	             print(f"{bcol.WARNING}No existing match history found or empty for {gamer.nickname}.{bcol.ENDC}")
	             continue

	        for match in gamer.data["match_history"]:
	            # Basic check for match structure
	            if not isinstance(match, dict) or "game_mode_id" not in match or "match_uid" not in match:
	                print(f"{bcol.WARNING}Skipping invalid match entry for {gamer.nickname}: {match}{bcol.ENDC}")
	                continue

	            # Check desired game mode (e.g., 2)
	            if match["game_mode_id"] != game_mode: # Use the configured game_mode
	                continue

	            match_uid = match["match_uid"]
	            match_filename = f"{match_uid}.json"
	            dest_file = os.path.join(gamer_dir, match_filename)

	            # 1. Skip if the match file already exists for this gamer.
	            if os.path.exists(dest_file):
	                # print(f"Match {match_filename} already exists for {gamer.nickname}.") # Optional verbosity
	                continue

	            # 2. Look for the match file in all *other* gamer directories.
	            found_copy = False
	            for other_gamer in self.gamers:
	                if other_gamer.nickname == gamer.nickname:
	                    continue # Don't check self
	                other_dir = os.path.join(profile_dir, other_gamer.nickname)
	                source_file = os.path.join(other_dir, match_filename)
	                if os.path.exists(source_file):
	                    try:
	                        print(f"Found {match_filename} in {other_gamer.nickname}'s directory. Copying to {gamer.nickname}...")
	                        shutil.copy(source_file, dest_file)
	                        print(f"{bcol.OKGREEN}Copied {match_filename} from {other_gamer.nickname} to {gamer.nickname}.{bcol.ENDC}")
	                        found_copy = True
	                        break # Exit the inner loop once copied
	                    except Exception as e:
	                        print(f"{bcol.FAIL}Error copying {match_filename} from {other_gamer.nickname} to {gamer.nickname}: {e}{bcol.ENDC}")
	                        # Decide if you want to break or let it try downloading
	                        break # Let's break here, assuming copy error is serious

	            if found_copy:
	                continue # Move to the next match for this gamer

	            # 3. If not found locally or copied, attempt to download it with retries.
	            print(f"Match {match_filename} not found locally for {gamer.nickname}. Attempting download...")
	            match_data = None
	            download_success = False
	            for attempt in range(1 + API_RETRIES): # Initial attempt + retries
	                match_data = self.get_match(match_uid) # Call your single match download method
	                if match_data:
	                    # Download successful
	                    try:
	                        with open(dest_file, "w") as f:
	                            json.dump(match_data, f, indent=4)
	                        print(f"{bcol.OKBLUE}Downloaded and saved match {match_uid} for {gamer.nickname} (Attempt {attempt + 1}).{bcol.ENDC}")
	                        download_success = True
	                        break # Exit retry loop on success
	                    except IOError as e:
	                        print(f"{bcol.FAIL}Failed to write match file {dest_file}: {e}{bcol.ENDC}")
	                        # This is a local issue, maybe don't retry API? Break retry loop.
	                        break
	                else:
	                    # Download failed
	                    print(f"{bcol.WARNING}Download attempt {attempt + 1} failed for match {match_uid}.{bcol.ENDC}")
	                    if attempt < API_RETRIES:
	                        print(f"Retrying in {RETRY_DELAY_SECONDS}s...")
	                        time.sleep(RETRY_DELAY_SECONDS)
	                    # No need for else here, loop will end

	            if not download_success:
	                print(f"{bcol.FAIL}Failed to download match {match_uid} for {gamer.nickname} after {1 + API_RETRIES} attempts.{bcol.ENDC}")
	                # Decide if you want to exit or just continue with the next match/gamer
	                # exit(f"Exiting due to persistent download failure for match {match_uid}.") # Uncomment to exit script
	                # continue # Continue processing next match

	    # --- Part 2: Check for and fetch new matches if data is old (with retries) ---
	    print(f"\n{bcol.HEADER}--- Checking for new matches (if data is not from yesterday) ---{bcol.ENDC}")
	    yesterday = datetime.datetime.today().date() - datetime.timedelta(days=1)

	    for gamer in self.gamers:
	        gamer_dir = os.path.join(profile_dir, gamer.nickname) # Recalculate here just in case
	        latest_date_str = getattr(gamer, 'latest_game_night_date', None) # Safely get attribute

	        needs_fetch = False
	        if not latest_date_str:
	            print(f"{bcol.WARNING}Attribute 'latest_game_night_date' not found for {gamer.nickname}. Assuming fetch is needed.{bcol.ENDC}")
	            needs_fetch = True
	        else:
	            try:
	                latest_date = datetime.datetime.strptime(latest_date_str, "%Y-%m-%d").date()
	                if latest_date != yesterday:
	                    print(f"{gamer.nickname}'s data is from {latest_date_str} (not yesterday). Fetching new matches.")
	                    needs_fetch = True
	                else:
	                    print(f"{gamer.nickname} has data from yesterday ({latest_date_str}), skipping match-history API call.")
	                    needs_fetch = False
	            except ValueError:
	                print(f"{bcol.FAIL}Invalid date format for 'latest_game_night_date' for {gamer.nickname}: '{latest_date_str}'. Assuming fetch is needed.{bcol.ENDC}")
	                needs_fetch = True

	        if needs_fetch:
	            print(f"Attempting to fetch latest match history for {gamer.nickname}...")
	            gamer_id = getattr(gamer, 'id', None)
	            if not gamer_id:
	                print(f"{bcol.FAIL}Gamer ID ('id' attribute) not found for {gamer.nickname}. Cannot fetch matches.{bcol.ENDC}")
	                continue # Skip this gamer

	            # Apply rate limit *before* the first API attempt for this gamer
	            print(f"Applying rate limit delay: {rate_limiter}s")
	            time.sleep(rate_limiter)

	            url = f"{base_api_v2}player/{gamer_id}/match-history?limit={match_limit}&game_mode={game_mode}"
	            print(f"API URL: {url}")

	            fetched_matches_data = None # Variable to store successful fetch result
	            fetch_success = False

	            # --- Retry Loop for Fetching Match History List ---
	            for attempt in range(1 + API_RETRIES):
	                try:
	                    print(f"Attempting API call (Attempt {attempt + 1}/{1 + API_RETRIES})...")
	                    r = requests.get(url, headers=headers, timeout=15) # Added timeout
	                    r.raise_for_status() # Raises HTTPError for 4xx/5xx status codes

	                    fetched_matches_data = r.json() # Try to parse JSON
	                    print(f"{bcol.OKGREEN}Successfully fetched match history list for {gamer.nickname}.{bcol.ENDC}")
	                    fetch_success = True
	                    break # Exit retry loop on success

	                except requests.exceptions.HTTPError as e:
	                    print(f"{bcol.FAIL}HTTP Error during fetch for {gamer.nickname} (Attempt {attempt + 1}): {e.response.status_code} {e.response.reason}{bcol.ENDC}")
	                    # Optional: print response body for debugging, be careful with large responses
	                    # print(f"Response body: {r.text[:500]}")
	                    # Decide if specific errors are non-retryable (e.g., 401 Unauthorized, 404 Not Found)
	                    if e.response.status_code in [401, 403, 404]:
	                         print(f"{bcol.FAIL}Non-retryable HTTP error {e.response.status_code}. Aborting fetch for {gamer.nickname}.{bcol.ENDC}")
	                         break # Stop retrying for this specific error

	                except requests.exceptions.RequestException as e:
	                    # Includes connection errors, timeouts, etc.
	                    print(f"{bcol.FAIL}Network error fetching history for {gamer.nickname} (Attempt {attempt + 1}): {e}{bcol.ENDC}")

	                except json.JSONDecodeError as e:
	                     print(f"{bcol.FAIL}Error decoding JSON response for {gamer.nickname} (Attempt {attempt + 1}): {e}{bcol.ENDC}")
	                     # Optional: print response text that failed parsing
	                     # print(f"Response text: {r.text[:500]}") # Be careful if r might not be defined

	                except Exception as e:
	                    # Catch any other unexpected errors during the fetch attempt
	                    print(f"{bcol.FAIL}An unexpected error occurred during fetch attempt {attempt + 1} for {gamer.nickname}: {e}{bcol.ENDC}")
	                    import traceback
	                    traceback.print_exc() # Print stack trace for debugging unexpected errors


	                # If we are here, the attempt failed and we might retry
	                if attempt < API_RETRIES:
	                    print(f"Retrying fetch in {RETRY_DELAY_SECONDS}s...")
	                    time.sleep(RETRY_DELAY_SECONDS)
	                # else: loop will naturally end after last attempt

	            # --- End of Retry Loop for Fetching Match History List ---

	            if not fetch_success or fetched_matches_data is None:
	                print(f"{bcol.FAIL}Failed to fetch match history list for {gamer.nickname} after {1 + API_RETRIES} attempts. Skipping processing for this gamer.{bcol.ENDC}")
	                continue # Move to the next gamer

	            # Now process the successfully fetched matches
	            if "match_history" not in fetched_matches_data or not fetched_matches_data["match_history"]:
	                print(f"{bcol.WARNING}No 'match_history' found or empty in the fetched data for {gamer.nickname}.{bcol.ENDC}")
	                continue # Move to the next gamer

	            try:
	                print(f"Processing {len(fetched_matches_data['match_history'])} fetched matches for {gamer.nickname}...")
	                latest_matches_file = os.path.join(gamer_dir, "latest_comp_games.json")
	                print(f"{bcol.OKGREEN}Successfully stored latest_comp_games for {gamer.nickname}.{bcol.ENDC}")
	            except:
	                print(f"{bcol.FAIL}STORING FAILED, ERROR. Exiting().{gamer.nickname}.{bcol.ENDC}")
	                exit()
	            with open(latest_matches_file, "w") as f: json.dump(fetched_matches_data, f)
	            # --- Duplicated Match Processing Logic ---
	            for match in fetched_matches_data["match_history"]:
	                if not isinstance(match, dict) or "match_uid" not in match:
	                    print(f"{bcol.WARNING}Skipping invalid match entry in fetched data for {gamer.nickname}: {match}{bcol.ENDC}")
	                    continue

	                # We assume the API call already filtered by game_mode, but you could double-check
	                # if "game_mode_id" in match and match["game_mode_id"] != game_mode: continue

	                match_uid = match["match_uid"]
	                match_filename = f"{match_uid}.json"
	                dest_file = os.path.join(gamer_dir, match_filename)

	                # 1. Skip if exists
	                if os.path.exists(dest_file):
	                    continue

	                # 2. Check other gamers & copy
	                found_copy = False
	                for other_gamer in self.gamers:
	                    if other_gamer.nickname == gamer.nickname: continue
	                    other_dir = os.path.join(profile_dir, other_gamer.nickname)
	                    source_file = os.path.join(other_dir, match_filename)
	                    if os.path.exists(source_file):
	                        try:
	                            print(f"Found fetched {match_filename} in {other_gamer.nickname}'s dir. Copying to {gamer.nickname}...")
	                            shutil.copy(source_file, dest_file)
	                            print(f"{bcol.OKGREEN}Copied {match_filename} from {other_gamer.nickname} to {gamer.nickname}.{bcol.ENDC}")
	                            found_copy = True
	                            break
	                        except Exception as e:
	                            print(f"{bcol.FAIL}Error copying {match_filename} from {other_gamer.nickname}: {e}{bcol.ENDC}")
	                            break

	                if found_copy:
	                    continue

	                # 3. Download with retries
	                print(f"Match {match_filename} (from fetch) not found locally for {gamer.nickname}. Attempting download...")
	                match_detail_data = None
	                download_success_inner = False
	                for attempt_inner in range(1 + API_RETRIES):
	                    match_detail_data = self.get_match(match_uid) # Call single match download method
	                    if match_detail_data:
	                        try:
	                            with open(dest_file, "w") as f:
	                                json.dump(match_detail_data, f, indent=4)
	                            print(f"{bcol.OKBLUE}Downloaded and saved match {match_uid} for {gamer.nickname} (Attempt {attempt_inner + 1}).{bcol.ENDC}")
	                            download_success_inner = True
	                            break
	                        except IOError as e:
	                            print(f"{bcol.FAIL}Failed to write match file {dest_file}: {e}{bcol.ENDC}")
	                            break
	                    else:
	                        print(f"{bcol.WARNING}Download attempt {attempt_inner + 1} failed for match {match_uid}.{bcol.ENDC}")
	                        if attempt_inner < API_RETRIES:
	                            print(f"Retrying in {RETRY_DELAY_SECONDS}s...")
	                            time.sleep(RETRY_DELAY_SECONDS)

	                if not download_success_inner:
	                    print(f"{bcol.FAIL}Failed to download match details for {match_uid} for {gamer.nickname} after {1 + API_RETRIES} attempts.{bcol.ENDC}")
	                    # continue # Continue with the next match in the fetched list
	            # --- End of Duplicated Match Processing Logic ---

	    print(f"\n{bcol.HEADER}--- Finished processing all gamers ---{bcol.ENDC}")

	def get_match(self, match_id):
		time.sleep(rate_limiter)
		url = base_api+"match/"+match_id
		print(url)
		r = requests.get(url, headers=headers)
		if r.status_code != 200:
			print("API call not successful, {} returned.".format(str(r.status_code)))
			return None
		else:
			return r.json()

	def convert_timestamp_to_date(self, timestamp):
		dt_oslo = datetime.datetime.fromtimestamp(timestamp, tz=ZoneInfo(time_zone))
		return dt_oslo.strftime("%d.%m.%Y %H:%M")

	def load_and_sort_recent_match_data(self):
		# Process each gamer in self.gamers
		for gamer in self.gamers:
			# Initialize the match_data list
			gamer.match_data = []
			
			# Build the profile directory path
			profile_dir = os.path.join("../profiles", gamer.nickname)
			if not os.path.exists(profile_dir):
				print(f"Directory {profile_dir} does not exist for {gamer.nickname}.")
				continue
			
			# Build the path to latest_comp_games.json
			comp_games_path = os.path.join(profile_dir, "latest_comp_games.json")
			if not os.path.exists(comp_games_path):
				print(f"latest_comp_games.json not found for {gamer.nickname}.")
				continue
			
			# Load the comp_games data
			with open(comp_games_path, 'r') as f:
				comp_games = json.load(f)
			
			# For each match listed in the comp_games (assumed to be the last 20 matches)
			for comp_game in comp_games["match_history"]:
				match_uid = str(comp_game["match_uid"])
				match_file = None
				
				# Look for a file that represents this match.
				# We assume the file name starts with the match_uid and follows the scheme: "matchUID_timestamp_xxx_xxx_xxx.json"
				for filename in os.listdir(profile_dir):
					if filename == match_uid+".json":
						match_file = filename
				
				# If we found a matching file, load its JSON and attach extended data
				if match_file:
					file_path = os.path.join(profile_dir, match_file)
					with open(file_path, 'r') as f:
						data = json.load(f)
					
					# Optionally, extract a timestamp from the file name (the second part)
					try:
						timestamp = int(match_file[:-5].split("_")[1])
					except (ValueError, IndexError):
						timestamp = 0
					
					data["match_timestamp"] = timestamp
					# Attach the comp_game info as extended data
					data["extended_data"] = comp_game
					if data["match_details"] is not None:
						gamer.match_data.append(data)
				else:
					print(f"Match file for match_uid {match_uid} not found in {gamer.nickname}'s folder.")
			
			# Sort the match_data list descending by match_timestamp so that the latest match is first.
			gamer.match_data.sort(key=lambda m: m.get("match_timestamp", 0), reverse=True)
			
			# Optional debug print: show the latest match date
			if gamer.match_data:
				print(f"Latest match for {gamer.nickname} has timestamp {self.convert_timestamp_to_date(gamer.match_data[0]['match_timestamp'])}")
			else:
				print(f"No valid match files found for {gamer.nickname}.")

	def get_game_night_date(self, timestamp, cutoff_hour=5):
		dt = datetime.datetime.fromtimestamp(timestamp, tz=ZoneInfo(time_zone))
		if dt.hour < cutoff_hour:
			adjusted = dt - datetime.timedelta(days=1)
		else:
			adjusted = dt
		return adjusted.date().isoformat()  # Converts to string


	def get_latest_match_night(self):
		for g in self.gamers:
			# Make sure we have match_data for the gamer.
			if not g.match_data:
				g.latest_game_night = []
				continue

			# Determine the game night date for the most recent match.
			latest_night = self.get_game_night_date(g.match_data[0]["extended_data"]["match_time_stamp"])
			g.latest_game_night_date = latest_night
			
			# Filter matches that belong to this same game night.
			latest_night_matches = []
			for match in g.match_data:
				if "extended_data" in match:
					match_ts = match["extended_data"]["match_time_stamp"]
					match_night_date = self.get_game_night_date(match_ts)
					if match_night_date == latest_night:
						latest_night_matches.append(match)
			
			# Save the filtered list into the gamer object.
			g.latest_game_night = latest_night_matches

	def get_hero_stats(self):
		for g in self.gamers:
			for hero in g.top_heroes:
				hero["match_stats"] = []
				hero["mvp_count"] = 0
				hero["svp_count"] = 0
				for match in hero["match_array"]:
					stat_object = {}
					stat_object["match_date"] = self.get_game_night_date(match["extended_data"]["match_time_stamp"])
					stat_object["match_time"] = match["extended_data"]["match_time_stamp"]
					stat_object["primary"] = False

					if match["match_details"]["mvp_uid"] == g.id:
						hero["mvp_count"] += 1
					if match["match_details"]["svp_uid"] == g.id:
						hero["svp_count"] += 1
					# REPEAT ALL ADDITIONS HERE FOR PRIMARIES OR THEY GET LOST
					if match["extended_data"]["match_player"]["player_hero"]["hero_id"] == hero["hero_id"]:
						stat_object = match["extended_data"]["match_player"]["player_hero"]
						stat_object["match_date"] = self.get_game_night_date(match["extended_data"]["match_time_stamp"])
						stat_object["match_time"] = match["extended_data"]["match_time_stamp"]
						stat_object["primary"] = True
						if match["extended_data"]["score_info"]["0"] == match["extended_data"]["score_info"]["1"]:
							stat_object["win"] = "draw"
						else:
							if match["extended_data"]["match_player"]["is_win"]["is_win"]:
								stat_object["win"] = "win"
							else:
								stat_object["win"] = "loss"


					# TRY TO GET STATS IF NOT MORE THAN TWO HEROES PLAYED
					# OR MAYBE INFER IF LITTLE TIME ON OTHERS.
					# Nah impossible. Maybe in the future.
					else:
						pass
						s="""
						if hero["play_time"] > minimum_time_played_to_count_match:
							for participant in match["match_details"]["match_players"]:
								if participant["nick_name"] == g.nickname:
									eligble_heroes = [hero for hero in participant["player_heroes"] if hero["play_time"] > minimum_time_played_to_count_match]
									duelists = []
									vanguards = []
									strategists = []
									for eligble in eligble_heroes:
										exact_hero = self.get_hero_from_id(eligble["hero_id"])
										if exact_hero["role"] == "Vanguard":
											vanguards.append(hero)
										if exact_hero["role"] == "Duelist":
											duelists.append(hero)
										if exact_hero["role"] == "Strategist":
											strategists.append(hero)
									print(eligble)
									print(match["match_details"]["match_uid"])"""

					hero["match_stats"].append(stat_object)

	def get_hero_matches(self):
		for g in self.gamers:
			for hero in g.top_heroes:
				hero["match_array"] = []
				for match in g.match_data:
					for participant in match["match_details"]["match_players"]:
						if participant["nick_name"] == g.nickname:
							for played_hero in participant["player_heroes"]:
								if played_hero["hero_id"] == hero["hero_id"]:
									hero["match_array"].append(match)
				hero["match_count"] = len(hero["match_array"])
			g.top_heroes = sorted([h for h in g.top_heroes if h["match_count"] > 0], key=lambda h: h["match_count"], reverse=True)

	def get_comp_heroes(self):
		for g in self.gamers:
			hero_array = []
			for hero in g.data["heroes_ranked"]:
				hero_array.append(hero)
			heroes_filtered = []
			for hero in hero_array:
				hero_data = self.get_hero_from_id(hero["hero_id"])
				hero["role"] = hero_data["role"]
				hero["name"] = self.secure_name(hero_data["transformations"][0]["name"])
				hero["difficulty"] = hero_data["difficulty"]
			if g.nickname in role_lock:
				for hero in hero_array:
					if hero["role"] in role_lock[g.nickname]:
						if hero["matches"] > 0:
							heroes_filtered.append(hero)
				g.top_heroes = heroes_filtered
			else:
				for hero in hero_array:
					if hero["matches"] > 0:
						heroes_filtered.append(hero)
					else:
						print(f"Filtered out {self.secure_name(hero['name'])} for {g.nickname}")
				g.top_heroes = heroes_filtered
		print("")

	def get_hero_from_id(self,h_id):
		bcol = Bcol()
		filepath = "heroes.json"
		fetched_hero = None
		if os.path.exists(filepath):
			with open(filepath, 'r') as f:
				heroes = json.load(f)
		for hero in heroes:
			if int(hero["id"]) == int(h_id):
				fetched_hero = hero
		if not fetched_hero:
			exit(f"{bcol.FAIL}Hero {h_id} is not present in {filepath}. Try to run broker with --heroes param. If it still fails, maybe it is a new season, and you need to wait for the hero to be added?{bcol.ENDC}")
		return fetched_hero

	def calculate_scores(self):
		for g in self.gamers:
			# Initialize total counters
			healing_array = []
			damage_array = []
			tank_array = []
			deaths_array = []
			kills_array = []
			assists_array = []
			grouped_match_scores = {}

			totals = {
				"kills": 0, "assists": 0, "deaths": 0, "wins": 0, "draws": 0, "losses": 0,
				"damage": 0, "healing": 0, "tanked": 0, "seconds_played": 0, "unique_matches" : []
			}

			match_count = len(g.match_data)

			for match in g.match_data:
				# Sometimes a hero has a primary match, but it is not... counted?
				# So they have 0 matches in their stats. And that crashes this part.
				# So we just check if match_date is added, and if not? Just skip it.

				if "match_date" in match["extended_data"]["match_player"]["player_hero"]:
					match_date = match["extended_data"]["match_player"]["player_hero"]["match_date"]  # Extract match date

					# Find the participant corresponding to the gamer
					for participant in match["match_details"]["match_players"]:
						if participant["nick_name"] == g.nickname:
							# Aggregate player totals
							totals["kills"] += participant["kills"]
							totals["assists"] += participant["assists"]
							totals["deaths"] += participant["deaths"]
							totals["damage"] += participant["total_hero_damage"]
							totals["healing"] += participant["total_hero_heal"]
							totals["tanked"] += participant["total_damage_taken"]
							totals["seconds_played"] += self.duration_to_seconds(match["extended_data"]["match_play_duration"])

							if participant["is_win"] == 0:
								totals["losses"] += 1
								totals["unique_matches"].append({"match_id":match["match_details"]["match_uid"],"win":"loss", "duration":self.duration_to_seconds(match["extended_data"]["match_play_duration"])})
							if participant["is_win"] == 1:
								totals["wins"] += 1
								totals["unique_matches"].append({"match_id":match["match_details"]["match_uid"],"win":"win", "duration":self.duration_to_seconds(match["extended_data"]["match_play_duration"])})
							if participant["is_win"] == 2:
								totals["draws"] += 1
								totals["unique_matches"].append({"match_id":match["match_details"]["match_uid"],"win":"draw", "duration":self.duration_to_seconds(match["extended_data"]["match_play_duration"])})

							# Track arrays for consistency calculations
							deaths_array.append(participant["deaths"])
							kills_array.append(participant["kills"])
							assists_array.append(participant["assists"])

							# --- GROUP MATCH SCORES BY DATE ---
							if match_date not in grouped_match_scores:
								grouped_match_scores[match_date] = {
									"kills": 0, "assists": 0, "deaths": 0, "wins": 0, "draws": 0, "losses": 0,
									"damage": 0, "healing": 0, "tanked": 0, "seconds_played": 0,
									"match_count": 0, "unique_matches" : []
								}

							# Aggregate stats per date
							grouped_match_scores[match_date]["kills"] += participant["kills"]
							grouped_match_scores[match_date]["assists"] += participant["assists"]
							grouped_match_scores[match_date]["deaths"] += participant["deaths"]
							grouped_match_scores[match_date]["seconds_played"] += self.duration_to_seconds(match["extended_data"]["match_play_duration"])

							grouped_match_scores[match_date]["damage"] += participant["total_hero_damage"]
							grouped_match_scores[match_date]["healing"] += participant["total_hero_heal"]
							grouped_match_scores[match_date]["tanked"] += participant["total_damage_taken"]
							grouped_match_scores[match_date]["match_count"] += 1
							if participant["is_win"] == 0:
								grouped_match_scores[match_date]["losses"] += 1
								grouped_match_scores[match_date]["unique_matches"].append({"match_id":match["match_details"]["match_uid"],"win":"loss", "duration":self.duration_to_seconds(match["extended_data"]["match_play_duration"])})
							if participant["is_win"] == 1:
								grouped_match_scores[match_date]["wins"] += 1
								grouped_match_scores[match_date]["unique_matches"].append({"match_id":match["match_details"]["match_uid"],"win":"win", "duration":self.duration_to_seconds(match["extended_data"]["match_play_duration"])})
							if participant["is_win"] == 2:
								grouped_match_scores[match_date]["draws"] += 1
								grouped_match_scores[match_date]["unique_matches"].append({"match_id":match["match_details"]["match_uid"],"win":"draw", "duration":self.duration_to_seconds(match["extended_data"]["match_play_duration"])})
							grouped_match_scores[match_date]["heroes"] = []
							if "secondaries" not in grouped_match_scores[match_date]:
								grouped_match_scores[match_date]["secondaries"] = []
							primaries = []
							for hero in g.top_heroes:
								if "grouped_match_scores" in hero:
									if match_date in hero["grouped_match_scores"]:
										primaries.append(hero["hero_id"])
										added_hero = hero["grouped_match_scores"][match_date]
										added_hero["name"] = self.secure_name(hero["name"])
										added_hero["hero_id"] = hero["hero_id"]
										added_hero["role"] = hero["role"]
										grouped_match_scores[match_date]["heroes"].append(added_hero)
							for hero in participant["player_heroes"]:
								if hero["hero_id"] not in primaries:
									second = self.get_hero_from_id(hero["hero_id"])
									hero["name"] = self.secure_name(second["name"])
									grouped_match_scores[match_date]["secondaries"].append(hero)


			# --- Derived Statistics Calculations ---
			derived = {}
			# KDA calculation: handle zero deaths to avoid division by zero.
			derived["kda"] = (totals["kills"] + totals["assists"]) / totals["deaths"] if totals["deaths"] > 0 else totals["kills"] + totals["assists"]

			# Calculate minutes played (avoid division by zero)
			minutes_played = totals["seconds_played"] / 60 if totals["seconds_played"] > 0 else 0
			derived["damage_per_minute"] = totals["damage"] / minutes_played if minutes_played > 0 else 0
			derived["healing_per_minute"] = totals["healing"] / minutes_played if minutes_played > 0 else 0
			derived["tanking_per_minute"] = totals["tanked"] / minutes_played if minutes_played > 0 else 0

			# Win rate (if at least one game played)
			total_games = totals["wins"] + totals["losses"]
			derived["win_rate"] = totals["wins"] / total_games if total_games > 0 else 0

			# Additional averages (optional)
			derived["kills_per_game"] = totals["kills"] / match_count if match_count > 0 else 0
			derived["assists_per_game"] = totals["assists"] / match_count if match_count > 0 else 0
			derived["deaths_per_game"] = totals["deaths"] / match_count if match_count > 0 else 0

			# Add the derived stats into the totals dictionary
			totals["derived_stats"] = derived

			# Compute consistency
			totals["kills_consistency"] = self.compute_consistency(kills_array)
			totals["deaths_consistency"] = self.compute_consistency(deaths_array)
			totals["assists_consistency"] = self.compute_consistency(assists_array)

			# Store final stats in player object
			g.match_scores = totals

			# Store grouped match scores
			g.grouped_match_scores = grouped_match_scores
			# Compute final player score
			g.match_scores["score"] = self.compute_composite_value(g.match_scores["derived_stats"])
			g.match_scores["derived_stats"]["score"] = totals["score"]

			# Compute scores for grouped matches by date
			for match_date, stats in g.grouped_match_scores.items():
				# Calculate per-minute values for proper scoring
				minutes_played = stats["seconds_played"] / 60 if stats["seconds_played"] > 0 else 0
				derived = {
					"damage_per_minute": stats["damage"] / minutes_played if minutes_played > 0 else 0,
					"healing_per_minute": stats["healing"] / minutes_played if minutes_played > 0 else 0,
					"tanking_per_minute": stats["tanked"] / minutes_played if minutes_played > 0 else 0,
					"win_rate": stats["wins"] / stats["match_count"] if stats["match_count"] > 0 else 0,
					"kda": (stats["kills"] + stats["assists"]) / stats["deaths"] if stats["deaths"] > 0 else stats["kills"] + stats["assists"],
					"kills_per_game": stats["kills"] / stats["match_count"] if stats["match_count"] > 0 else 0,
					"assists_per_game": stats["assists"] / stats["match_count"] if stats["match_count"] > 0 else 0,
					"deaths_per_game": stats["deaths"] / stats["match_count"] if stats["match_count"] > 0 else 0
				}
				stats["score"] = self.compute_composite_value(derived)


	def compute_composite_value(self, stats, role=False):
		"""
		Calculate a composite score using role-specific stats, allowing slight overperformance bonuses
		and softer death penalties.
		"""
		# Get role-based max values
		max_values = MAX_STAT_VALUES.get(role, MAX_STAT_VALUES["default"])

		# Get relevant stats for this role
		relevant_stats = ROLE_SCORING_CATEGORIES.get(role, ROLE_SCORING_CATEGORIES["default"])
		OVERPERFORMANCE_CAP = CATEGORY_MAX_POINTS * 1.5

		def normalize(stat):
			raw_value = stats.get(stat, 0)
			max_value = max_values.get(stat, 1)
			return min(raw_value / max_value * 1.1, 1.1)

		def log_scale(value, max_val, factor=2):
			if value <= 0:
				return 0
			return min(math.log(1 + value) / math.log(1 + max_val), 1) * factor

		def sigmoid(x, max_x):
			return 1 / (1 + math.exp(-15 * (x - (max_x / 2))))

		def softened_inverse_scale(value, max_val):
			# Less punishing curve: 1 / (1 + (x / max)^1.5)
			if max_val == 0:
				return 0
			return 1 / (1 + (value / max_val)**1.5)

		composite = 0

		for stat in relevant_stats:
			raw_value = stats.get(stat, 0)

			# Special handling
			if "deaths" in stat:
				scaled_value = softened_inverse_scale(raw_value, max_values[stat])
			elif "win_rate" in stat:
				scaled_value = sigmoid(raw_value, max_values[stat])
			elif "assists" in stat or "kills" in stat:
				scaled_value = log_scale(raw_value, max_values[stat], factor=1.2)
			else:
				scaled_value = normalize(stat)

			score_contribution = scaled_value * CATEGORY_MAX_POINTS
			score_contribution = min(score_contribution, OVERPERFORMANCE_CAP)
			composite += score_contribution

		final_score = max(0, int(composite))
		return final_score



	def classify_performances(self):
		for g in self.gamers:
			# Build the profile directory path
			game_night_json = os.path.join(self.game_nights_folder, f"{g.latest_game_night_date}.json".replace("-","_"))
			if not os.path.exists(game_night_json):
				print(f"The gamenight file for {g.latest_game_night_date} does not exist. {g.nickname} reverting to non-AI feedback.")
				continue

			# Load the comp_games data
			with open(game_night_json, 'r') as f:
				game_night_data = json.load(f)
				
			if "personal_AI_summaries" in game_night_data:
				for summary in game_night_data["personal_AI_summaries"]:
					if summary["nickname"] == g.nickname:
						ai_summary = summary
				if ai_summary:
					g.feedback = {
						"ai_enabled": True,
						"content": ai_summary["content"],
						"title": ai_summary["title"],
						"main_title": summary["title"],
						"score": None,
						"percent_difference": 0,
						"feedback": "",
						"sentiment": None
					}
				else:
					print(f"The gamenight file for {g.latest_game_night_date} is corrupt, or missing data. {g.nickname} reverting to non-AI feedback.")
					continue
			else:
				print(f"The gamenight file for {g.latest_game_night_date} is corrupt, or missing data. {g.nickname} reverting to non-AI feedback.")
				continue

	def compute_consistency(self, values):
		# If there is not enough data, assume perfect consistency.
		if len(values) < 2:
			return 1.0
		mean_val = statistics.mean(values)
		# Avoid division by zero if mean is 0.
		if mean_val == 0:
			return 0
		stdev_val = statistics.stdev(values)
		cv = stdev_val / mean_val
		consistency_score = 1 / (1 + cv)
		return consistency_score

	def sort_hero_scores(self):
		for g in self.gamers:
			for hero in g.top_heroes:
				if "score_array" in hero["match_scores"]:
					# 🆕 Sort by 'date' (which is in "dd.mm" format)
					hero["match_scores"]["score_array"].sort(key=lambda entry: datetime.datetime.strptime(entry["date"], "%d.%m"))

	def duration_to_seconds(self,duration):
		if isinstance(duration,dict):
			return duration["raw"]
		if isinstance(duration,int):
			return duration
		if isinstance(duration,float):
			return int(duration)
		match = re.match(r'(?:(\d+)m)?\s*(?:(\d+)s)?', duration)
		minutes = int(match.group(1)) if match.group(1) else 0
		seconds = int(match.group(2)) if match.group(2) else 0
		return minutes * 60 + seconds

	def calculate_hero_scores(self):
		for g in self.gamers:
			for hero in g.top_heroes:
				# Initialize total counters
				healing_array = []
				damage_array = []
				tank_array = []
				deaths_array = []
				kills_array = []
				assists_array = []
				grouped_match_scores = {}

				totals = {
					"kills": 0, "assists": 0, "deaths": 0, "wins": 0, "losses": 0,
					"damage": 0, "healing": 0, "tanked": 0, "seconds_played": 0
				}
				count = 1
				for match in hero["match_stats"]:
					if match["primary"]:  # Only count matches where this hero was primary
						match_date = match["match_date"]  # Get the date for grouping

						# Aggregate data per match
						totals["kills"] += match["kills"]
						totals["assists"] += match["assists"]
						totals["deaths"] += match["deaths"]
						totals["seconds_played"] += self.duration_to_seconds(match["play_time"])
						totals["damage"] += match["total_hero_damage"]
						totals["healing"] += match["total_hero_heal"]
						totals["tanked"] += match["total_damage_taken"]
						if match["win"] == "win":
							totals["wins"] += 1
						if match["win"] == "loss":
							totals["losses"] += 1

						# Track arrays for consistency calculations
						deaths_array.append(match["deaths"])
						kills_array.append(match["kills"])
						assists_array.append(match["assists"])
						healing_array.append(match["total_hero_heal"])
						damage_array.append(match["total_hero_damage"])
						tank_array.append(match["total_damage_taken"])

						# --- GROUP MATCH SCORES BY DATE ---
						if match_date not in grouped_match_scores:
							grouped_match_scores[match_date] = {
								"kills": 0, "assists": 0, "deaths": 0, "wins": 0, "losses": 0,
								"damage": 0, "healing": 0, "tanked": 0, "seconds_played": 0,
								"match_count": 0
							}

						# Aggregate per day
						grouped_match_scores[match_date]["kills"] += match["kills"]
						grouped_match_scores[match_date]["assists"] += match["assists"]
						grouped_match_scores[match_date]["deaths"] += match["deaths"]
						grouped_match_scores[match_date]["seconds_played"] += self.duration_to_seconds(match["play_time"])
						grouped_match_scores[match_date]["damage"] += match["total_hero_damage"]
						grouped_match_scores[match_date]["healing"] += match["total_hero_heal"]
						grouped_match_scores[match_date]["tanked"] += match["total_damage_taken"]
						grouped_match_scores[match_date]["match_count"] += 1
						if match["win"] == "win":
							grouped_match_scores[match_date]["wins"] += 1
						if match["win"] == "loss":
							grouped_match_scores[match_date]["losses"] += 1

						# --- Derived Statistics Calculations ---
						derived = {}
						match_count = totals["wins"] + totals["losses"]

						# KDA calculation: handle zero deaths to avoid division by zero
						derived["kda"] = (totals["kills"] + totals["assists"]) / totals["deaths"] if totals["deaths"] > 0 else totals["kills"] + totals["assists"]

						# Minutes played (avoid division by zero)
						minutes_played = totals["seconds_played"] / 60 if totals["seconds_played"] > 0 else 0
						derived["damage_per_minute"] = totals["damage"] / minutes_played if minutes_played > 0 else 0
						derived["healing_per_minute"] = totals["healing"] / minutes_played if minutes_played > 0 else 0
						derived["tanking_per_minute"] = totals["tanked"] / minutes_played if minutes_played > 0 else 0
						derived["kills_per_minute"] = totals["kills"] / minutes_played if minutes_played > 0 else 0

						# Win rate calculation
						derived["win_rate"] = totals["wins"] / match_count if match_count > 0 else 0

						# Per-game stats
						derived["kills_per_game"] = totals["kills"] / match_count if match_count > 0 else 0
						derived["assists_per_game"] = totals["assists"] / match_count if match_count > 0 else 0
						derived["deaths_per_game"] = totals["deaths"] / match_count if match_count > 0 else 0

						# Add the derived stats into the totals dictionary
						totals["derived_stats"] = derived

						# Compute consistency
						totals["kills_consistency"] = self.compute_consistency(kills_array)
						totals["deaths_consistency"] = self.compute_consistency(deaths_array)
						totals["assists_consistency"] = self.compute_consistency(assists_array)

						# Store final stats in hero object
						hero["match_scores"] = totals
						hero["match_scores"]["role"] = hero["role"]
						hero["match_scores"]["hero_id"] = hero["hero_id"]

						# Store grouped match scores
						hero["grouped_match_scores"] = grouped_match_scores

						# Compute final hero score using improved formula
						hero["match_scores"]["score"] = self.compute_composite_value(hero["match_scores"]["derived_stats"], role=hero["role"])
						hero["match_scores"]["derived_stats"]["score"] = totals["score"]
						match["score"] = totals["score"]

						# Compute scores for grouped matches by date
						for match_date, stats in hero["grouped_match_scores"].items():
							# Calculate per-minute values for proper scoring
							minutes_played = stats["seconds_played"] / 60 if stats["seconds_played"] > 0 else 0
							derived = {
								"damage_per_minute": stats["damage"] / minutes_played if minutes_played > 0 else 0,
								"healing_per_minute": stats["healing"] / minutes_played if minutes_played > 0 else 0,
								"tanking_per_minute": stats["tanked"] / minutes_played if minutes_played > 0 else 0,
								"kills_per_minute": stats["kills"] / minutes_played if minutes_played > 0 else 0,
								"win_rate": stats["wins"] / stats["match_count"] if stats["match_count"] > 0 else 0,
								"kda": (stats["kills"] + stats["assists"]) / stats["deaths"] if stats["deaths"] > 0 else stats["kills"] + stats["assists"],
								"kills_per_game": stats["kills"] / stats["match_count"] if stats["match_count"] > 0 else 0,
								"assists_per_game": stats["assists"] / stats["match_count"] if stats["match_count"] > 0 else 0,
								"deaths_per_game": stats["deaths"] / stats["match_count"] if stats["match_count"] > 0 else 0
							}
							stats["score"] = self.compute_composite_value(derived, role=hero["role"])

	def generate_star_chart_for_heroes(self):
		for g in self.gamers:
			for hero in g.top_heroes:
				if hero["role"] == "Vanguard":
					hero["starchart"] = {"KDA":hero["match_scores"]["derived_stats"]["kda"]*w_kda,
					"Tanking":hero["match_scores"]["derived_stats"]["tanking_per_minute"]*w_tanking}
				if hero["role"] == "Strategist":
					pass
				if hero["role"] == "Duelist":
					pass

	def remove_html_tags(self, text):
	    clean = re.compile(r'<[^>]+>')
	    return re.sub(clean, '', text)

	def compute_star_rating(self, value, max_value):
	    """Convert a stat value into a star rating based on its max possible score."""
	    steps = max_value / MAX_STEPS
	    stars = min(math.floor(value / steps), MAX_STEPS)  # Ensure it doesn't exceed 5 stars
	    return stars, STAR_ICONS[stars]  # Returns (numeric rating, HTML stars)

	def generate_hero_feedbacks(self):
		for gamer in self.gamers:
			for hero in gamer.top_heroes:
				#print(f"{gamer.nickname} : {self.secure_name(hero["name"])}")
				hero["match_scores"]["final_ratings"] = {}  # Store one final rating per category

				# Get role-specific max values
				role = hero["role"]
				max_values = MAX_STAT_VALUES.get(role, MAX_STAT_VALUES["default"])

				# Compute star ratings for each category
				for stat in max_values:
					overall_value = hero["match_scores"]["derived_stats"].get(stat, 0)

					stars, stars_html = self.compute_star_rating(overall_value, max_values[stat])
					hero["match_scores"]["final_ratings"][stat] = {"stars": stars, "html": stars_html}

	def get_strongest_performances(self):
		results = {}
		for stat in performances:
			results[stat] = []
			for g in self.gamers:
				for match in g.match_data:
					results[stat].append({"stat":stat,"player":g,"metric":match["extended_data"]["match_player"]["player_hero"][stat],"hero":match["extended_data"]["match_player"]["player_hero"]["hero_id"]})
		toppers = []
		for stat in performances:
			toppers.append(sorted(results[stat], key=lambda h: h["metric"], reverse=True)[0])

		return toppers

	def set_matchups(self):
		for g in self.gamers:
			# Copy the threshold locally
			threshold = matchup_threshold
			min_threshold = 1  # Define how low you're willing to go

			valid_matchups = []
			while threshold >= min_threshold:
				valid_matchups = [m for m in g.data["hero_matchups"] if m["matches"] >= threshold]
				if valid_matchups:
					break
				threshold -= 1  # Reduce gradually

			if not valid_matchups:
				# Still none found, skip this gamer
				continue

			g.strongest_matchup = valid_matchups[0]
			g.weakest_matchup = valid_matchups[0]

			for matchup in valid_matchups:
				win_rate = float(matchup["win_rate"])
				if win_rate > float(g.weakest_matchup["win_rate"]):
					g.weakest_matchup = matchup
				if win_rate < float(g.strongest_matchup["win_rate"]):
					g.strongest_matchup = matchup

			g.strongest_matchup["win_rate"] = int(100 - float(g.strongest_matchup["win_rate"]))
			g.weakest_matchup["win_rate"] = int(100 - float(g.weakest_matchup["win_rate"]))


	def get_superstars(self):
		all_heroes = []
		for g in self.gamers:
			for hero in g.top_heroes:
				all_heroes.append({"gamer":g,"hero":hero,"mvp":hero["mvp_count"]})
		top_two = sorted(all_heroes, key=lambda entry: entry["mvp"], reverse=True)[:3]
		return top_two

	def sort_gamers(self):
		self.gamers = sorted(self.gamers, key=lambda g: g.match_scores["score"], reverse=True)

	def export_data_objects(self):
	    for g in self.gamers:
	        valid_heroes = []

	        for hero in g.top_heroes:
	            # Build out the 'score_array' for each hero
	            if "match_scores" in hero:
	                hero["match_scores"]["score_array"] = []
	                hero["match_scores"]["costume"] = g.get_hero_costume(hero["hero_id"])

	                if "match_stats" in hero:
	                    for stat in hero["match_stats"][:stack_score_count]:
	                        if "score" in stat: 
	                            hero["match_scores"]["score_array"].append({
	                                "date": datetime.datetime.strptime(stat["match_date"], "%Y-%m-%d").strftime("%d.%m"),
	                                "time": stat["match_time"],
	                                "score": stat["score"]
	                            })

	                # Append to valid_heroes only if the hero has match_scores
	                valid_heroes.append(hero)

	        # Now that valid_heroes is built, we can SORT it based on usage
	        def hero_sort_key(h):
	            # 1) Did we use this hero on the 'latest_game_night_date'?
	            #    If so, we want it to appear *before* heroes not used recently
	            usage_in_latest = 0
	            total_usage = 0

	            if "grouped_match_scores" in h:
	                # If the hero has any usage in the latest date
	                if g.latest_game_night_date in h["grouped_match_scores"]:
	                    usage_in_latest = h["grouped_match_scores"][g.latest_game_night_date]["match_count"]

	                # Sum up all match_counts across all dates
	                total_usage = sum(val["match_count"] for val in h["grouped_match_scores"].values())

	            # We want:
	            #   1) Heroes used in the latest date first (so used_in_latest = usage_in_latest > 0)
	            #   2) Among those, higher usage_in_latest goes first
	            #   3) Among ties, fallback to total usage
	            # Because we want descending, we return them as a tuple
	            used_in_latest_flag = 1 if usage_in_latest > 0 else 0
	            return (used_in_latest_flag, usage_in_latest, total_usage)

	        # Sort in descending order
	        valid_heroes = sorted(valid_heroes, key=lambda h: hero_sort_key(h), reverse=True)

	        # Finally, assign back
	        g.top_heroes = valid_heroes

	        # Also build 'score_array' for g.match_scores
	        g.match_scores["score_array"] = []
	        for date_str, value in g.grouped_match_scores.items():
	            g.match_scores["score_array"].append({
	                "date": datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m"),
	                "score": value["score"]
	            })

	def _extract_timestamp(self, match_id):
	        """Helper to extract timestamp from match_id string."""
	        try:
	            # Assumes format like: "mapid_timestamp_duration_queue_server"
	            parts = match_id.split('_')
	            if len(parts) > 1:
	                return int(parts[1])
	            return 0 # Default if format is unexpected
	        except (ValueError, IndexError):
	            return 0 # Handle potential errors

	def format_duration(self, seconds):
	    """Formats seconds into a more readable 'Xm Ys' or 'Ys' string."""
	    if seconds is None or not isinstance(seconds, (int, float)) or seconds < 0:
	        return "" # Handle invalid input gracefully
	    try:
	        seconds = int(seconds) # Ensure integer math
	        minutes = seconds // 60
	        secs = seconds % 60
	        if minutes > 0:
	            return f"{minutes}m {secs}s"
	        return f"{secs}s"
	    except Exception: # Catch potential conversion issues
	         return ""

	def aggregate_game_night_data(self):
	    os.makedirs(self.game_nights_folder, exist_ok=True)

	    # --- Step 1: Collect all data grouped by game night date ---
	    all_game_night_data = defaultdict(lambda: {
	        "matches": {}, # Store match_id -> {win: bool, players: set}
	        "player_stats": {} # Store nickname -> player_night_stats
	    })

	    for g in self.gamers:
	        for game_night_date, stats in g.grouped_match_scores.items():
	            # Store player's stats for this night
	            all_game_night_data[game_night_date]["player_stats"][g.nickname] = stats

	            # Collect matches and participants for this night
	            current_matches = all_game_night_data[game_night_date]["matches"]
	            for match in stats["unique_matches"]:
	                match_id = match["match_id"]
	                if match_id not in current_matches:
	                    current_matches[match_id] = {"result": match["win"], "players": set(),"duration":match["duration"]}
	                # Add player to the set for this match
	                current_matches[match_id]["players"].add(g.nickname)

	    # --- Step 2: Process each game night individually ---
	    for game_night_date, night_data in all_game_night_data.items():

	        file_path = os.path.join(self.game_nights_folder, f"{game_night_date.replace('-', '_')}.json")
	        # 🛠️ Check if the game night file already exists (optional, keep if needed)
	        if os.path.exists(file_path):
	            print(f"ℹ️ Skipping {game_night_date}, file already exists.")
	            continue

	        if not night_data["matches"]: # Skip if no matches found for this date (shouldn't happen with defaultdict)
	            continue

	        # --- Step 3: Sort matches chronologically ---
	        sorted_match_ids = sorted(
	            night_data["matches"].keys(),
	            key=self._extract_timestamp # Sort by timestamp
	        )

	        # --- Step 4: Build the Event List ---
	        events = []
	        current_players = set()
	        solo_queue_matches = [] # Track solo queue matches for the final output

	        # Event: Game Night Started
	        first_timestamp = self._extract_timestamp(sorted_match_ids[0])
	        start_time_str = datetime.datetime.fromtimestamp(first_timestamp).strftime('%H:%M:%S')
	        events.append({
	            "event_type": "game_night_started",
	            "timestamp": first_timestamp,
	            "readable_time": start_time_str,
	            "message": f"Game night started around {start_time_str}."
	        })

	        for i, match_id in enumerate(sorted_match_ids):
	            match_info = night_data["matches"][match_id]
	            match_players = match_info["players"]
	            match_win = match_info["result"]
	            match_timestamp = self._extract_timestamp(match_id)
	            match_time_str = datetime.datetime.fromtimestamp(match_timestamp).strftime('%H:%M:%S')

	            # --- Get Match Duration ---
	            # Ensure you are storing duration in your match_info correctly during Step 1
	            # Example: current_matches[match_id] = {"win": match["win"], "players": set(), "duration": match.get("duration")}
	            match_duration = match_info.get("duration") # Fetch duration in seconds

	            # Detect player changes *before* processing the match itself
	            if i == 0:
	                # First match: Players arrived
	                current_players = match_players
	                events.append({
	                    "event_type": "players_arrived",
	                    "timestamp": match_timestamp,
	                     "readable_time": match_time_str,
	                    "players": sorted(list(current_players)),
	                    "message": f"Initial players joined: {', '.join(sorted(list(current_players)))}."
	                })
	            else:
	                previous_players = current_players # Players from the state *before* this match
	                departed_players = previous_players - match_players
	                joined_players = match_players - previous_players

	                if departed_players:
	                    events.append({
	                        "event_type": "players_departed",
	                        "timestamp": match_timestamp, # Occurred *before* this match started
	                        "readable_time": match_time_str,
	                        "players": sorted(list(departed_players)),
	                        "message": f"Players departed: {', '.join(sorted(list(departed_players)))}."
	                    })

	                if joined_players:
	                     events.append({
	                        "event_type": "players_joined",
	                        "timestamp": match_timestamp, # Occurred *before* this match started
	                        "readable_time": match_time_str,
	                        "players": sorted(list(joined_players)),
	                        "message": f"Players joined: {', '.join(sorted(list(joined_players)))}."
	                    })
	                # Update current roster for the *next* comparison
	                current_players = match_players


	            # --- Event: Match Played (with enhanced message) ---
	            stomp_time = average_match_time * 0.55
	            struggle_time = average_match_time * 1.3
	            outcome_term = "victory"
	            if match_win == "loss":
	            	outcome_term = "defeat"
	            if match_win == "draw":
	            	outcome_term = "draw"
	            num_players = len(match_players)
	            duration_str = self.format_duration(match_duration) # Format for display

	            message = "" # Initialize message string

	            # Determine context: fast, long, or normal duration
	            is_fast = match_duration is not None and match_duration <= stomp_time
	            is_long = match_duration is not None and match_duration >= struggle_time

	            # --- Build the message based on context ---
	            if num_players == 1:
	                player_name = list(match_players)[0] # Get the solo player's name
	                action_prefix = f"{player_name} queued up solo"

	                if is_fast:
	                    if match_win == "win":
	                        message = f"{action_prefix} and swiftly secured a victory in just {duration_str}! WHAT!?"
	                    else:
	                        message = f"{action_prefix} but faced a rapid {outcome_term} ({duration_str}). LMAO!"
	                elif is_long:
	                     if match_win == "win":
	                        message = f"{action_prefix} and clinched a hard-fought {outcome_term} after a long {duration_str} battle! Ugh..."
	                     else:
	                        message = f"After a marathon solo match ({duration_str}), {player_name}'s effort ended in a {outcome_term}. Gross."
	                else: # Normal duration
	                    duration_suffix = f" ({duration_str})" if duration_str else ""
	                    if match_win == "win":
	                         message = f"{action_prefix} and achieved {outcome_term}{duration_suffix}. DAMN, SON!"
	                    else:
	                         message = f"{action_prefix}, resulting in a {outcome_term}{duration_suffix}. Lol smh."

	            else: # Stacked queue (2+ players)
	                stack_desc = f"The {num_players}-stack" # Could randomize: "The squad", "Playing as {num_players}"

	                if is_fast:
	                    if match_win  == "win":
	                         message = f"{stack_desc} dominated, claiming a quick {outcome_term} in only {duration_str}!"
	                    else:
	                         message = f"{stack_desc} got steamrolled, suffering a swift {outcome_term} ({duration_str})."
	                elif is_long:
	                    if match_win == "win":
	                        message = f"After a lengthy {duration_str} struggle, {stack_desc} finally emerged with a {outcome_term}!"
	                    else:
	                        message = f"It was a long {duration_str} grind, but {stack_desc} ultimately faced a {outcome_term}."
	                else: # Normal duration
	                    duration_suffix = f" ({duration_str})" if duration_str else ""
	                    if match_win == "win":
	                         message = f"{stack_desc} worked together for the {outcome_term}{duration_suffix}."
	                    else:
	                         message = f"{stack_desc} fought for {squadname}, but ended the match in a {outcome_term}{duration_suffix}."

	            # Fallback message if duration was None or context couldn't be determined
	            if not message:
	                 prefix = f"{list(match_players)[0]} soloqueued" if num_players == 1 else f"The {num_players}-stack played"
	                 message = f"{prefix}, resulting in a {outcome_term}."

	            # --- Append the event ---
	            events.append({
	                "event_type": "match_played",
	                "match_duration": match_duration, # Store raw duration if needed elsewhere
	                "timestamp": match_timestamp,
	                "readable_time": match_time_str,
	                "match_id": match_id, # Keep raw match_id if needed for linking/debugging
	                "outcome": outcome_term, # Store semantic outcome ('victory'/'defeat')
	                "players": sorted(list(match_players)),
	                "message": message # Use the newly generated message
	            })

	            # Check for Solo Queue
	            if len(match_players) == 1:
	                 solo_queue_matches.append({
	                    "player": list(match_players)[0], # Get the single player's name
	                    "match_id": match_id,
	                    "win": match_win
	                })

	        # Event: Game Night Ended
	        last_timestamp = self._extract_timestamp(sorted_match_ids[-1]) # Use last match time as proxy
	        end_time_str = datetime.datetime.fromtimestamp(last_timestamp+(average_match_time)).strftime('%H:%M:%S')
	        events.append({
	            "event_type": "game_night_ended",
	            "timestamp": last_timestamp, # Approximate end time
	            "readable_time": end_time_str,
	            "message": f"Game night concluded after the last match around {end_time_str}."
	        })


	        # --- Step 5: Aggregate Final Stats and Assemble Output ---
	        final_data = {
	            "date": game_night_date,
	            "total_kills": 0,
	            "total_deaths": 0,
	            "total_assists": 0,
	            "total_wins": 0,
	            "total_losses": 0,
	            "total_draws": 0,
	            "total_damage": 0,
	            "total_healing": 0,
	            "total_tanked": 0,
	            "match_count": len(sorted_match_ids),
	            "unique_matches": sorted_match_ids, # Already sorted chronologically
	            "soloqueue": solo_queue_matches, # Populate from event loop
	            "players": [],
	            "events": events # Add the generated events list
	        }

	        # Aggregate totals and player details
	        for nickname, player_night_stats in night_data["player_stats"].items():
	            # Only include players who actually played on this night
	            # (This check might be redundant if player_stats is populated correctly)
	            if any(nickname in night_data["matches"][mid]["players"] for mid in sorted_match_ids):
	                final_data["total_kills"] += player_night_stats.get("kills", 0)
	                final_data["total_deaths"] += player_night_stats.get("deaths", 0)
	                final_data["total_assists"] += player_night_stats.get("assists", 0)
	                final_data["total_damage"] += player_night_stats.get("damage", 0)
	                final_data["total_healing"] += player_night_stats.get("healing", 0)
	                final_data["total_tanked"] += player_night_stats.get("tanked", 0)

	                # Store individual player's contribution
	                final_data["players"].append({
	                    "nickname": nickname,
	                    "kills": player_night_stats.get("kills", 0),
	                    "deaths": player_night_stats.get("deaths", 0),
	                    "assists": player_night_stats.get("assists", 0),
	                    "wins": player_night_stats.get("wins", 0), # Wins/Losses per player for the night
	                    "losses": player_night_stats.get("losses", 0),
	                    "damage": player_night_stats.get("damage", 0),
	                    "healing": player_night_stats.get("healing", 0),
	                    "tanked": player_night_stats.get("tanked", 0),
	                    "match_count": player_night_stats.get("match_count", 0), # Matches played *by this player*
	                    "score": player_night_stats.get("score", 0),
	                    "heroes": player_night_stats.get("heroes", []),
	                    "secondaries": player_night_stats.get("secondaries", [])
	                })

	        # Calculate overall wins/losses for the night
	        final_data["total_wins"] = sum(1 for mid in sorted_match_ids if night_data["matches"][mid]["result"] == "win")
	        final_data["total_losses"] = sum(1 for mid in sorted_match_ids if night_data["matches"][mid]["result"] == "loss")
	        final_data["total_draws"] = sum(1 for mid in sorted_match_ids if night_data["matches"][mid]["result"] == "draw")


	        # --- Step 6: Save Data ---
	        with open(file_path, "w", encoding="utf-8") as f:
	            json.dump(final_data, f, indent=4)
	            print(f"✅ Stored {game_night_date} with events in {self.game_nights_folder}")


	def set_synergies(self):
		self.gamers = synergies.enrich_gamers_with_synergies(self.gamers)
		for g in self.gamers:
			decoded_bans = []
			decoded_combos = []
			decoded_anti_combos = []
			for ban in g.ban_list:
				banned = self.get_hero_from_id(ban["hero_id"])
				ban["name"] = self.secure_name(banned["transformations"][0]["name"])
				ban["role"] = banned["role"]
				decoded_bans.append(ban)
			for combo in g.combo_list:
				others = []
				played_hero = self.get_hero_from_id(combo["player_hero"])
				combo["player_hero_name"] = self.secure_name(played_hero["transformations"][0]["name"])
				combo["player_role"] = played_hero["role"]
				for other in combo["hero_combos"]:
					add = self.get_hero_from_id(other)
					others.append({"hero":self.secure_name(add["transformations"][0]["name"]),"role":add["role"]})

				combo["hero_combos"] = others
				decoded_combos.append(combo)
			g.combo_list = decoded_combos
			g.ban_list = decoded_bans

			for combo in g.anti_combo_list:
				others = []
				played_hero = self.get_hero_from_id(combo["player_hero"])
				combo["player_hero_name"] = self.secure_name(played_hero["transformations"][0]["name"])
				combo["player_role"] = played_hero["role"]
				for other in combo["hero_combos"]:
					others.append(other)
				combo["hero_combos"] = others
				decoded_anti_combos.append(combo)

			g.combo_list = decoded_combos
			g.ban_list = decoded_bans
			g.anti_combo_list = decoded_anti_combos

			# Add the role-hero synergy analysis
			best_role_synergies, worst_role_synergies = self.analyze_role_hero_synergies(g)
			g.best_role_synergies = best_role_synergies
			g.worst_role_synergies = worst_role_synergies


	def analyze_role_hero_synergies(self, g):
	    """
	    Determines how specific heroes in different roles impact the player's win rate.
	    """
	    role_hero_synergy = defaultdict(lambda: {"games": 0, "wins": 0})

	    # Go through all the best and worst synergy combos
	    for combo in g.combo_list + g.anti_combo_list:
	        player_role = combo["player_role"]
	        
	        for teammate in combo["hero_combos"]:
	            # 🔥 Ensure `teammate` is a dictionary
	            if isinstance(teammate, int):
	                # Convert hero ID to hero name & role
	                hero_data = self.get_hero_from_id(teammate)
	                if hero_data:
	                    teammate = {"hero": hero_data["transformations"][0]["name"], "role": hero_data["role"]}
	                else:
	                    continue  # Skip if hero lookup fails

	            # Now `teammate` is guaranteed to be a dictionary
	            team_hero = teammate["hero"]
	            team_role = teammate["role"]

	            role_hero_synergy[(player_role, team_hero)]["games"] += combo["games_played"]
	            role_hero_synergy[(player_role, team_hero)]["wins"] += (combo["win_percent"] / 100) * combo["games_played"]

	    # Process the insights
	    insights = []
	    for (player_role, team_hero), stats in role_hero_synergy.items():
	        win_rate = (stats["wins"] / stats["games"]) * 100 if stats["games"] else 0

	        insights.append({
	            "player_role": player_role,
	            "supporting_hero": team_hero,
	            "games_played": stats["games"],
	            "win_percent": round(win_rate, 1)
	        })

	    # Sort by highest and lowest win rates for insights
	    insights.sort(key=lambda x: x["win_percent"], reverse=True)

	    return insights[:10], insights[-10:]  # Return best and worst role-hero synergies 

	def compute_kpi_records(self, records_location="records.json"):

	    folder = self.game_nights_folder
	    """
	    This function loops through JSON files in a folder, computes various KPIs,
	    and keeps track of the highest and lowest values for each metric.
	    It then writes the structured records into a records.json file.
	    """
	    # Define the metrics we want to track.
	    # For soloqueue we compute a win rate per player.
	    metrics = [
	        "total_wins",
	        "total_losses",
	        "match_count",
	        "win_rate",
	        "KDA",
	        "total_damage",
	        "total_healing",
	        "total_tanked",
	        "soloqueue"  # soloqueue metric will be the solo win rate per player.
	    ]
	    
	    # Initialize a dictionary to hold records for each metric.
	    records = {metric: {"highest": None, "lowest": None} for metric in metrics}
	    
	    # Additional custom metric: difference between wins and losses.
	    records["win_loss_diff"] = {"highest": None, "lowest": None}
	    
	    def update_record(metric_name, value, formatted_date, title, extra_data=None):
	        """
	        Updates the record for a given metric if the current value is higher or lower than the recorded ones.
	        extra_data can include additional fields like the player's name.
	        """
	        current = records[metric_name]
	        if extra_data is None:
	            extra_data = {}
	        # Update highest record if this is the first value or if the new value is greater.
	        if current["highest"] is None or value > current["highest"]["value"]:
	            current["highest"] = {
	                "direction": "highest",
	                "metric": metric_name,
	                "date": formatted_date,
	                "title": title,
	                "value": value,
	            }
	            current["highest"].update(extra_data)
	        # Update lowest record if this is the first value or if the new value is lower.
	        if current["lowest"] is None or value < current["lowest"]["value"]:
	            current["lowest"] = {
	                "direction": "lowest",
	                "metric": metric_name,
	                "date": formatted_date,
	                "title": title,
	                "value": value,
	            }
	            current["lowest"].update(extra_data)
	    
	    # Loop over files in the folder.
	    for filename in os.listdir(folder):
	        if filename.endswith('.json') and filename != 'happenings.json':
	            filepath = os.path.join(folder, filename)
	            with open(filepath, 'r') as f:
	                try:
	                    data = json.load(f)
	                except json.JSONDecodeError:
	                    print(f"Error decoding {filename}. Skipping...")
	                    continue
	            
	            # Format the date as dd.mm.yyyy (input date is expected as yyyy-mm-dd).

	            date_parts = data.get("date", "").split('-')
	            formatted_date = f"{date_parts[2]}.{date_parts[1]}.{date_parts[0]}" if len(date_parts) == 3 else "Unknown"
	            
	            # Use the AI title if available.
	            title = self.remove_html_tags(data.get("AI_title", ""))
	            
	            # Extract raw KPIs.
	            total_wins = data.get("total_wins", 0)
	            total_losses = data.get("total_losses", 0)
	            match_count = data.get("match_count", 1)  # Prevent division by zero.
	            
	            win_rate = total_wins / match_count if match_count else 0
	            total_kills = data.get("total_kills", 0)
	            total_assists = data.get("total_assists", 0)
	            total_deaths = data.get("total_deaths", 1)  # Avoid division by zero.
	            kda = (total_kills + total_assists) / total_deaths
	            
	            total_damage = data.get("total_damage", 0)
	            total_healing = data.get("total_healing", 0)
	            total_tanked = data.get("total_tanked", 0)
	            
	            # Additional custom metric: win-loss difference.
	            win_loss_diff = total_wins - total_losses
	            
	            # Update records for the standard metrics.
	            update_record("total_wins", total_wins, formatted_date, title)
	            update_record("total_losses", total_losses, formatted_date, title)
	            update_record("match_count", match_count, formatted_date, title)
	            update_record("win_rate", win_rate, formatted_date, title)
	            update_record("KDA", kda, formatted_date, title)
	            update_record("total_damage", total_damage, formatted_date, title)
	            update_record("total_healing", total_healing, formatted_date, title)
	            update_record("total_tanked", total_tanked, formatted_date, title)
	            update_record("win_loss_diff", win_loss_diff, formatted_date, title)
	            
	            # Process soloqueue: compute the solo win rate for each player.
	            soloqueue = data.get("soloqueue", [])
	            solo_data = {}
	            for entry in soloqueue:
	                player = entry.get("player")
	                if player:
	                    if player not in solo_data:
	                        solo_data[player] = {"wins": 0, "games": 0}
	                    solo_data[player]["games"] += 1
	                    if entry.get("win", False):
	                        solo_data[player]["wins"] += 1
	            
	            # Update records for soloqueue for each player in this file.
	            for player, stats in solo_data.items():
	                solo_win_rate = stats["wins"] / stats["games"] if stats["games"] > 0 else 0
	                update_record("soloqueue", solo_win_rate, formatted_date, title, extra_data={"player": player})
	    
	    # Save the records dictionary to a file named records.json.
	    with open(records_location, "w") as outfile:
	        json.dump(records, outfile, indent=4)
	    
	    print(f"Records saved!")

	def debug(self):
		self.set_synergies()
		n = 0
		for g in self.gamers:
			x = """
			print("")
			print(g.nickname)
			print("Ban list")
			print(g.ban_list)
			print("Combo list")
			print(g.combo_list)
			print("Anti Combo list")
			print(g.anti_combo_list)
			print("Best role synergies")
			print(g.best_role_synergies)
			print("Worst role synergies")
			print(g.worst_role_synergies)"""


if __name__ == '__main__':

	gamers = gamerlist
	game_nights_folder = "./game_nights/"

	for arg in sys.argv:
		if arg == "--bronze":
			gamers = gamerlist_bronze
			game_nights_folder = "./game_nights_bronze/"

	g_master = Gamer_master(gamers,game_nights_folder=game_nights_folder)


	
	g_master.initiate()
	g_master.export_data_objects()
	g_master.compute_kpi_records()
	g_master.debug()
