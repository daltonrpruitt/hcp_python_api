import requests
import os

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

    assert(len(HCP_API_KEY) == 32, "API Key is wrong length!")
    
    headers = {
        'Authorization': f'Bearer {HCP_API_KEY}',
        'Content-Type': 'application/json'
    }


if __name__ == "__main__":
    main()
