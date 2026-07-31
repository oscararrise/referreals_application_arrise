from django.test import TestCase

from referrals.models import EmployeeDirectoryHiBob
from referrals.services.hibob.sync_service import HiBobEmployeeSyncService


class FakeHiBobClient:
    def get_fields_metadata(self):
        return []

    def search_employees(self, fields):
        return [
            {
                "/work/employeeIdInCompany": "100",
                "/root/email": "updated@example.com",
                "/root/firstName": "Updated",
                "/root/surname": "Person",
                "/work/startDate": "2026-01-01",
                "humanReadable": {
                    "/work/site": "Bogota",
                    "/work/department": "Technology",
                    "/work/title": "Engineer",
                },
            },
            {
                "/work/employeeIdInCompany": "200",
                "/root/email": "new@example.com",
                "/root/firstName": "New",
                "/root/surname": "Employee",
                "/work/startDate": "2026-02-01",
                "humanReadable": {
                    "/work/site": "Medellin",
                    "/work/department": "Operations",
                    "/work/title": "Analyst",
                },
            },
        ]


class HiBobSyncServiceTests(TestCase):
    def setUp(self):
        self.existing = EmployeeDirectoryHiBob.objects.create(
            employee_id="100",
            email="old@example.com",
            first_name="Old",
            last_name="Person",
            entity="Keep existing optional value",
        )

    def test_dry_run_does_not_modify_postgresql(self):
        result = HiBobEmployeeSyncService(
            client=FakeHiBobClient()
        ).run(dry_run=True)

        self.assertEqual(result.created, 1)
        self.assertEqual(result.updated, 1)
        self.assertEqual(EmployeeDirectoryHiBob.objects.count(), 1)

        self.existing.refresh_from_db()
        self.assertEqual(self.existing.email, "old@example.com")

    def test_sync_updates_and_creates_without_clearing_unresolved_fields(self):
        result = HiBobEmployeeSyncService(
            client=FakeHiBobClient()
        ).run()

        self.assertEqual(result.created, 1)
        self.assertEqual(result.updated, 1)
        self.assertEqual(EmployeeDirectoryHiBob.objects.count(), 2)

        self.existing.refresh_from_db()
        self.assertEqual(self.existing.email, "updated@example.com")
        self.assertEqual(self.existing.first_name, "Updated")
        self.assertEqual(self.existing.site, "Bogota")
        self.assertEqual(
            self.existing.entity,
            "Keep existing optional value",
        )

        new_employee = EmployeeDirectoryHiBob.objects.get(employee_id="200")
        self.assertEqual(new_employee.email, "new@example.com")
        self.assertEqual(new_employee.job_title, "Analyst")
