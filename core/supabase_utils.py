import io
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from django.conf import settings
from PyPDF2 import PdfReader
from supabase import Client, create_client

from .utils import chunk_text, embed_texts

logger = logging.getLogger(__name__)


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name) or getattr(settings, name, default)


def get_supabase_client(use_service_role: bool = False) -> Client:
    supabase_url = _get_env("NEXT_PUBLIC_SUPABASE_URL")
    if not supabase_url:
        supabase_url = _get_env("SUPABASE_URL")

    if use_service_role:
        supabase_key = _get_env("SUPABASE_SERVICE_ROLE_KEY")
    else:
        supabase_key = _get_env("NEXT_PUBLIC_SUPABASE_ANON_KEY") or _get_env("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and "
            "NEXT_PUBLIC_SUPABASE_ANON_KEY, plus SUPABASE_SERVICE_ROLE_KEY for server operations."
        )

    return create_client(supabase_url, supabase_key)


def connect_supabase() -> bool:
    # Health-check helper.
    try:
        get_supabase_client(use_service_role=True)
        return True
    except Exception as exc:
        logger.error("Supabase connection failed: %s", exc)
        return False


def is_supabase_service_configured() -> bool:
    url = _get_env("NEXT_PUBLIC_SUPABASE_URL") or _get_env("SUPABASE_URL")
    key = _get_env("SUPABASE_SERVICE_ROLE_KEY")
    return bool(url and key)


def _truncate(text: Optional[str], max_len: int = 4000) -> str:
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def sync_app_user_to_supabase(
    django_user_id: str,
    email: str,
    name: str,
    role: str = "user",
    *,
    set_last_login: bool = False,
) -> None:
    """Upsert profile row in app_users (no passwords). Safe to call on login/register."""
    if not is_supabase_service_configured():
        return
    try:
        client = get_supabase_client(use_service_role=True)
        now = datetime.now(timezone.utc).isoformat()
        payload: Dict[str, Any] = {
            "django_user_id": str(django_user_id),
            "email": email,
            "name": name or "",
            "role": role or "user",
            "updated_at": now,
        }
        if set_last_login:
            payload["last_login_at"] = now
        client.table("app_users").upsert(payload, on_conflict="django_user_id").execute()
    except Exception as exc:
        logger.warning("sync_app_user_to_supabase failed: %s", exc)


def log_auth_event_to_supabase(django_user_id: str, email: str, event_type: str) -> None:
    """Record register / login / logout for analytics."""
    if not is_supabase_service_configured():
        return
    if event_type not in ("register", "login", "logout"):
        return
    try:
        client = get_supabase_client(use_service_role=True)
        client.table("user_auth_events").insert(
            {
                "django_user_id": str(django_user_id),
                "user_email": email,
                "event_type": event_type,
            }
        ).execute()
    except Exception as exc:
        logger.warning("log_auth_event_to_supabase failed: %s", exc)


