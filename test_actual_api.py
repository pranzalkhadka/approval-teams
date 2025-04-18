import requests
import msal
import webbrowser
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse
import time
import os
from dotenv import load_dotenv

load_dotenv() 

CLIENT_ID = os.getenv('CLIENT_ID')
TENANT_ID = os.getenv('TENANT_ID')
APPROVER_EMAIL = os.getenv('APPROVER_EMAIL')
API_USERNAME = os.getenv('API_USERNAME')
API_PASSWORD = os.getenv('API_PASSWORD')

API_BASE_URL = "https://wo-flow-prod-10-2023-os3mt.ondigitalocean.app"
LOGIN_URL = f"{API_BASE_URL}/api/mobile/v3.0/login"
TICKETS_API_URL = f"{API_BASE_URL}/api/mobile/v3.0/uniform-requests/all"


AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://graph.microsoft.com/ApprovalSolution.ReadWrite", "https://graph.microsoft.com/User.Read"]
GRAPH_API_BASE = "https://graph.microsoft.com"

def get_api_token():

    headers = {"Content-Type": "application/json"}
    payload = {
        "username": API_USERNAME,
        "password": API_PASSWORD
    }
    try:
        response = requests.post(LOGIN_URL, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            if not token:
                raise Exception("No token found in login response")
            return token
        else:
            raise Exception(f"Login failed: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Login request failed: {str(e)}")

def get_access_token():

    app = msal.PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY
    )
    
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(scopes=SCOPE, account=accounts[0])
        if result and "access_token" in result:
            return result["access_token"]

    flow = app.initiate_device_flow(scopes=SCOPE)
    if "user_code" not in flow:
        raise Exception("Failed to create device flow")
    
    print(f"Please go to {flow['verification_uri']} and enter code: {flow['user_code']}")
    webbrowser.open(flow["verification_uri"])
    
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Authentication failed: {result.get('error_description', 'Unknown error')}")

def get_user_details(access_token, email):

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    response = requests.get(
        f"{GRAPH_API_BASE}/v1.0/users/{email}",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        user_data = response.json()
        return user_data["id"], user_data.get("displayName", email)
    else:
        raise Exception(f"Failed to get user details: {response.status_code} - {response.text}")

def get_tickets():

    try:
        token = get_api_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        response = requests.get(TICKETS_API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") != "OK":
                raise Exception(f"API error: {data.get('message', 'Unknown error')}")
            tickets = [
                {
                    "id": req["requestId"],
                    "title": f"Uniform Request #{req['requestId']} by {req['technicianName']}",
                    "description": req["notes"] or "No notes provided",
                    "status": req["status"]
                }
                for req in data.get("data", [])
            ]
            return tickets
        else:
            raise Exception(f"Failed to fetch uniform requests: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Uniform requests API request failed: {str(e)}")

def list_approvals(access_token, display_name, post_time, retries=2, delay=5):

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"{GRAPH_API_BASE}/beta/solutions/approval/approvalItems"
    
    for attempt in range(retries + 1):
        approvals = []
        try:
            while url:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    approvals.extend(data.get("value", []))
                    url = data.get("@odata.nextLink")
                else:
                    print(f"Attempt {attempt + 1}: Failed to list approvals: {response.status_code} - {response.text}")
                    return None
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1}: List approvals request failed: {str(e)}")
            return None
        
        print(f"Attempt {attempt + 1}: Found approvals with displayNames: {[a['displayName'] for a in approvals]}")
        
        for approval in approvals:
            if approval["displayName"].lower() == display_name.lower():
                created_time = parse(approval["createdDateTime"]).astimezone(timezone.utc)
                if created_time >= post_time - timedelta(seconds=120):
                    print(f"Matched approval ID: {approval['id']} at {created_time}")
                    return approval["id"]
        
        if attempt < retries:
            print(f"No approval found for {display_name} at attempt {attempt + 1}. Retrying in {delay} seconds...")
            time.sleep(delay)
    
    print(f"No approval found with displayName: {display_name} created around {post_time} after {retries + 1} attempts")
    return None

def submit_response(access_token, approval_id, response="Approve", comments="Auto-processed"):

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "response": response,
        "comments": comments
    }
    
    try:
        response = requests.post(
            f"{GRAPH_API_BASE}/beta/solutions/approval/approvalItems/{approval_id}/responses",
            headers=headers,
            json=payload,
            timeout=10
        )
        if response.status_code in [200, 201, 202]:
            print(f"Successfully set approval {approval_id} status to {response}")
            if response.text:
                try:
                    print("Response Response:", response.json())
                except ValueError:
                    print("No JSON response body returned.")
            else:
                print("No response body returned.")
        else:
            print(f"Failed to set approval {approval_id} status: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Response submission failed for approval {approval_id}: {str(e)}")

def create_approval(access_token, approver_id, approver_display_name, ticket, desired_status="Approve"):

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "displayName": ticket["title"],
        "description": f"{ticket['description']} (Request ID: {ticket['id']}, Status: {ticket['status']})",
        "approvalType": "basic",
        "allowEmailNotification": True,
        "approvers": [
            {
                "user": {
                    "id": approver_id,
                    "displayName": approver_display_name
                }
            }
        ]
    }
    
    try:
        post_time = datetime.now(timezone.utc)
        response = requests.post(
            f"{GRAPH_API_BASE}/beta/solutions/approval/approvalItems",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code in [201, 202]:
            print(f"Approval created successfully for request ID {ticket['id']}: {ticket['title']} (Status: Requested)")
            if response.text:
                try:
                    print("Create Response:", response.json())
                except ValueError:
                    print("No response body returned.")
            else:
                print("No response body returned.")
            time.sleep(2)
            approval_id = list_approvals(access_token, ticket["title"], post_time)
            if approval_id:
                print(f"Found approval ID: {approval_id}")
                submit_response(access_token, approval_id, response=desired_status, comments=f"Auto-{desired_status.lower()} for request #{ticket['id']}")
            else:
                print("Could not find approval ID; manual action required in Teams.")
        else:
            raise Exception(f"Failed to create approval for request ID {ticket['id']}: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Approval request failed for request ID {ticket['id']}: {str(e)}")

def main():

    try:
        access_token = get_access_token()
        print("Authenticated successfully with Microsoft Graph.")
        
        approver_id, approver_display_name = get_user_details(access_token, APPROVER_EMAIL)
        print(f"Found user details for {APPROVER_EMAIL}: ID={approver_id}, DisplayName={approver_display_name}")
        
        tickets = get_tickets()
        if not tickets:
            print("No uniform requests found.")
            return
        
        ticket_status_map = {
            5: "Approve",  
            4: "Reject",  
            3: "Approve",  
            2: "Approve", 
            1: "Reject"   
        }
        
        for ticket in tickets:
            if ticket.get("status") == "Submitted" :
                ticket_id = ticket["id"]
                if ticket_id in ticket_status_map:
                    desired_status = ticket_status_map[ticket_id]
                    print(f"Processing request ID {ticket_id}: {ticket['title']} with desired status: {desired_status}")
                    create_approval(access_token, approver_id, approver_display_name, ticket, desired_status)
                else:
                    print(f"Skipping request ID {ticket_id}: {ticket['title']} (no status specified in ticket_status_map)")
        
        print("All uniform requests processed.")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()