# Copyright (c) 2026, SAH Diagnostics and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase


def make_shift(shift_id, **overrides):
	doc = frappe.get_doc(
		{
			"doctype": "VC Roster Shift",
			"vc_shift_id": shift_id,
			"shift_date": "2027-07-14",
			"start_time": "09:00:00",
			"end_time": "17:00:00",
			"clinic_name": "Test Clinic",
			"staffing": [{"user_type": "Sonographer", "required": 2, "assigned": 1, "open": 1}],
			"clinicians": [
				{"vc_practitioner_role_id": "role-a", "clinician_name": "Dr A", "user_type": "Sonographer"}
			],
			**overrides,
		}
	)
	return doc.insert(ignore_permissions=True)


def printed_page(html):
	return html.split('<div class="print-format">', 1)[1].split("<script data-frappe-print>", 1)[0]


class TestVCRosterShift(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_named_by_vc_shift_id(self):
		doc = make_shift("test-shift-naming")
		self.assertEqual(doc.name, "test-shift-naming")
		self.assertEqual(doc.status, "Active")
		self.assertEqual(len(doc.staffing), 1)
		self.assertEqual(len(doc.clinicians), 1)

	def test_trust_shift_id_is_the_title_while_vc_id_stays_the_name(self):
		doc = make_shift("test-shift-title", vc_reference_id="S00042")
		self.assertEqual(doc.name, "test-shift-title")
		self.assertEqual(doc.get_title(), "S00042")
		meta = frappe.get_meta("VC Roster Shift")
		self.assertTrue(meta.show_title_field_in_link)
		self.assertIn("vc_reference_id", meta.search_fields)
		self.assertTrue(meta.get_field("vc_reference_id").in_list_view)
		found = frappe.get_all("VC Roster Shift", filters={"vc_reference_id": "S00042"}, pluck="name")
		self.assertEqual(found, ["test-shift-title"])

	def test_people_see_short_ids_and_the_long_vc_ids_sit_in_the_collapsed_section(self):
		doc = make_shift("test-shift-short-ids", vc_reference_id="S00043", clinic_reference_id="D007")
		self.assertEqual(frappe.db.get_value("VC Roster Shift", doc.name, "clinic_reference_id"), "D007")
		meta = frappe.get_meta("VC Roster Shift")
		order = [f.fieldname for f in meta.fields]
		references = order.index("vc_section")
		self.assertLess(order.index("clinic_reference_id"), references)
		for fieldname in ("vc_shift_id", "trust_id", "clinic_id", "location_id"):
			self.assertGreater(order.index(fieldname), references, fieldname)
			self.assertFalse(meta.get_field(fieldname).in_list_view, fieldname)
		self.assertTrue(meta.get_field("vc_section").collapsible)
		clinician = frappe.get_meta("VC Roster Shift Clinician")
		self.assertFalse(clinician.get_field("vc_practitioner_role_id").in_list_view)
		self.assertTrue(clinician.get_field("clinician_name").in_list_view)

	def test_print_shows_short_ids_and_no_vc_uuids(self):
		uuid = "0f1e2d3c-4b5a-4968-8776-655443322110"
		role_uuid = "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"
		doc = make_shift(
			uuid,
			vc_reference_id="S00044",
			clinic_reference_id="D007",
			trust_id="7b6a5948-3726-4150-9f8e-7d6c5b4a3928",
			clinicians=[
				{"vc_practitioner_role_id": role_uuid, "clinician_name": "Dr A", "user_type": "Consultant"}
			],
		)
		self.assertEqual(frappe.get_meta("VC Roster Shift").default_print_format, "VC Roster Shift")
		for print_format in ("VC Roster Shift", "Standard"):
			html = printed_page(
				frappe.get_print("VC Roster Shift", doc.name, print_format=print_format, no_letterhead=1)
			)
			self.assertIn("S00044", html, print_format)
			for long_id in (uuid, role_uuid, "7b6a5948-3726-4150-9f8e-7d6c5b4a3928"):
				self.assertNotIn(long_id, html, print_format)
		custom = printed_page(frappe.get_print("VC Roster Shift", doc.name, print_format="VC Roster Shift"))
		self.assertIn("D007", custom)
		self.assertIn("Dr A", custom)
		self.assertNotIn(uuid, custom)

	def test_second_record_with_same_vc_shift_id_is_rejected(self):
		make_shift("test-shift-duplicate")
		with self.assertRaises(frappe.DuplicateEntryError):
			make_shift("test-shift-duplicate")

	def test_status_accepts_only_active_or_cancelled(self):
		doc = make_shift("test-shift-status")
		doc.status = "Cancelled"
		doc.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("VC Roster Shift", doc.name, "status"), "Cancelled")
		doc.status = "Deleted"
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_sync_role_can_write_but_not_delete(self):
		perms = {p.role: p for p in frappe.get_meta("VC Roster Shift").permissions}
		sync = perms["VC Roster Sync"]
		self.assertEqual((sync.read, sync.write, sync.create, sync.delete), (1, 1, 1, 0))

	def test_people_can_only_read_because_vc_is_the_source_of_truth(self):
		perms = {p.role: p for p in frappe.get_meta("VC Roster Shift").permissions}
		manager = perms["System Manager"]
		self.assertEqual((manager.read, manager.write, manager.create, manager.delete), (1, 0, 0, 0))
		self.assertEqual(set(perms), {"VC Roster Sync", "System Manager"})

	def test_desk_offers_no_new_button_even_to_administrator(self):
		self.assertTrue(frappe.get_meta("VC Roster Shift").in_create)
		from frappe.utils.user import UserPermissions

		admin = UserPermissions("Administrator")
		admin.build_permissions()
		self.assertNotIn("VC Roster Shift", admin.can_create)

	def test_sync_role_is_shipped_as_a_fixture(self):
		self.assertTrue(frappe.db.exists("Role", "VC Roster Sync"))
