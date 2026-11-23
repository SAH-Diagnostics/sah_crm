# Copyright (c) 2026, SAH Diagnostics and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class VCRosterShift(Document):
	@property
	def sub_heading(self):
		return self.vc_reference_id or self.name
