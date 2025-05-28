import random
from decouple import config

api_key = config("MARVEL_RIVALS_KEY")
headers = {
	"x-api-key": api_key
}

# All the options below rely on a valid API key for OpenAI, and active credits. It's very cheap though. 
# Maybe try it for 10 USD, it will last you a LONG time.

ai_enabled = False # Should AI give feedback to each player based on their performances?

# python3 ./html_gen.py; git add ../.; git commit -am "Hotfix"; git push; ssh marvelstack@login.domeneshop.no "bash ~/housekeeping.sh";

squadname = ""
site = "" # Used to point to images and other files hosted on site

# Config file for MarvelStack

premium_member = True
base_api = "https://marvelrivalsapi.com/api/v1/"
base_api_v2 = "https://marvelrivalsapi.com/api/v2/"
base_image_api = "https://marvelrivalsapi.com"
current_season = 2
match_limit = 40
average_match_time = 15 * 60 # How long do you consider an average match (15 by default)? we calculate stomps/struggles from this, for the timeline
game_mode = 2 # 2 = Comp
rate_limiter = 5 # For getting matches
time_zone = "Europe/Oslo" # What timezone you are in locally
api_time_zone = "America/New_York" # What timezone the API returns, so we know how to convert


gamerlist = ["zEagleModdz","zKaiju","Zimmons","PaLANator","Xalteros"] # Input the members of your stack
role_lock = {} # If you want to lock any players to a specific role for their player cards.

# This is a bit nitty gritty since it uses hero_id and costume_id, but set it here to make correct skins show up for gamers/heroes
# WARNING!! Skins dont alway retain ID, sometimes they are shuffled around when new ones release.
# So if you're unsure, just delete all costumes in /img/heroes for a hero that has a new skin released, and download new assets, to get correct ID's.
costume_attachments = {

}

gamerlist_bronze = [] # Input the members of your alt stack if you have one


gamer_card_hero_count = 6 # How many heroes do you want displayed in the profile card on site, at a max.
rank_history_count = 20 # How far back should the Rank Score chart show metrics.
stack_score_count = 14 # How many matches to show for hero scores
# Used to decide how light to "push" the player colors extracted from their profile avatars.
color_threshold = 400
default_banner = "30000001_banner.webp"
default_player_head = "30000001.png"

# Polling is a bit odd. Since a player may have no new matches since the last update request,
# it is impossible to know if there is still a reason to wait for new data, or accept the data currently being
# returned. Usually waiting for about 10 minutes is enough, so we use 15 minutes by default to make sure.
polling_rate = 1 * 60 # We poll every n minutes + wait an intitial n minutes after first refresh
timeout = 5 * 60 # We poll for n minutes before accepting the data.
# for matches
update_rate = 16 # How old can data be before we need to refresh it, in hours.
API_RETRIES = 5  # How many times to retry API calls after the initial failure
RETRY_DELAY_SECONDS = 10 # How many seconds to wait between retries


rank_chart_break_points = [3000,3300,3600,3900,4200,4500,4800,5100] # Corresponds to each SR rank tier, from Bronze to Eternity
rank_chart_break_points_names = ["Bronze","Silver","Gold","Platinum","Diamond","Grandmaster","Celestial","Eternity"] # Names for rank annotations
rank_chart_break_points_colors = ["sandybrown","silver","gold","powderblue","#1680FF","#EB46FF","#d15438","hotpink"] # Colors for ranks
display_chart_rank_names = False # Looks clean without, but you might want to show the rank name. Feel free to rename then as well, "Wood league" is popular.
profile_dir = "../profiles"

level_to_rank_map = {
    "1": "Bronze III",
    "2": "Bronze II",
    "3": "Bronze I",
    "4": "Silver III",
    "5": "Silver II",
    "6": "Silver I",
    "7": "Gold III",
    "8": "Gold II",
    "9": "Gold I",
    "10": "Platinum III",
    "11": "Platinum II",
    "12": "Platinum I",
    "13": "Diamond III",
    "14": "Diamond II",
    "15": "Diamond I",
    "16": "Grandmaster III",
    "17": "Grandmaster II",
    "18": "Grandmaster I",
    "19": "Celestial III",
    "20": "Celestial II",
    "21": "Celestial I",
    "22": "Eternity",
    "23": "One Above All",
}


# Top performances to show in "Biggest Number section"
performances = ["total_hero_damage","total_damage_taken","total_hero_heal"]

matchup_threshold = 5 # How many matches must a player at least have against someone to show up in Matchups section
minimum_time_played_to_count_match = 2 * 60 # I reccomend having at least played a hero for 2 minutes to count it towards a match score

