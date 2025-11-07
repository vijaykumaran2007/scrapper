from flask import Flask, jsonify
import json
import os
from flask import request
import requests
from datetime import datetime, timedelta
from pytrends.request import TrendReq
from apscheduler.schedulers.background import BackgroundScheduler
import time
import random
import traceback  # add this at top


def scheduled_job():
    print("⏰ Auto updating outbreak data...")
    data = integrate_data_with_state_analysis()
    with open("enhanced_outbreak_dataset.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print("✅ Data updated!")

scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_job, 'interval', hours=6)
scheduler.start()



app = Flask(__name__)
CORS(app)
# Your existing code here (all the functions)
# ...



# ---------------------------
# CONFIGURATION
# ---------------------------

X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN", "JVV1v9noLtu6GPTY9M7YFGBRG")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-ad1dff2916b64198881456cc0df4e6e2")
 
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"  
DISEASE_KEYWORDS = [
    "dengue", "malaria", "chikungunya", "influenza", "covid", "viral fever",
    "cholera", "typhoid", "pneumonia", "hepatitis", "tuberculosis"
]

DISEASE_MEDICINES = {
    "dengue": "Paracetamol, ORS; avoid aspirin. Hydration essential.",
    "malaria": "ACTs (artemisinin-based), Chloroquine, Primaquine.",
    "chikungunya": "Pain relievers, hydration, and rest.",
    "influenza": "Oseltamivir (Tamiflu), rest, fluids.",
    "covid": "Paracetamol, rest, hydration, antivirals if prescribed.",
    "viral fever": "Paracetamol, fluids, and rest.",
    "cholera": "ORS, Doxycycline, Zinc, and hydration.",
    "typhoid": "Ciprofloxacin, Azithromycin, fluids.",
    "pneumonia": "Antibiotics (Amoxicillin), rest, hydration.",
    "hepatitis": "Rest, hydration, antiviral therapy (if viral).",
    "tuberculosis": "Rifampicin, Isoniazid, Pyrazinamide, Ethambutol (HRZE)."
}

# ---------------------------
# STATE COORDINATES
# ---------------------------
INDIA_STATE_COORDS = {
    "Andhra Pradesh": (15.9129, 79.7400),
    "Arunachal Pradesh": (28.2180, 94.7278),
    "Assam": (26.2006, 92.9376),
    "Bihar": (25.0961, 85.3131),
    "Chhattisgarh": (21.2787, 81.8661),
    "Goa": (15.2993, 74.1240),
    "Gujarat": (22.2587, 71.1924),
    "Haryana": (29.0588, 76.0856),
    "Himachal Pradesh": (31.1048, 77.1734),
    "Jharkhand": (23.6102, 85.2799),
    "Karnataka": (15.3173, 75.7139),
    "Kerala": (10.8505, 76.2711),
    "Madhya Pradesh": (22.9734, 78.6569),
    "Maharashtra": (19.7515, 75.7139),
    "Manipur": (24.6637, 93.9063),
    "Meghalaya": (25.4670, 91.3662),
    "Mizoram": (23.1645, 92.9376),
    "Nagaland": (26.1584, 94.5624),
    "Odisha": (20.9517, 85.0985),
    "Punjab": (31.1471, 75.3412),
    "Rajasthan": (27.0238, 74.2179),
    "Sikkim": (27.5330, 88.5122),
    "Tamil Nadu": (11.1271, 78.6569),
    "Telangana": (17.1232, 79.2088),
    "Tripura": (23.9408, 91.9882),
    "Uttar Pradesh": (26.8467, 80.9462),
    "Uttarakhand": (30.0668, 79.0193),
    "West Bengal": (22.9868, 87.8550),
    "Delhi": (28.6139, 77.2090),
    "Jammu and Kashmir": (33.7782, 76.5762),
    "Ladakh": (34.1526, 77.5770)
}

# ---------------------------
# WEATHER FETCH FUNCTION
# ---------------------------
# ---------------------------
# WEATHER FETCH FUNCTION (FREE OPEN-METEO)
# ---------------------------
def get_weather_data():
    weather_data = {}
    for state, (lat, lon) in INDIA_STATE_COORDS.items():
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m&timezone=auto"
            r = requests.get(url, timeout=10)
            data = r.json()
            
            if "current" in data:
                current = data["current"]
                weather_data[state] = {
                    "temperature": current.get("temperature_2m"),
                    "humidity": current.get("relative_humidity_2m"),
                    "wind_speed": current.get("wind_speed_10m"),
                    "weather": "Current conditions"  # Open-Meteo doesn't provide descriptions
                }
            else:
                weather_data[state] = {"error": "Weather data not available"}
                
        except Exception as e:
            weather_data[state] = {"error": str(e)}
    return weather_data

