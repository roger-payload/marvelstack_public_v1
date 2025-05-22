## 🕹️ Marvel Rivals Squad Site – Setup Guide

Follow these steps to configure and deploy your personalized squad site.

---

### Step 1: Set up environment variables

Create a file at `code/.env` with the following content:

```
MARVEL_RIVALS_KEY=####
OPENAI_API_KEY=####
```

> ⚠️ Add both variables, but only fill in the API key(s) for the service(s) you plan to use.

---

### Step 2: Configure your squad

Edit the file: `code/config.py`

Update the following:

* `squadname`: Your squad's name.
* `site`: Your preferred site URL.
* `time_zone`: Your local time zone (e.g., `"Europe/Oslo"`).

#### Example Squad Setup

```python
role_lock = {
	"Noxxey": ["Strategist"]
}

gamerlist = [
	"MegabyteBro",
	"Noxxey",
	"DanteMagic",
	"MORTEN7331"
]

costume_attachments = {
	"MegabyteBro": {1011: 1, 1050: 0, 1031: 3, 1035: 3},
	"MORTEN7331": {1039: 4, 1031: 1, 1034: 4, 1041: 2, 1050: 3},
	"DanteMagic": {1031: 3, 1048: 3},
	"Noxxey": {1031: 3, 1050: 3, 1025: 2}
}
```

* **`role_lock`** (optional): Locks specific players to a role (or roles) for their player card. Useful if someone flexes roles but prefers to be scored only for a specific one.
* **`gamerlist`**: Case-sensitive list of in-game usernames in your squad.
* **`costume_attachments`**: Manually define which costumes to show for each player’s heroes.

> 🧵 Costume image filenames follow the format: `HEROID_costume_COSTUMEID.png`. You can find them in `img/heroes/`.

To update your local cache of costumes, run:

```bash
python async_broker.py --heroes
```

---

### Step 3: Generate your squad site

Run the pipeline script:

```bash
python pipeline.py
```

This will process your recent game nights and generate a summary site.

---

### Step 4: Deploy the site

Deploy your generated files however you like (e.g., a web server or static host).

Make sure to publish the following directories and files:

```bash
cp -r img ~/www
cp -r dist ~/www
cp -r fonts ~/www
cp *.html ~/www
cp *.css ~/www
```

> 💡 If AI commentary is enabled, also include:

```bash
cp -r audio ~/www
cp -r audio_bronze ~/www
```

---

Let me know if you'd like a badge, logo, or features section added!
