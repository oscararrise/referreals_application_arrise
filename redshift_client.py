import os
import traceback

import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_redshift_connection():
    required_env_vars = [
        "REDSHIFT_HOST",
        "REDSHIFT_PORT",
        "REDSHIFT_DBNAME",
        "REDSHIFT_USER",
        "REDSHIFT_PASSWORD",
    ]

    missing_vars = [
        var for var in required_env_vars
        if not os.getenv(var)
    ]

    if missing_vars:
        raise ValueError(
            f"Missing Redshift environment variables: {', '.join(missing_vars)}"
        )

    return psycopg2.connect(
        host=os.getenv("REDSHIFT_HOST"),
        port=os.getenv("REDSHIFT_PORT", "5439"),
        dbname=os.getenv("REDSHIFT_DBNAME"),
        user=os.getenv("REDSHIFT_USER"),
        password=os.getenv("REDSHIFT_PASSWORD"),
        sslmode=os.getenv("REDSHIFT_SSLMODE", "require"),
    )


def query_redshift(query: str) -> pd.DataFrame:
    conn = None

    try:
        conn = get_redshift_connection()
        return pd.read_sql(query, conn)

    except Exception as error:
        print("Error executing Redshift query:", error)
        return pd.DataFrame()

    finally:
        if conn:
            conn.close()


query_obtain_list_applications = """
SELECT DISTINCT
    job_title,
    job_location_country,
    job_requisition_id
FROM hr_ops_jbv_schematic.vw_jbv_job
WHERE job_status = 'Open'
  AND job_title IS NOT NULL
  AND job_location_country IS NOT NULL
  AND LOWER(job_title) NOT LIKE '%withdrawal%'
  AND LOWER(job_title) NOT LIKE '%test%'
  AND LOWER(job_title) NOT LIKE '%tst%'
  AND LOWER(job_publish_option) LIKE '%external%'
ORDER BY job_location_country, job_title, job_requisition_id;
"""


def obtain_list_applications():
    conn = None

    try:
        conn = get_redshift_connection()
        df = pd.read_sql(query_obtain_list_applications, conn)

        df = df.dropna(subset=["job_title", "job_location_country"])

        formatted_roles = [
            f"{row['job_location_country']} - {row['job_title']}"
            for _, row in df.iterrows()
        ]

        return formatted_roles

    except Exception as error:
        print("Error obtaining application list:", error)
        return []

    finally:
        if conn:
            conn.close()


def build_referral_link_by_role(role_name, user_id):
    conn = None

    query = """
    SELECT DISTINCT
        job_title,
        job_eid AS eid
    FROM hr_ops_jbv_schematic.vw_jbv_job
    WHERE job_status = 'Open'
      AND job_title IS NOT NULL
      AND job_eid IS NOT NULL;
    """

    try:
        conn = get_redshift_connection()
        df = pd.read_sql(query, conn)

        df = df.dropna(subset=["job_title", "eid"])

        match = df[df["job_title"] == role_name]

        if match.empty:
            return None

        eid = match.iloc[0]["eid"]

        link = (
            "https://jobs.jobvite.com/careers/pragmaticplay/job/"
            f"{eid}/__jvst=Referral&__jvsd=HiBobID_{user_id}"
        )

        return {
            "job_title": role_name,
            "eid": eid,
            "link": link,
        }

    except Exception as error:
        print("Error building referral link:", error)
        print(traceback.format_exc())
        return None

    finally:
        if conn:
            conn.close()