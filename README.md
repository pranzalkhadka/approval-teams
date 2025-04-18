# approval-teams

### 1. Make an env file and fill the credentials.

### 2. Running any script prompts for a code that can be found in the terminal when running.

## 1. create_approval_in_teams.py :





Use this to creates a single, hardcoded Teams approval request




Just to check how to authenticate with Microsoft Graph API and create a simple approval in teams programatically.



## 2. test_own_api.py :





Fetches tickets from https://ticket-teams.fly.dev/tickets.

Use this to create approval request for each ticket entry fetched from the API.

Use the ticket_status_map to decide the status for each ticket





## 3. test_actual_api.py :





Fetches uniform requests from https://wo-flow-prod-10-2023-os3mt.ondigitalocean.app/api/mobile/v3.0/uniform-requests/all.

Use this to create approval request for each ticket entry fetched from the API.

Use the ticket_status_map to decide the status for each ticket


