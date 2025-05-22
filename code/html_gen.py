import json
import glob
import os
import re
import math
import random
import sys 
from datetime import datetime

from gamer_master import Gamer_master
import gpt_master

from config import gamer_card_hero_count, rank_history_count, squadname, gamerlist, gamerlist_bronze, ai_enabled
from config import rank_chart_break_points, rank_chart_break_points_colors, rank_chart_break_points_names, display_chart_rank_names


def remove_html_tags(text):
    clean = re.compile(r'<[^>]+>')
    return re.sub(clean, '', text)

def get_global_sr_range(players):
  """
  Finds the lowest and highest SR among all players,
  then snaps them to the nearest rank breakpoints,
  with 50 SR padding.
  """
  min_sr = float('inf')
  max_sr = float('-inf')

  # Find the lowest and highest SR across all players
  for g in players:
    for rank_data in g.data["rank_history"]:
      sr = rank_data["score_progression"]["total_score"]
      min_sr = min(min_sr, sr)
      max_sr = max(max_sr, sr)

  # === ✅ Find the closest breakpoints for min/max SR ===
  # Ensure the min_sr doesn't snap to something too low
  closest_min = max([bp for bp in rank_chart_break_points if bp <= min_sr], default=rank_chart_break_points[0])
  # Ensure the max_sr doesn't snap too high
  closest_max = min([bp for bp in rank_chart_break_points if bp >= max_sr], default=rank_chart_break_points[-1])

  # === ✅ Apply Smart Padding ===
  final_min = max(0, closest_min - 25)  # Ensure min never drops below 0
  final_max = closest_max + 25  # Extend slightly past the next rank

  return final_min, final_max

def get_global_score_range(gamers):
  min_score = float('inf')
  max_score = float('-inf')

  for g in gamers:
    for hero in g.top_heroes:
      if "score_array" in hero["match_scores"]:
        for entry in hero["match_scores"]["score_array"]:
          score = entry["score"]
          if score < min_score:
            min_score = score
          if score > max_score:
            max_score = score

  # Add padding
  max_score = max_score * 1.1  # Increase max by 10%
  min_score = min_score * 0.9  # Decrease min by 10%

  # Round to nearest 100
  max_score = math.ceil(max_score / 10) * 10  # Round UP to nearest 100
  min_score = math.floor(min_score / 10) * 10  # Round DOWN to nearest 100

  return min_score, max_score

def get_rank_breakpoint_annotations(global_min_sr, global_max_sr):
  """
  Generates the rank breakpoint annotations for Chart.js.
  """
  annotations = {}

  for i, rank_sr in enumerate(rank_chart_break_points):
    rank_color = rank_chart_break_points_colors[i]
    rank_name = rank_chart_break_points_names[i]  # 🔹 Get the corresponding rank name

    # Only include breakpoints that fall within the player's SR range
    if global_min_sr <= rank_sr <= global_max_sr:
      annotations[f"rank_line_{rank_sr}"] = {
        "type": "line",
        "scaleID": "y",
        "value": rank_sr,
        "borderColor": rank_color,
        "borderWidth": 2,
        "borderDash": [5, 5],  # Dashed line
        "label": {
          "display": display_chart_rank_names,
          "content": f"{rank_name}",
          "position": "start",
          "backgroundColor": "rgba(0,0,0,0.2)",
          "color": "white",
          "font": {"size": 7}
        }
      }

  # Convert Python dictionary to a JSON string
  return json.dumps(annotations)

def format_text(g_master,text):
  return text
  colored_text = text
  for g in g_master.gamers:
    colored_text = colored_text.replace(g.nickname_safe,f"<span class='text-color-{g.nickname_safe}'>{g.nickname_safe}</span>")
  return colored_text.replace("\\n","<br>")

def generate_top(g_master):
  ret =f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <link rel="icon" type="image/png" sizes="32x32" href="favicon-32x32.png"  >
    <link rel="icon" type="image/png" sizes="16x16" href="favicon-16x16.png">
    <meta name="description" content="Marvel Rivals private profile site">
    <meta name="author" content="Roger Blotekjaer">
    <title>The Rivals Stack</title>

    <link href="./dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="fonts/remixicon.css" rel="stylesheet">
    <link href="./dist/css/animate.css" rel="stylesheet">
    <link href="./custom.css?v=1" rel="stylesheet">
    <style>"""
  for gamer in g_master.gamers:
    ret +=""".text-color-{} {{
        color: rgb({},{},{});
        background-color: rgba({}, {}, {}, 0.3);
        padding: 1px 8px;
        border-radius: 15px;
      }}""".format(gamer.nickname_safe,gamer.color_light_r,gamer.color_light_g,gamer.color_light_b,gamer.color_dark_r,gamer.color_dark_g,gamer.color_dark_b)
  ret +="""
    </style>

    <script src="./dist/js/jquery-3.6.3.min.js"></script>
    <!-- Latest Chart.js v4 -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.3.0/dist/chart.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chartjs-plugin-annotation/3.1.0/chartjs-plugin-annotation.min.js" integrity="sha512-8MntMizyPIYkcjoDkYqgrQOuWOZsp92zlZ9d7M2RCG0s1Zua8H215p2PdsxS7qg/4hLrHrdPsZgVZpXheHYT+Q==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
    <script src="./dist/js/bootstrap.bundle.min.js"></script>
  </head>
  <body  class="text-white">
    
<div id="content" class="col-lg-8 mx-auto p-4 py-md-5">
  <div class="d-flex align-items-center pb-3 mb-5 border-bottom">
      <span class="fs-5">Stack boys... ASSEMBLE!</span>
  </div>
