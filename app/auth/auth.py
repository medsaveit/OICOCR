from msal import ConfidentialClientApplication
from config.config import CLIENT_ID, CLIENT_SECRET, AUTHORITY, SCOPES

def get_access_token():
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET
    )

    token = app.acquire_token_for_client(scopes=SCOPES)

    if "access_token" not in token:
        raise Exception(f"Auth failed: {token}")

    return token["access_token"]