def log_user_search_to_supabase(
    *,
    django_user_id: Optional[str],
    user_email: Optional[str],
    user_name: Optional[str],
    query_text: str,
    response_preview: Optional[str] = None,
    search_type: str = "text",
    success: bool = True,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist question/search for analytics (identified by email + django id when logged in)."""
    if not is_supabase_service_configured():
        return
    if not (query_text or "").strip():
        return
    try:
        client = get_supabase_client(use_service_role=True)
        row: Dict[str, Any] = {
            "django_user_id": str(django_user_id) if django_user_id else None,
            "user_email": user_email or None,
            "user_name": user_name or None,
            "query_text": _truncate(query_text, 4000),
            "response_preview": _truncate(response_preview, 4000) or None,
            "search_type": search_type,
            "success": success,
            "error_message": _truncate(error_message, 2000) or None,
            "metadata": metadata or {},
        }
        client.table("user_search_logs").insert(row).execute()
    except Exception as exc:
        logger.warning("log_user_search_to_supabase failed: %s", exc)


def _safe_path(filename: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{base}"


def upload_pdf_and_create_document(
    filename: str,
    file_bytes: bytes,
    uploader: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    client = get_supabase_client(use_service_role=True)
    bucket = _get_env("SUPABASE_PDF_BUCKET", "pdfs")
    storage_path = f"{user_id or 'public'}/{_safe_path(filename)}"

    client.storage.from_(bucket).upload(
        storage_path,
        file_bytes,
        {"content-type": "application/pdf", "upsert": "false"},
    )

    row = {
        "filename": filename,
        "storage_path": storage_path,
        "uploader": uploader or "",
        "user_id": user_id or "",
        "status": "uploaded",
    }
    data = client.table("documents").insert(row).execute().data or []
    if not data:
        raise RuntimeError("Failed to create documents row")
    return data[0]


def create_signed_upload_url(filename: str, expires_in: int = 3600, user_id: Optional[str] = None) -> Dict[str, Any]:
    client = get_supabase_client(use_service_role=True)
    bucket = _get_env("SUPABASE_PDF_BUCKET", "pdfs")
    storage_path = f"{user_id or 'public'}/{_safe_path(filename)}"
    signed = client.storage.from_(bucket).create_signed_upload_url(storage_path)
    return {
        "bucket": bucket,
        "storage_path": storage_path,
        "token": signed.get("token"),
        "signed_url": signed.get("signedUrl"),
        "expires_in": expires_in,
    }


def _extract_pdf_text_by_page(file_bytes: bytes) -> List[Dict[str, Any]]:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages: List[Dict[str, Any]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page_number": i, "text": text})
    return pages


def ingest_document(document_id: str) -> Dict[str, Any]:
    client = get_supabase_client(use_service_role=True)
    bucket = _get_env("SUPABASE_PDF_BUCKET", "pdfs")

    doc_rows = client.table("documents").select("*").eq("id", document_id).limit(1).execute().data or []
    if not doc_rows:
        raise RuntimeError("Document not found")
    doc = doc_rows[0]
    storage_path = doc["storage_path"]

    file_bytes = client.storage.from_(bucket).download(storage_path)
    page_texts = _extract_pdf_text_by_page(file_bytes)
    inserts: List[Dict[str, Any]] = []
    total_chunks = 0

    for page in page_texts:
        page_number = page["page_number"]
        chunks = chunk_text(page["text"])
        if not chunks:
            continue
        embeddings = embed_texts(chunks)
        for idx, chunk in enumerate(chunks):
            vector = embeddings[idx].tolist() if hasattr(embeddings[idx], "tolist") else embeddings[idx]
            inserts.append(
                {
                    "document_id": document_id,
                    "page_number": page_number,
                    "chunk_index": idx,
                    "text": chunk,
                    "embedding": vector,
                    "metadata": {
                        "source_path": storage_path,
                        "filename": doc.get("filename", ""),
                    },
                }
            )
            total_chunks += 1

    if inserts:
        client.table("document_chunks").insert(inserts).execute()

    client.table("documents").update(
        {"status": "indexed", "indexed_at": datetime.now(timezone.utc).isoformat(), "chunk_count": total_chunks}
    ).eq("id", document_id).execute()

    return {"success": True, "document_id": document_id, "chunk_count": total_chunks}


def match_document_chunks(query: str, k: int = 5) -> List[Dict[str, Any]]:
    client = get_supabase_client(use_service_role=True)
    query_embedding = embed_texts([query])[0]
    vector = query_embedding.tolist() if hasattr(query_embedding, "tolist") else query_embedding
    result = client.rpc("match_document_chunks", {"query_embedding": vector, "match_count": k}).execute()
    return result.data or []


def store_user_contribution(contribution_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        client = get_supabase_client(use_service_role=True)
        payload = {
            "question": contribution_data.get("question", ""),
            "answer": contribution_data.get("message", ""),
            "question_type": contribution_data.get("type", "general"),
            "user_id": contribution_data.get("user_id", ""),
            "user_email": contribution_data.get("email", ""),
            "rating": float(contribution_data.get("rating", 0.0) or 0.0),
            "improvement_type": contribution_data.get("improvement_type", "enhancement"),
            "status": "pending",
        }
        data = client.table("feedback").insert(payload).execute().data or []
        if not data:
            return {"success": False, "error": "insert_failed"}
        return {"success": True, "contribution_id": str(data[0].get("id")), "message": "Contribution stored successfully"}
    except Exception as exc:
        return {"success": False, "error": str(exc), "message": "Failed to store contribution"}


def search_similar_contributions(query: str, limit: int = 5, min_rating: float = 0.0) -> List[Dict[str, Any]]:
    try:
        client = get_supabase_client(use_service_role=True)
        rows = (
            client.table("feedback")
            .select("*")
            .eq("status", "approved")
            .gte("rating", min_rating)
            .order("rating", desc=True)
            .limit(100)
            .execute()
            .data
            or []
        )
        q = query.lower()
        scored = []
        for row in rows:
            question = (row.get("question") or "").lower()
            answer = (row.get("answer") or "").lower()
            score = 0.0
            if q in question or q in answer:
                score = 1.0
            else:
                overlap = len(set(q.split()) & set((question + " " + answer).split()))
                score = overlap / max(len(set(q.split())), 1)
            if score > 0:
                row["similarity_score"] = score
                row["is_approved"] = row.get("status", "pending")
                scored.append(row)
        scored.sort(key=lambda x: (x.get("similarity_score", 0), x.get("rating", 0)), reverse=True)
        return scored[:limit]
    except Exception:
        return []


def get_contribution_analytics(question_type: Optional[str] = None) -> Dict[str, Any]:
    client = get_supabase_client(use_service_role=True)
    query = client.table("feedback").select("*")
    if question_type:
        query = query.eq("question_type", question_type)
    rows = query.execute().data or []
    total = len(rows)
    avg = sum(float(r.get("rating", 0) or 0) for r in rows) / total if total else 0.0
    return {
        "question_type": question_type or "overall",
        "total_contributions": total,
        "average_rating": avg,
        "questions_and_answers": rows[:50],
        "top_rated_qa": sorted(rows, key=lambda x: float(x.get("rating", 0) or 0), reverse=True)[:10],
        "recent_contributions": sorted(rows, key=lambda x: x.get("created_at", ""), reverse=True)[:20],
    }


def get_top_contributions(limit: int = 10) -> List[Dict[str, Any]]:
    client = get_supabase_client(use_service_role=True)
    return client.table("feedback").select("*").eq("status", "approved").order("rating", desc=True).limit(limit).execute().data or []


def get_questions_and_answers(question_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    client = get_supabase_client(use_service_role=True)
    query = client.table("feedback").select("*").eq("status", "approved")
    if question_type:
        query = query.eq("question_type", question_type)
    return query.order("created_at", desc=True).limit(limit).execute().data or []


def get_top_rated_qa(question_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    client = get_supabase_client(use_service_role=True)
    query = client.table("feedback").select("*").eq("status", "approved")
    if question_type:
        query = query.eq("question_type", question_type)
    return query.order("rating", desc=True).limit(limit).execute().data or []


def get_recent_qa(question_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    client = get_supabase_client(use_service_role=True)
    query = client.table("feedback").select("*").eq("status", "approved")
    if question_type:
        query = query.eq("question_type", question_type)
    return query.order("created_at", desc=True).limit(limit).execute().data or []


def search_qa_by_keyword(keyword: str, question_type: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = get_questions_and_answers(question_type=question_type, limit=200)
    needle = keyword.lower()
    return [r for r in rows if needle in (r.get("question", "").lower() + " " + r.get("answer", "").lower())]


def approve_all_pending_contributions() -> Dict[str, Any]:
    client = get_supabase_client(use_service_role=True)
    pending = client.table("feedback").select("id").eq("status", "pending").execute().data or []
    pending_count = len(pending)
    if pending_count == 0:
        return {"success": True, "approved_count": 0, "pending_count": 0, "message": "No pending contributions found"}
    client.table("feedback").update({"status": "approved"}).eq("status", "pending").execute()
    return {
        "success": True,
        "approved_count": pending_count,
        "pending_count": pending_count,
        "message": f"Successfully approved {pending_count} pending contributions",
    }


def list_contributions(status_filter: str = "all", page: int = 1, per_page: int = 20, search_query: str = "") -> Dict[str, Any]:
    client = get_supabase_client(use_service_role=True)
    query = client.table("feedback").select("*", count="exact")
    if status_filter != "all":
        query = query.eq("status", status_filter)
    if search_query:
        query = query.or_(f"question.ilike.%{search_query}%,answer.ilike.%{search_query}%")
    start_index = (page - 1) * per_page
    end_index = start_index + per_page - 1
    resp = query.order("created_at", desc=True).range(start_index, end_index).execute()
    total_count = resp.count or 0
    return {
        "items": resp.data or [],
        "total_count": total_count,
    }


def update_contribution_status(contribution_id: str, action: str) -> Dict[str, Any]:
    client = get_supabase_client(use_service_role=True)
    new_status = "approved" if action == "approve" else "rejected"
    updated = client.table("feedback").update({"status": new_status}).eq("id", contribution_id).execute().data or []
    if not updated:
        return {"success": False, "error": "Contribution not found"}
    return {"success": True, "new_status": new_status}