</div>
"""
  #<img src="./img/full_logo_s4.png">

  return ret

def generate_progress_bar(value, title, g):

    # Current rank extracted from player's stored rank
    current_rank_name = g.rank.capitalize()
    rank_index = rank_chart_break_points_names.index(current_rank_name)
    current_break_point = rank_chart_break_points[rank_index]

    diff = value - current_break_point

    # Last two digits define percentage progress
    progress = abs(int(diff % 100))
    style_class = "progress-bar"
    if diff < 0:
        style_class = "progress-bar progress_bad"
        progress = 100-progress
        progress_text = f"""-{progress}%"""
        positive_progress = 0
        negative_progress = progress
    else:
        style_class = "progress-bar progress_good"
        next_rank_name = rank_chart_break_points_names[min(rank_index + 1, len(rank_chart_break_points_names)-1)]
        progress_text = f"{progress}%"
        positive_progress = progress
        negative_progress = 0

    return f"""
    <div class="progress-container">
        <div id="{g.nickname_safe}_progress" class="{style_class}"
            style="--progress-value: {positive_progress}%; --negative-progress: {negative_progress}%;">
            <span class="progress-text">{progress_text}</span>
        </div>
        <p class="progress-title">{title}</p>
    </div>
    <style>
    #{g.nickname_safe}_progress::after {{

        content: "";
        position: absolute;
        left: 0;
        top: 0;
        height: 100%;
        width: var(--progress-value, 50%); /* Dynamically set via inline style */

        border-radius: 10px;
        overflow: hidden;

        background: linear-gradient(90deg, #00041680, rgba({g.color_light_r}, {g.color_light_g}, {g.color_light_b}, 0.8));
    }}
    </style>
    """

def generate_gamer_cards(g_master):
  global_min_score, global_max_score = get_global_score_range(g_master.gamers)
  globalMinSR, globalMaxSR = get_global_sr_range(g_master.gamers)
  html = f"""<div class='container mt-4'><img src="img/mainlogo.png" id="banner"><h2 class='gradient-header'>Performance Overview <img src="img/Galacta.webp" id="galacta"></h2>
  <script>
  var globalMinScore = {global_min_score};
  var globalMaxScore = {global_max_score};</script>"""
  for g in g_master.gamers:
    g.set_rank_and_sr()
    gamer_sr = g.sr
    top = g.top_heroes[0]
#        <div class="col-4 d-flex flex-column justify-content-end">
#                <img src="img/heroes/{top["hero_id"]}_costume_0.png" class="top_hero_costume">
#        </div>
    html = html + f"""<div class="profile_card p-3" 
                    style="background: radial-gradient(circle at top right, rgba({g.color_light_r}, {g.color_light_g}, {g.color_light_b}, 0.8), rgba(255, 0, 150, 0) 65%);">
                    <div class="row">
                        <div class="col-7">
                            <div class="row d-flex justify-content-between">"""
    hero_count = len(g.top_heroes)
    if hero_count > gamer_card_hero_count:
      hero_count = gamer_card_hero_count
    col_size = int(12 / hero_count)
    active_set = False
    for n in range(hero_count):
      active_class = "non_active_hero"
      if not active_set:
        active_class = "active_hero"
      html = html+f"""<div class="col-{col_size} {active_class} d-flex justify-content-center {g.nickname_safe}_{g.top_heroes[n]["hero_id"]}_card">
           <img src="img/heroes/{g.top_heroes[n]["hero_id"]}.png" class="hero_vertical img-fluid">
           </div><script type="text/javascript">var {g.nickname_safe}_{g.top_heroes[n]["hero_id"]}_card = {json.dumps(g.top_heroes[n]["match_scores"])}</script>"""
      active_set = True
    contributions = ""
    if top["role"] == "Vanguard":
      contributions += f"""<tr>
                            <td id="{g.nickname_safe}_contribution1">Tanking</td>
                            <td id="{g.nickname_safe}_overall_c1">{int(top["match_scores"]["derived_stats"]["tanking_per_minute"])}</td>
                            <td id="{g.nickname_safe}_c1_rating">{top["match_scores"]["final_ratings"]["tanking_per_minute"]["html"]}</td>
                          </tr>
                          <tr>
                            <td id="{g.nickname_safe}_contribution2">Damage</td>
                            <td id="{g.nickname_safe}_overall_c2">{int(top["match_scores"]["derived_stats"]["damage_per_minute"])}</td>
                            <td id="{g.nickname_safe}_c2_rating">{top["match_scores"]["final_ratings"]["damage_per_minute"]["html"]}</td>
                          </tr>
                          <tr><td colspan="3" class="hero_chart"><canvas id="{g.nickname_safe}_hero_chart"></canvas></td></tr>
                          """
    elif top["role"] == "Duelist":
      contributions += f"""<tr>
                            <td id="{g.nickname_safe}_contribution1">Damage</td>
                            <td id="{g.nickname_safe}_overall_c1">{int(top["match_scores"]["derived_stats"]["damage_per_minute"])}</td>
                            <td id="{g.nickname_safe}_c1_rating">{top["match_scores"]["final_ratings"]["damage_per_minute"]["html"]}</td>
                          </tr>
                          <tr>
                            <td id="{g.nickname_safe}_contribution2">Kills</td>
                            <td id="{g.nickname_safe}_overall_c2">{round(top["match_scores"]["derived_stats"]["kills_per_minute"],2)}</td>
                            <td id="{g.nickname_safe}_c2_rating">{top["match_scores"]["final_ratings"]["kills_per_minute"]["html"]}</td>
                          </tr>
                          <tr><td colspan="3" class="hero_chart"><canvas id="{g.nickname_safe}_hero_chart"></canvas></td></tr>
                          """
    else:
      contributions += f"""<tr>
                            <td id="{g.nickname_safe}_contribution1">Healing</td>
                            <td id="{g.nickname_safe}_overall_c1">{int(top["match_scores"]["derived_stats"]["healing_per_minute"])}</td>
                            <td id="{g.nickname_safe}_c1_rating">{top["match_scores"]["final_ratings"]["healing_per_minute"]["html"]}</td>
                          </tr>
                          <tr>
                            <td id="{g.nickname_safe}_contribution2">Damage</td>
                            <td id="{g.nickname_safe}_overall_c2">{int(top["match_scores"]["derived_stats"]["damage_per_minute"])}</td>
                            <td id="{g.nickname_safe}_c2_rating">{top["match_scores"]["final_ratings"]["damage_per_minute"]["html"]}</td>
                          </tr>
                          <tr><td colspan="3"><canvas class="hero_chart" id="{g.nickname_safe}_hero_chart"></canvas></td></tr>
                          """

    html = html +f"""</div>
                            <div class="row table-responsive bg-dark">
                                <table class="table table-dark table-borderless">
                                  <thead class="text-muted">
                                    <tr>

                                      <td></td>
                                      <td>Overall</td>
                                      <td>Rating</td>

                                    </tr>
                                  </thead>
                        <tbody>
                        <tr>
                          <td>Score</td>
                          <td id="{g.nickname_safe}_overall_score_value">{round(top["match_scores"]["score"])}%</td>
                          <td id="{g.nickname_safe}_score_rating">{top["match_scores"]["final_ratings"]["score"]["html"]}</td>
                        </tr>
                        <tr>
                          <td>Winrate</td>
                          <td id="{g.nickname_safe}_overall_winrate">{int(top["match_scores"]["derived_stats"]["win_rate"]*100)}%</td>
                          <td id="{g.nickname_safe}_win_rating">{top["match_scores"]["final_ratings"]["win_rate"]["html"]}</td>
                        </tr>
                        <tr>
                          <td>KDA</td>
                          <td id="{g.nickname_safe}_overall_kda">{round(top["match_scores"]["derived_stats"]["kda"],2)}</td>
                          <td id="{g.nickname_safe}_kda_rating">{top["match_scores"]["final_ratings"]["kda"]["html"]}</td>
                        </tr>
                        {contributions}
                      </tbody>
                                </table>
                            </div>
                        </div>
                        <div class="col-5 text-center profile_column">
                            <div class="row justify-content-between">
                                <p class="profile_name"><span><img src="img/player_heads/{g.data["player"]["icon"]["player_icon_id"]}.png" class="player_head_image rounded-circle img-fluid"></span> <span>{g.nickname_safe.upper()}</span></p>
                            </div>
                            <div class="row sr_chart">
                                <canvas id="{g.nickname_safe}chart"></canvas>
                            </div>
                            <script>"""
    rank_history_size = len(g.match_data)
    if rank_history_size > rank_history_count:
      rank_history_size = rank_history_count
    labels = ""
    datapoints = ""
    if g.feedback["percent_difference"] > 0:
      g.feedback["percent_difference"] = "+"+str(g.feedback["percent_difference"])
    feedback = '<span class="badge bg-'
    if g.feedback["sentiment"] == "toast" or g.feedback["sentiment"] == "above":
      feedback += f'success">{g.feedback["percent_difference"]} %</span>'
    elif g.feedback["sentiment"] == "neutral":
      feedback += f'secondary">{g.feedback["percent_difference"]} %</span>'
    else:
      feedback += f'danger">{g.feedback["percent_difference"]} %</span>'
    for n in range(rank_history_size):
      labels += "'"+g_master.convert_timestamp_to_date(g.match_data[n]["extended_data"]["match_time_stamp"])+"',"
      datapoints +=str(int(g.match_data[n]["extended_data"]["match_player"]["score_info"]["new_score"]))+","
    rank_annotations = get_rank_breakpoint_annotations(globalMinSR, globalMaxSR)
    html = html + f"""
                              const {g.nickname_safe}labels = [{labels}];
                              {g.nickname_safe}labels.reverse()

                              function createResizedImage(src, width, height, callback) {{
                                const img = new Image();
                                img.src = src;
                                img.onload = function () {{
                                  const canvas = document.createElement('canvas');
                                  canvas.width = width;
                                  canvas.height = height;
                                  const ctx = canvas.getContext('2d');
                                  ctx.drawImage(img, 0, 0, width, height);
                                  const resizedImg = new Image();
                                  resizedImg.src = canvas.toDataURL();
                                  resizedImg.onload = function () {{
                                    callback(resizedImg);
                                  }};
                                }};
                              }}

                              // Resize the image and then create the chart
                              createResizedImage('./img/rank/{g.rank}.png', 50, 40, function (customImage) {{

                                const {g.nickname_safe}dataPoints = [{datapoints}];
                                {g.nickname_safe}dataPoints.reverse()

                                const pointStyles = {g.nickname_safe}dataPoints.map((_, index) =>
                                  index === {g.nickname_safe}dataPoints.length - 1 ? customImage : 'circle'
                                );

                                const pointRadii = {g.nickname_safe}dataPoints.map((_, index) =>
                                  index === {g.nickname_safe}dataPoints.length - 1 ? 10 : 3
                                );

                                const globalMinSR = {globalMinSR};
                                const globalMaxSR = {globalMaxSR};

                                const rankAnnotations = {rank_annotations};  // ✅ Injected from Python

                                console.log("Injected Rank Annotations:", rankAnnotations);  // ✅ Debugging

                                const data = {{
                                  labels: {g.nickname_safe}labels,
                                  datasets: [{{
                                    label: 'SR',
                                    backgroundColor: 'rgb({g.color_dark_r}, {g.color_dark_g}, {g.color_dark_b})',
                                    borderColor: 'rgb({g.color_light_r}, {g.color_light_g}, {g.color_light_b})',
                                    data: {g.nickname_safe}dataPoints,
                                    pointStyle: pointStyles,
                                    pointRadius: pointRadii,
                                    pointHoverRadius: 5
                                  }}]
                                }};

                                const config = {{
                                  type: 'line',
                                  data: data,
                                  options: {{
                                    maintainAspectRatio: false,
                                    responsive: true,
                                    plugins: {{
                                      legend: {{ display: false }},
                                      annotation: {{ annotations: rankAnnotations }}  // ✅ Now injected directly from Python!
                                    }},
                                    scales: {{
                                      x: {{ ticks: {{ display: false }} }},
                                      y: {{
                                        ticks: {{display: false}},
                                        min: globalMinSR,
                                        max: globalMaxSR
                                      }}
                                    }}
                                  }}
                                }};

                                const {g.nickname_safe}chart = new Chart(
                                  document.getElementById('{g.nickname_safe}chart'),
                                  config
                                );
                              }});

                              // Extract labels & data
                              let {g.nickname_safe}_heroLabels = {json.dumps([entry["date"] for entry in top["match_scores"]["score_array"]])};
                              let {g.nickname_safe}_heroData = {json.dumps([entry["score"] for entry in top["match_scores"]["score_array"]])};

                              // 🆕 If only one data point exists, create a fake second point to center it
                              if ({g.nickname_safe}_heroData.length === 1) {{
                                {g.nickname_safe}_heroLabels = ["", {g.nickname_safe}_heroLabels[0], ""];  // Empty labels on both sides
                                {g.nickname_safe}_heroData = [null, {g.nickname_safe}_heroData[0], null];  // Keep the real value in the center
                              }}

                              // 🆕 Determine Chart Type
                              const {g.nickname_safe}_chartType = ({g.nickname_safe}_heroData.filter(v => v !== null).length > 1) ? 'line' : 'scatter';

                              // Prepare hero chart data
                              const {g.nickname_safe}_heroChartData = {{
                                labels: {g.nickname_safe}_heroLabels,
                                datasets: [{{
                                  label: 'Hero Score Progression',
                                  backgroundColor: 'rgb({g.color_dark_r}, {g.color_dark_g}, {g.color_dark_b})',
                                  borderColor: 'rgb({g.color_light_r}, {g.color_light_g}, {g.color_light_b})',
                                  data: {g.nickname_safe}_heroData,
                                  pointRadius: 7,
                                  pointHoverRadius: 12
                                }}]
                              }};


                                const {g.nickname_safe}_heroChartConfig = {{
                                  type: {g.nickname_safe}_chartType,
                                  data: {g.nickname_safe}_heroChartData,
                                  options: {{
                                    maintainAspectRatio: false,
                                    responsive: true,
                                    plugins: {{
                                      legend: {{ display: false }},
                                      tooltip: {{  // 🆕 Custom tooltip formatter
                                        callbacks: {{
                                          title: (tooltipItems) => `Date: ${{tooltipItems[0].label}}`,  // First line: Date
                                          label: (tooltipItem) => `Hero Score: ${{tooltipItem.raw}}`  // Second line: Hero Score: N
                                        }}
                                      }}
                                    }},
                                    scales: {{
                                      y: {{
                                        min: globalMinScore,
                                        max: globalMaxScore
                                      }},
                                      x: {{ ticks: {{ display: true }} }}
                                    }}
                                  }}
                                }};


                              // Store chart globally so we can update it later
                              window["{g.nickname_safe}_heroChart"] = new Chart(
                                document.getElementById("{g.nickname_safe}_hero_chart"),
                                {g.nickname_safe}_heroChartConfig
                              );



                            </script>
                            <div class="row mt-3">
                                <div class="col-6 text-center">
                                    <p>Stack score</p>
                                    <h5>{g.match_scores["score"]}</h5>
                                </div>
                                <div class="col-6 text-center">
                                    <p>Rank Score</p>
                                    <h5>{gamer_sr}</h5>
                                </div>
                            </div>
                            <div class="row mt-3">
                              {generate_progress_bar(gamer_sr,g.full_rank,g)}
                            </div>

                        </div>
                        </div>
                            <div class="row mt-3 feedback">
                              {g.get_styled_feedback()}
                            </div>
                    </div>

                
    """
  return html

def generate_toppers(g_master):
    html = """
    <div class="container">
        <div class="row justify-content-center">
          <h2 class='gradient-header text-center'>Biggest Numbers <img src="img/Galacta.webp" id="galacta"></h2>
        </div>      
        <div class='topper-container row p-3'>
    """
    toppers = g_master.get_strongest_performances()

    # Define a mapping for cleaner names
    stat_name_mapping = {
        "total_hero_damage": "Damage",
        "total_damage_taken": "Tanking",
        "total_hero_heal": "Healing"
    }

    for top in toppers:
        clean_stat = stat_name_mapping.get(top["stat"], top["stat"].replace("_", " ").title())

        html += f"""
        <div class="col-4 topper_wrapper" style="background: radial-gradient(circle at bottom left, rgba({top["player"].color_light_r}, {top["player"].color_light_g}, {top["player"].color_light_b}, 0.8), rgba(255, 0, 150, 0) 65%);">
            <p class="topper-stat">{clean_stat}</p>
            <p class="topper-player"><span><img src="img/player_heads/{top["player"].data["player"]["icon"]["player_icon_id"]}.png" class="player_head_image rounded-circle img-fluid"></span> <span>{top["player"].nickname.upper()}</span></p>
            <div class="section-divider">
              <span>{int(top["metric"])}</span>
            </div>
            <img src="{top["player"].get_hero_costume(top["hero"])}" class="topper-hero">
        </div>
        """

    html += """
                </div>
              </div>
        </div>
    </div>
    """
    return html

def generate_superstars(g_master):
    html = """
    <div class="container">
        <div class="row justify-content-center">
          <h2 class='gradient-header text-center'>Our superstars <img src="img/Galacta.webp" id="galacta"></h2>
        </div>      
        <div class='topper-container row p-4'>
    """
    superstars = g_master.get_superstars()
    sizes = [6,4,2]
    count = 0
    for star in superstars:
        html += f"""
        <div class="col-{sizes[count]} topper_wrapper" style="background: radial-gradient(circle at bottom left, rgba({star["gamer"].color_light_r}, {star["gamer"].color_light_g}, {star["gamer"].color_light_b}, 0.8), rgba(255, 0, 150, 0) 65%);">
            <p class="topper-{sizes[count]}"><span><img src="img/player_heads/{star["gamer"].data["player"]["icon"]["player_icon_id"]}.png" class="player_head_image rounded-circle img-fluid"></span> <span>{star["gamer"].nickname.upper()}</span></p>
            <p class="mvp-count"><span class="">{star["hero"]["mvp_count"]}</span></p>
            <p class="svp-count"><span class="">{star["hero"]["svp_count"]}</span></p>
            <img src="{star["gamer"].get_hero_costume(star["hero"]["hero_id"])}" class="topper-hero">
        </div>
        """
        count += 1

    html += """
                </div>
              </div>
        </div>
    </div>
    """
    return html

def generate_hero_highlights(top_heroes):
  html = """
  <div class="container mt-5">
    <h2 class='gradient-header text-center'>Heroes & Villains <img src="img/Galacta.webp" id="galacta"></h2>
    <div class="row">
      <!-- 🔹 Column: Top 3 Best Performances -->
      <div class="col-md-12 highlight_wrapper">
        <p>The heroes we need</p>
        <ul class="list-group list-group list-group-flush">
  """

  # 🆕 Generate Top 3 List Items
  for star in top_heroes:
    html += f"""
        <li class="list-group-item text-light border-secondary" style="background-color: rgba(0,0,0,0);">
          <div class="row highlight_row">
            <div class="col-5 custom_vertical">
              <img src="img/player_heads/{star["gamer"].data["player"]["icon"]["player_icon_id"]}.png" class="player_head_image rounded-circle img-fluid me-2" width="35">
              <span>{star["gamer"].nickname.upper()}</span>
            </div>
            <div class="col-5 custom_vertical">
              <img src="img/heroes/{star["hero"]["hero_id"]}_icon.webp" class="highlight-hero me-2">
              <p class="highlight_date"> {datetime.strptime(star["date"], "%Y-%m-%d").strftime("%d.%m")}</p>
            </div>
            <div class="col-2 custom_vertical">
              <span class="">{star["value"]}</span>
            </div>
          </div>
        </li>
    """

  html += """
        </ul>
      </div>
    </div>
  </div>
  """

  return html

def generate_timeline(g_master, bronze):
    """
    Builds an HTML section that shows:
      1) A chronological event timeline for the latest game night.
      2) The latest game_night's AI_title & AI_summary in a simple card.
      3) A Chart.js line chart (canvas) with a custom tooltip.
    """

    game_night_folder = "./game_nights/"
    audiopath = "../audio/"
    if bronze:
        game_night_folder = "./game_nights_bronze/"
        audiopath = "../audio_bronze/"


    # Arrays for the chart & latest data
    dates_obj = []
    avg_scores = []
    ai_titles = []
    total_wins_list = []
    total_losses_list = []
    players_details = []
    all_events = {} # Store events per date

    latest_date = None
    latest_ai_title = ""
    latest_ai_summary = ""
    latest_events = [] # <-- Store events for the latest night

    # --- Pass 1: Read all data and find the latest date ---
    for filename in os.listdir(game_night_folder):
        if not filename.endswith(".json") or filename == "happenings.json":
            continue

        full_path = os.path.join(game_night_folder, filename)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            continue

        file_date_str = data.get("date")
        if not file_date_str: continue

        try:
            date_obj = datetime.strptime(file_date_str, "%Y-%m-%d")
        except ValueError:
            print(f"Skipping {filename}, invalid date format.")
            continue

        # Store data needed for the chart AND events
        players = data.get("players", [])
        total_score = sum(p.get("score", 0) for p in players)
        avg_score = total_score / len(players) if players else 0
        p_details = sorted(
            [{"nickname": p.get("nickname", "N/A"), "score": p.get("score", 0)} for p in players],
            key=lambda x: x["score"], reverse=True
        )

        dates_obj.append(date_obj)
        avg_scores.append(avg_score)
        ai_titles.append(data.get("AI_title", "(No AI_title found)"))
        total_wins_list.append(data.get("total_wins", 0))
        total_losses_list.append(data.get("total_losses", 0))
        players_details.append(p_details)
        all_events[date_obj] = data.get("events", []) # Store events keyed by date_obj

        # Track the latest date
        if latest_date is None or date_obj > latest_date:
            latest_date = date_obj
            latest_events = data.get("events", [])
            if ai_enabled:
              latest_ai_title = data.get("AI_title", "(No AI_title found)")
              latest_ai_summary = data.get("AI_summary", "(No AI_summary found)")
              # Get events for the latest date *after* confirming it's the latest
            else:
              latest_ai_title = "Game night"
              latest_ai_summary = ""


    # --- Check if any data was processed ---
    if not dates_obj:
        return "<p>No game night data found to generate timeline.</p>"


    # --- Combine, sort by date, and unzip for the chart ---
    combined_data = list(zip(
        dates_obj, avg_scores, ai_titles, total_wins_list, total_losses_list, players_details
    ))
    combined_data.sort(key=lambda x: x[0])  # ascending by date

    sorted_dates_obj, sorted_avg_scores, sorted_ai_titles, \
        sorted_wins, sorted_losses, sorted_players_details = zip(*combined_data)


    # --- Prepare data for Chart.js ---
    date_labels_ddmm = [d.strftime("%d.%m") for d in sorted_dates_obj]
    js_labels = ",".join(f"'{lbl}'" for lbl in date_labels_ddmm)
    js_data = ",".join(str(round(s, 2)) for s in sorted_avg_scores)
    safe_ai_titles = [remove_html_tags(t.replace("'", "\\'")) for t in sorted_ai_titles]
    js_ai_titles = ",".join(f"'{t}'" for t in safe_ai_titles)
    js_wins = ",".join(str(w) for w in sorted_wins)
    js_losses = ",".join(str(l) for l in sorted_losses)

    timeline_players_str_list = []
    for p_list in sorted_players_details:
        encoded = json.dumps(p_list).replace("'", "\\'")
        timeline_players_str_list.append(f"'{encoded}'")
    js_timeline_players = ",".join(timeline_players_str_list)


    # --- Prepare Audio Button ---
    latest_date_str_dmy = latest_date.strftime("%d.%m.%Y") if latest_date else ""
    latest_date_str_dm = latest_date.strftime("%d.%m") if latest_date else ""
    latest_audio_file = latest_date.strftime(f"%Y_%m_%d.mp3") if latest_date else ""
    latest_audio_path_rel = os.path.join(audiopath, latest_audio_file).replace("\\", "/")[1:] # Relative path for HTML src
    latest_audio_path_abs = os.path.join(audiopath, latest_audio_file)

    audio_button_html = ""
    if os.path.exists(latest_audio_path_abs):
        audio_button_html = f"""
        <button class="audiobutton" id="play-btn-{latest_date_str_dm}" title="Play Game Night Summary Audio">
            <i class="ri-play-circle-line"></i> <!-- Play icon -->
        </button>
        <audio id="audio-{latest_date_str_dm}" src="{latest_audio_path_rel}" preload="none"></audio>
        <script>
            (function() {{ // IIFE to scope variables
                const playBtn = document.getElementById('play-btn-{latest_date_str_dm}');
                const audio = document.getElementById('audio-{latest_date_str_dm}');
                if (playBtn && audio) {{
                    playBtn.addEventListener('click', () => {{
                        if (audio.paused) {{
                            audio.play();
                            playBtn.innerHTML = '<i class="ri-pause-circle-line"></i>'; // Pause icon
                            playBtn.title = "Pause Game Night Summary Audio";
                        }} else {{
                            audio.pause();
                            playBtn.innerHTML = '<i class="ri-play-circle-line"></i>'; // Play icon
                            playBtn.title = "Play Game Night Summary Audio";
                        }}
                    }});
                    audio.addEventListener('ended', () => {{
                         playBtn.innerHTML = '<i class="ri-play-circle-line"></i>'; // Reset to Play icon
                         playBtn.title = "Play Game Night Summary Audio";
                    }});
                     audio.addEventListener('pause', () => {{
                         // Ensure button resets if paused not via button (e.g. navigating away)
                         if(audio.paused && !audio.ended) {{ // only reset if paused mid-play
                           // playBtn.innerHTML = '<i class="ri-play-circle-line"></i>';
                           // playBtn.title = "Play Game Night Summary Audio";
                         }}
                    }});
                }}
            }})();
        </script>
        """

    # --- Generate HTML for the Event Timeline ---
    event_timeline_html = ""
    if latest_events:
        event_list_items = []
        for event in latest_events:
            event_type = event.get("event_type", "unknown")
            readable_time = event.get("readable_time", "")
            message = event.get("message", "Event occurred.")
            outcome = event.get("outcome", "") # Specifically for match_played

            icon_class = "ri-question-mark" # Default icon
            outcome_class = "" # For win/loss styling

            if event_type == "game_night_started":
                icon_class = "ri-calendar-event-line"
            elif event_type == "players_arrived" or event_type == "players_joined":
                icon_class = "ri-user-add-line"
            elif event_type == "players_departed":
                icon_class = "ri-user-unfollow-line"
            elif event_type == "match_played":
                icon_class = "ri-gamepad-line"
                if outcome == "victory":
                    outcome_class = "event-win"
                elif outcome == "defeat":
                    outcome_class = "event-loss"
            elif event_type == "game_night_ended":
                icon_class = "ri-flag-line"

            # Sanitize message slightly for HTML display
            safe_message = message.replace('<', '<').replace('>', '>')

            event_list_items.append(f"""
            <li class="event-item {outcome_class}">
                <span class="event-icon"><i class="{icon_class}"></i></span>
                <span class="event-time">{readable_time}</span>
                <span class="event-message">{safe_message}</span>
            </li>
            """)

        event_timeline_html = f"""
        <div class="game-night-event-timeline mb-4">
            <h4 class="mb-3">Latest Game Night Timeline ({latest_date_str_dm})</h4>
            <ul class="event-list">
                {''.join(event_list_items)}
            </ul>
        </div>
        """


    # --- Build final HTML ---
    # Added CSS within a <style> tag for simplicity. Move to your CSS file if preferred.
    html = f"""
