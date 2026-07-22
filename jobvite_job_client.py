import os

import requests
from dotenv import load_dotenv
from django.core.cache import cache

load_dotenv()

JOBVITE_JOB_BASE_URL = os.getenv(
    "JOBVITE_JOB_BASE_URL",
    "https://api.jobvite.com/api/v2/job",
)

JOBVITE_JOB_API_KEY = os.getenv("JOBVITE_JOB_API_KEY")
JOBVITE_JOB_API_SECRET = os.getenv("JOBVITE_JOB_API_SECRET")
JOBVITE_OPEN_JOBS_CACHE_KEY = "jobvite_open_jobs"
JOBVITE_OPEN_JOBS_CACHE_TIMEOUT = 15 * 60


def _get_headers():
    missing_variables = []

    if not JOBVITE_JOB_API_KEY:
        missing_variables.append("JOBVITE_JOB_API_KEY")

    if not JOBVITE_JOB_API_SECRET:
        missing_variables.append("JOBVITE_JOB_API_SECRET")

    if missing_variables:
        raise ValueError(
            "Missing Jobvite environment variables: "
            + ", ".join(missing_variables)
        )

    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-jvi-api": JOBVITE_JOB_API_KEY,
        "x-jvi-sc": JOBVITE_JOB_API_SECRET,
    }


def get_open_jobs(force_refresh=False):
    """
    Retrieve all open jobs from Jobvite.

    Results are cached for 15 minutes to avoid calling
    Jobvite every time the referral form is opened.
    """

    if not force_refresh:
        cached_jobs = cache.get(JOBVITE_OPEN_JOBS_CACHE_KEY)

        if cached_jobs is not None:
            return cached_jobs

    jobs = []
    start = 1
    count = 500

    while True:
        response = requests.get(
            JOBVITE_JOB_BASE_URL,
            headers=_get_headers(),
            params={
                "format": "json",
                "jobStatus": "Open",
                "start": start,
                "count": count,
            },
            timeout=60,
        )

        response.raise_for_status()

        payload = response.json()
        current_jobs = payload.get("requisitions", [])

        if not current_jobs:
            break

        jobs.extend(current_jobs)

        if len(current_jobs) < count:
            break

        start += count

    cache.set(
        JOBVITE_OPEN_JOBS_CACHE_KEY,
        jobs,
        JOBVITE_OPEN_JOBS_CACHE_TIMEOUT,
    )

    return jobs


def _get_primary_location(job):
    country = str(job.get("locationCountry") or "").strip()
    location = str(job.get("location") or "").strip()

    job_locations = job.get("jobLocations") or []

    if job_locations:
        primary_location = job_locations[0]

        if not country:
            country = str(primary_location.get("country") or "").strip()

        if not location:
            location = str(primary_location.get("name") or "").strip()

    return country, location

def _is_open_job(job):
    job_state = str(job.get("jobState") or "").strip().lower()

    return job_state == "open"


def _is_external_job(job):
    posting_type = str(
        job.get("postingType")
        or job.get("jobPosting")
        or job.get("availableTo")
        or ""
    ).lower()

    return "external" in posting_type


def _is_valid_job_title(title):
    normalized_title = str(title or "").strip().lower()

    if not normalized_title:
        return False

    excluded_terms = [
        "withdrawal",
        "test",
        "tst",
    ]

    return not any(
        term in normalized_title
        for term in excluded_terms
    )


def obtain_list_applications():
    """
    Return the values used by the referral form datalist.

    Format:
        Country - Job title
    """

    try:
        jobs = get_open_jobs()
        role_options = set()

        for job in jobs:
            title = str(job.get("title") or "").strip()

            if not _is_open_job(job):
                continue

            if not _is_valid_job_title(title):
                continue

            if not _is_external_job(job):
                continue

            country, location = _get_primary_location(job)

            display_location = country or location

            if not display_location:
                continue

            role_options.add(
                f"{display_location} - {title}"
            )

        return sorted(role_options)

    except requests.RequestException as error:
        print("Error requesting open jobs from Jobvite:", error)
        return []

    except Exception as error:
        print("Error obtaining Jobvite job list:", error)
        return []


def build_referral_link_by_role(role_name, user_id):
    """
    Find the selected open job and build its referral URL.
    """

    try:
        selected_role = str(role_name or "").strip()

        if " - " not in selected_role:
            return None

        selected_location, selected_title = selected_role.split(
            " - ",
            1,
        )

        jobs = get_open_jobs()

        for job in jobs:
            title = str(job.get("title") or "").strip()
            job_eid = str(job.get("eId") or "").strip()

            if not _is_open_job(job):
                continue

            if not title or not job_eid:
                continue

            if not _is_external_job(job):
                continue

            country, location = _get_primary_location(job)
            display_location = country or location

            if (
                title.casefold() == selected_title.casefold()
                and display_location.casefold()
                == selected_location.casefold()
            ):
                apply_link = str(job.get("applyLink") or "").strip()

                if not apply_link:
                    return None

                separator = "&" if "?" in apply_link else "?"

                referral_link = (
                    f"{apply_link}"
                    f"{separator}__jvst=Referral"
                    f"&__jvsd=HiBobID_{user_id}"
                )

                return {
                    "job_title": title,
                    "eid": job_eid,
                    "requisition_id": job.get("requisitionId"),
                    "location": location,
                    "country": country,
                    "link": referral_link,
                }

        return None

    except requests.RequestException as error:
        print("Error requesting Jobvite job details:", error)
        return None

    except Exception as error:
        print("Error building Jobvite referral link:", error)
        return None