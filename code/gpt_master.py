import os
import json
import sys
import re

from gpt import GPT
from collections import defaultdict
from datetime import datetime

from config import player_max_score, hero_max_score, squadname, ai_enabled



def get_hero_feedback(hero_data):
	"""
	Evaluates a hero's performance based on score percentage of max possible score.
	Returns a feedback statement.
	"""
	# Compute percentage of max score
	score_percentage = (hero_data["score"] / hero_max_score) * 100

	# New tier distribution (compressed towards 30%-100%)
	tiers = [
		(95, "SS-Tier: Absolute Godlike Domination! A performance worthy of legend."),
		(90, "S-Tier: Unstoppable! Nearly perfect execution!"),
		(80, "A-Tier: Outstanding! A powerful showing."),
		(70, "B-Tier: Very strong! A force to be reckoned with."),
		(60, "C-Tier: Above average! Solid performance."),
		(50, "D-Tier: Decent, but could be better."),
		(40, "E-Tier: Struggled to make an impact."),
		(35, "F-Tier: Underwhelming. Something went wrong."),
		(30, "G-Tier: Catastrophic! Needs massive improvement."),
		(0, "H-Tier: Almost nonexistent performance.")
	]

	# Determine the tier
	for threshold, message in tiers:
		if score_percentage >= threshold:
			return f"{hero_data['name']} ({hero_data['role']}): {message} ({score_percentage:.1f}% of max)"

	# Fallback (should never hit)
	return f"{hero_data['name']} ({hero_data['role']}): No valid score data."


def get_player_feedback(player_data):
	"""
	Evaluates a player's overall performance across all heroes.
	Returns a feedback statement.
	"""
	# Compute percentage of max score
	score_percentage = (player_data["score"] / player_max_score) * 100

	# New compressed tier distribution
	tiers = [
		(90, f"SS-Tier: Galactic Overlord! This is the peak of {squadname}."),
		(80, "S-Tier: Dominant performance! Completely outclassed the competition."),
		(80, "A-Tier: Exceptional! Played a crucial role in the team's success."),
		(70, "B-Tier: Very strong contribution! Solid all around."),
		(60, "C-Tier: Above average! Held their ground well."),
		(50, "D-Tier: Decent, but left room for improvement."),
		(40, "E-Tier: Struggled to impact the game."),
		(35, "F-Tier: Had a tough night. Needs to step up."),
		(30, "G-Tier: Poor showing. The squad needed more."),
		(0, "H-Tier: Did they even play? 😂")
	]

	# Determine the tier
	for threshold, message in tiers:
		if score_percentage >= threshold:
			return f"{player_data['nickname']}: {message} ({score_percentage:.1f}% of max)"

	# Fallback
	return f"{player_data['nickname']}: No valid score data."


