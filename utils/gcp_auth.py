"""
utils/gcp_auth.py
Manejo de credenciales GCP — ADC o Service Account.
"""

import warnings

from google.auth import default as google_auth_default
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def get_credentials(credentials_config: str):
    """Retorna credenciales GCP segun config: 'ADC' o ruta a JSON key."""
    if credentials_config.upper() == "ADC":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            creds, _ = google_auth_default(scopes=SCOPES)
        return creds
    return service_account.Credentials.from_service_account_file(
        credentials_config, scopes=SCOPES
    )
