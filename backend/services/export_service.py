import csv
import io
import json
import os
import tempfile
from typing import Generator, List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from backend.api.dependencies import verify_website_ownership, verify_website_ownership_async
from backend.database import crud
from backend.config import settings

class ExportService:
    @staticmethod
    def export_report(website_id: int, user_id: int, format: str, db: Session) -> dict:
        website = verify_website_ownership(website_id, user_id, db)
        fmt = (format or "pdf").lower()
        return {
            "status": "exported",
            "website_id": website.id,
            "domain": website.domain,
            "format": fmt,
            "download_url": f"/api/v1/reports/download/{website.id}.{fmt}",
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    async def export_report_async(website_id: int, user_id: int, format: str, db: AsyncSession) -> dict:
        website = await verify_website_ownership_async(website_id, user_id, db)
        fmt = (format or "pdf").lower()
        return {
            "status": "exported",
            "website_id": website.id,
            "domain": website.domain,
            "format": fmt,
            "download_url": f"/api/v1/reports/download/{website.id}.{fmt}",
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    def stream_csv_audits(website_id: int, user_id: int, db: Session) -> Generator[str, None, None]:
        """Streams audit records for a website in memory efficient CSV chunks."""
        website = verify_website_ownership(website_id, user_id, db)
        audits = crud.get_user_audits_for_website(db, website_id=website.id, user_id=user_id)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header row
        writer.writerow(["Audit ID", "Website ID", "Domain", "Score", "Meta Title", "Meta Description", "Created At"])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        chunk_size = 100
        for i in range(0, len(audits), chunk_size):
            chunk = audits[i:i + chunk_size]
            for audit in chunk:
                writer.writerow([
                    audit.id,
                    website.id,
                    website.domain,
                    getattr(audit, "score", None),
                    getattr(audit, "title", None),
                    getattr(audit, "description", None),
                    getattr(audit, "created_at", None)
                ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    @staticmethod
    async def stream_csv_audits_async(website_id: int, user_id: int, db: AsyncSession) -> Generator[str, None, None]:
        """Streams audit records for a website in memory efficient CSV chunks asynchronously."""
        website = await verify_website_ownership_async(website_id, user_id, db)
        audits = await crud.get_user_audits_for_website_async(db, website_id=website.id, user_id=user_id)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header row
        writer.writerow(["Audit ID", "Website ID", "Domain", "Score", "Meta Title", "Meta Description", "Created At"])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        chunk_size = 100
        for i in range(0, len(audits), chunk_size):
            chunk = audits[i:i + chunk_size]
            for audit in chunk:
                writer.writerow([
                    audit.id,
                    website.id,
                    website.domain,
                    getattr(audit, "score", None),
                    getattr(audit, "title", None),
                    getattr(audit, "description", None),
                    getattr(audit, "created_at", None)
                ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    @staticmethod
    async def generate_sheets_payload_async(website_id: int, user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """Generates Google Sheets API compatible grid data payload for remote exports asynchronously."""
        website = await verify_website_ownership_async(website_id, user_id, db)
        audits = await crud.get_user_audits_for_website_async(db, website_id=website.id, user_id=user_id)
        
        rows = [
            ["Audit ID", "Score", "Title Length", "Images Without Alt", "Created At"]
        ]
        for a in audits:
            rows.append([
                str(a.id),
                str(getattr(a, "score", 0)),
                str(getattr(a, "title_length", 0)),
                str(getattr(a, "images_without_alt", 0)),
                str(getattr(a, "created_at", ""))
            ])
            
        return {
            "spreadsheetTitle": f"SEO Report - {website.domain}",
            "domain": website.domain,
            "totalRows": len(rows),
            "values": rows
        }

    @staticmethod
    def generate_sheets_payload(website_id: int, user_id: int, db: Session) -> Dict[str, Any]:
        """Generates Google Sheets API compatible grid data payload for remote exports."""
        website = verify_website_ownership(website_id, user_id, db)
        audits = crud.get_user_audits_for_website(db, website_id=website.id, user_id=user_id)
        
        rows = [
            ["Audit ID", "Score", "Title Length", "Images Without Alt", "Created At"]
        ]
        for a in audits:
            rows.append([
                str(a.id),
                str(getattr(a, "score", 0)),
                str(getattr(a, "title_length", 0)),
                str(getattr(a, "images_without_alt", 0)),
                str(getattr(a, "created_at", ""))
            ])
            
        return {
            "spreadsheetTitle": f"SEO Report - {website.domain}",
            "domain": website.domain,
            "totalRows": len(rows),
            "values": rows
        }

    @staticmethod
    def create_temp_report_file(website_id: int, user_id: int, format: str, db: Session) -> str:
        """Creates a temporary report artifact on disk and returns the file path."""
        website = verify_website_ownership(website_id, user_id, db)
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}", prefix=f"seo_report_{website_id}_")
        try:
            data = f"SEO Audit Report for {website.domain}\nGenerated at: {datetime.utcnow().isoformat()}\nFormat: {format}\n"
            temp.write(data.encode('utf-8'))
            temp.flush()
            return temp.name
        finally:
            temp.close()

    @staticmethod
    def cleanup_temp_file(filepath: str) -> None:
        """Safely removes temporary export files from disk."""
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass
