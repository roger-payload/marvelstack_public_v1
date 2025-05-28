import os
import json
import sys
import datetime
import time
import requests
import asyncio
import aiohttp
import shutil

from gamer_master import Gamer_master
from config import base_api, current_season, headers, update_rate, base_image_api, polling_rate, timeout, premium_member
from config import api_time_zone, time_zone, base_api_v2
from config import Bcol

from zoneinfo import ZoneInfo  # Requires Python 3.9+


# Directory where profile JSON files are stored.
PROFILE_DIR = "../profiles/"
bcol = Bcol()

def return_readable_date(date):

	dt_naive = datetime.datetime.strptime(date, "%m/%d/%Y, %I:%M:%S %p")
	dt_utc = dt_naive.replace(tzinfo=ZoneInfo(api_time_zone))
	dt_local = dt_utc.astimezone(ZoneInfo(time_zone))
	return dt_local.strftime("%d.%m - %H:%M:%S")


def get_heroes():
	url = base_api+"heroes"
	print("Getting all heroes")
	print(url)
	r = requests.get(url, headers=headers)
	print("Request status code: "+str(r.status_code))
	if r.status_code != 200:
		print("API call not successful, {} returned.".format(str(r.status_code)))
	else:	
		with open("heroes.json", "w") as outfile:
		    outfile.write(json.dumps(r.json()))

def get_hero_assets():
	if os.path.exists("heroes.json"):
		with open("heroes.json", 'r') as f:
			heroes = json.load(f)
	for hero in heroes:
		filename = "../img/heroes/"+str(hero["id"])+".png"
		if not os.path.exists(filename):
			time.sleep(1)
			print("Missing default "+hero["name"]+" avatar, collecting now:")
			url = base_image_api+hero["imageUrl"]
			print(url)
			try:
				avatar_image = requests.get(url, stream = True)
				avatar_image.raw.decode_content = True
				with open(filename,"wb") as outfile:
					shutil.copyfileobj(avatar_image.raw, outfile)
			except:
				print("!! WARNING: AVATAR NOT COLLECTED FOR "+hero["transformations"]["name"])
		filename = "../img/heroes/"+str(hero["id"])+"_icon.webp"
		if not os.path.exists(filename):
			time.sleep(1)
			print("Missing secondary "+hero["name"]+" avatar, collecting now:")
			url = base_image_api+"/rivals"+hero["transformations"][0]["icon"]
			print(url)
			try:
				avatar_image = requests.get(url, stream = True)
				avatar_image.raw.decode_content = True
				with open(filename,"wb") as outfile:
					shutil.copyfileobj(avatar_image.raw, outfile)
			except:
				print("!! WARNING: ICON NOT COLLECTED FOR "+hero["transformations"]["name"])
		if not len(hero["transformations"]) > 1:
			filename = "../img/heroes/"+str(hero["id"])+"_lord.png"
			if not os.path.exists(filename):
				time.sleep(1)
				print("Missing "+hero["name"]+" lord avatar, collecting now:")
				url = base_image_api+"/rivals/lord/{}_lord.png".format(str(hero["id"]))
				print(url)
				try:
					avatar_image = requests.get(url, stream = True)
					avatar_image.raw.decode_content = True
					with open(filename,"wb") as outfile:
						shutil.copyfileobj(avatar_image.raw, outfile)
				except:
					print("!! WARNING: AVATAR NOT COLLECTED FOR "+hero["transformations"]["name"])
		else:
			for n in range(len(hero["transformations"])):
				count = str(n+1)
				filename = "../img/heroes/"+str(hero["id"])+"_{}_lord.png".format(count)
				if not os.path.exists(filename):
					time.sleep(1)
					print("Missing "+hero["name"]+" lord {} avatar, collecting now:".format(count))
					url = base_image_api+"/rivals/lord/{}_{}_lord.png".format(str(hero["id"]),count)
					print(url)
					try:
						avatar_image = requests.get(url, stream = True)
						avatar_image.raw.decode_content = True
						with open(filename,"wb") as outfile:
							shutil.copyfileobj(avatar_image.raw, outfile)
					except:
						print("!! WARNING: AVATAR NOT COLLECTED FOR "+hero["transformations"]["name"])
		costume_count = 0
		for costume in hero["costumes"]:
			filename = "../img/heroes/"+str(hero["id"])+"_costume_{}.png".format(costume_count)
			if not os.path.exists(filename):
				time.sleep(1)
				print("Missing "+hero["name"]+" costume {}, collecting now:".format(costume_count))
				url = base_image_api+"/rivals{}".format(costume["icon"])
				print(url)
				try:
					avatar_image = requests.get(url, stream = True)
					avatar_image.raw.decode_content = True
					with open(filename,"wb") as outfile:
						shutil.copyfileobj(avatar_image.raw, outfile)
				except:
					print("!! WARNING: AVATAR NOT COLLECTED FOR "+hero["transformations"]["name"])
			costume_count += 1


