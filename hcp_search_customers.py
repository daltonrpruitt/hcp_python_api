#!/usr/bin/env python3
"""
Housecall Pro Customer Search
Usage:
  python hcp_search_customers.py --name "John Smith"
  python hcp_search_customers.py --email "john@example.com"
  python hcp_search_customers.py --phone "555-123-4567"
  python hcp_search_customers.py --address "123 Main St"
  python hcp_search_customers.py --name "John" --email "john@example.com"
"""

import argparse
import json
import os
import sys
import requests

# ── Config ──────────────────────────────────────────────────────────────────
API_BASE = "https://api.housecallpro.com"
HCP_CUSTOMER_URL = "https://pro.housecallpro.com/customers/{customer_id}"

# Set your API key here or via the HCP_API_KEY environment variable
API_KEY = os.environ.get("HCP_API_KEY", "YOUR_API_KEY_HERE")


# ── Helpers ──────────────────────────────────────────────────────────────────

def build_headers() -> dict:
    return {
        "Authorization": f"Token {API_KEY}",
        "Content-Type": "application/json",
    }


def search_customers(query: str) -> list[dict]:
    """Fetch all pages of results for a given query string."""
    all_customers = []
    page = 1
    page_size = 100

    while True:
        resp = requests.get(
            f"{API_BASE}/customers",
            headers=build_headers(),
            params={"q": query, "page": page, "page_size": page_size},
            timeout=15,
        )

        if resp.status_code == 401:
            sys.exit("❌  Authentication failed. Check your HCP_API_KEY.")
        if not resp.ok:
            sys.exit(f"❌  API error {resp.status_code}: {resp.text}")

        data = resp.json()
        # The list is under a 'customers' key; fall back to the raw list
        batch = data.get("customers", data) if isinstance(data, dict) else data
        all_customers.extend(batch)

        # Stop when we've received a partial page (last page)
        if len(batch) < page_size:
            break
        page += 1

    return all_customers


def normalize_phone(phone: str) -> str:
    """Strip non-digit characters for loose phone matching."""
    return "".join(ch for ch in phone if ch.isdigit())


def detect_matches(customer: dict, args: argparse.Namespace) -> dict[str, str]:
    """
    Return a list of human-readable strings describing which search fields
    matched this customer record.
    """
    matches = {}

    first = (customer.get("first_name") or "").lower()
    last  = (customer.get("last_name")  or "").lower()
    full  = f"{first} {last}".strip()

    if args.name:
        needle = args.name.lower()
        if needle in full or needle in first or needle in last:
            matches["name"] = args.name

    if args.email:
        cust_email = (customer.get("email") or "").lower()
        if args.email.lower() in cust_email:
            matches["email"] = args.email

    if args.phone:
        needle_digits = normalize_phone(args.phone)
        for ph_field in ["mobile_number", "home_number", "work_number"]:
            raw = customer.get(ph_field) or ""
            if needle_digits and needle_digits in normalize_phone(raw):
                matches[f"phone_{ph_field}"] = args.phone

    if args.address:
        needle = args.address.lower()
        for addr in customer.get("addresses", []):
            street = (addr.get("street") or "").lower()
            city   = (addr.get("city")   or "").lower()
            state  = (addr.get("state")  or "").lower()
            zip_   = (addr.get("zip")    or "").lower()
            full_addr = f"{street} {city} {state} {zip_}".strip()
            if needle in full_addr:
                matches["address"] = args.address
                break  # one match per customer is enough

    return matches


def format_customer(customer: dict, matches: list[str]) -> str:
    """Pretty-print one customer record."""
    cid   = customer.get("id", "N/A")
    first = customer.get("first_name", "")
    last  = customer.get("last_name",  "")
    email = customer.get("email", "N/A")
    mobile = customer.get("mobile_number", "N/A")
    home   = customer.get("home_number",   "N/A")
    work   = customer.get("work_number",   "N/A")
    notes  = customer.get("notes", "")

    hcp_url = HCP_CUSTOMER_URL.format(customer_id=cid)

    # Addresses
    addr_lines = []
    for addr in customer.get("addresses", []):
        parts = [
            addr.get("street", ""),
            addr.get("city",   ""),
            addr.get("state",  ""),
            addr.get("zip",    ""),
        ]
        addr_lines.append(", ".join(p for p in parts if p))

    lines = [
        "─" * 60,
        f"  Customer:   {first} {last}".rstrip(),
        f"  ID:         {cid}",
        f"  HCP URL:    {hcp_url}",
        f"  Email:      {email}",
        f"  Mobile:     {mobile}",
        f"  Home:       {home}",
        f"  Work:       {work}",
    ]
    if addr_lines:
        lines.append(f"  Addresses:")
        for a in addr_lines:
            lines.append(f"              {a}")
    if notes:
        lines.append(f"  Notes:      {notes[:120]}{'…' if len(notes) > 120 else ''}")

    lines.append(f"  Matched on: {', '.join(matches) if matches else '(returned by API query - matched some string)'}")
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Search Housecall Pro customers by name, email, phone, or address."
    )
    parser.add_argument("--name",    metavar="NAME",    help="Customer name (full or partial)")
    parser.add_argument("--email",   metavar="EMAIL",   help="Customer email address")
    parser.add_argument("--phone",   metavar="PHONE",   help="Customer phone number")
    parser.add_argument("--address", metavar="ADDRESS", help="Customer address (partial OK)")
    parser.add_argument("--json",    action="store_true", help="Output raw JSON instead of formatted text")
    args = parser.parse_args()

    if not any([args.name, args.email, args.phone, args.address]):
        parser.error("Provide at least one of --name, --email, --phone, --address")

    if API_KEY == "YOUR_API_KEY_HERE":
        sys.exit("❌  Set your API key via the HCP_API_KEY environment variable or edit API_KEY in the script.")

    # Build search queries — one per provided argument, then deduplicate results
    search_terms = [v for v in [args.name, args.email, args.phone, args.address] if v]

    seen_ids: set = set()
    results: list[tuple[dict, list[str]]] = []

    for term in search_terms:
        print(f"🔍  Searching HCP for: '{term}' …", file=sys.stderr)
        customers = search_customers(term)
        for customer in customers:
            cid = customer.get("id")
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            matches = detect_matches(customer, args)
            results.append((customer, matches))

    # ── Output ────────────────────────────────────────────────────────────────
    if not results:
        print("No customers found matching your search criteria.")
        return


    if args.json:
        print(f"\n✅  Found {len(results)} customer(s) (print as JSON)\n", file=sys.stderr)
        output = []
        for customer, matches in results:
            output.append({
                "customer": customer,
                "matched_on": matches,
                "customer_id": customer.get("id"),
                "hcp_url": HCP_CUSTOMER_URL.format(customer_id=customer.get("id", "")),
            })
        print(json.dumps(output, indent=2))
    else:
        print(f"\n✅  Found {len(results)} customer(s):\n")
        for customer, matches in results:
            print(format_customer(customer, matches))
        print("─" * 60)


if __name__ == "__main__":
    main()