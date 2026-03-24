# Backend API Testing and Usage

This guide describes practical ways to authenticate and call the HOLMES backend API locally or from scripts.

## Prerequisites

- You can access the tenant and API scope.
- Backend is running locally (for example on http://localhost:8000).
- You have one of the required groups/roles for the target endpoint.

Useful values in this project:

- Tenant ID: 0ae51e19-07c8-4e4b-bb6d-648ee58410f4
- Backend API App ID: b04cd453-bbd3-4f57-8453-e430bbf3fbc1
- Scope: api://b04cd453-bbd3-4f57-8453-e430bbf3fbc1/user_impersonation

## Method 1: Azure CLI (recommended for developers)

### 1. Interactive sign-in with scope consent

```powershell
az logout
az login --tenant "0ae51e19-07c8-4e4b-bb6d-648ee58410f4" --scope "api://b04cd453-bbd3-4f57-8453-e430bbf3fbc1/user_impersonation"
```

If you get AADSTS65001 (consent_required), tenant policy is blocking the Azure CLI app from this scope until user/admin consent is granted.

### 2. Request bearer token

```powershell
$token = az account get-access-token --scope "api://b04cd453-bbd3-4f57-8453-e430bbf3fbc1/user_impersonation" --query accessToken -o tsv
```

### 3. Call backend endpoint

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/groups" -Headers @{ Authorization = "Bearer $token" }
```

Example for system benchmark endpoint:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/system/table-stats" -Headers @{ Authorization = "Bearer $token" }
```

## Method 2: cURL/Postman with a bearer token

Once you have a token (from Azure CLI or another flow), you can call endpoints directly.

```bash
curl -H "Authorization: Bearer <ACCESS_TOKEN>" http://localhost:8000/api/groups
```

System benchmark endpoint:

```bash
curl -H "Authorization: Bearer <ACCESS_TOKEN>" http://localhost:8000/api/system/table-stats
```

## Method 3: Python script (native power-user integration)

This is the most useful pattern for future power users.

Install dependency:

```bash
pip install msal requests
```

Example script using device code flow:

```python
import requests
import msal

TENANT_ID = "0ae51e19-07c8-4e4b-bb6d-648ee58410f4"
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"  # Azure CLI public client
SCOPE = ["api://b04cd453-bbd3-4f57-8453-e430bbf3fbc1/user_impersonation"]
BASE_URL = "http://localhost:8000"

authority = f"https://login.microsoftonline.com/{TENANT_ID}"
app = msal.PublicClientApplication(CLIENT_ID, authority=authority)

accounts = app.get_accounts()
result = None
if accounts:
	result = app.acquire_token_silent(SCOPE, account=accounts[0])

if not result:
	flow = app.initiate_device_flow(scopes=SCOPE)
	if "user_code" not in flow:
		raise RuntimeError("Failed to start device flow")
	print(flow["message"])
	result = app.acquire_token_by_device_flow(flow)

if "access_token" not in result:
	raise RuntimeError(f"Token acquisition failed: {result}")

token = result["access_token"]
headers = {"Authorization": f"Bearer {token}"}

response = requests.get(f"{BASE_URL}/api/system/table-stats", headers=headers, timeout=120)
response.raise_for_status()
print(response.json())
```

Notes:

- For enterprise tools, use your own app registration client ID instead of Azure CLI client ID.
- Keep scope exactly aligned with your backend API.

## Method 4: Reuse frontend-issued token (local debugging)

If you are already logged in to frontend, you can reuse the server-side access token for quick tests.

- This is suitable for local debugging.
- Do not keep token logging enabled in shared environments.

## Common errors and fixes

1. 401 Unauthorized
- Token missing/expired.
- Audience mismatch: token must target backend API app ID.

2. 403 Forbidden
- Token valid but user not in required group/role for endpoint.
- Example: system table stats endpoint is restricted to development access group.

3. AADSTS65001 consent_required
- User/admin consent missing for requested client + scope combination.
- Re-run interactive login with scope and request tenant admin consent if needed.

## Endpoint quick reference

- Auth debug: GET /api/groups
- Table data/meta: GET /api/{space}/tables/{data_kind}/{table_name}
- System benchmark: GET /api/system/table-stats

