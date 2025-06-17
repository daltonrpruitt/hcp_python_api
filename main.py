import requests
import os
import json

def main():
    try:
        HCP_API_KEY = os.environ['HCP_API_KEY']
    except KeyError as e:
        e.add_note("No 'HCP_API_KEY' environment variable found!")
        e.add_note("Set environment variables via:")
        e.add_note("   $env:HCP_API_KEY = 'XYZ'")
        e.add_note("in Powershell or")
        e.add_note("   export HCP_API_KEY='XYZ'")
        e.add_note("in Bash.")
        raise 

    assert len(HCP_API_KEY) == 32, "API Key is wrong length!"
    
    headers = {
        'Authorization': f'Bearer {HCP_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    BASE_URL = 'https://api.housecallpro.com/'

    url = f'{BASE_URL}/events'
    
    # all_jobs = []
    # while url:
    #     response = requests.get(url, headers=headers)
    #     data = response.json()
    #     all_jobs.extend(data['jobs'])
    #     url = data.get('next_page_url')
    querystring = {"scheduled_start_min":"2025-06-06","scheduled_end_max":"2025-06-13"}

    response = requests.get(url, headers=headers, params=querystring)
    if response.status_code == 200:
        events = response.json()
        filepath = "hidden_events.json"
        with open(filepath, "w") as f:
            json.dump(events, f)
        print(events["events"][:5])
    else:
        print(f"Error: {response.status_code}")


if __name__ == "__main__":
    main()
