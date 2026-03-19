import os
from typing import Dict, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

COLLECTION_NAME = "isirpalldata"
_FIRESTORE_CLIENT = None


def _build_firebase_options() -> Dict[str, str]:
    options: Dict[str, str] = {}
    project_id = os.getenv("FIREBASE_PROJECT_ID")
    database_url = os.getenv("FIREBASE_DATABASE_URL")

    if project_id:
        options["projectId"] = project_id
    if database_url:
        options["databaseURL"] = database_url

    return options


def initialize_firebase() -> None:
    """Initialize Firebase Admin SDK exactly once."""
    global _FIRESTORE_CLIENT

    if _FIRESTORE_CLIENT is not None:
        return

    options = _build_firebase_options()
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

    if not firebase_admin._apps:
        if service_account_path:
            if not os.path.exists(service_account_path):
                raise RuntimeError(
                    f"FIREBASE_SERVICE_ACCOUNT_JSON not found: {service_account_path}"
                )
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred, options=options)
        else:
            # This requires GOOGLE_APPLICATION_CREDENTIALS or runtime ADC.
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, options=options)

    _FIRESTORE_CLIENT = firestore.client()


def get_firestore_client():
    if _FIRESTORE_CLIENT is None:
        initialize_firebase()
    return _FIRESTORE_CLIENT


def _collection_ref():
    return get_firestore_client().collection(COLLECTION_NAME)


def get_paper_by_id(paper_id: str) -> Optional[Dict]:
    doc = _collection_ref().document(paper_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    data.setdefault("paper_id", paper_id)
    return data


def get_paper_by_credentials(paper_id: str, email: str) -> Optional[Dict]:
    paper = get_paper_by_id(paper_id)
    if not paper:
        return None

    stored_email = (paper.get("corresponding_author_email") or "").strip().lower()
    if stored_email != (email or "").strip().lower():
        return None

    return paper


def create_paper(paper_id: str, paper_data: Dict) -> None:
    payload = dict(paper_data)
    payload["paper_id"] = paper_id
    _collection_ref().document(paper_id).set(payload)


def update_paper(paper_id: str, updates: Dict) -> None:
    _collection_ref().document(paper_id).set(updates, merge=True)