<div class="container mt-4">

    <!-- *NEW* Event Timeline Section -->
    {event_timeline_html}

    <!-- Latest Game Night Info -->
    <div class="card mb-4 text-light game_night_summary">
        <div class="card-header">
            <p>Latest Game Night Summary</p>
        </div>
        <div class="card-body">
            <h5 class="card-title">
                <span>{latest_ai_title} ({latest_date_str_dm})</span>
                {audio_button_html}
            </h5>
            <p class="card-text">{format_text(g_master, latest_ai_summary)}</p>
        </div>
    </div>

    <!-- Performance Timeline Chart -->
    <div class="performance-timeline-container">
        <div class="row">
            <div class="col-12">
                <h2 class="mb-3">{squadname} Performance Timeline</h2>
                <div class="chart-container-wrapper">
                   <canvas id="scoreTimelineCanvas"></canvas>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
  // Prepare data from Python
  const timelineLabels = [{js_labels}];
  const timelineData = [{js_data}];
  const timelineAiTitles = [{js_ai_titles}];
  const timelineWins = [{js_wins}];
  const timelineLosses = [{js_losses}];
  const timelinePlayers = [{js_timeline_players}]; // array of JSON strings

  // Build Chart.js config
  const timelineChartConfig = {{
    type: 'line',
    data: {{
      labels: timelineLabels,
      datasets: [
        {{
          label: 'Average Player Score',
          data: timelineData,
          backgroundColor: 'rgba(0, 150, 199, 0.3)', // Adjusted color
          borderColor: 'rgba(0, 150, 199, 1)', // Adjusted color
          borderWidth: 2,
          fill: true,
          tension: 0.1, // Slight curve to lines
          pointRadius: 5, // Smaller points
          pointHoverRadius: 8,
          pointBackgroundColor: 'rgba(0, 150, 199, 1)',
        }}
      ]
    }},
    options: {{
      maintainAspectRatio: false, // Important with wrapper div
      responsive: true,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          backgroundColor: 'rgba(0, 0, 0, 0.8)', // Darker tooltip
          titleColor: '#fff',
          bodyColor: '#ddd',
          padding: 10,
          boxPadding: 5,
          callbacks: {{
            // Tooltip Title: "24.02 | 4/1"
            title: (tooltipItems) => {{
              const idx = tooltipItems[0].dataIndex;
              const dateLabel = tooltipItems[0].label;
              return dateLabel + ' | W:' + timelineWins[idx] + ' / L:' + timelineLosses[idx];
            }},
            // Tooltip Label: 1) AI Title
            //               2) Each player's "nickname: score" on separate lines
            label: (tooltipItem) => {{
              const idx = tooltipItem.dataIndex;
              let lines = [];
              lines.push(timelineAiTitles[idx]);

              const playersData = JSON.parse(timelinePlayers[idx]);
              lines.push(''); // Spacer line
              for (const p of playersData) {{
                lines.push(p.nickname + ': ' + p.score);
              }}
              return lines;
            }}
          }}
        }}
      }},
      scales: {{
        y: {{
          beginAtZero: false, // Don't force Y axis to start at 0
          ticks: {{ color: '#bbb' }},
          grid: {{ color: 'rgba(255, 255, 255, 0.1)' }} // Lighter grid lines
        }},
        x: {{
          ticks: {{ color: '#bbb' }},
          grid: {{ color: 'rgba(255, 255, 255, 0.1)' }} // Lighter grid lines
        }}
      }}
    }}
  }};

  // Create the Chart
  const scoreTimelineCtx = document.getElementById('scoreTimelineCanvas')?.getContext('2d');
  if (scoreTimelineCtx) {{ // Check if canvas exists
      new Chart(scoreTimelineCtx, timelineChartConfig);
  }} else {{
      console.error("Could not find canvas element with id 'scoreTimelineCanvas'");
  }}
