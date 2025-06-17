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

    response = requests.get(f'{BASE_URL}/jobs', headers=headers)
    if response.status_code == 200:
        jobs = response.json()
        filepath = "tmp.json"
        with open(filepath, "w") as f:
            json.dump(jobs, f)
        print(jobs["jobs"][:5])
    else:
        print(f"Error: {response.status_code}")


if __name__ == "__main__":
    main()
