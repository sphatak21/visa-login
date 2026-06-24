import sys
import time
import random
import requests
import os
import smtplib
import csv
import json
from datetime import datetime
from bs4 import BeautifulSoup
from email.message import EmailMessage
from email.utils import make_msgid
import dotenv

dotenv.load_dotenv()

# --- Configuration ---
LOGIN_URL = "https://ais.usvisa-info.com/en-ca/niv/users/sign_in"
DASHBOARD_URL = "https://ais.usvisa-info.com/en-ca/niv/account"
CSV_FILE_NAME = "visa_status_log.csv"
JSON_STATE_FILE = "city_dates.json"
THREAD_FILE = "thread_id_updates.txt"

# Your specific schedule ID
SCHEDULE_ID = "74844716"

# The 7 target cities
FACILITIES = {
    "89": "Calgary",
    "90": "Halifax",
    "91": "Montreal",
    "92": "Ottawa",
    "93": "Quebec City",
    "94": "Toronto",
    "95": "Vancouver"
}

# Email Configuration
sender_email = os.getenv("SENDER_EMAIL")       
sender_password = os.getenv("SENDER_PASSWORD") 
login_email = os.getenv("LOGIN_EMAIL")
login_password = os.getenv("LOGIN_PASSWORD")
receiver_email_string = os.getenv("RECEIVER_EMAIL")

# Initialize global session and thread tracker
session = requests.Session()
email_thread_root = None

def load_thread_id():
    global email_thread_root
    if os.path.exists(THREAD_FILE):
        with open(THREAD_FILE, "r") as file:
            saved_id = file.read().strip()
            if saved_id:
                email_thread_root = saved_id

load_thread_id()

# --- State Management ---
def load_saved_dates():
    """Loads the previously saved dictionary of dates from JSON."""
    if os.path.exists(JSON_STATE_FILE):
        try:
            with open(JSON_STATE_FILE, "r") as file:
                return json.load(file)
        except json.JSONDecodeError:
            pass
    # Default state if file is missing or corrupted
    return {fid: None for fid in FACILITIES.keys()}

def save_current_dates(dates_dict):
    """Saves the current dictionary of dates to JSON."""
    with open(JSON_STATE_FILE, "w") as file:
        json.dump(dates_dict, file, indent=4)

