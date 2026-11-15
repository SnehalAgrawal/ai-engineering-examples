# Administrator Guide

This guide is for the people who run an organization: the Owner and the Admins. It covers organization settings, roles, members, single sign-on, user provisioning, the audit log, and security settings. Everyday work with projects and tasks is covered in the help center.

Most settings in this guide are under Settings in the left sidebar. If you don't see an option described here, check your role: many settings are visible only to the Owner or to Admins, and some are available only on the Pro plan.

## 1. Organization settings

### 1.1 Name and address

The organization name appears in the sidebar, in invitation emails, and on invoices. Change it under Settings > Organization > General. Every organization also has a web address of the form app.example.com/your-name. The address can be changed once every 30 days. Old links keep working for 90 days after a change and then stop redirecting, so update bookmarks and integrations that use the old address.

### 1.2 Defaults for new members

Admins can set a default language and a default time zone for the organization under Settings > Organization > Defaults. These apply only to members who join after the change, and every member can still override both in their own profile. The available languages are English, German, French, and Spanish.

### 1.3 Data region

The data region is chosen when the organization is created: the European Union (Frankfurt) or the United States (Virginia). It is shown under Settings > Organization > General and can't be changed. To move to the other region, create a new organization there, export your data from the old one, and import it into the new one. Comments, attachments, and the audit log are not included in an import, so keep the export of the old organization if you need them.

## 2. Roles and permissions

Every member of an organization has exactly one role. Guests are not members: they are invited to individual projects and see nothing else.

| Capability | Owner | Admin | Member | Guest |
|---|---|---|---|---|
| Create projects | Yes | Yes | Yes | No |
| Invite members to the organization | Yes | Yes | No | No |
| Invite guests to a project | Yes | Yes | Yes | No |
| Remove members | Yes | Yes | No | No |
| Change project settings | Yes | Yes | Only in projects they created | No |
| Restore a deleted project | Yes | Yes | No | No |
| View the audit log | Yes | Yes | No | No |
| Configure SSO and SCIM | Yes | Yes | No | No |
| Manage billing and plans | Yes | No | No | No |
| Transfer ownership | Yes | No | No | No |
| Delete the organization | Yes | No | No | No |

Each organization has exactly one Owner. Change a member's role under Settings > Members by opening the member and choosing a new role. Role changes take effect immediately; the member doesn't need to sign in again.

Custom roles are not supported. If you need finer control over who sees what, use project membership: members see only the projects they belong to, while Admins can open every project in the organization.

## 3. Managing members

### 3.1 Inviting members

Invite members from Settings > Members > Invite. You can paste up to 50 email addresses at once and choose one role for all of them. Invitations expire after 7 days and can be resent from the same page. On the Basic plan, pending invitations count toward the limit of 5 members, so a sixth invitation can't be sent while five members and invitations exist.

To let people join without an invitation, turn on Allowed email domains under Settings > Members > Joining. Anyone who signs up with a verified email address on one of those domains can join as a Member. Admins are notified by email each time someone joins this way.

### 3.2 Suspending a member

Suspending is for people who will be away for a while, such as on long leave. A suspended member can't sign in, and their API keys stop working, but they keep their role, their project memberships, and their task assignments. Suspended members still count toward the member limit. Suspend or reactivate a member under Settings > Members by opening the member's menu.

### 3.3 Removing a member

Removing a member is permanent. The member loses access immediately and is signed out of every device. Their tasks become unassigned, the work they created stays in its projects, and their comments keep their name. Their API keys stop working, and any webhooks they created keep running. To give someone access again later, invite them again; their old assignments are not restored.

## 4. Single sign-on

### 4.1 Requirements

Single sign-on (SSO) is available on the Pro plan and works with any identity provider that supports SAML 2.0, such as Okta or Microsoft Entra ID. Only the Owner and Admins can configure it. You need administrator access to your identity provider, and every member who will use SSO must exist there with the same email address they use for this app.

### 4.2 Setting up SSO

Set up SSO in this order. Don't enforce it until the test in step 6 succeeds.

1. Go to Settings > Security > SSO and select Set up SAML. The page shows two values you will need: the Assertion Consumer Service (ACS) URL, https://app.example.com/sso/acs, and your organization's Entity ID.
2. In your identity provider, create a new SAML application. Paste the ACS URL and the Entity ID from step 1.
3. Configure the identity provider to send the email address as the NameID, in email format. Optionally, map the attributes firstName and lastName, which are used to fill in new members' names.
4. Assign the application to the people and groups who should be able to sign in.
5. Copy the identity provider's metadata URL and paste it into the Metadata URL field on the SSO page. Select Save.
6. Select Test connection. A new window signs you in through your identity provider with your own account. If the test fails, the window shows an error code; see section 4.5.
7. When the test succeeds, choose whether to enforce SSO. If you don't enforce it, members can sign in with either SSO or their password.
8. If you enforce SSO, members who haven't signed in through SSO yet get a grace period of 7 days, during which they can still use their password. After the grace period, password sign-in is turned off for them.

