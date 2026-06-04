import traceback

import psycopg2
import pandas as pd


def get_redshift_connection():
    return psycopg2.connect(
        host="tf-redshift-cluster.crjnei9qdhec.eu-west-1.redshift.amazonaws.com",
        port=5439,
        dbname="bi_db_rs",
        user="oscar_j",
        password="O$c@rJ&91l/",
        sslmode="require"
    )


def query_redshift(query: str) -> pd.DataFrame:
    conn = None
    try:
        conn = get_redshift_connection()
        df = pd.read_sql(query, conn)
        return df

    except Exception as e:
        print("Error ejecutando query:", e)
        return pd.DataFrame()

    finally:
        if conn:
            conn.close()

query_table_vw_jbv_application = """
SELECT
app_id,
app_candidate_id,
app_deleted,
app_eid,
job_id,
app_sent_date,
app_workflow_state_name,
app_workflow_state_date,
app_modified,
app_sourcetype,
app_source
    
FROM hr_ops_jbv_schematic.vw_jbv_application
WHERE app_candidate_id = 193183234
"""

query_table_vw_jbv_job = """
select

job_requisition_id,
job_title,
job_department_name,
job_workflow_title

from hr_ops_jbv_schematic.vw_jbv_job
"""

query_table_vw_jbv_candidate_workflow = """ 
select 

app_next_workflow_state_name,
app_next_workflow_state_position,
app_next_workflow_state_date

from hr_ops_jbv_schematic.vw_jbv_candidate_workflow
"""
query_table_vw_jbv_job_custom_fields = """
                                Select 
                                job_id,
                                job_custom_field_value,
                                job_custom_field_name
                                from hr_ops_jbv_schematic.vw_jbv_job_custom_fields
                                """



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

    except Exception as e:
        print("Error executing query:", e)
        return []

    finally:
        if conn:
            conn.close()

def build_referral_link_by_role(role_name, user_id):
    conn = None
    query_obtain_list_applications = """
select
    distinct
    job_title,
    job_eid as eid
from hr_ops_jbv_schematic.vw_jbv_job
where job_status = 'Open'

"""
    try:
        conn = get_redshift_connection()
        df = pd.read_sql(query_obtain_list_applications, conn)

        df = df.dropna(subset=['job_title', 'eid'])
        match = df[df['job_title'] == role_name]

        if match.empty:
            return None

        eid = match.iloc[0]['eid']
        link = f"https://jobs.jobvite.com/careers/pragmaticplay/job/{eid}/__jvst=Referral&__jvsd=HiBobID_{user_id}"

        return {
            'job_title': role_name,
            'eid': eid,
            'link': link,
        }

    except Exception as e:
        import traceback
        print("Error executing query:", e, traceback.format_exc())
        return None