def log_status_to_csv(status):
    """Logs the current time and status to a CSV file."""
    file_exists = os.path.isfile(CSV_FILE_NAME)
    with open(CSV_FILE_NAME, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Timestamp", "Status"])
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([timestamp, status])

def setup_email_threading(msg):
    global email_thread_root
    current_msg_id = make_msgid()
    msg['Message-ID'] = current_msg_id
    
    if email_thread_root:
        msg['In-Reply-To'] = email_thread_root
        msg['References'] = email_thread_root
    else:
        email_thread_root = current_msg_id
        with open(THREAD_FILE, "w") as file:
            file.write(current_msg_id)

def send_update_email(changes, current_dates):
    """Sends an HTML formatted email detailing the changes and current status of all cities."""
    if not sender_email or not sender_password or not receiver_email_string:
        print("Skipping email: Credentials or recipients not set.")
        return

    recipients = [email.strip() for email in receiver_email_string.split(';') if email.strip()]
    msg = EmailMessage()
    setup_email_threading(msg)
    
    msg['Subject'] = "🚨 US Visa Appointment Updates 🚨"
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipients) 

    changes_html = "<ul>"
    for change in changes:
        old_val = change['old'] if change['old'] else "None"
        new_val = change['new'] if change['new'] else "None"
        changes_html += f"<li><strong>{change['city']}</strong>: Changed from <em>{old_val}</em> to <strong>{new_val}</strong></li>"
    changes_html += "</ul>"

    table_html = """
    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 400px;">
        <tr style="background-color: #f2f2f2;">
            <th style="text-align: left;">City</th>
            <th style="text-align: left;">Appointment Date</th>
        </tr>
    """
    for fid, city_name in FACILITIES.items():
        date_val = current_dates.get(fid)
        display_date = date_val if date_val else "No slots available"
        table_html += f"<tr><td>{city_name}</td><td>{display_date}</td></tr>"
    table_html += "</table>"

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #2c3e50;">Appointment Dates Changed!</h2>
        <p>The following changes triggered this alert:</p>
        {changes_html}
        <hr style="border: 0; border-top: 1px solid #ccc; margin: 20px 0;">
        <h3>Current Status for All Cities</h3>
        {table_html}
        <p style="margin-top: 20px;">
            <a href="{LOGIN_URL}" style="display: inline-block; padding: 10px 15px; background-color: #0056b3; color: white; text-decoration: none; border-radius: 5px;">Log In to US Visa Portal</a>
        </p>
        <p style="font-size: 0.8em; color: #777;">Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
      </body>
    </html>
    """

    msg.set_content("Your email client does not support HTML. Please enable HTML to view this message.")
    msg.add_alternative(html_content, subtype='html')

    try:
        print(f"\n[EMAIL ALERT] Sending updates to {len(recipients)} recipient(s)...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        print("Alert email sent successfully!")
    except Exception as e:
        print(f"Failed to send email alert: {e}")

def automate_login():
    """Authenticates and sets up the session cookies and CSRF headers."""
    global session
    session.close()
    session = requests.Session()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.5 Safari/605.1.15"
    }
    
    try:
        get_response = session.get(LOGIN_URL, headers=headers, timeout=15)
        soup = BeautifulSoup(get_response.text, 'html.parser')
        
        csrf_meta = soup.find('meta', attrs={'name': 'csrf-token'})
        if not csrf_meta or not csrf_meta.get('content'):
            return False
            
        csrf_token = csrf_meta.get('content')
        payload = {
            "user[email]": login_email, 
            "user[password]": login_password,
            "commit": "Sign In",
            "policy_confirmed": "1", 
            "authenticity_token": csrf_token 
        }

        headers["X-CSRF-Token"] = csrf_token
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["Referer"] = LOGIN_URL
        session.headers.update(headers)

        post_response = session.post(LOGIN_URL, data=payload)

        if 'window.location.href="/en-ca/niv/account"' in post_response.text or post_response.url == DASHBOARD_URL:
            return True
        else:
            return False
    except Exception:
        return False

def check_appointment_api(facility_id):
    """Queries the JSON API for a specific facility ID."""
    api_endpoint = f"https://ais.usvisa-info.com/en-ca/niv/schedule/{SCHEDULE_ID}/appointment/days/{facility_id}.json"
    
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://ais.usvisa-info.com/en-ca/niv/schedule/{SCHEDULE_ID}/appointment"
    }
    
    try:
        response = session.get(api_endpoint, headers=headers, timeout=10)
        
        if response.status_code == 401 or "sign_in" in response.url:
            return "Expired", None
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                dates = [item['date'] for item in data]
                return min(dates), data 
            else:
                return None, [] 
        else:
            return None, None 
    except Exception:
        return None, None 

# --- Main Daemon ---
if __name__ == "__main__":
    print("Starting Multi-City US Visa Scraper...")
    
    previous_dates = load_saved_dates()
    print("Loaded initial states from JSON:")
    for fid, name in FACILITIES.items():
        print(f"  - {name}: {previous_dates.get(fid)}")
    
    is_logged_in = False

    while True:
        try:
            
            if not is_logged_in:
                sys.stdout.write("\rAttempting to authenticate... ")
                sys.stdout.flush()
                is_logged_in = automate_login()
                
                if not is_logged_in:
                    print("Failed.")
                    log_status_to_csv("Login Failed / Blocked")
                    time.sleep(60)
                    continue
                else:
                    print("Success.\n")

            
            changes_detected = []
            current_dates = previous_dates.copy()
            session_expired = False

            print(f"--- Checking APIs at {datetime.now().strftime('%H:%M:%S')} ---")
            for fid, city_name in FACILITIES.items():
                sys.stdout.write(f"  Checking {city_name.ljust(15)} ")
                sys.stdout.flush()
                
                earliest_date, all_dates = check_appointment_api(fid)
                
                if earliest_date == "Expired":
                    print("[Session Expired]")
                    session_expired = True
                    break
                
                if earliest_date is None and all_dates is None:
                    print("[API/Network Error - Skipping]")
                    continue 
                
                print(f"[{earliest_date if earliest_date else 'No Slots'}]")
                
                old_date = previous_dates.get(fid)
                if earliest_date != old_date:
                    # 1. Always update our internal state tracker to reflect reality
                    current_dates[fid] = earliest_date
                    
                    # 2. Alert Logic: Only trigger if we went from None -> Date, or Later -> Earlier
                    if earliest_date is not None:
                        if old_date is None or earliest_date < old_date:
                            changes_detected.append({
                                "city": city_name,
                                "old": old_date,
                                "new": earliest_date
                            })
                
                time.sleep(3)

            if session_expired:
                is_logged_in = False
                log_status_to_csv("Session Expired")
                time.sleep(5)
                continue

            # 3. Always save the state if the board changed, so we don't alert on old data next cycle
            if current_dates != previous_dates:
                save_current_dates(current_dates)
                previous_dates = current_dates.copy()

            # 4. Only send the email if actual upgrades were found
            if changes_detected:
                print(f"\n>> {len(changes_detected)} UPGRADE(S) DETECTED! <<")
                log_status_to_csv(f"Alert: {len(changes_detected)} cities improved")
                send_update_email(changes_detected, current_dates)
            else:
                log_status_to_csv("No upgrades")


        except Exception as e:
            print(f"\nUnexpected error in main loop: {e}")
            log_status_to_csv("Loop Exception")

        wait_time = int(random.uniform(5, 20))
        print("")
        for remaining in range(wait_time, 0, -1):
            mins, secs = divmod(remaining, 60)
            sys.stdout.write(f"\rNext full check in {mins:02d}:{secs:02d}...    ")
            sys.stdout.flush()
            time.sleep(1)
        print("\n")