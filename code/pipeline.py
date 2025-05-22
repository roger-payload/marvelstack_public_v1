import asyncio
import async_broker
import gamer_master
import gpt_master
import html_gen
import sys

from config import site,squadname,Bcol,base_api, polling_rate, timeout, gamerlist, gamerlist_bronze

if __name__ == '__main__':
	feature_flag_skip = False
	feature_flag_bronze = False
	force = False

	gamers = gamerlist

	for arg in sys.argv:
		if arg == "--skip":
			feature_flag_skip = True
		if arg == "--bronze":
			feature_flag_bronze = True
			gamers = gamerlist_bronze
		if arg == "--force":
			force = True

	bcol = Bcol()

	# Get the data
	print(f"######")
	print(f"###### STARTING PIPELINE FOR {bcol.OKCYAN}{squadname}{bcol.ENDC} on {bcol.OKCYAN}{site}{bcol.ENDC}")
	print(f"###### Running with current parameters:")
	print(f"###### API: {bcol.OKCYAN}{base_api}{bcol.ENDC}")
	print(f"###### Polling rate: {bcol.OKCYAN}{polling_rate/60}{bcol.ENDC} minutes. Timeout set to {bcol.OKCYAN}{timeout/60}{bcol.ENDC} minutes")
	print(f"######")
	print(f"{bcol.BOLD}Async broker fetching data:{bcol.ENDC}")

	async_broker.get_gamer_uids(gamers)
	if not feature_flag_skip:
		asyncio.run(async_broker.update_gamer_data(gamers,force_update=force))
	async_broker.enrich_gamers(gamers)

	print(f"{bcol.BOLD}Gamer_master performing analysis:{bcol.ENDC}")
	# Do all the banckend analysis we need
	if not feature_flag_bronze:
		g_master = gamer_master.Gamer_master(gamers)
	else:
		g_master = gamer_master.Gamer_master(gamers,game_nights_folder="game_nights_bronze")
	g_master.initiate()
	g_master.export_data_objects()
	if not feature_flag_bronze:
		g_master.compute_kpi_records()
	else:
		g_master.compute_kpi_records(records_location="records_bronze.json")

	print(f"{bcol.BOLD}GPT_master getting AI commentary:{bcol.ENDC}")
	# Get Galacta to enrich our data with AI bullshit
	if not feature_flag_bronze:
		gpt_master.process_game_nights()
	else:
		gpt_master.process_game_nights(game_night_folder="./game_nights_bronze/", records_location="records_bronze.json")

	if not feature_flag_bronze:
		gpt_master.get_latest_tts()
	else:
		gpt_master.get_latest_tts(game_night_folder="./game_nights_bronze/",audio_folder="../audio_bronze/")

	print(f"{bcol.BOLD}Building site:{bcol.ENDC}")
	html_gen.build_site(gamers, feature_flag_bronze)