def convert_to_timestamp(date_str):
	dt = datetime.datetime.strptime(date_str, "%m/%d/%Y, %I:%M:%S %p")
	return dt.timestamp()

def time_stamp_is_today(ts):
	dt_from_ts = datetime.datetime.fromtimestamp(ts)
	# Now you can compare the date part with today's date
	return dt_from_ts.date() == datetime.datetime.today().date()

def verify_update(updates):
	last_update_request = convert_to_timestamp(updates["last_update_request"])
	last_history_update = convert_to_timestamp(updates["last_history_update"])
	print(f"Last request: {return_readable_date(updates['last_update_request'])} and last update: {return_readable_date(updates['last_history_update'])}")
	last_date = datetime.datetime.fromtimestamp(last_history_update).date()
	today = datetime.datetime.today().date()
	if last_date == today:
		print("Last update is from today, accepting the data")
		return True
	if last_history_update > last_update_request:
		print("The update is after the request timestamp, accepting the data")
		return True
	return False

def enrich_gamers(gamerlist):
	g_master = Gamer_master(gamerlist)
	g_master.get_player_matches()
	for g in g_master.gamers:
		g.add_readable_dates()
		url = base_image_api+"/rivals"+g.data["player"]["icon"]["player_icon"]

		icon = os.path.join("../img/player_heads/", g.data["player"]["icon"]["player_icon_id"]+".png")
		print(icon)
		if not os.path.exists(icon):
			try:
				print("Getting new player head")
				player_icon = requests.get(url, stream = True)
				player_icon.raw.decode_content = True
				with open("../img/player_heads/{}".format(g.data["player"]["icon"]["player_icon_id"])+".png","wb") as outfile:
					shutil.copyfileobj(player_icon.raw, outfile)
			except:
				print("!! WARNING: PLAYER ICON NOT COLLECTED FOR "+g.nickname)
		if premium_member and "banner" in g.data["player"]["icon"]:
			url = base_image_api+g.data["player"]["icon"]["banner"]
			url_parts = url.split("/")
			url_length = len(url_parts)
			banner_name = url_parts[url_length-1].split("?")[0]
			banner = os.path.join(f"../img/banners/{banner_name}")
			if not os.path.exists(banner):
				try:
					print("Getting new banner")
					player_icon = requests.get(url, stream = True)
					player_icon.raw.decode_content = True
					with open(banner,"wb") as outfile:
						shutil.copyfileobj(player_icon.raw, outfile)
				except:
					print("!! WARNING: PLAYER ICON NOT COLLECTED FOR "+g.nickname)


def stale_timestamp(last_history_update):
	# Check if the provided timestamp is older than N hours.
	last_history_update = convert_to_timestamp(last_history_update)
	profile_update_time = datetime.datetime.fromtimestamp(last_history_update)
	current_time = datetime.datetime.now()
	time_diff = current_time - profile_update_time
	return time_diff > datetime.timedelta(hours=update_rate)

async def request_new_gamer_data(session, gamer, uids):
    url = f"https://marvelrivalsapi.com/api/v1/player/{uids[gamer]}/update"
    async with session.get(url, headers=headers) as r:
        status = r.status
        if status != 200:
        	print(f"Request new data for {gamer} returned status {bcol.HEADER}{status}{bcol.ENDC}")
        	print(f"API call for update not successful for {gamer}. Possibly rate-limited or API error.")
        else:
        	print(f"Request new data for {gamer} returned status {bcol.OKGREEN}{status}{bcol.ENDC}")
        	print(f"{bcol.OKGREEN}Data refresh request successful for {gamer}.{bcol.ENDC}")
        # Return status code so caller can decide what to do
        return status

