# Food Waste Reduction & Donation Coordinator

A web app that connects people with surplus food (restaurants, hostels, caterers) to NGOs and volunteers who can collect it before it goes to waste.

## Problem
Large amounts of edible food are thrown away every day while people nearby go hungry. There is no simple, real-time way for donors to reach NGOs before the food expires.

## Features
- Role-based login: **Donor** and **NGO/Receiver**
- Donors post food with quantity, servings, expiry time, and pickup address
- NGOs browse available listings, filter by area, and claim them
- Status tracking: Available → Claimed → Picked up (expired listings are hidden automatically)
- Impact dashboard: meals donated, kg of food waste prevented, active listings
- Safe claiming: one atomic database update prevents two NGOs claiming the same food

## Tech Stack
Python, Flask, SQLite, Jinja2, Bootstrap 5

## Setup
```bash
git clone <repo-url>
cd food-waste-coordinator
python -m venv venv
venv\Scripts\activate        # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## How to use
1. Register one account as **Donor** and another as **NGO**.
2. Log in as the donor and post a food listing.
3. Log in as the NGO, claim the listing, then mark it as picked up.
4. Check the home page for updated impact numbers.

## Future Scope
- Nearest-NGO matching using location/maps
- ML model to predict surplus food by day and event type
- SMS/WhatsApp notifications
- Admin panel and verified-NGO badges

## Team
| Name | Role |
|------|------|
| Member 1 | Backend & database |
| Member 2 | Frontend templates |
| Member 3 | Testing, README & demo data |