# ---------------------------
# GOOGLE TRENDS
# ---------------------------
def get_google_trends_data():
    pytrends = TrendReq(hl='en-US', tz=330)
    state_trends = {}

    for keyword in DISEASE_KEYWORDS:
        retries = 3  # retry count

        while retries > 0:
            try:
                pytrends.build_payload([keyword], timeframe='today 3-m', geo='IN')
                time.sleep(random.uniform(5, 12))  # ✅ wait 5-12 sec randomly

                interest = pytrends.interest_by_region(resolution='REGION')

                for state in INDIA_STATE_COORDS.keys():
                    if state not in state_trends:
                        state_trends[state] = {}

                    if state in interest.index:
                        state_trends[state][keyword] = int(interest[keyword][state])

                print(f"✅ Data collected for: {keyword}")
                
                time.sleep(random.uniform(10, 18))  # ✅ longer wait before next keyword
                break  # success → exit retry loop

            except Exception as e:
                if "429" in str(e):
                    retries -= 1
                    wait = random.uniform(20, 40)
                    print(f"⚠ Rate limited! Waiting {int(wait)}s... Retries left: {retries}")
                    time.sleep(wait)  # ✅ wait longer before retry
                else:
                    print("❌ Error:", e)
                    return {}

    return state_trends

# ---------------------------
# GDELT DATA
# ---------------------------
def get_gdelt_data():
    end = datetime.utcnow()
    start = end - timedelta(days=60)
    gdelt_url = (
        f"https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query=({' OR '.join(DISEASE_KEYWORDS)})&mode=ArtList&maxrecords=50&format=json"
        f"&startdatetime={start.strftime('%Y%m%d%H%M%S')}&enddatetime={end.strftime('%Y%m%d%H%M%S')}"
    )
    try:
        r = requests.get(gdelt_url, timeout=15)
        data = r.json()
        articles = []
        seen_titles = set()
        for a in data.get("articles", []):
            title = a.get("title", "")
            if title in seen_titles:  # avoid duplicates
                continue
            seen_titles.add(title)
            found_diseases = [d for d in DISEASE_KEYWORDS if d.lower() in title.lower()]
            medicines = [DISEASE_MEDICINES[d] for d in found_diseases if d in DISEASE_MEDICINES]
            articles.append({
                "title": title,
                "date": a.get("seendate", ""),
                "url": a.get("url", ""),
                "country": a.get("domain_country", ""),
                "diseases": found_diseases,
                "medicines": medicines
            })
        return articles
    except Exception as e:
        return {"error": str(e)}

# ---------------------------
# X (TWITTER) API DATA
# ---------------------------
def get_twitter_data():
    tweets_data = []
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    start_time = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
    query = "(" + " OR ".join(DISEASE_KEYWORDS) + ") lang:en -is:retweet"

    # CHANGE max_results from 50 to 5:
    url = f"https://api.x.com/2/tweets/search/recent?query={query}&max_results=5&tweet.fields=created_at,lang,public_metrics"
    #                                                                  ^^^^^^^^^^
    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        # Also add limit to only process 5 tweets:
        for t in data.get("data", [])[:5]:  # ← ADD THIS SLICE
            text = t.get("text", "")
            found_diseases = [d for d in DISEASE_KEYWORDS if d.lower() in text.lower()]
            tweets_data.append({
                "tweet": text,
                "created_at": t.get("created_at", ""),
                "metrics": t.get("public_metrics", {}),
                "diseases": found_diseases
            })
        return tweets_data
    except Exception as e:
        return {"error": str(e)}