</script>
"""
    return html





def generate_matchups(g_master):
    html = """
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-lg-10">
                <h2 class='gradient-header text-center'>Matchups <img src="img/Galacta.webp" id="galacta"></h2>
                <div class='matchup-container'>
    """

    for g in g_master.gamers:
        strong = g.strongest_matchup
        weak = g.weakest_matchup
        style_strong = "secondary"
        style_weak = "secondary"
        if strong['win_rate'] > 60:
          style_strong = "success"
        if weak['win_rate'] < 40: 
          style_weak = "danger"
        
        wr_strong = f"""<span class="badge ">{strong['win_rate']} %</span>"""
        wr_weak = f"""<span class="badge ">{weak['win_rate']} %</span>"""

        html += f"""
        <div class="matchup-card" style="background: radial-gradient(circle at top right, rgba({g.color_light_r}, {g.color_light_g}, {g.color_light_b}, 0.8), rgba(255, 0, 150, 0) 65%);">
            <div class="matchup-header">
                <p class="matchup-player"><span><img src="img/player_heads/{g.data["player"]["icon"]["player_icon_id"]}.png" class="player_head_image rounded-circle img-fluid"></span> <span>{g.nickname_safe.upper()}</span></p>
            </div>
            
            <div class="matchup-body">
                <div class="matchup-block">
                    <p class="matchup-label strong">Loves to see</p>
                    <img src="img/heroes/{strong['hero_id']}_icon.webp" class="matchup-hero">
                    <p class="matchup-count"><span class="badge">{strong["matches"]}</span></p>
                    <p class="matchup-hero-name">{strong['hero_name'].title()}</p>
                    <p class="matchup-winrate">Winrate: {wr_strong}</p>
                </div>

                <div class="matchup-block">
                    <p class="matchup-label weak">Hates to see</p>
                    <img src="img/heroes/{weak['hero_id']}_icon.webp" class="matchup-hero">
                    <p class="matchup-count"><span class="badge">{weak["matches"]}</span></p>
                    <p class="matchup-hero-name">{weak['hero_name'].title()}</p>
                    <p class="matchup-winrate">Winrate: {wr_weak}</p>
                </div>
            </div>
        </div>
        """

    html += """
                </div>
            </div>
        </div>
    
    """
    return html


def generate_bottom(g_master):
	html = """
	<footer class="pt-5 border-top">
	Created by MegabyteBro &middot; &copy; 2025
	</footer>
  </div>
	</div>
      <script>
  $(document).ready(function () {
    $(".profile_card").each(function () {
      let parentCard = $(this); // Get the current profile card

      // Find the first active hero inside this card
      let firstActiveHero = parentCard.find(".active_hero");
      
      if (firstActiveHero.length) {
        let matchingClass = firstActiveHero.attr("class").split(/\\s+/).find(cls => cls.endsWith("_card"));

        if (matchingClass && typeof window[matchingClass] !== "undefined") {
          let jsonData = window[matchingClass]; // ✅ Access hero data
          console.log("Setting initial background for:", matchingClass, jsonData);

          // Get the correct hero image URL
          let initialHeroImage = `url(${jsonData.costume})`;

          // ✅ Set the background dynamically for this profile card
          parentCard[0].style.setProperty("--hero-bg", initialHeroImage);
        }
      }
    });
    $(".profile_card").each(function () {
      attachClickHandlers($(this));
    });

function attachClickHandlers(parentCard) {
  parentCard.find(".non_active_hero").off("click").on("click", function () {
    let activeHero = parentCard.find(".active_hero");

    // Swap classes: Make active hero non-active
    activeHero.removeClass("active_hero").addClass("non_active_hero");

    // Make the clicked one active
    $(this).removeClass("non_active_hero").addClass("active_hero");

    // Extract JSON data using the global variable
    let matchingClass = $(this).attr("class").split(/\\s+/).find(cls => cls.endsWith("_card"));
    console.log("Matching class found:", matchingClass); // ✅ Debugging log

    if (matchingClass && typeof window[matchingClass] !== "undefined") {
      let jsonData = window[matchingClass]; // ✅ Access the global variable
      console.log("Extracted JSON:", jsonData); // ✅ Should now print correct data

      // Extract the player's nickname from the class name
      let playerNickname = matchingClass.split("_")[0]; // Get the first part of the class (nickname)
      let newHeroImage = `url(${jsonData.costume})`;

      // ✅ Dynamically update the background image of the parent .profile_card
      parentCard[0].style.setProperty("--hero-bg", newHeroImage);
      let roleMapping = {
        "Vanguard": ["Tanking", "Damage"],
        "Duelist": ["Damage", "Kills"],
        "Strategist": ["Healing", "Damage"] // Updated role name
      };

      let role = jsonData.role;
      let categories = roleMapping[role] || ["Unknown", "Unknown"]; // Default fallback

      $(`#${playerNickname}_contribution1`).text(categories[0]);
      $(`#${playerNickname}_contribution2`).text(categories[1]);

      // Helper function to validate numbers
      function safeNumber(value, fallback = "-") {
        return (typeof value === "number" && !isNaN(value)) ? Math.round(value) : fallback;
      }

      function safePercentage(value, fallback = "-") {
        return (typeof value === "number" && !isNaN(value)) ? `${Math.round(value * 100)}%` : fallback;
      }

      function safeDecimal(value, fallback = "-") {
        return (typeof value === "number" && !isNaN(value)) ? value.toFixed(2) : fallback;
      }

      // Update the stats dynamically in the table
      $(`#${playerNickname}_overall_score_value`).text(safeNumber(jsonData.score)+"%");

      $(`#${playerNickname}_overall_winrate`).text(safePercentage(jsonData.derived_stats?.win_rate));

      $(`#${playerNickname}_overall_kda`).text(safeDecimal(jsonData.derived_stats?.kda));

      // Determine whether to use integers or decimals for contribution stats
      let overallC1 = safeNumber(jsonData.derived_stats?.[categories[0].toLowerCase() + "_per_minute"]);

      // If the hero is a Duelist, use 2 decimal places for c2 (Kills)
      let overallC2 = (role === "Duelist") 
          ? safeDecimal(jsonData.derived_stats?.[categories[1].toLowerCase() + "_per_minute"]) 
          : safeNumber(jsonData.derived_stats?.[categories[1].toLowerCase() + "_per_minute"]);

      // Update contribution values dynamically
      $(`#${playerNickname}_overall_c1`).text(overallC1);

      $(`#${playerNickname}_overall_c2`).text(overallC2);

      $(`#${playerNickname}_c1_rating`).html(jsonData.final_ratings?.[categories[0].toLowerCase() + "_per_minute"].html);
      $(`#${playerNickname}_c2_rating`).html(jsonData.final_ratings?.[categories[1].toLowerCase() + "_per_minute"].html);
      $(`#${playerNickname}_kda_rating`).html(jsonData.final_ratings?.kda.html);
      $(`#${playerNickname}_score_rating`).html(jsonData.final_ratings?.score.html);
      $(`#${playerNickname}_win_rating`).html(jsonData.final_ratings?.win_rate.html);

// --- 🆕 Update the Hero Chart! ---
let chartKey = `${playerNickname}_heroChart`;
if (window[chartKey]) {
  // Extract new labels & data
  let newLabels = jsonData.score_array.map(entry => entry.date);
  let newData = jsonData.score_array.map(entry => entry.score);

  // 🆕 If only one data point exists, center it
  if (newData.length === 1) {
    newLabels = ["", newLabels[0], ""];
    newData = [null, newData[0], null];  // Fake points to center it
  }

  // 🆕 Determine the correct chart type dynamically
  let newChartType = (newData.filter(v => v !== null).length > 1) ? 'line' : 'scatter';

  // Update chart type if necessary
  if (window[chartKey].config.type !== newChartType) {
    window[chartKey].config.type = newChartType;
  }

  // Update chart data
  window[chartKey].data.labels = newLabels;
  window[chartKey].data.datasets[0].data = newData;

  // Repaint chart
  window[chartKey].update();
} else {
  console.warn(`⚠ Chart for ${playerNickname} not found! Check if it was properly initialized.`);
}



    } else {
      console.warn("No JSON data found for:", matchingClass);
    }

    // Reattach click handlers to all eligible non-active heroes
    attachClickHandlers(parentCard);
  });
}


  });
