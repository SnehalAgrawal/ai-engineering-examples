# Release Notes

New releases are listed first. Web app changes reach every organization on the release date; the mobile apps follow within a week, after app store review.

## Version 6.4 (2026-10-27)

### New

- Add a second signing certificate for single sign-on under Settings > Security > SSO > Certificates. Both certificates are accepted until you remove one, so you can rotate certificates without downtime.
- Owners and Admins now get an email 30 days and 7 days before an SSO certificate expires.

### Fixed

- Reminders set for the last day of a month were sometimes sent a day early in time zones ahead of UTC.
- The board view no longer jumps back to the top after a task is dragged to another column.

## Version 6.3 (2026-10-06)

### Changed

- The limit on custom statuses was raised from 6 to 10 per project.
- Search results now show which comment matched, instead of only the task.

### Fixed

- Exports of projects with more than 5,000 tasks no longer time out.
- Guests could see the names of labels from projects they don't belong to in the label filter. They can now see only their own projects' labels.

## Version 6.2 (2026-09-15)

### New

- IP allowlist for Pro organizations. Admins can limit sign-ins and API requests to up to 50 IP address ranges. The Owner is exempt.
- Former members can be anonymized, which replaces their name with "Former member" in every project.

### Changed

- The maximum page size in the API was raised from 100 to 200.

## Version 6.1 (2026-08-18)

### New

- SCIM provisioning for Pro organizations that use single sign-on. Your identity provider can now create, update, and deactivate members automatically.

### Changed

- Audit log events are now kept for one year, up from 90 days. Events from before this release that were older than 90 days had already been deleted and can't be recovered.
- One audit log export can now cover up to 90 days, up from 31.

## Version 6.0 (2026-07-07)

### New

- Admins can set how long members stay signed in, from 1 to 90 days. The default stays at 30 days.
- Sign out all members, for use after a suspected breach.

### Fixed

- Due dates entered on mobile were saved in the device's time zone instead of the profile's time zone.

## Version 5.9 (2026-06-01)

### New

- Version 2 of the API. It uses cursor pagination instead of page numbers, signs webhooks with a timestamp to prevent replays, and supports idempotency keys on POST requests.
- Webhooks for comments: comment.created.

### Changed

- Version 1 of the API is deprecated. It will keep working until 2027-03-31.
- Each organization can now have up to 20 webhooks, up from 10.
- Failed webhook deliveries are now retried up to 5 times over 24 hours, instead of 3 times over 1 hour.

## Version 5.8 (2026-05-12)

### Changed

- The maximum file size on the Pro plan was raised from 1 GB to 2 GB.
- Images in comments are now shown as previews.

### Fixed

- Importing a CSV file with a byte order mark no longer adds a stray character to the first column name.

## Version 5.7 (2026-04-14)

### New

- Allowed email domains: people with a verified address on one of your domains can join the organization without an invitation.

### Changed

- The member limit on the Basic plan now includes pending invitations, so the limit can't be exceeded by inviting people first and accepting later.

## Version 5.6 (2026-03-10)

### New

- Members can be suspended instead of removed, for example during long leave. Suspended members keep their role and their assignments, but can't sign in.

### Fixed

- Recurring tasks set to repeat on the 31st now repeat on the last day of shorter months, instead of skipping them.

## Version 5.5 (2026-02-09)

### New

- The app is now available in Spanish, in addition to English, German, and French.
- Recurring tasks can repeat on a custom schedule, such as every second Tuesday.

## Version 5.4 (2026-01-12)

### Changed

- Organization web addresses can now be changed once every 30 days, instead of once only. Old addresses redirect for 90 days.

### Removed

- SMS codes for two-factor authentication are no longer accepted. Members who still used SMS codes were asked to switch to an authenticator app by 2026-01-31; after that date, they were asked to set up an authenticator app at their next sign-in.

## Version 5.3 (2025-12-01)

### New

- Admins can require two-factor authentication for all members. Members get 3 days to set it up.

### Changed

- Downgrading to Basic now checks every limit on the Change plan page and lists what still needs to be done, instead of failing with a single error.

## Version 5.2 (2025-11-03)

### New

- Bank transfer payments for annual plans, on request through live chat.

### Changed

- Exports are now emailed to the Owner as a download link, valid for 7 days, instead of as an attachment.
