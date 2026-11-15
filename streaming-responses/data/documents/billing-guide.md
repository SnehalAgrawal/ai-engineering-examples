# Billing and Plans Guide

This guide explains the two plans, how billing works, and what happens when you change plans, miss a payment, or cancel. Only the Owner can change the plan, the billing frequency, or the payment method. Admins and members can see which plan the organization is on, but not its invoices.

## Plans at a glance

Prices are per organization, not per member, and don't include tax.

| | Basic | Pro |
|---|---|---|
| Monthly price | $10 | $25 |
| Annual price | $100 | $250 |
| Active projects | 3 | Unlimited |
| Members | 5 | Unlimited |
| Guests per project | 10 | Unlimited |
| Maximum file size | 100 MB | 2 GB |
| Storage per organization | 10 GB | 1 TB |
| API requests per minute, per key | 100 | 1,000 |
| Reports | No | Yes |
| Single sign-on and SCIM | No | Yes |
| Audit log | No | Yes |
| IP allowlist | No | Yes |
| Support | Live chat | Live chat, with priority |

Archived projects don't count toward the project limit, and guests don't count toward the member limit.

## The Basic plan

The Basic plan is meant for small teams that work on a few projects at a time. It includes up to 3 active projects and 5 members, and each project can have up to 10 guests. Pending invitations count toward the member limit.

Everything in the app works on this plan except the features marked Pro in the table above. The API is fully available, with a lower rate limit. When the organization reaches its storage limit, new uploads are blocked until files are deleted or the plan is upgraded; nothing that is already stored is removed.

## The Pro plan

The Pro plan removes the limits on projects, members, and guests, and adds the features larger organizations need: reports, single sign-on, SCIM provisioning, the audit log, and the IP allowlist. Support conversations from Pro organizations are answered first. Pro organizations can also request the latest independent security audit report through live chat.

## The free trial

Every new organization starts with a 14-day trial of the Pro plan, without a credit card. The trial includes every Pro feature. Each organization can start one trial; creating another organization to extend a trial isn't allowed.

To keep Pro after the trial, add a payment method and choose Pro under Settings > Billing > Change plan before the trial ends. If you do nothing, the organization moves to the Basic plan. No data is deleted, but projects beyond the third become read-only until you upgrade or archive them, and Pro settings such as single sign-on and the IP allowlist are switched off.

## Billing frequency and billing dates

### Monthly billing

A monthly plan is charged on the same day of each month as the first payment. If that day doesn't exist in a month, for example the 31st, the charge is made on the last day of that month.

### Annual billing

An annual plan costs the same as 10 months of monthly billing. It renews automatically on the anniversary of the purchase date, and the Owner receives a reminder email 14 days before each renewal. Switch between monthly and annual billing under Settings > Billing > Billing frequency. When you switch from monthly to annual, the unused part of the current month is credited against the first annual payment. When you switch from annual to monthly, the change takes effect when the annual period ends.

## Changing plans

### Upgrading

Upgrades take effect immediately. You are charged a prorated amount for the rest of the current billing period, and the next regular charge is at the new price.

For example, an organization on monthly Basic, billed on the 1st, upgrades to Pro on the 16th of a 30-day month. Half the period is left, so the upgrade costs half the difference between the two prices: (25 - 10) / 2 = $7.50. On the 1st of the next month, it is charged $25.

### Downgrading

Downgrades take effect at the start of the next billing period, so you keep Pro features until then. On an annual plan, a downgrade takes effect when the annual period ends. There is no refund for the rest of the current period.

Before you can downgrade to Basic, the organization has to fit within its limits:

1. Archive projects until no more than 3 are active.
2. Remove or suspend members until no more than 5 remain, including pending invitations.
3. Remove guests from any project that has more than 10.
4. Delete files until storage is under 10 GB. Files larger than 100 MB that are already stored are kept, but new uploads must be under 100 MB.
5. Turn off single sign-on, SCIM, and the IP allowlist. The audit log is kept, but it stops recording new events and becomes visible again only if you upgrade.

The Change plan page checks each of these and lists anything that still needs to be done.

## Taxes

Prices don't include tax. For organizations in the European Union, VAT is added at the rate of your country, unless you enter a valid VAT number under Settings > Billing > Invoice details; then the reverse-charge mechanism applies and no VAT is added. The VAT number is checked when you save it, and an invalid number is rejected. Organizations elsewhere are charged the sales tax that applies at the billing address, if any. Tax is shown as a separate line on every invoice.

A VAT number added after a payment doesn't change that payment's invoice. Past invoices can't be edited, but billing@example.com can reissue an invoice from the last 90 days with corrected details.

## Invoices

An invoice is emailed to the Owner after each payment, and every invoice can be downloaded as a PDF under Settings > Billing > Invoices. To send invoices to someone else as well, such as your finance team, add their address as a billing contact under Settings > Billing > Invoice details. You can add up to 3 billing contacts. Company name, address, and VAT number changes apply to invoices issued after you save them.

## Payment methods

We accept Visa, Mastercard, and American Express. Organizations on an annual plan can also pay by bank transfer against an invoice. Ask for this through live chat before your first annual payment. A bank transfer invoice is due within 30 days of its date; if it isn't paid by then, the organization becomes read-only, as with a failed card payment. PayPal and cryptocurrency are not accepted.

Change the card on file under Settings > Billing > Payment method. The new card is used for the next payment, and any payment that is currently overdue is retried on the new card straight away.

## Failed payments

If a card payment fails, we retry it on this schedule, and email the Owner after each failed attempt:

| Attempt | When |
|---|---|
| First retry | 1 day after the failed payment |
| Second retry | 3 days after the failed payment |
| Third retry | 7 days after the failed payment |

If the third retry also fails, the organization becomes read-only until the payment method is updated. While an organization is read-only, members can sign in and view everything, but nobody can create or edit anything, and the API accepts only read requests. Nothing is deleted. Updating the card retries the overdue payment immediately, and the organization becomes writable again as soon as the payment succeeds.

## Refunds

You can request a refund within 30 days of purchase, through live chat. A purchase is the first payment of a plan or an annual renewal. Approved refunds go back to the original payment method.

Prorated upgrade charges and monthly renewals after the first month are not refunded. A refunded annual plan is cancelled when the refund is approved, and the organization moves to the Basic plan.

## Cancelling

Cancel under Settings > Billing > Cancel. The plan stays active until the end of the current billing period, and then the organization becomes read-only.

After the plan ends, your data is kept for 90 days. During that time you can sign in, export your data, and reactivate the subscription from Settings > Billing, and everything will be exactly as you left it. After 90 days, all projects, tasks, and files are permanently deleted. If you want your data deleted sooner, delete the organization instead; see the Data Processing Policy for how long deletion takes, including backups.