</script>
"""
	return html


def generate_tabs(g_master):
    """
    Creates a tabbed navigation for squad insights.
    """
    html = """
    <ul class="nav nav-tabs" id="playerTabs">
    """
    for g in g_master.gamers:
        active_class = "active" if g == g_master.gamers[0] else ""
        html += f"""
        <li class="nav-item">
            <a class="nav-link {active_class}" data-bs-toggle="tab" href="#{g.nickname_safe.lower()}">{g.nickname_safe}</a>
        </li>
        """
    html += "</ul>"
    return html

def generate_player_insights(g,g_master):
    """
    Generates an HTML section for a player's insights, including their ban list, synergies, and worst matchups.
    """
    html = f"""
    <div id="{g.nickname_safe.lower()}" class="tab-pane fade {'show active' if g == g_master.gamers[0] else ''}">
        <h3>{g.nickname_safe} Insights</h3>

        <!-- Ban List -->
        <div class="card mb-3">
            <div class="card-header">Ban List</div>
            <ul class="list-group list-group-flush">
    """
    for ban in g.ban_list:
        html += f"""
            <li class="list-group-item">{ban["name"]} ({ban["role"]}) - Win Rate: {ban["win_percent"]}%</li>
        """
    html += "</ul></div>"

    # Best & Worst Synergies
    html += f"""
        <div class="card mb-3">
            <div class="card-header">Best Hero Synergies</div>
            <ul class="list-group list-group-flush">
    """
    for combo in g.combo_list:
        combo_names = ", ".join([f"{h['hero']} ({h['role']})" for h in combo["hero_combos"]])
        html += f"""
            <li class="list-group-item">{combo["player_hero_name"]} + {combo_names} - WR: {combo["win_percent"]}%</li>
        """
    html += "</ul></div>"

    html += f"""
        <div class="card mb-3">
            <div class="card-header">Worst Hero Synergies</div>
            <ul class="list-group list-group-flush">
    """
    for anti_combo in g.anti_combo_list:
        anti_names = ", ".join([f"{h['hero']} ({h['role']})" for h in anti_combo["hero_combos"]])
        html += f"""
            <li class="list-group-item">{anti_combo["player_hero_name"]} + {anti_names} - WR: {anti_combo["win_percent"]}%</li>
        """
    html += "</ul></div>"

    # Charts placeholder
    html += f"""
        <div class="row">
            <div class="col-md-6">
                <canvas id="banChart_{g.nickname_safe.lower()}"></canvas>
            </div>
            <div class="col-md-6">
                <canvas id="synergyChart_{g.nickname_safe.lower()}"></canvas>
            </div>
        </div>
    """

    html += "</div>"
    return html

def generate_chart_scripts(g_master):
    """
    Generates Chart.js scripts dynamically for each player's analytics.
    """
    html = "<script>"

    for g in g_master.gamers:
        # Ban Effectiveness Chart (Dual-Axis)
        ban_labels = [ban["name"] for ban in g.ban_list]
        ban_win_data = [ban["win_percent"] for ban in g.ban_list]
        ban_count_data = [ban["bans"] for ban in g.ban_list]

        html += f"""
        new Chart(document.getElementById('banChart_{g.nickname_safe.lower()}').getContext('2d'), {{
            type: 'bar',
            data: {{
                labels: {ban_labels},
                datasets: [
                    {{
                        label: 'Win Rate (%)',
                        data: {ban_win_data},
                        backgroundColor: 'rgba(255, 99, 132, 0.6)', // Red color
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1,
                        yAxisID: 'y-win-rate',
                    }},
                    {{
                        label: 'Bans Count',
                        data: {ban_count_data},
                        backgroundColor: 'rgba(54, 162, 235, 0.4)', // Blue color
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1,
                        yAxisID: 'y-ban-count',
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: true
                    }}
                }},
                scales: {{
                    'y-win-rate': {{
                        type: 'linear',
                        position: 'left',
                        beginAtZero: true,
                        max: 100,
                        title: {{
                            display: true,
                            text: 'Win Rate (%)',
                        }}
                    }},
                    'y-ban-count': {{
                        type: 'linear',
                        position: 'right',
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Bans Count',
                        }}
                    }}
                }}
            }}
        }});"""

        # Synergies grouped by played hero (Dual-Axis)
        hero_synergies = {}
        for combo in g.combo_list:
            played_hero = combo["player_hero_name"]
            if played_hero not in hero_synergies:
                hero_synergies[played_hero] = {"labels": [], "win_data": [], "games_data": []}
            synergy_names = ", ".join([h["hero"] for h in combo["hero_combos"]])
            hero_synergies[played_hero]["labels"].append(synergy_names)
            hero_synergies[played_hero]["win_data"].append(combo["win_percent"])
            hero_synergies[played_hero]["games_data"].append(combo["games_played"])

        for hero, synergy_data in hero_synergies.items():
            chart_id = f"synergyChart_{g.nickname_safe.lower()}_{hero.replace(' ', '')}"
            html += f"""
            new Chart(document.getElementById('{chart_id}').getContext('2d'), {{
                type: 'bar',
                data: {{
                    labels: {synergy_data["labels"]},
                    datasets: [
                        {{
                            label: 'Win Rate (%)',
                            data: {synergy_data["win_data"]},
                            backgroundColor: 'rgb({g.color_dark_r}, {g.color_dark_g}, {g.color_dark_b})',
                            borderColor: 'rgb({g.color_light_r}, {g.color_light_g}, {g.color_light_b})',
                            borderWidth: 1,
                            yAxisID: 'y-win-rate',
                        }},
                        {{
                            label: 'Games Played',
                            data: {synergy_data["games_data"]},
                        backgroundColor: 'rgba(54, 162, 235, 0.4)', // Blue color
                        borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1,
                            yAxisID: 'y-games-played',
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{
                            display: true
                        }}
                    }},
                    scales: {{
                        'y-win-rate': {{
                            type: 'linear',
                            position: 'left',
                            beginAtZero: true,
                            max: 100,
                            title: {{
                                display: true,
                                text: 'Win Rate (%)',
                            }}
                        }},
                        'y-games-played': {{
                            type: 'linear',
                            position: 'right',
                            beginAtZero: true,
                            title: {{
                                display: true,
                                text: 'Games Played',
                            }}
                        }}
                    }}
                }}
            }});"""

    html += "</script>"
    return html




def generate_squad_analysis(g_master):
    """
    Generates the full squad insights page with player tabs and analytics charts.
    """
    html = "<div class='container mt-4'>"
    html += generate_tabs(g_master)
    html += "<div class='tab-content'>"

    for g in g_master.gamers:
        imgrow = ""
        for ban in g.ban_list[:3]:
          imgrow += f"<img class='player_head_image_chart rounded-circle img-fluid' src='./img/heroes/{ban["hero_id"]}_icon.webp'>"
        html += f"""
        <div id="{g.nickname_safe.lower()}" class="tab-pane fade {'show active' if g == g_master.gamers[0] else ''}">
            <div class="row analytics_header">
              <img class="player_banner" src="{g.get_banner()}">
              <h3>{g.nickname_safe} Analytics</h3>
            </div>

            <!-- Ban Effectiveness -->
            <div class="row">
                <div class="col-md-12 outer_analytics_container">
                  <div class="analytics_container">
                    <h4 class="chart_header"><p>{g.nickname_safe} Ban Effects</p>{imgrow}</h4>
                    <canvas class="ban_chart" id="banChart_{g.nickname_safe.lower()}"></canvas>
                  </div>
                </div>
            </div>
        """

        # Generate hero synergy charts
        hero_synergies = set(combo["player_hero_name"] for combo in g.combo_list)

        html += """<div class="row">"""
        for hero in hero_synergies:
            chart_id = f"synergyChart_{g.nickname_safe.lower()}_{hero.replace(' ', '')}"
            html += f"""
                <div class="col-md-6 outer_analytics_container">
                  <div class="analytics_container">
                    <h4 class="chart_header"><p>{hero} Synergies</p></h4>
                    <canvas class="synergy_chart" id="{chart_id}"></canvas>
                  </div>
                </div>
            """

        html += "</div></div>"

    html += "</div></div>"  # Close tab-content & container
    html += generate_chart_scripts(g_master)
    return html


def build_site(gamerlist, bronze):

    game_nights_folder = "./game_nights/"
    sitename="../index.html"
    if bronze:
      game_nights_folder = "./game_nights_bronze/"
      sitename="../bronze.html"

    g_master = Gamer_master(gamerlist,game_nights_folder=game_nights_folder)
    g_master.initiate()
    g_master.sort_gamers()
    g_master.export_data_objects()
    g_master.sort_hero_scores()

    # Create lists to store all heroes with their scores
    hero_scores = []

    # Collect all hero scores across gamers
    for g in g_master.gamers:
      for hero in g.top_heroes:
        for date, value in hero["grouped_match_scores"].items():
          hero_scores.append({
            "date": date,
            "value": value["score"],
            "hero": hero,
            "gamer": g
          })

    # 🆕 Sort heroes by score (descending for highest)
    top_heroes = sorted(hero_scores, key=lambda x: x["value"], reverse=True)[:5]

    # 🆕 Sort heroes by score (ascending for lowest)
    #bottom_heroes = sorted(hero_scores, key=lambda x: x["value"])[:3]
    # Compute and store min/max scores


    html = ""
    html += generate_top(g_master)
    html += generate_gamer_cards(g_master)
    html += generate_squad_analysis(g_master)  # **INSERTED HERE!**
    html += generate_hero_highlights(top_heroes)
    html += generate_timeline(g_master,bronze)    # <--- Insert our new timeline section here!
    html += generate_toppers(g_master)
    html += generate_superstars(g_master)
    html += generate_matchups(g_master)
    html += generate_bottom(g_master)
    html += "</body></html>"

    with open(sitename,"w", encoding="utf-8") as outfile:
        outfile.write(html)
    print("Site built!")

if __name__ == '__main__':
  build_site(gamerlist, False)

