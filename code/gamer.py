
import os
import re
import json
import math
import datetime
import colorsys

from config import profile_dir, time_zone, api_time_zone, color_threshold, ai_enabled, costume_attachments
from config import default_player_head, level_to_rank_map

from colorthief import ColorThief
from zoneinfo import ZoneInfo
from PIL import UnidentifiedImageError

class Gamer():

	def __init__(self, nickname):
		# Try to load the local data if it exists.
		filepath = profile_dir+"/{}/{}.json".format(nickname,nickname)
		self.latest_game_night_date = "2000-01-01" #Just initiate this to avoid AttributeErrors
		if os.path.exists(filepath):
			print(f"Loading {nickname}")
			with open(filepath, 'r') as f:
				cached_data = json.load(f)
			self.data = cached_data
		else:
			print("Tried loading a non-existing profile, exiting.")
			exit()
		
		filepath = "../img/player_heads/{}.png".format(self.data["player"]["icon"]["player_icon_id"])

		try:
			colors = self.extract_color(filepath)
		except UnidentifiedImageError:
			print(f"Error for {nickname}: Unable to identify the image file. The file might be corrupted or not a valid image.")
			colors = self.extract_color(f"../img/player_heads/{default_player_head}")

		if colors:

			self.color_light_r = str(colors["light"][0])
			self.color_light_g = str(colors["light"][1])
			self.color_light_b = str(colors["light"][2])

			self.color_dark_r = str(colors["dark"][0])
			self.color_dark_g = str(colors["dark"][1])
			self.color_dark_b = str(colors["dark"][2])
		else:
			print("Player head for "+nickname+" not collected yet.")


		self.nickname = nickname
		self.nickname_safe = self.nickname.replace("'","").replace(" ","")
		self.id = self.data["uid"]
		self.full_rank = self.data["player"]["rank"]["rank"]
		self.rank = self.full_rank.split(" ")[0].lower()

	def store_self(self):
		filepath = profile_dir+"/{}/{}.json".format(self.nickname,self.nickname)
		with open(filepath, 'w') as f:
			f.write(json.dumps(self.data))

	def add_readable_dates(self):
		# Get the array of update date strings from self.data.
		updates = self.data["updates"]
		local_updates = {}

		for key, update in updates.items():
			# Parse the date string using the given format.
			dt_naive = datetime.datetime.strptime(update, "%m/%d/%Y, %I:%M:%S %p")
			# Mark the datetime as UTC.
			dt_utc = dt_naive.replace(tzinfo=ZoneInfo(api_time_zone))
			# Convert the datetime to the local timezone.
			dt_local = dt_utc.astimezone(ZoneInfo(time_zone))
			# Format the datetime as desired.
			local_str = dt_local.strftime("%d.%m.%Y %H:%M:%S")
			# Store it under the same key.
			local_updates[key] = local_str
		
		# Store the new local_updates array next to the original updates.
		self.data["local_updates"] = local_updates
		self.store_self()

	def get_hero_costume(self,hero_id):
		if self.nickname in costume_attachments:
			for key, value in costume_attachments[self.nickname].items():
				if hero_id == key:
					return f"img/heroes/{hero_id}_costume_{value}.png"
		return f"img/heroes/{hero_id}_costume_0.png"

	def set_rank_and_sr(self):
		self.sr = int(self.match_data[0]["extended_data"]["match_player"]["score_info"]["new_score"])
		self.level = self.match_data[0]["extended_data"]["match_player"]["score_info"]["new_level"]
		self.full_rank = level_to_rank_map[str(self.level)]
		self.rank = self.full_rank.split(" ")[0].lower()


	def get_banner(self):
		if "banner" in self.data["player"]["icon"]:
			url = self.data["player"]["icon"]["banner"]
			url_parts = url.split("/")
			url_length = len(url_parts)
			banner_name = url_parts[url_length-1].split("?")[0]
			banner = os.path.join(f"./img/banners/{banner_name}")
			return banner
		else:
			return "./img/banners/30000001_banner.webp"


	def get_styled_feedback(self):
		if ai_enabled:
			s = f"<p>{self.feedback["title"]} ({datetime.datetime.strptime(self.latest_game_night_date, "%Y-%m-%d").strftime("%d.%m")})</p><p>{self.feedback["content"]}</p>"
			return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', s)
		# Add the AI stuff here
		return self.feedback["feedback"].replace(self.full_rank,f"<span class='colored_rank' style='color: {self.data["player"]["rank"]["color"]};background-color: #00000080;padding: 3px 6px;border-radius: 5px;'>"+
			self.full_rank+"</span>").replace("quell","quell ("+datetime.datetime.strptime(self.latest_game_night_date, "%Y-%m-%d").strftime("%d.%m")+")")

	def saturate_color(self, rgb, min_saturation=0.4):
	    """
	    Convert an (r, g, b) tuple to HSV, bump the saturation
	    if below min_saturation, then convert back to RGB.
	    """
	    r, g, b = rgb
	    # Convert 0-255 range to 0-1 for colorsys
	    r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0
	    
	    # Convert to HSV
	    h, s, v = colorsys.rgb_to_hsv(r_norm, g_norm, b_norm)
	    
	    # Clamp saturation to at least min_saturation
	    if s < min_saturation:
	        s = min_saturation
	    
	    # Convert back to RGB (still 0-1 range)
	    r_out, g_out, b_out = colorsys.hsv_to_rgb(h, s, v)
	    
	    # Scale back to 0-255 range and return integers
	    return (int(r_out * 255), int(g_out * 255), int(b_out * 255))

	def extract_color(self,filepath):
	    if not os.path.exists(filepath):
	        return None

	    color_thief = ColorThief(filepath)
	    # Get the dominant color from the image
	    r, g, b = color_thief.get_color(quality=1)

	    # Optionally saturate the color to avoid greyish tones
	    r, g, b = self.saturate_color((r, g, b), min_saturation=0.4)

	    # Optionally apply your brightness threshold logic
	    color_total = r + g + b
	    if color_total < color_threshold:
	        delta = color_threshold - color_total
	        add = math.ceil(delta / 2)
	        r += add
	        g += add
	        b += add

	    # Generate your light/dark versions
	    color_light_r = str(r)
	    color_light_g = str(g)
	    color_light_b = str(b)
	    
	    color_dark_r = str(math.ceil(r / 2))
	    color_dark_g = str(math.ceil(g / 2))
	    color_dark_b = str(math.ceil(b / 2))

	    return {
	        "light": (color_light_r, color_light_g, color_light_b),
	        "dark": (color_dark_r, color_dark_g, color_dark_b)
	    }

# Example usage:
if __name__ == "__main__":
    filepath = "example_image.jpg"
    colors = extract_color(filepath)
    if colors:
        print("Light color:", colors["light"])
        print("Dark color:", colors["dark"])
