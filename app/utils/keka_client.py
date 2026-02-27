# app/utils/keka_client.py
# Keka Hire API Client
# Handles OAuth2 authentication and provides methods for importing
# jobs, candidates, and resumes from Keka into the local system.

import os
import time
import requests
from typing import Optional, Dict, List, Any


class KekaAuthError(Exception):
    """Raised when Keka authentication fails."""
    pass


class KekaAPIError(Exception):
    """Raised when a Keka API call fails."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Keka API Error ({status_code}): {message}")


class KekaClient:
    """
    Reusable HTTP client for the Keka Hire API.

    Handles:
    - OAuth2 token generation and caching (auto-refresh on expiry)
    - Rate-limit-aware requests (50 req/min)
    - Pagination for list endpoints
    - All Keka Hire endpoints needed for candidate import
    """

    TOKEN_URL = "https://login.keka.com/connect/token"
    DEFAULT_PAGE_SIZE = 100

    def __init__(
        self,
        base_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("KEKA_BASE_URL", "")).rstrip("/")
        self.client_id = client_id or os.getenv("KEKA_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("KEKA_CLIENT_SECRET", "")
        self.api_key = api_key or os.getenv("KEKA_API_KEY", "")

        # Token cache
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0  # epoch seconds

        # Rate limiting
        self._request_timestamps: list = []

        if not self.base_url:
            raise ValueError(
                "KEKA_BASE_URL is required. Set it in .env or pass base_url parameter. "
                "Example: https://yourcompany.keka.com"
            )

    # ─────────────────────────────────────────────────────
    # Authentication
    # ─────────────────────────────────────────────────────

    def _generate_token(self) -> str:
        """Generate a new OAuth2 access token from Keka."""
        if not all([self.client_id, self.client_secret, self.api_key]):
            raise KekaAuthError(
                "Missing Keka credentials. Set KEKA_CLIENT_ID, KEKA_CLIENT_SECRET, "
                "and KEKA_API_KEY in your .env file."
            )

        payload = {
            "grant_type": "kekaapi",
            "scope": "kekaapi",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "api_key": self.api_key,
        }

        try:
            response = requests.post(
                self.TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            self._access_token = data["access_token"]
            # Cache token with a 5-minute safety margin
            expires_in = data.get("expires_in", 3600)
            self._token_expiry = time.time() + expires_in - 300

            print(f"[KEKA] Access token generated (expires in {expires_in}s)")
            return self._access_token

        except requests.exceptions.RequestException as e:
            raise KekaAuthError(f"Failed to generate Keka access token: {e}")

    def _get_token(self) -> str:
        """Get a valid access token, refreshing if expired."""
        if not self._access_token or time.time() >= self._token_expiry:
            return self._generate_token()
        return self._access_token

    # ─────────────────────────────────────────────────────
    # Rate Limiting
    # ─────────────────────────────────────────────────────

    def _wait_for_rate_limit(self):
        """Enforce 50 requests/minute rate limit."""
        now = time.time()
        # Remove timestamps older than 60 seconds
        self._request_timestamps = [
            ts for ts in self._request_timestamps if now - ts < 60
        ]

        if len(self._request_timestamps) >= 50:
            # Wait until the oldest request in the window expires
            wait_time = 60 - (now - self._request_timestamps[0]) + 0.5
            if wait_time > 0:
                print(f"[KEKA] Rate limit reached. Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)

        self._request_timestamps.append(time.time())

    # ─────────────────────────────────────────────────────
    # HTTP Request Wrapper
    # ─────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        retry_on_401: bool = True,
    ) -> requests.Response:
        """
        Make an authenticated request to the Keka API.
        Auto-retries once on 401 (token expired).
        """
        self._wait_for_rate_limit()

        url = f"{self.base_url}/api/v1/hire/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Accept": "application/json",
        }

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                files=files,
                timeout=30,
            )

            # Auto-retry on 401 (token expired)
            if response.status_code == 401 and retry_on_401:
                print("[KEKA] Token expired, refreshing...")
                self._access_token = None
                return self._request(
                    method, path, params, json_data, files, retry_on_401=False
                )

            if response.status_code >= 400:
                error_msg = response.text[:500]
                raise KekaAPIError(response.status_code, error_msg)

            return response

        except requests.exceptions.RequestException as e:
            raise KekaAPIError(0, str(e))

    # ─────────────────────────────────────────────────────
    # Pagination Helper
    # ─────────────────────────────────────────────────────

    def _get_all_pages(self, path: str, params: Optional[Dict] = None) -> List[Dict]:
        """Fetch all pages of a paginated endpoint."""
        params = params or {}
        params.setdefault("pageSize", self.DEFAULT_PAGE_SIZE)
        params.setdefault("pageNumber", 1)

        all_results = []

        while True:
            response = self._request("GET", path, params=params)
            data = response.json()

            # Keka wraps results in a "data" key
            records = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(records, list):
                all_results.extend(records)
            else:
                # Single object response
                return [records] if records else []

            # Check if there are more pages
            if isinstance(data, dict):
                total = data.get("totalCount", len(all_results))
                if len(all_results) >= total:
                    break
            else:
                break

            params["pageNumber"] += 1

        return all_results

    # ─────────────────────────────────────────────────────
    # Job Boards
    # ─────────────────────────────────────────────────────

    def get_job_boards(self) -> List[Dict]:
        """GET /v1/hire/jobboards — Fetch all job boards."""
        response = self._request("GET", "jobboards")
        data = response.json()
        return data.get("data", data) if isinstance(data, dict) else data

    # ─────────────────────────────────────────────────────
    # Jobs
    # ─────────────────────────────────────────────────────

    def get_jobs(self, status: Optional[str] = None) -> List[Dict]:
        """
        GET /v1/hire/jobs — Fetch all jobs from Keka.

        Args:
            status: Optional filter (e.g., 'Published', 'Archived')

        Returns:
            List of job dicts with id, title, department, location, etc.
        """
        params = {}
        if status:
            params["status"] = status
        return self._get_all_pages("jobs", params)

    def get_application_fields(self, job_id: str) -> Dict:
        """
        GET /v1/hire/jobs/{jobId}/applicationfields
        Get the application form fields for a specific job.
        """
        response = self._request("GET", f"jobs/{job_id}/applicationfields")
        data = response.json()
        return data.get("data", data) if isinstance(data, dict) else data

    # ─────────────────────────────────────────────────────
    # Candidates (Import-focused)
    # ─────────────────────────────────────────────────────

    def get_candidates(
        self,
        job_id: str,
        archived: bool = False,
    ) -> List[Dict]:
        """
        GET /v1/hire/jobs/{jobId}/candidates
        Fetch all candidates for a job.

        Args:
            job_id: Keka job ID
            archived: If True, fetch archived candidates

        Returns:
            List of candidate dicts
        """
        params = {}
        if archived:
            params["isArchived"] = True
        return self._get_all_pages(f"jobs/{job_id}/candidates", params)

    def get_candidate_resume(self, candidate_id: str) -> Optional[bytes]:
        """
        GET /v1/hire/jobs/candidate/{candidateId}/resume
        Download a candidate's resume file.

        Returns:
            Raw file bytes, or None if no resume.
        """
        try:
            response = self._request("GET", f"jobs/candidate/{candidate_id}/resume")
            if response.status_code == 200 and response.content:
                return response.content
            return None
        except KekaAPIError:
            return None

    def get_candidate_interviews(
        self, job_id: str, candidate_id: str
    ) -> List[Dict]:
        """
        GET /v1/hire/jobs/{jobId}/candidate/{candidateId}/interviews
        Get interviews scheduled/completed for a candidate.
        """
        response = self._request(
            "GET", f"jobs/{job_id}/candidate/{candidate_id}/interviews"
        )
        data = response.json()
        return data.get("data", data) if isinstance(data, dict) else data

    def get_candidate_scorecards(
        self, job_id: str, candidate_id: str
    ) -> List[Dict]:
        """
        GET /v1/hire/jobs/{jobId}/candidate/{candidateId}/scorecards
        Get evaluation scorecards for a candidate.
        """
        response = self._request(
            "GET", f"jobs/{job_id}/candidate/{candidate_id}/scorecards"
        )
        data = response.json()
        return data.get("data", data) if isinstance(data, dict) else data

    # ─────────────────────────────────────────────────────
    # Connection Test
    # ─────────────────────────────────────────────────────

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the Keka API connection by fetching jobs.
        Returns a status dict.
        """
        try:
            token = self._get_token()
            jobs = self.get_jobs()
            return {
                "status": "connected",
                "authenticated": True,
                "jobs_found": len(jobs),
                "base_url": self.base_url,
            }
        except KekaAuthError as e:
            return {
                "status": "auth_failed",
                "authenticated": False,
                "error": str(e),
                "base_url": self.base_url,
            }
        except KekaAPIError as e:
            return {
                "status": "api_error",
                "authenticated": True,
                "error": str(e),
                "base_url": self.base_url,
            }


# ─────────────────────────────────────────────────────
# Singleton accessor
# ─────────────────────────────────────────────────────
_client_instance: Optional[KekaClient] = None


def get_keka_client() -> KekaClient:
    """Get or create the singleton KekaClient instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = KekaClient()
    return _client_instance