async def fetch_gamer_data(session, gamer, uids, season):
	url = f"{base_api}player/{uids[gamer]}?season={current_season}"
	print(f"Getting stats for {gamer}:")
	print(url)
	async with session.get(url, headers=headers) as r:
		status = r.status
		print(f"Fetch for {gamer} returned status {status}")
		if status != 200:
			print(f"API call for fetching {gamer} not successful.")
			return None
		data = await r.json()
		return data

async def poll_for_update(session, gamer, uids, store_temp_cache, poll_interval=polling_rate, timeout=timeout, file_path="./whoops.json"):

	"""
	Poll the API until the profile's enriched data is available.
	Specifically, wait until 'last_history_update' exists and is greater than the update_request_time.
	"""
	start_time = datetime.datetime.now()
	while True:
		data = await fetch_gamer_data(session, gamer, uids, current_season)
		if data and "updates" in data:
			if verify_update(data["updates"]):
				print(f"{bcol.OKGREEN}{gamer} update is complete.{bcol.ENDC}")
				return data
			if time_stamp_is_today(convert_to_timestamp(data["updates"]["last_history_update"])):
				print(f"{bcol.OKGREEN}{gamer} has updated history from today. Using data!{bcol.ENDC}")
				return data
			if store_temp_cache:
				dirname = os.path.dirname(file_path)
				os.makedirs(dirname, exist_ok=True)
				print(f"{bcol.HEADER}Storing intitial object to retain update_request.{bcol.ENDC}")
				with open(file_path, "w") as outfile:
					outfile.write(json.dumps(data))
				store_temp_cache = False
		elapsed = (datetime.datetime.now() - start_time).total_seconds()
		if elapsed > timeout:
			if data:
				print(f"Timeout reached while waiting for {gamer} update.")
				if not stale_timestamp(data["updates"]["last_update_request"]):
					print(f"{bcol.WARNING}Last update is kind of new though, using this data.{bcol.ENDC}")
					return data
				else:
					print(f"{bcol.FAIL}  #### Last_update_request not processed. MOVING ON!{bcol.ENDC}")
					return data
			else:
				print(f"{bcol.FAIL}  #### API Responding with ERROR. MOVING ON!{bcol.ENDC}")
				return data
		print(f"Time elapsed: {str(elapsed)}. {gamer} update not complete yet. Waiting {poll_interval} seconds. Timing out when {timeout} seconds has passed..")
		await asyncio.sleep(poll_interval)

async def update_single_profile(session, gamer, uids, force_update=False):
    file_path = os.path.join(PROFILE_DIR + f"{gamer}/", f"{gamer}.json")
    cached_data = None
    last_update_request = None
    needs_update_request = True
    store_temp_cache = False

    if force_update:
        print(f"{bcol.OKCYAN}## FORCING UPDATES ##{bcol.ENDC}")

    # Try to load the local data if it exists
    if os.path.exists(file_path):
        print(f"Cached file found for {gamer}. Loading data...")
        try:
            if os.stat(file_path).st_size > 0:
                with open(file_path, 'r') as f:
                    cached_data = json.load(f)
            else:
                print("Cache file is empty.")
        except json.decoder.JSONDecodeError:
            print("Cache file contains invalid JSON.")
            cached_data = None

    # Check if we have enriched data with a last_history_update
    if cached_data and "updates" in cached_data and not force_update:
        last_update_request = cached_data["updates"]["last_update_request"]
        if not stale_timestamp(last_update_request):
            print(f"Request is up to date, verifying data")
            if verify_update(cached_data["updates"]):
                print(f"{bcol.OKGREEN}Cached data for {gamer} is up-to-date. Using cached data.{bcol.ENDC}")
                return cached_data
            else:
                print(f"{bcol.WARNING}Cached data for {gamer} is old, but update is fresh. Polling.{bcol.ENDC}")
                needs_update_request = False
        else:
            print(f"Cached data for {gamer} is old.")
    else:
        print(f"No enriched cached data found for {gamer}.")

    # ---------------------------------------------------
    # If we need an update request, do it with retries.
    # ---------------------------------------------------
    if needs_update_request or force_update:
        store_temp_cache = True
        max_retries = 3
        wait_seconds = 5
        request_success = False

        # Decide which gamer name to send to request_new_gamer_data
        gamer_name_for_api = (
            cached_data["name"] if (cached_data and "player" in cached_data) 
            else gamer
        )

        for attempt in range(max_retries):
            status = await request_new_gamer_data(session, gamer_name_for_api, uids)
            if status == 200:
                request_success = True
                break
            else:
                if attempt < max_retries - 1:
                    print(f"{bcol.WARNING}Request failed on attempt {attempt+1}/{max_retries}. "
                          f"Waiting {wait_seconds}s before retry...{bcol.ENDC}")
                    await asyncio.sleep(wait_seconds)

        if not request_success:
            # ❌ Immediately stop for this gamer if repeated attempts failed
            print(f"{bcol.FAIL}Failed to request new gamer data for {gamer} after {max_retries} attempts. Aborting update for this gamer.{bcol.ENDC}")
            return None

    # If we reach here, we successfully requested new data (or didn't need to).
    await asyncio.sleep(polling_rate)

    # Now poll until the enriched data is available or times out
    new_data = await poll_for_update(session, gamer, uids, store_temp_cache, file_path=file_path)

    if new_data:
        # Create the directory (and any intermediate directories) if it doesn't exist
        dirname = os.path.dirname(file_path)
        os.makedirs(dirname, exist_ok=True)

        # Write updated data
        with open(file_path, "w") as outfile:
            outfile.write(json.dumps(new_data))
        print(f"{bcol.OKGREEN}{gamer} data stored successfully.{bcol.ENDC}")
        return new_data
    else:
        print(f"{bcol.FAIL}Failed to update data for {gamer}.{bcol.ENDC}")
        return None


