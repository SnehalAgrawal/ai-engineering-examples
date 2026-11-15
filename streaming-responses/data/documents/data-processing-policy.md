# Data Processing Policy

Last updated: 2026-09-01

This policy describes how we process the data that customers store in the app: what we collect, where it is stored, how long it is kept, who else processes it, and what we do if something goes wrong. It forms part of the terms of service. Where this policy and the terms of service conflict on a question about personal data, this policy applies.

## 1. Definitions

In this policy:

- "Customer" means the organization that has agreed to the terms of service, acting through its Owner.
- "Customer data" means everything the customer and its members, guests, and integrations store in the app: projects, tasks, comments, files, and the names and email addresses of the people who use it.
- "Personal data" has the meaning given in the EU General Data Protection Regulation (GDPR).
- "Subprocessor" means a company we engage to process customer data on our behalf.
- "Business day" means a day from Monday to Friday, excluding public holidays in Germany.

## 2. Roles

For customer data, the customer is the controller and we are the processor. We process customer data only to provide the app and its support, and only on the customer's documented instructions. The terms of service, the customer's settings, and requests to support count as such instructions.

For account and billing information that we need to run our own business, such as the Owner's contact details and payment records, we are the controller.

## 3. Categories of data

We process:

1. Customer data, as defined in section 1.
2. Account data: names, email addresses, profile photos, time zones, and sign-in records of members and guests.
3. Usage data: which features are used and how often, collected without the content of tasks, comments, or files.
4. Billing data: the billing address, VAT number, invoices, and the last four digits and expiry date of the card on file. Full card numbers are handled by our payment processor and never stored by us.

We don't use customer data to train machine learning models, and we don't sell any data.

## 4. Where data is stored

### 4.1 Data regions

Customer data and account data are stored in the data region chosen when the organization was created: the European Union (Frankfurt, Germany) or the United States (Virginia). The region can't be changed afterwards.

### 4.2 Backups

Backups are encrypted and stored in the same region as the data they contain. They are made every 6 hours.

### 4.3 Access from other countries

Support staff may access customer data from outside the data region to resolve a support request, with the customer's permission, as described in section 8.3. For transfers of personal data out of the European Union, we rely on the European Commission's standard contractual clauses.

## 5. Retention

### 5.1 While the subscription is active

Customer data is kept for as long as the customer keeps it in the app. Deleted tasks, files, and projects stay in Trash for 30 days and are then permanently deleted.

### 5.2 After the subscription ends

When a subscription ends, for example after cancellation, customer data is kept for 90 days so that the customer can export it or reactivate the subscription. After 90 days, it is permanently deleted from the app.

### 5.3 Backups

Each backup is kept for 35 days and then deleted. Data deleted from the app therefore remains in backups for up to 35 days after the deletion. Backups are used only to recover from failures of our systems, not to restore individual items for customers.

### 5.4 Logs

Server logs, which contain IP addresses and request paths but not the content of customer data, are kept for 30 days. Audit log events are kept for one year, as described in the Administrator Guide.

### 5.5 Support conversations

Live chat conversations and support emails are kept for 2 years after the conversation ends, so that we can refer to earlier requests. A customer can ask for its support conversations to be deleted sooner.

### 5.6 Billing records

Invoices and payment records are kept for 10 years, because tax law requires it. This applies even after the organization is deleted.

## 6. Deletion

### 6.1 Deleting an organization

When the Owner deletes the organization, all customer data is deleted from the app within 24 hours. Copies in backups are not deleted early; they expire as described in section 5.3. Billing records are kept as described in section 5.6.

### 6.2 Deleting an individual's data

A member can't delete their own account while they belong to an organization; they must be removed first. When a member is removed, their name stays on the comments and tasks they created, because that work belongs to the customer. To remove a person's name from the customer data, an Admin can anonymize them under Settings > Members > Former members, which replaces the name with "Former member" everywhere. Anonymizing can't be undone.

### 6.3 Confirmation

On request, we confirm in writing that an organization's data has been deleted. We send the confirmation within 10 business days of the request, and not before the backups have expired.

## 7. Subprocessors

We use the following categories of subprocessors. The current list of companies, with their locations, is available on request through live chat.

| Category | Purpose | Location |
|---|---|---|
| Cloud infrastructure | Hosting the app, storing data and backups | The customer's data region |
| Email delivery | Sending notifications, invitations, and invoices | European Union and United States |
| Payment processing | Charging cards and storing card details | European Union and United States |
| Live chat | Support conversations | European Union |

We notify the Owner by email at least 30 days before we add or replace a subprocessor. The customer can object within 14 days of the notice, giving reasons. If we can't resolve the objection, the customer can cancel the affected subscription and receive a refund for the unused part of the current billing period, even if the 30-day refund period in the Billing and Plans Guide has passed.

## 8. Security

### 8.1 Technical measures

Data is encrypted in transit with TLS 1.2 or later, and at rest with AES-256. Backups are encrypted with separate keys. Production systems can only be reached by on-call engineers through a hardware-key protected connection.

### 8.2 Audits

An independent auditor reviews our security controls every year. Pro customers can request the latest audit report through live chat. Customers can't carry out their own on-site audits; the audit report is provided instead.

### 8.3 Access by our staff

Our staff can access customer data only to resolve a support request, and only with permission from the Owner or an Admin of the organization. Permission is given in the support conversation and lasts for 7 days or until the request is closed, whichever comes first. Every access is logged and appears in the customer's audit log.

## 9. Personal data breaches

If we become aware of a breach of security that affects customer data, we notify the Owner without undue delay, and in any case within 48 hours. The notification describes, as far as we know at the time:

1. what happened and when;
2. which categories of data and roughly how many people are affected;
3. the likely consequences;
4. what we have done and will do to contain the breach;
5. a contact person for further information.

When information isn't available yet, we send it as soon as it is, without waiting for a complete report. As the controller, the customer decides whether to notify the authorities and the people affected; we help with the information we have.

## 10. Requests from individuals

If a person asks us directly to access, correct, or delete their personal data in customer data, we forward the request to the customer within 5 business days and don't respond to it ourselves. We help the customer respond to such requests, for example by exporting a person's data, within 10 business days of the customer's request.

## 11. Changes to this policy

We may change this policy to reflect changes in the app, our subprocessors, or the law. We email the Owner at least 30 days before a change takes effect, unless the law requires a change sooner. The current version and the date of the last change are always shown at the top of this policy.