The Owner can always sign in with a password, even when SSO is enforced, so a misconfigured identity provider can't lock everyone out of the organization.

### 4.3 What changes for members

When SSO is enforced, members sign in through the identity provider, and their email address is managed there: they can't change it in their profile. Two-factor authentication settings in this app no longer apply to them; use your identity provider's own multi-factor authentication instead. Members who are signed in when you enforce SSO stay signed in until their session ends.

Guests are not affected by SSO. They keep signing in with a password, because they belong to other organizations.

### 4.4 Rotating the signing certificate

Identity providers sign their SAML responses with a certificate that expires, typically every one to three years. When your identity provider issues a new certificate, add it under Settings > Security > SSO > Certificates before the old one expires. Up to two certificates can be active at the same time, so you can add the new one, switch the identity provider over, and then remove the old one, without any downtime. The Owner and Admins receive an email 30 days and again 7 days before an active certificate expires.

If a certificate expires before it is replaced, SSO sign-in fails for everyone, and only the Owner can sign in, with a password.

### 4.5 Troubleshooting

| Error code | Meaning | What to do |
|---|---|---|
| SSO-101 | The response wasn't signed with an active certificate | Add the identity provider's current certificate (section 4.4) |
| SSO-102 | The response is older than 5 minutes | Check that the identity provider's clock is correct |
| SSO-103 | The email address doesn't match any member | Invite the person, or check the NameID format (step 3) |
| SSO-104 | The Entity ID doesn't match | Copy the Entity ID again from Settings > Security > SSO |
| SSO-105 | The person isn't assigned to the application | Assign them in the identity provider (step 4) |

If the problem continues, contact support through live chat with the error code and the time of the failed attempt.

## 5. User provisioning (SCIM)

With SCIM, your identity provider creates, updates, and removes members automatically, so you don't have to invite or remove people by hand. SCIM is available on the Pro plan and requires SSO to be set up first.

To connect SCIM:

1. Go to Settings > Security > SCIM and select Generate token. Copy the token; it is shown only once.
2. In your identity provider's SAML application, turn on SCIM provisioning. Use the base URL https://api.example.com/scim/v2 and the token from step 1.
3. Choose which provisioning actions to allow: create users, update user attributes, and deactivate users.
4. Assign a test user and check that they appear under Settings > Members within a few minutes.

SCIM tokens are valid for one year. The Owner and Admins are emailed 14 days before a token expires; generate a new token and update it in the identity provider before then. When a token expires, provisioning stops, but existing members are not affected.

When the identity provider deactivates a user, the member is removed from the organization within 5 minutes, with the same effects as removing them by hand (section 3.3). Members created through SCIM join with the Member role; change their role in this app if they need to be Admins. Groups from the identity provider are not synchronized.

## 6. The audit log

The audit log records security-relevant events in the organization: sign-ins, failed sign-ins, role changes, members joining and leaving, changes to SSO and SCIM, API keys being created or revoked, exports, and project deletions. It is available on the Pro plan, to the Owner and Admins, under Settings > Security > Audit log.

Each event shows the time, the person or API key that caused it, the IP address, and what changed. Events are kept for one year. Filter the log by person, event type, or date range, and export the filtered events as a CSV file. One export can cover at most 90 days; for a longer period, export it in parts.

Audit log entries can't be edited or deleted, not even by the Owner. Deleting the organization deletes its audit log along with everything else.

## 7. Security settings

### 7.1 Session length

By default, members stay signed in for 30 days on each device. Admins can change this to anywhere from 1 to 90 days under Settings > Security > Sessions. A shorter session length applies at each member's next sign-in; it doesn't sign anyone out immediately. To sign everyone out now, for example after a suspected breach, use Sign out all members on the same page. The person who uses it stays signed in.

### 7.2 Requiring two-factor authentication

Admins can require two-factor authentication for every member under Settings > Security > Two-factor. Members who haven't set it up are asked to do so at their next sign-in and have 3 days to complete it. After that, they can't open any project until they set it up. Only authenticator apps are supported; SMS codes are not. Members who sign in through enforced SSO are exempt, because their identity provider handles multi-factor authentication.

### 7.3 IP allowlist

On the Pro plan, Admins can limit sign-ins and API requests to a list of IP address ranges, under Settings > Security > IP allowlist. Enter up to 50 ranges in CIDR notation, such as 203.0.113.0/24. Requests from other addresses are refused with an error that names the allowlist. The Owner is exempt from the allowlist, so a wrong entry can't lock everyone out. Webhook deliveries are not affected, because they go from our servers to yours.

Before turning the allowlist on, check the address you are connecting from: the settings page shows it, and it warns you if your own address isn't in the list.

## 8. When the Owner leaves

Ownership can only be transferred by the current Owner, under Settings > Organization > Transfer ownership, and only to an existing Admin. After the transfer, the previous Owner becomes an Admin, and billing emails go to the new Owner.

If the Owner has left your company without transferring ownership, contact support through live chat. We will ask for written confirmation from someone authorized to act for your company, such as a director, on company letterhead. Ownership transfers through support usually take 3 to 5 business days.