def format_game_night_summary(game_night_data,records_location="records.json"):

	recordsfile = os.path.join(records_location)
	records = ""
	# Read the JSON file
	print(recordsfile)
	if os.path.exists(recordsfile):
		with open(recordsfile, "r", encoding="utf-8") as f:
			records = json.load(f)

	if records != "":
		formatted_records = f"\r\n(for context) Highest and lowest achieved metrics by {squadname}:\r\n"
		for key,value in records.items():
			formatted_records += f"\r\n- {key} : {value}"
	records = formatted_records
	"""
	Transforms raw game night stats into a structured text summary
	that Galacta can process and comment on.
	"""

	date = game_night_data["date"]
	total_matches = game_night_data["match_count"]
	total_wins = game_night_data["total_wins"]
	total_losses = game_night_data["total_losses"]
	total_kills = game_night_data["total_kills"]
	total_deaths = game_night_data["total_deaths"]
	total_assists = game_night_data["total_assists"]
	total_damage = game_night_data["total_damage"]
	total_healing = game_night_data["total_healing"]
	total_tanked = game_night_data["total_tanked"]
	soloqueue_games = game_night_data["soloqueue"]
	players = game_night_data["players"]

	# === 🧠 Smart Analysis ===
	winrate = total_wins / total_matches if total_matches > 0 else 0
	kda = (total_kills + total_assists) / total_deaths if total_deaths > 0 else total_kills + total_assists

	# Classify the night’s performance
	if winrate >= 0.7:
		overall_performance = f"{squadname} was UNSTOPPABLE! A total massacre!"
	elif winrate >= 0.5:
		overall_performance = "A respectable night. The forces of chaos were balanced."
	elif winrate >= 0.3:
		overall_performance = "Not the best showing. Perhaps the villains had their day?"
	else:
		overall_performance = "A night of brutal losses. This will be remembered."

	solo_summary = ""

	# ✅ Process Solo Queue Stats
	if len(soloqueue_games) > 0:
		solo_stats = {}  # Store player-based solo queue stats

		for game in soloqueue_games:
			player = game["player"]
			win = game["win"]

			# Initialize player's solo stats if not present
			if player not in solo_stats:
				solo_stats[player] = {"matches": 0, "wins": 0}

			# Update solo stats
			solo_stats[player]["matches"] += 1
			if win:
				solo_stats[player]["wins"] += 1

		# ✅ Generate Solo Queue Summary
		solo_warriors = []
		solo_losers = []

		for player, stats in solo_stats.items():
			win_rate = (stats["wins"] / stats["matches"]) * 100 if stats["matches"] > 0 else 0
			solo_stats[player]["win_rate"] = round(win_rate, 1)  # Store win rate (rounded to 1 decimal)

			if win_rate >= 50:  # Classify as a "Solo Queue Warrior" if win rate is decent
				solo_warriors.append(f"{player} ({stats['wins']}/{stats['matches']} wins, {win_rate}%)")
			else:
				solo_losers.append(f"{player} ({stats['wins']}/{stats['matches']} wins, {win_rate}%)")

		# ✅ Construct Summary Text
		solo_summary = "Someone went on soloqueue games, comepletely without the squad. How did that go??\r\n"
		if solo_warriors:
			solo_summary += f"\n🏆 Solo queue warriors: {', '.join(solo_warriors)} emerged victorious in their lonely battles! HOW DO YOU DO IT SOLO? THATS SICK!!"
		if solo_losers:
			solo_summary += f"\n💀 Painful solo losses for: {', '.join(solo_losers)}. Absolutely embarrassing! Who let bro cook?? WHY DO YOU QUEUE ALONE!?"

	# The solo_summary can now be added to the AI prompt or game night summary.


	# Individual player highlights
	player_highlights = ""
	highest_scorer = max(players, key=lambda p: p["score"], default=None)
	worst_performer = min(players, key=lambda p: p["score"], default=None)

	if highest_scorer:
		player_highlights += f"\n🌟 MVP of the night: {highest_scorer['nickname']} with {highest_scorer['score']} points!"
	if worst_performer:
		if worst_performer["score"] < 3500:
			player_highlights += f"\n💀 Horrible night by: {worst_performer['nickname']} with only {worst_performer['score']} points. So rough."

	# === 📝 Final Summary ===
	game_night_summary = f"""
=== THESE WERE THE EVENTS IN ORDER ===
{game_night_data["events"]}

=== GAME NIGHT REPORT: {date} ===

{overall_performance}

🔥 The squad fought in {total_matches} matches, securing {total_wins} wins and suffering {total_losses} losses.
⚔️ They racked up {total_kills} eliminations and {total_assists} assists.
💀 However, they also took {total_deaths} deaths.
🩹 Total healing done: {total_healing:,}, while tanks absorbed {total_tanked:,} damage.

{solo_summary}
{player_highlights}
{records}
"""
	game_night_summary += "Player performances:\r\n"
	for g in game_night_data["players"]:
		game_night_summary += f"- {get_player_feedback(g)}\r\n"
		game_night_summary += "They played these characters:\r\n"
		for hero in g["heroes"]:
			game_night_summary += f"  - {get_hero_feedback(hero)}\r\n"

	return game_night_summary.strip()

