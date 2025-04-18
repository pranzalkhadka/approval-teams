import requests
import msal
import webbrowser

CLIENT_ID = "e3da78d9-309d-4ae1-9746-948aa196667f"
TENANT_ID = "46d6a910-c309-42a3-8144-6fa061daf05f"
APPROVER_EMAIL = "pranjal.khadka@Adex911.onmicrosoft.com"

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://graph.microsoft.com/ApprovalSolution.ReadWrite", "https://graph.microsoft.com/User.Read"]
GRAPH_API_BASE = "https://graph.microsoft.com"

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

def create_approval(access_token, approver_id, approver_display_name):

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "displayName": "third Approval",
        "description": "Creating third approval.",
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
        response = requests.post(
            f"{GRAPH_API_BASE}/beta/solutions/approval/approvalItems",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 202:
            print("Approval created successfully!")
        else:
            raise Exception(f"Failed to create approval: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")

def main():
    
    access_token = get_access_token()
    print("Authenticated successfully.")
    
    approver_id, approver_display_name = get_user_details(access_token, APPROVER_EMAIL)
    print(f"Found user details for {APPROVER_EMAIL}: ID={approver_id}, DisplayName={approver_display_name}")
    
    create_approval(access_token, approver_id, approver_display_name)

if __name__ == "__main__":
    main()