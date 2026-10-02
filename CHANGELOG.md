# Portfolio preparation changes

- Moved database configuration and the session secret into a local `.env`.
- Disabled debug mode by default; retained localhost binding.
- Replaced the shared hard-coded login password with salted password hashes and an interactive setup script.
- Added CSRF protection and changed logout to POST.
- Restricted trip selection and confirmation reports to the signed-in owner.
- Added valid date parsing, positive finite monetary values, length checks, and precise decimal hotel totals.
- Kept booking and flight/hotel inserts in one transaction; rollback on request failure.
- Implemented the previously missing destination visa-information lookup.
- Changed “Search” to “Save Booking” to reflect the actual record-entry workflow.
- Replaced personal sample accounts and immigration claims with fictional accounts and explicitly illustrative visa text.
- Removed the automatic database drop; setup now creates an independent `TravelEaseDemo` database.
- Documented the actual ten-table schema, setup, contribution, and project limitations.

The original academic implementation is the basis of this portfolio copy. No real reservations or live search capabilities were added.
