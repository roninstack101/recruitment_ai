#candidates.py
from fastapi import APIRouter, UploadFile, File, Form
import tempfile
import zipfile
import os

router = APIRouter(prefix="/candidates", tags=["Candidates"])

@router.post("/run_pipeline")
async def run_pipeline(
    jd_text: str = Form(...),
    resumes: UploadFile = File(...)
):
    """
    Temporary dummy pipeline (replace later with real logic)
    """

    # Save ZIP
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, resumes.filename)
        with open(zip_path, "wb") as f:
            f.write(await resumes.read())

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            files = zip_ref.namelist()

    return {
        "Candidate Intelligence": [
            {
                "company": "Example Corp",
                "snippet": "Strong AI hiring pipeline",
                "link": "https://example.com"
            }
        ],
        "Evaluation": [
            {
                "resume": name,
                "semantic_score": 0.87
            }
            for name in files
        ]
    }