def format_personal_summary(player_data, game_night_date):
	"""
	Generates a structured summary of a player's performance, including:
	- General performance feedback
	- Role distribution (time spent per role)
	- Hero feedback for each character they played
	- Analysis of secondary hero swaps
	"""
	nickname = player_data["nickname"]
	score = player_data["score"]
	kda = (player_data["kills"]+player_data["assists"]) / player_data["deaths"]
	winrate = (player_data["wins"] / (player_data["wins"]+player_data["losses"])) * 100
	heroes = player_data["heroes"]
	secondaries = player_data.get("secondaries", [])

	# Compute role distribution
	role_playtime = defaultdict(float)
	total_seconds_played = 0

	for hero in heroes:
		role_playtime[hero["role"]] += hero["seconds_played"]
		total_seconds_played += hero["seconds_played"]

	# Determine primary role based on most playtime
	if role_playtime:
		main_role = max(role_playtime, key=role_playtime.get)
		main_role_time = role_playtime[main_role]
		main_role_percentage = (main_role_time / total_seconds_played) * 100
	else:
		main_role = "Unknown"
		main_role_percentage = 0

	# Analyze secondary hero usage
	swap_count = len(secondaries)

	# Determine if they "one-tricked" their main
	if swap_count == 0:  # Less than 1 min in secondaries
		secondary_analysis = f"{nickname} was a **one-trick specialist**, sticking to one hero per match!"
	elif swap_count >= 3:
		secondary_analysis = f"{nickname} experimented with **{swap_count} different heroes**, staying flexible!"
	else:
		secondary_analysis = f"{nickname} played secondaries but mostly focused on their main."
	if swap_count > 0:
		secondary_analysis += "\r\nSecondaries for this player:\r\n"
		for hero in secondaries:
			secondary_analysis += f"- {hero["name"]} with {hero["kills"]}/{hero["deaths"]}/{hero["assists"]} kda"

	# Generate feedback using helper functions
	player_feedback = get_player_feedback(player_data)
	hero_feedback = "\n".join(get_hero_feedback(hero) for hero in heroes)

	# Format the full structured summary
	return f"""
=== GAME NIGHT REPORT: {game_night_date} ===

🎮 Player: {nickname}
🏆 Overall Performance: {player_feedback}

🔹 **Primary Role**: {main_role} ({main_role_percentage:.1f}% of playtime)
🔹 **Role Breakdown**: {", ".join(f"{role}: {int(time/60)} min" for role, time in role_playtime.items())}
🔹 **Hero Performance**:
{hero_feedback}

🔄 **Hero Swaps**: {swap_count} swaps
{secondary_analysis}
"""


def extract_json_from_response(response):
	"""
	Parses the JSON content from the AI response.
	"""
	try:
		# Extract message content
		messages = response.data  # Extract list of messages from response object
		for message in messages:
			if message.role == "assistant":
				raw_text = message.content[0].text.value.strip()
				if raw_text.startswith("```json"):
					raw_text = raw_text.replace("```json", "").replace("```", "").strip()
				return json.loads(raw_text.replace("—"," — "))
	except Exception as e:
		print(f"❌ Failed to parse AI response: {e}")
		return {"title": "Unknown Game Night", "content": "AI response could not be processed."}

def process_game_nights(game_night_folder="./game_nights/", records_location="records.json",test=False, force_personal=False, force_general=False, only_this=False):
	"""
	Loops through all game night JSON files and enhances them with AI insights
	if they haven't already been processed.
	"""

	gpt = GPT(test=test)  # Set to True for testing, False for real AI calls
	# Loop through all game night JSON files
	if not test:
		get_latest_tts()
	for filename in os.listdir(game_night_folder):
		if filename.endswith(".json") and not filename == "happenings.json":
			if only_this:
				if filename != only_this:
					continue
			file_path = os.path.join(game_night_folder, filename)

			# Read the JSON file
			with open(file_path, "r", encoding="utf-8") as f:
				game_night_data = json.load(f)

			# =============================== 🟢 General Game Night Summary ===============================
			if not game_night_data.get("AI_enhanced") or force_general:
				print(f"🚀 Enhancing {filename} with AI insights...")
				game_night_summary = format_game_night_summary(game_night_data,records_location=records_location)
				if ai_enabled:
					ai_response = gpt.create_game_night_summary(game_night_summary)
				# Extract JSON data from the AI response
				if not test:
					if ai_enabled:
						parsed_response = extract_json_from_response(ai_response)
					
						game_night_data["AI_title"] = parsed_response.get("title", "")
						if game_night_data["AI_title"] == "":
							game_night_data["AI_title"] = parsed_response.get("wtf", "This went bad, Butler is giving you all the content so bro can bugfix: "+str(parsed_response))
						game_night_data["AI_summary"] = parsed_response.get("content", "")
						if game_night_data["AI_summary"] == "":
							game_night_data["AI_summary"] = parsed_response.get("verdict", "This went bad, Butler is giving you all the content so bro can bugfix: "+str(parsed_response))
						game_night_data["AI_enhanced"] = True  # Mark file as enhanced
						print(f"✅ {filename} now has a general AI summary!")
					else:
						game_night_data["AI_title"] = ""
						game_night_data["AI_summary"] = game_night_summary
						game_night_data["AI_enhanced"] = True  # Mark file as enhanced
						print(f"✅ {filename} now has summary!")

				else:
					print(ai_response)

				# Store AI-generated title & summary

			# =============================== 🔵 Personal Player Summaries ===============================
			if not game_night_data.get("AI_personal_summaries") or force_personal:
				print(f"🚀 Generating AI summaries for players in {filename}...")
				game_night_data["personal_AI_summaries"] = []

				for player in game_night_data["players"]:
					print(f"🎮 Processing {player['nickname']}...")

					# Format personal summary for GPT
					personal_summary_prompt = format_personal_summary(player, game_night_data["date"])
					if ai_enabled:
						ai_response = gpt.create_personal_game_night_summary(personal_summary_prompt)

					# Extract JSON response
					if not test:
						if ai_enabled:
							parsed_response = extract_json_from_response(ai_response)

							content = parsed_response.get("content", "")
							if content == "":
								content = parsed_response.get("verdict", "")

							if content == "":
								print("ERROR BROTHER!!")
								print(parsed_response)

							# Store personal AI summary
							game_night_data["personal_AI_summaries"].append({
								"nickname": player["nickname"],
								"title": parsed_response.get("title", "AI did not return a title."),
								"content": content
							})
						else:
							game_night_data["personal_AI_summaries"].append({
								"nickname": player["nickname"],
								"title": "",
								"content": personal_summary_prompt
							})

					else:
						print(ai_response)

				# Mark file as having personal summaries
				game_night_data["AI_personal_summaries"] = True
				print(f"✅ {filename} now has personal AI summaries!")

			# =============================== 🔴 Save Updated File ===============================
			if not test:
				with open(file_path, "w", encoding="utf-8") as f:
					json.dump(game_night_data, f, indent=4)

				print(f"✅ {filename} fully processed!\n")
def remove_html_tags(text):
    clean = re.compile(r'<[^>]+>')
    return re.sub(clean, '', text)
def get_latest_tts(game_night_folder="./game_nights/",audio_folder="../audio/"):

	# Regex to match filenames like '2025_02_25.json'
	date_regex = re.compile(r'^(\d{4}_\d{2}_\d{2})\.json$')

	# List all files, skipping 'happenings.json', and collect date-based files
	date_files = [
		f for f in os.listdir(game_night_folder)
		if f != 'happenings.json' and date_regex.match(f)
	]

	# Sort files by actual dates extracted from filenames
	sorted_files = sorted(
		date_files,
		key=lambda x: datetime.strptime(date_regex.match(x).group(1), '%Y_%m_%d')
	)

	if not sorted_files:
		print("No valid game night files found.")
		return

	# Latest file
	latest_file = sorted_files[-1]
	latest_filename_without_ext = os.path.splitext(latest_file)[0]

	speech_file_path = f"{latest_filename_without_ext}.mp3"

	# Check if the TTS file already exists
	if not os.path.exists(audio_folder+speech_file_path):
		try:
			gpt = GPT(test=False)  # Set to True for testing, False for real AI calls
			with open(game_night_folder+latest_file, "r", encoding="utf-8") as f:
				game_night_data = json.load(f)

			with gpt.client.audio.speech.with_streaming_response.create(
				model="tts-1",
				voice="sage",
				input=remove_html_tags(game_night_data["AI_summary"])
				) as response:
					response.stream_to_file(audio_folder+speech_file_path)
			print(f"TTS created: {speech_file_path}")
		except Exception as e:
			print("Could not generate TTS:", e)
	else:
		print(f"TTS file already exists: {speech_file_path}")


if __name__ == '__main__':
	test = False
	if len(sys.argv) > 1:
		game_night_folder="./game_nights/"
		records_location="records.json"

		for arg in sys.argv:
			if arg == "--bronze":
				print("Handling BRONZE stuff now.")
				records_location="records_bronze.json"
				game_night_folder="./game_nights_bronze/"
			if arg == "--test":
				test = True

		print(f"Trying to force update on {sys.argv[1]}")
		# False means go, actually. If True is passed as param, that means test = True
		process_game_nights(game_night_folder=game_night_folder, records_location=records_location, test=test, force_personal=True, force_general=True, only_this=sys.argv[1])
	else:
		# False means go, actually. If True is passed as param, that means test = True
		process_game_nights(test=test, force_personal=False, force_general=False, only_this=False)