# How do we normalize each category scoring when generating a performance score?
CATEGORY_MAX_POINTS = 20 # With 1500, each category maxes out at that score. Adapt as you wish, purely cosmetic.
# For star ratings
# Define reasonable max values for each stat
MAX_STAT_VALUES = {
	"default": {
		"score": 95,
		"win_rate": 0.65,  # Scales between 0-1 (100%)
		"kda": 5.0,
		"tanking_per_minute": 1500,
		"damage_per_minute": 1500,
		"healing_per_minute": 1500,
		"kills_per_minute": 2.0,
		"assists_per_game": 10,
		"deaths_per_game": 8
	},
	"Vanguard": {
		"score": 95,
		"win_rate": 0.65,
		"kda": 5.0,
		"tanking_per_minute": 2700,  # Higher cap for tanking
		"damage_per_minute": 1200,  # Lower priority on damage
		"healing_per_minute": 1000,
		"kills_per_minute": 1.7,
		"assists_per_game": 5.5,
		"deaths_per_game": 8
	},
	"Strategist": {
		"score": 95,
		"win_rate": 0.65,
		"kda": 4.5,
		"tanking_per_minute": 1000,  # Lower tanking
		"damage_per_minute": 800,  # Lower damage
		"healing_per_minute": 2000,  # Higher healing cap
		"kills_per_minute": 1.5,
		"assists_per_game": 30,
		"deaths_per_game": 8
	},
	"Duelist": {
		"score": 95,
		"win_rate": 0.65,
		"kda": 5.0,  # Higher KDA expectation
		"tanking_per_minute": 800,  
		"damage_per_minute": 1900,  # Higher damage cap
		"healing_per_minute": 1000,
		"kills_per_minute": 1.8,  # Higher expected kills
		"assists_per_game": 8,
		"deaths_per_game": 8
	}
}

# MAKE SURE THE ROLE CATEGORY ARRAYS ARE THE SAME LENGTH!!
ROLE_SCORING_CATEGORIES = {
	"Vanguard": ["tanking_per_minute", "win_rate", "kda", "assists_per_game", "deaths_per_game"],
	"Strategist": ["healing_per_minute", "win_rate", "kda", "assists_per_game", "deaths_per_game"],
	"Duelist": ["damage_per_minute", "win_rate", "kda", "kills_per_minute", "deaths_per_game"],
	"default": ["win_rate","kda","tanking_per_minute","damage_per_minute","healing_per_minute","kills_per_minute","assists_per_game","deaths_per_game"] 
}
scoring_leeway = .95 # Makes it so that a perfect performance is 10% away from an ACTUAL perfect performance
player_max_score = (len(ROLE_SCORING_CATEGORIES["default"]) * CATEGORY_MAX_POINTS) * scoring_leeway - 2500
hero_max_score = (len(ROLE_SCORING_CATEGORIES["Vanguard"]) * CATEGORY_MAX_POINTS) * scoring_leeway



# If you want custom icons or styles for the feedbacks in profile cards, you can edit this.
# It *should* adapt to any number of discrete steps you want. It is 1-5 stars by default (5 steps).
STAR_ICONS = [
    """<span style="color:#cd4242;"><i class='ri-star-fill'></i></span>""",
    """<i class='ri-star-fill'></i><i class='ri-star-fill'></i>""",
    """<i class='ri-star-fill'></i><i class='ri-star-fill'></i><i class='ri-star-fill'></i>""",
    """<i class='ri-star-fill'></i><i class='ri-star-fill'></i><i class='ri-star-fill'></i><i class='ri-star-fill'></i>""",
    """<span style="color:#db9a34;"><i class='ri-star-fill'></i><i class='ri-star-fill'></i><i class='ri-star-fill'></i><i class='ri-star-fill'></i><i class='ri-star-fill'></i></span>""",
]
MAX_STEPS = len(STAR_ICONS) - 1  # 5-star system

# Configuration dictionary for sentiment messages.
TOAST_MESSAGES = [
	"completely crushed it in",
	"outperformed yourself in",
	"set a new standard in",
	"blazed a trail of excellence in",
	"dominated the field in",
	"left everyone in awe in",
	"elevated your game to epic levels in",
	"turned game night into a masterclass in"
]

ABOVE_MESSAGES = [
	"did solidly in",
	"made your coach proud in",
	"raised your game in",
	"performed exceptionally in",
	"surpassed expectations in",
	"showed off a top-tier performance in",
	"stepped up significantly in",
	"proved you can excel in"
]

NEUTRAL_MESSAGES = [
	"held your ground in",
	"performed as expected in",
	"kept it steady in",
	"matched your usual form in",
	"stayed consistent in",
	"did exactly what you normally do in",
	"maintained your standard in",
	"showed up reliably in"
]

BELOW_MESSAGES = [
	"struggled a bit in",
	"had some rough games in",
	"fell short in",
	"didn't quite hit the mark in",
	"underperformed in",
	"couldn't find your usual spark in",
	"had an off night in",
	"let your guard down in"
]

ROAST_MESSAGES = [
	"were a disaster in",
	"completely embarrassed yourself in",
	"had a night to forget in",
	"turned the evening into a farce in",
	"left everyone questioning your skills in",
	"showed an utterly off performance in",
	"made it a night to regret in",
	"set a new low in"
]
class Bcol:
	HEADER = '\033[95m'
	OKBLUE = '\033[94m'
	OKCYAN = '\033[96m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	FAIL = '\033[91m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'