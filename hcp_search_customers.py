#!/usr/bin/env python3
"""
Housecall Pro Customer Search
Runs as a standalone CLI script or as a Zapier "Run Python" code step.

─── CLI Usage ───────────────────────────────────────────────────────────────
  python hcp_search_customers.py --name "John Smith"
  python hcp_search_customers.py --email "john@example.com"
  python hcp_search_customers.py --phone "555-123-4567"
  python hcp_search_customers.py --address "123 Main St"
  python hcp_search_customers.py --name "John" --email "john@example.com"
  python hcp_search_customers.py --name "John" --json   # JSON output

─── Zapier "Run Python" Input Fields ───────────────────────────────────────
  inputData keys (all optional, but at least one search field required):
    name      - Customer name (full or partial)
    email     - Customer email address
    phone     - Customer phone number
    address   - Customer address (partial OK)
    api_key   - HCP API key (falls back to HCP_API_KEY env var)

─── Zapier Output Dict ──────────────────────────────────────────────────────
  {
    "match_count": <int>,         # number of unique customers found
    "matches":     "<json str>",  # JSON-encoded list of all match dicts
    "error":       "<str>"        # empty string on success; message on failure
  }
"""

import argparse
import json
import os
import sys
import requests

# ── Config ───────────────────────────────────────────────────────────────────
API_BASE = "https://api.housecallpro.com"
HCP_CUSTOMER_URL = "https://pro.housecallpro.com/app/customers/{customer_id}"


# ── Exceptions ───────────────────────────────────────────────────────────────


class HCPError(Exception):
    """Raised for API or input errors so callers can handle gracefully."""


# ── Input resolution ─────────────────────────────────────────────────────────


def get_inputs() -> dict:
    """
    Return a unified input dict regardless of execution context.

    Priority:
      1. Zapier  — `inputData` is injected into globals() by the Zapier runtime.
      2. CLI     — parse sys.argv via argparse.
    """
    # ── Zapier path ──────────────────────────────────────────────────────────
    # Zapier injects `inputData` as a global before running the script.
    if "inputData" in globals() and isinstance(inputData, dict):  # noqa: F821
        d = inputData  # noqa: F821
        return {
            "name": d.get("name") or None,
            "email": d.get("email") or None,
            "phone": d.get("phone") or None,
            "address": d.get("address") or None,
            "api_key": d.get("api_key") or None,
            "as_json": False,  # not relevant in Zapier context
        }

    # ── CLI path ─────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="Search Housecall Pro customers by name, email, phone, or address."
    )
    parser.add_argument(
        "--name", metavar="NAME", help="Customer name (full or partial)"
    )
    parser.add_argument("--email", metavar="EMAIL", help="Customer email address")
    parser.add_argument("--phone", metavar="PHONE", help="Customer phone number")
    parser.add_argument(
        "--address", metavar="ADDRESS", help="Customer address (partial OK)"
    )
    parser.add_argument(
        "--api-key", metavar="KEY", help="HCP API key (overrides env var)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print results as JSON instead of formatted text",
    )
    args = parser.parse_args()
    return {
        "name": args.name,
        "email": args.email,
        "phone": args.phone,
        "address": args.address,
        "api_key": args.api_key,
        "as_json": args.as_json,
    }


def resolve_api_key(inputs: dict) -> str:
    """
    Resolve the API key from (in priority order):
      1. inputs["api_key"]  — CLI --api-key flag or Zapier inputData["api_key"]
      2. HCP_API_KEY env var
    Raises HCPError if no key is found.
    """
    key = (inputs.get("api_key") or "").strip() or os.environ.get(
        "HCP_API_KEY", ""
    ).strip()
    if not key or key == "YOUR_API_KEY_HERE":
        raise HCPError(
            "No API key found. Set HCP_API_KEY env var, pass --api-key, "
            "or include 'api_key' in Zapier inputData."
        )
    return key


# ── API helpers ───────────────────────────────────────────────────────────────


def build_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }


def search_customers(query: str, api_key: str) -> list[dict]:
    """Fetch all pages of /customers results for a given query string."""
    all_customers = []
    page = 1
    page_size = 100

    while True:
        resp = requests.get(
            f"{API_BASE}/customers",
            headers=build_headers(api_key),
            params={"q": query, "page": page, "page_size": page_size},
            timeout=15,
        )

        if resp.status_code == 401:
            raise HCPError("Authentication failed — check your HCP API key.")
        if not resp.ok:
            raise HCPError(f"API error {resp.status_code}: {resp.text}")

        data = resp.json()
        batch = data.get("customers", data) if isinstance(data, dict) else data
        all_customers.extend(batch)

        if len(batch) < page_size:
            break
        page += 1

    return all_customers


# ── Match detection ───────────────────────────────────────────────────────────


def normalize_phone(phone: str) -> str:
    """Strip non-digit characters for loose phone matching."""
    return "".join(ch for ch in phone if ch.isdigit())


