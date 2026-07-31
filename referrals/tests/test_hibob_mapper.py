from datetime import date

from django.test import SimpleTestCase

from referrals.services.hibob.mapper import map_employee


class HiBobMapperTests(SimpleTestCase):
    def test_maps_hibob_payload_to_existing_model_shape(self):
        field_lookup = {
            "employee_id": "work.employeeIdInCompany",
            "email": "root.email",
            "first_name": "root.firstName",
            "last_name": "root.surname",
            "site": "work.site",
            "department": "work.department",
            "job_title": "work.title",
            "start_date": "work.startDate",
            "business_unit": "custom.businessUnit",
            "termination_date": "custom.terminationDate",
        }
        employee = {
            "/work/employeeIdInCompany": {"value": "12345"},
            "/root/email": " PERSON@EXAMPLE.COM ",
            "/root/firstName": "Ada",
            "/root/surname": "Lovelace",
            "/work/startDate": "2026-01-15",
            "/custom/terminationDate": "2026-07-20",
            "humanReadable": {
                "/work/site": {"value": "Bogota"},
                "/work/department": {"value": "Technology"},
                "/work/title": {"value": "Developer"},
                "/custom/businessUnit": {"value": "Central"},
            },
        }

        mapped = map_employee(employee, field_lookup)

        self.assertEqual(mapped["employee_id"], "12345")
        self.assertEqual(mapped["email"], "person@example.com")
        self.assertEqual(mapped["first_name"], "Ada")
        self.assertEqual(mapped["last_name"], "Lovelace")
        self.assertEqual(mapped["site"], "Bogota")
        self.assertEqual(mapped["department"], "Technology")
        self.assertEqual(mapped["job_title"], "Developer")
        self.assertEqual(mapped["business_unit"], "Central")
        self.assertEqual(mapped["start_date"], date(2026, 1, 15))
        self.assertEqual(mapped["termination_date"], date(2026, 7, 20))
