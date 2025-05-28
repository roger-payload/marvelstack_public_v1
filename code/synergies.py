import json
import os
import itertools
from collections import defaultdict

def record_synergy(pick_stats, player_hero, team_heroes, match_won):
    """
    Records synergy data for a player's hero with other team picks.
    We consider:
    - The player's hero alone.
    - The player's hero + each teammate (2-hero synergy).
    - The player's hero + 2 teammates (3-hero synergy).
    """
    if not player_hero:
        return
    
    for subset_size in range(1, 3):  # Create 2-hero and 3-hero combos
        for combo in itertools.combinations(team_heroes, subset_size):
            full_combo = frozenset([player_hero] + list(combo))
            pick_stats[full_combo]["games"] += 1
            if match_won:
                pick_stats[full_combo]["wins"] += 1

def analyze_player_synergy(matches_json, gamer):
    """
    Analyzes hero synergy specific to a given player's hero picks.
    :param matches_json: list of match objects (each a dict).
    :param gamer: The player's object (with .id attribute).
    :return: dict mapping hero combos to synergy stats + ban stats.
    """
    pick_stats = defaultdict(lambda: {"games": 0, "wins": 0})
    ban_stats = defaultdict(lambda: {"bans": 0, "win_when_banned": 0})

    for match in matches_json:
        details = match["match_details"]
        if details:
            match_players = details["match_players"]

            # 🔍 Find the player's data in the match
            gamer_data = next((p for p in match_players if p["player_uid"] == gamer.id), None)
            if not gamer_data:
                continue  # Player wasn't in this match, skip

            player_side = gamer_data["camp"]
            match_won = gamer_data["is_win"] == 1  # 1 means win, 0 means loss

            # 🔍 Find the player's **most played hero** in the match
            if not gamer_data.get("player_heroes"):
                continue  # No hero data, skip

            player_hero = max(gamer_data["player_heroes"], key=lambda h: h["play_time"])["hero_id"]

            # 🔍 Collect the player's **team heroes**
            team_heroes = [
                p["cur_hero_id"] for p in match_players if p["camp"] == player_side and p["player_uid"] != gamer.id
            ]

            # 🔥 Record synergy
            record_synergy(pick_stats, player_hero, team_heroes, match_won)

            # 🔍 Track bans & match outcome (Simplified)
            for bp in details.get("dynamic_fields", {}).get("ban_pick_info", []):
                if bp["is_pick"] == 0:  # If it's a ban
                    banned_hero = bp["hero_id"]
                    ban_stats[banned_hero]["bans"] += 1
                    if match_won:
                        ban_stats[banned_hero]["win_when_banned"] += 1

    return pick_stats, ban_stats


def print_player_synergy_results(player, pick_stats, ban_stats, min_games=0, top_n=20):
    """
    Processes synergy, anti-synergy, and ban stats, returning structured lists as dictionaries.
    - Synergy (best combos)
    - Anti-synergy (worst combos)
    - Ban effectiveness
    """
    combos_list = []
    
    for combo, stat in pick_stats.items():
        games = stat["games"]
        wins = stat["wins"]
        if games >= min_games:
            win_rate = (wins / games) * 100 if games else 0

            combo_list = sorted(list(combo))  # Convert frozenset to sorted list
            
            # Ensure the player's hero is in the combo
            player_hero = None
            for hero_id in combo_list:
                for top_hero in player.top_heroes:
                    if hero_id == top_hero["hero_id"]:  # Check player's known played heroes
                        player_hero = hero_id
                        break

            if not player_hero:
                #print(f"⚠️ Warning: No played hero found in combo {combo_list} for {player.nickname}")
                continue  # Skip incorrect data

            # Remove the player's hero from the teammates list
            other_heroes = [h for h in combo_list if h != player_hero and h != 0]

            combos_list.append({
                "player_hero": player_hero,
                "hero_combos": other_heroes,
                "games_played": games,
                "win_percent": round(win_rate, 1),
                "combo": combo,
                "next_id": next(hero for hero in combo if hero != player_hero)
            })

    # Sort for best synergies (top win rates)
    combos_list.sort(key=lambda x: x["games_played"], reverse=True)
    combos_list_top = combos_list[:top_n]
    combos_list_top.sort(key=lambda x: x["win_percent"], reverse=True)

    # Sort for worst synergies (bottom win rates)
    anti_combo_list = sorted(combos_list, key=lambda x: x["win_percent"])[:top_n]

    # Process ban stats
    ban_list = []
    for hero_id, stat in ban_stats.items():
        if stat["bans"] >= min_games:
            win_rate = (stat["win_when_banned"] / stat["bans"]) * 100 if stat["bans"] else 0

            ban_list.append({
                "hero_id": hero_id,
                "bans": stat["bans"],
                "win_percent": round(win_rate, 1)
            })

    # Sort ban list by win rate (desc)
    ban_list.sort(key=lambda x: x["win_percent"], reverse=True)
    ban_list_top = ban_list[:top_n]


    return combos_list_top, ban_list_top, anti_combo_list





def load_match_data(match_uid, gamer_dir):
    """
    Loads a match JSON file given its UID.
    """
    match_filename = f"{match_uid}.json"
    match_path = os.path.join(gamer_dir, match_filename)
    if not os.path.exists(match_path):
        return None

    with open(match_path, "r") as f:
        return json.load(f)

def build_match_array(latest_comp_file, gamer_dir):
    """
    Builds an array of full match data from a player's history file.
    """
    with open(latest_comp_file, "r") as f:
        data = json.load(f)
        match_list = data.get("match_history", [])

    matches = []
    for m in match_list:
        match_uid = m["match_uid"]
        match_data = load_match_data(match_uid, gamer_dir)
        if match_data:
            matches.append(match_data)
        else:
            print(f"Warning: No JSON file found for match_uid={match_uid}")

    return matches

def enrich_gamers_with_synergies(gamers):
    for g in gamers:
        gamer_dir = f"../profiles/{g.nickname}"
        comp_file = os.path.join(gamer_dir, "latest_comp_games.json")

        # Load full match history
        full_matches = build_match_array(comp_file, gamer_dir)

        # Analyze hero synergy for this player
        player_synergy, ban_synergy = analyze_player_synergy(full_matches, g)

        # Print the best synergy picks and ban effectiveness
        combo_list, ban_list, anti_combo_list = print_player_synergy_results(g, player_synergy, ban_synergy, min_games=2, top_n=10)
        g.combo_list = combo_list
        g.anti_combo_list = anti_combo_list
        g.ban_list = ban_list
    return gamers