def detect_matches(customer: dict, inputs: dict) -> dict[str, str]:
    """
    Return a dict of {field: searched_value} for each input field that
    matched this customer record.  Accepts a plain dict so it works from
    both the CLI and Zapier code paths.
    """
    matches = {}

    first = (customer.get("first_name") or "").lower()
    last = (customer.get("last_name") or "").lower()
    full = f"{first} {last}".strip()

    name = inputs.get("name")
    if name:
        needle = name.lower()
        if needle in full or needle in first or needle in last:
            matches["name"] = name

    email = inputs.get("email")
    if email:
        cust_email = (customer.get("email") or "").lower()
        if email.lower() in cust_email:
            matches["email"] = email

    phone = inputs.get("phone")
    if phone:
        needle_digits = normalize_phone(phone)
        for ph_field in ["mobile_number", "home_number", "work_number"]:
            raw = customer.get(ph_field) or ""
            if needle_digits and needle_digits in normalize_phone(raw):
                matches[f"phone_{ph_field}"] = phone

    address = inputs.get("address")
    if address:
        needle = address.lower()
        for addr in customer.get("addresses", []):
            street = (addr.get("street") or "").lower()
            city = (addr.get("city") or "").lower()
            state = (addr.get("state") or "").lower()
            zip_ = (addr.get("zip") or "").lower()
            full_addr = f"{street} {city} {state} {zip_}".strip()
            if needle in full_addr:
                matches["address"] = address
                break

    return matches


# ── Core run logic ────────────────────────────────────────────────────────────


def run(inputs: dict) -> dict:
    """
    Execute the customer search and return a result dict suitable for both
    Zapier output and programmatic use.

    Returns:
      {
        "match_count": int,
        "matches":     str,   # JSON-encoded list of match dicts (all fields)
        "error":       str,   # empty on success
      }
    """
    output = {"match_count": 0, "matches": "[]", "error": ""}

    try:
        # Validate inputs
        search_fields = ["name", "email", "phone", "address"]
        if not any(inputs.get(f) for f in search_fields):
            raise HCPError("Provide at least one of: name, email, phone, address.")

        api_key = resolve_api_key(inputs)

        # One API query per non-empty search field; deduplicate by customer id
        search_terms = [inputs[f] for f in search_fields if inputs.get(f)]
        seen_ids: set = set()
        results: list = []

        for term in search_terms:
            print(f"🔍  Searching HCP for: '{term}' …", file=sys.stderr)
            customers = search_customers(term, api_key)
            for customer in customers:
                cid = customer.get("id")
                if cid in seen_ids:
                    continue
                seen_ids.add(cid)
                matches = detect_matches(customer, inputs)
                results.append(
                    {
                        "customer": customer,
                        "matched_on": matches,
                        "customer_id": cid,
                        "hcp_url": HCP_CUSTOMER_URL.format(customer_id=cid or ""),
                    }
                )

        output["match_count"] = len(results)
        output["matches"] = json.dumps(results)

    except HCPError as exc:
        output["error"] = str(exc)
    except Exception as exc:  # unexpected errors
        output["error"] = f"Unexpected error: {exc}"

    return output


# ── CLI pretty-printer ────────────────────────────────────────────────────────


def format_customer(match: dict) -> str:
    """Render one match dict as human-readable text for CLI output."""
    customer = match["customer"]
    matches = match["matched_on"]

    cid = customer.get("id", "N/A")
    first = customer.get("first_name", "")
    last = customer.get("last_name", "")
    email = customer.get("email", "N/A")
    mobile = customer.get("mobile_number", "N/A")
    home = customer.get("home_number", "N/A")
    work = customer.get("work_number", "N/A")
    notes = customer.get("notes", "")

    addr_lines = []
    for addr in customer.get("addresses", []):
        parts = [
            addr.get("street", ""),
            addr.get("city", ""),
            addr.get("state", ""),
            addr.get("zip", ""),
        ]
        addr_lines.append(", ".join(p for p in parts if p))

    lines = [
        "─" * 60,
        f"  Customer:   {first} {last}".rstrip(),
        f"  ID:         {cid}",
        f"  HCP URL:    {match['hcp_url']}",
        f"  Email:      {email}",
        f"  Mobile:     {mobile}",
        f"  Home:       {home}",
        f"  Work:       {work}",
    ]
    if addr_lines:
        lines.append("  Addresses:")
        for a in addr_lines:
            lines.append(f"              {a}")
    if notes:
        lines.append(f"  Notes:      {notes[:120]}{'…' if len(notes) > 120 else ''}")

    matched_str = (
        ", ".join(f"{k}='{v}'" for k, v in matches.items())
        if matches
        else "(returned by API query)"
    )
    lines.append(f"  Matched on: {matched_str}")
    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    inputs = get_inputs()

    if not any(inputs.get(f) for f in ["name", "email", "phone", "address"]):
        print(
            "❌  Provide at least one of --name, --email, --phone, --address",
            file=sys.stderr,
        )
        sys.exit(1)

    result = run(inputs)

    if result["error"]:
        print(f"❌  {result['error']}", file=sys.stderr)
        sys.exit(1)

    matches = json.loads(result["matches"])

    if not matches:
        print("No customers found matching your search criteria.")
        sys.exit(0)

    if inputs.get("as_json"):
        print(
            f"\n✅  Found {result['match_count']} customer(s) (JSON)\n", file=sys.stderr
        )
        print(json.dumps(matches, indent=2))
    else:
        print(f"\n✅  Found {result['match_count']} customer(s):\n")
        for match in matches:
            print(format_customer(match))
        print("─" * 60)

# ── Zapier tail ───────────────────────────────────────────────────────────────
# When Zapier runs this file it does NOT execute the if __name__ == "__main__"
# block, so we call run() here and assign to `output` which Zapier reads back.
else:
    output = run(get_inputs())  # noqa: F821  (inputData injected by Zapier)
