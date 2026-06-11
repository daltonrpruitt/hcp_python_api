# Housecall Pro API with Python

Testing and using the Housecall Pro (HCP) API via the `requests` module in Python to fetch/manipulate a HCP instance..

Note to use the HCP API, you must have an API key, which you can only obtain on the Max plan/tier of HCP (or higher).

## Recent work

### `hcp_search_customers.py`
Tool to query for customers in HCP using the `q` parameter which is "A query that can be used to search for a customer by name, email, mobile number and address" (read more [here](https://docs.housecallpro.com/docs/housecall-public-api/042bd3bf861ae-get-customers)). 

This script was made using Claude (the chat, not Claude Code), with some manual intervention in certain parts (LLM seems to really like using Unicode arrows...). 

This is ultimately to be used in Zapier, so it has been setup to use both in a Zapier Code step and locally via script execution (`uv run hcp_search_customers.py`) for quick testing.

I am currently unsure of the best way to add tests for this script, as I don't have access to a test HCP instance (and they don't typically give out such access). 
I could mock it, I guess, but that feels a bit more detailed than I currently need to be.