# ---------------------------
# MAIN INTEGRATION
# ---------------------------
def analyze_with_deepseek_state_insights(data, analysis_type="outbreak_risk"):
    """
    Enhanced analysis that extracts state-level insights including:
    - Risk estimate
    - Key diseases
    - Most required medicine
    - Estimated hospital beds required
    - Weather & trend influence
    """

    state_specific_prompt = """
    Analyze this disease monitoring data and provide STATE-SPECIFIC insights.

    For EACH Indian state, return:

    1. Risk level → High / Medium / Low
    2. Main diseases spreading
    3. Most required medicines (based on outbreak severity)
    4. Estimated number of hospital beds needed (approximate reasonable estimate)
    5. Weather conditions influencing disease
    6. Trend status → Increasing / Stable / Decreasing
    7. Short safety recommendations

    You MUST return only in valid JSON in this exact format:

    {
        "state_analysis": {
            "State Name": {
                "risk_level": "High/Medium/Low",
                "key_diseases": ["disease1", "disease2"],
                "required_medicines": ["medicine1", "medicine2"],
                "estimated_hospital_beds": 1200,
                "weather_factors": ["factor1", "factor2"],
                "trending_status": "Increasing/Stable/Decreasing",
                "recommendations": ["rec1", "rec2"]
            }
        },
        "overall_summary": "Short summary"
    }

    Make realistic estimates for medicine needs and bed requirements.
    Focus only on states where outbreak signals exist.
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are a public health analyzer that outputs only valid JSON."
            },
            {
                "role": "user",
                "content": f"{state_specific_prompt}\n\nData:\n{json.dumps(data, indent=2)}"
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        analysis_text = result["choices"][0]["message"]["content"]

        # Extract JSON safely
        json_start = analysis_text.find('{')
        json_end = analysis_text.rfind('}') + 1

        if json_start != -1 and json_end != 0:
            structured_analysis = json.loads(analysis_text[json_start:json_end])
        else:
            structured_analysis = {"raw_analysis": analysis_text}

        return {
            "analysis_type": analysis_type,
            "structured_insights": structured_analysis,
            "raw_analysis": analysis_text,
            "usage": result.get("usage", {})
        }

    except Exception as e:
        return {"error": f"DeepSeek API call failed: {str(e)}"}


# ---------------------------
# UTILITY FUNCTION TO EXTRACT STATE INSIGHTS
# ---------------------------
def get_state_risk_assessment(final_data):
    """
    Extract state-level risk assessment from the analysis
    """
    if "ai_analysis" not in final_data:
        return "No AI analysis available"
    
    analysis = final_data["ai_analysis"]
    
    if "structured_insights" in analysis and "state_analysis" in analysis["structured_insights"]:
        return analysis["structured_insights"]["state_analysis"]
    else:
        # Fallback: manually parse the raw analysis for state mentions
        states_mentioned = {}
        raw_text = analysis.get("raw_analysis", "")
        
        for state in INDIA_STATE_COORDS.keys():
            if state.lower() in raw_text.lower():
                states_mentioned[state] = "Mentioned in analysis"
        
        return states_mentioned or {"message": "No state-specific insights extracted"}

# Example usage in your main function:
# Example usage in your main function:
def integrate_data_with_state_analysis():
    weather = get_weather_data()
    try:
        trends = get_google_trends_data()
    except:
        trends = {"error": "Google Trends unavailable due to rate limiting"}

    gdelt = get_gdelt_data()
    twitter = get_twitter_data()
    
    final_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "weather_data": weather,
        "google_trends": trends, 
        "gdelt_outbreaks": gdelt,
        "twitter_outbreaks": twitter
    }
    
    if DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "YOUR_DEEPSEEK_API_KEY_HERE":
        print("🤖 Running state-level AI analysis...")
        state_analysis = analyze_with_deepseek_state_insights(final_data)
        final_data["ai_analysis"] = state_analysis
        
        # Extract and print state insights
        state_insights = get_state_risk_assessment(final_data)
        print("\n📊 STATE-LEVEL RISK ASSESSMENT:")
        for state, insights in state_insights.items():
            print(f"  {state}: {insights}")
    
    return final_data




@app.route('/api/outbreak-data', methods=['GET'])
def get_outbreak_data():
    try:
        if os.path.exists('enhanced_outbreak_dataset.json'):
            with open('enhanced_outbreak_dataset.json', 'r') as f:
                data = json.load(f)

            data_time = datetime.fromisoformat(data['timestamp'])
            if (datetime.utcnow() - data_time).total_seconds() < 6 * 3600:
                return jsonify(data)

        print("🔄 Generating fresh outbreak data...")
        new_data = integrate_data_with_state_analysis()

        # ✅ Save file
        with open("enhanced_outbreak_dataset.json", "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4, ensure_ascii=False)

        return jsonify(new_data)

    except Exception as e:
        print("\n🚨 ERROR IN SERVER 🚨")
        print(traceback.format_exc())  # ✅ This will print the full error in terminal
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)