async def update_gamer_data(gamerlist, force_update):
	if os.path.exists("uids.json"):
		with open("uids.json", 'r') as f:
			uids = json.load(f)
	async with aiohttp.ClientSession() as session:
		# Create tasks for all profiles concurrently.
		tasks = [update_single_profile(session, gamer, uids, force_update=force_update) for gamer in gamerlist]
		results = await asyncio.gather(*tasks)
		return results

def get_latest_patches():
	url = base_api+"patch-notes?page=1&limit=10"
	print("Getting patches")
	print(url)
	r = requests.get(url, headers=headers)
	print("Request status code: "+str(r.status_code))
	if r.status_code != 200:
		print("API call not successful, {} returned.".format(str(r.status_code)))
	else:	
		with open("patch_notes.json", "w") as outfile:
		    outfile.write(json.dumps(r.json()))

def make_api_call(url,headers=headers,image=False,filetype="png"):
	print(url)
	if not image:
		r = requests.get(url, headers=headers)
		print("Request status code: "+str(r.status_code))
		if r.status_code != 200:
			print("API call not successful, {} returned.".format(str(r.status_code)))
		else:	
			return r.json()
	else:
		try:
			img_file = requests.get(url, stream = True)
			img_file.raw.decode_content = True
			with open("returned_test_file."+filetype,"wb") as outfile:
				shutil.copyfileobj(img_file.raw, outfile)
		except:
			print("!! WARNING: Image not collected")

def get_gamer_uids(gamerlist):
	uids = {}
	if os.path.exists("uids.json"):
		with open("uids.json", 'r') as f:
			uids = json.load(f)
	all_good = True
	for gamer in gamerlist:
		if gamer not in uids:
			all_good = False
			uid = make_api_call(f"{base_api}find-player/{gamer}")
			uids[uid["name"]] = uid["uid"]
		else:
			print(f"{gamer} uid already collected - {bcol.OKGREEN}OK{bcol.ENDC}")
	if not all_good:
		with open("uids.json", "w") as outfile:
		    outfile.write(json.dumps(uids))


if __name__ == '__main__':
	feature_flag_all = False
	feature_flag_gamers = False
	feature_flag_heroes = False
	feature_flag_notes = False
	feature_flag_force_update = False

	for arg in sys.argv:
		if arg == "--all":
			feature_flag_all = True
		if arg == "--gamers":
			feature_flag_gamers = True
		if arg == "--heroes":
			feature_flag_heroes = True
		if arg == "--notes":
			feature_flag_notes = True
		if arg == "--force_update":
			feature_flag_force_update = True


	if feature_flag_all:
		asyncio.run(update_gamer_data())
		get_heroes()
		get_hero_assets()
		enrich_gamers()
		get_latest_patches()

	if feature_flag_gamers:
		asyncio.run(update_gamer_data(force_update=feature_flag_force_update))
		enrich_gamers()

	if feature_flag_heroes:
		get_heroes()
		get_hero_assets()

	if feature_flag_notes:
		get_latest_patches()

