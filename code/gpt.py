import os
from decouple import config
from openai import OpenAI
import json
import random
import datetime
import time

from config import squadname

class GPT():
	def __init__(self, test=True):
		self.test = test
		self.client = OpenAI(
	    	api_key = config("OPENAI_API_KEY")
		)

	def create_game_night_summary(self, game_night_summary):
		"""
		Sends the formatted game night summary to OpenAI Assistant
		and retrieves Galacta's response.
		"""
		happenings = self.get_notable_happenings()

		prompt = f"""
		Here is a summary of a game night, of {squadname}:
		{game_night_summary}

		Your job:
		- Choose a **title** that's concise.
		- You are encouraged to directly mention players, and/or their played characters! i.e: 'Noxxeys Teary Soloqueue'.
		- You are also encouraged to mix the names to be creative, for instance DanteMagic and MORTEN7331 could become 'Who let MORTENMagic cook?!"
		- Return the title and your **verdict** as a JSON response.
		{happenings}
		"""

		if self.test:
			return prompt
		else:
			print("Sending to GPT Assistant...")

			thread = self.client.beta.threads.create()
			message = self.client.beta.threads.messages.create(
				thread_id=thread.id,
				role="user",
				content=prompt
			)

			run = self.client.beta.threads.runs.create(
				thread_id=thread.id,
				assistant_id="asst_Kv3GInzYub9DcnL3KczhbtpP",
			)

			while run.status in ["queued", "in_progress"]:
				time.sleep(2)
				run = self.client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

			messages = self.client.beta.threads.messages.list(thread_id=thread.id)
			return messages

	def create_personal_game_night_summary(self, personal_summary):
		"""
		Sends the formatted game night summary to OpenAI Assistant
		and retrieves Galacta's response.
		"""
		happenings = self.get_notable_happenings()
		prompt = f"""
		Here is a personal performance for the night:
		{personal_summary}

		Your job:
		- Choose a **title** that's concise.
		- Highlight their **best moments** (if they performed well) or **poke fun at their struggles** (if they underperformed).
		- Make the feedback relevant for the heroes / roles. Compliment their usage of in-game skills and mechanics, or alternatively, roast them to pieces.
		- Mention **roles and ALL heroes they played**, also the secondaries (if any). Any scandalous and worthless dips in the hero pool, or maybe a stroke of brilliance?
		- Comment on their hero swaps (or lack of), highlight their **adaptability and versatile nature OR their confusion and chaotic nonsense**.
		- Return the title and a **short verdict** on their night in JSON format.
		{happenings}
		"""


		if self.test:
			return prompt
		else:
			print("Sending to GPT Assistant...")

			thread = self.client.beta.threads.create()
			message = self.client.beta.threads.messages.create(
				thread_id=thread.id,
				role="user",
				content=prompt
			)

			run = self.client.beta.threads.runs.create(
				thread_id=thread.id,
				assistant_id="asst_Kv3GInzYub9DcnL3KczhbtpP",
			)

			while run.status in ["queued", "in_progress"]:
				time.sleep(2)
				run = self.client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

			messages = self.client.beta.threads.messages.list(thread_id=thread.id)
			return messages

	def get_notable_happenings(self):
		# If you want the AI to reference fun stuff about the squad, add them to a json file referenced here:
		happenings = os.path.join("./game_nights/", "happenings.json")
		# File format should be [{"date":"yyyy-mm-dd","title":"title","event":"what happened"}]
		if not os.path.exists(happenings):
			print(f"No happenings file in game_nights.")
			return ""
		else:
			# Load the comp_games data
			with open(happenings, 'r') as f:
				notable = json.load(f)
			returnstr = f"\r\nNotable happenings of {squadname}, that can be referenced if it fits the narrative:\r\n"
			for happening in notable:
				returnstr += f"- **{happening["title"]}** ({happening["date"]}) : {happening["event"]}\r\n"
			returnstr += "\r\n"
			return returnstr