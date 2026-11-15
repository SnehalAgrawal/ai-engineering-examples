# API Reference

The REST API lets you read and change projects, tasks, and comments, and receive webhooks when tasks change. This reference covers version 2 of the API. Version 1 is deprecated; see Versioning and deprecation at the end of this page.

## Basics

All requests go to https://api.example.com/v2 over HTTPS. Plain HTTP requests are refused, not redirected. Request and response bodies are JSON, encoded as UTF-8, and requests with a body must send the header Content-Type: application/json.

Timestamps are strings in ISO 8601 format, always in UTC, such as 2026-03-14T09:30:00Z. Dates without a time, such as due dates, use the format YYYY-MM-DD. IDs are strings; don't assume a length or format.

The API is available on both plans. Everything you can do through the API is limited by the permissions of the member whose key you use.

## Authentication

Every request needs an API key, sent as a bearer token:

```
GET /v2/projects HTTP/1.1
Host: api.example.com
Authorization: Bearer YOUR_API_KEY
```

Create keys under Settings > Developer > API keys. A key has the same permissions as the member who created it, and works until it is revoked. If that member is suspended or removed, the key stops working. Each member can have up to 10 active keys.

A request without a key, or with a revoked key, receives 401 Unauthorized. A request for something the key's member isn't allowed to access receives 403 Forbidden, or 404 Not Found if the member can't see that the object exists at all.

Keep keys in a secret manager and never commit them to source code. If a key may have been exposed, revoke it immediately; revocation takes effect within one minute.

## Rate limits

Limits apply per API key, over a rolling window of one minute.

| Plan | Requests per minute, per key |
|---|---|
| Basic | 100 |
| Pro | 1,000 |

Every response includes three headers:

| Header | Meaning |
|---|---|
| X-RateLimit-Limit | The number of requests allowed per minute for this key |
| X-RateLimit-Remaining | How many requests are left in the current window |
| X-RateLimit-Reset | Seconds until the window has room for another request |

A request over the limit receives 429 Too Many Requests with a Retry-After header, which gives the number of seconds to wait. Requests that receive 429 still count toward the limit, so retrying immediately in a loop makes the wait longer. Creating more keys to get around the limit is against the terms of service.

## Pagination

Endpoints that return lists use cursor pagination. Pass limit to choose the page size: the default is 50, and the maximum is 200. A larger value is treated as 200, not rejected.

The response contains the items in data and, if there are more, a next_cursor value. Pass it as the cursor parameter to get the next page:

```
GET /v2/projects/p_8f2k/tasks?limit=100&cursor=c_19x7
```

When next_cursor is null, you have reached the last page. Cursors expire 24 hours after they are issued; a request with an expired cursor receives 400 with the error code cursor_expired, and you have to start again from the first page. Items created while you page through a list may or may not be included.

## Errors

Errors use standard HTTP status codes, and the body always has the same shape:

```
{
  "error": {
    "code": "validation_failed",
    "message": "title must not be empty",
    "request_id": "req_4t7hq2"
  }
}
```

Include the request_id when you contact support about a failed request.

| Status | Code | Meaning |
|---|---|---|
| 400 | invalid_json | The body isn't valid JSON |
| 400 | cursor_expired | The pagination cursor is more than 24 hours old |
| 401 | unauthorized | The API key is missing, wrong, or revoked |
| 403 | forbidden | The key's member isn't allowed to do this, or the request came from outside the IP allowlist |
| 404 | not_found | The object doesn't exist, or the key's member can't see it |
| 409 | conflict | The object was changed by someone else; fetch it again and retry |
| 409 | idempotency_mismatch | The idempotency key was already used with a different body |
| 422 | validation_failed | A field is missing or has an invalid value; message says which |
| 423 | organization_read_only | The organization is read-only, for example after a failed payment |
| 429 | rate_limited | Too many requests; wait for the time in Retry-After |
| 500 | internal_error | Something went wrong on our side; retry later |
| 503 | maintenance | Scheduled maintenance; retry after the time in Retry-After |

Requests that fail with 500 or 503 can be retried safely if they use an idempotency key, or if they are GET requests.

## Idempotency

Network failures make it impossible to know whether a POST request was processed. To retry safely, send an Idempotency-Key header with a unique value, such as a UUID, on every POST request. If a request with the same key and the same body arrives again within 24 hours, the API returns the original response instead of creating a second object. Reusing a key with a different body receives 409 with the code idempotency_mismatch.

PATCH and DELETE requests are idempotent by design and ignore the header.

## Projects

| Method and path | Description |
|---|---|
| GET /v2/projects | List the projects the key's member belongs to |
| POST /v2/projects | Create a project |
| GET /v2/projects/{project_id} | Get one project |
| PATCH /v2/projects/{project_id} | Change a project's name, description, or archived state |
| DELETE /v2/projects/{project_id} | Move a project to Trash |

A project has an id, a name of up to 100 characters, a description, an archived flag, and created_at and updated_at timestamps. Creating a project on the Basic plan when 3 projects are already active receives 422 with a message about the project limit. Deleting a project moves it to Trash, where it can be restored in the app for 30 days; the API can't restore it.

## Tasks

| Method and path | Description |
|---|---|
| GET /v2/projects/{project_id}/tasks | List a project's tasks |
| POST /v2/projects/{project_id}/tasks | Create a task |
| GET /v2/tasks/{task_id} | Get one task |
| PATCH /v2/tasks/{task_id} | Change a task |
| DELETE /v2/tasks/{task_id} | Move a task to Trash |

Task fields:

| Field | Type | Notes |
|---|---|---|
| title | string | Required, 1 to 500 characters |
| description | string | Up to 50,000 characters, in Markdown |
| status | string | The name of one of the project's statuses |
| assignee | string or null | The email address of a member or a guest of the project |
| due_date | string or null | YYYY-MM-DD |
| labels | array of strings | Names of existing labels in the project |
| parent_id | string or null | Set to make the task a subtask of another task in the same project |

When listing tasks, filter with the query parameters status, assignee, label, and due_before. Combine them to narrow the results; each one can be given only once. Completed subtasks are included unless you pass include_completed=false.

To create a task:

```
POST /v2/projects/p_8f2k/tasks HTTP/1.1
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
Idempotency-Key: 3f1c9a52-7d4e-4b8a-9c61-0e2f5d8b7a13

{"title": "Draft the launch email", "assignee": "dana@example.com", "due_date": "2026-03-20"}
```

A successful request receives 201 Created with the full task in the body. Assigning a task to someone who isn't a member or guest of the project receives 422.

## Comments

| Method and path | Description |
|---|---|
| GET /v2/tasks/{task_id}/comments | List a task's comments, oldest first |
| POST /v2/tasks/{task_id}/comments | Add a comment |
| DELETE /v2/comments/{comment_id} | Delete a comment |

A comment has a body of up to 10,000 characters in Markdown. Mentions in comments created through the API don't send notifications. A key can delete only comments created by its own member, within 24 hours of posting, as in the app.

## Webhooks

Webhooks send an HTTP POST request to your URL when something happens in the organization. Configure them under Settings > Developer > Webhooks; each organization can have up to 20 webhooks. Webhook URLs must use HTTPS.

### Events

| Event | Sent when |
|---|---|
| task.created | A task is created, including by import |
| task.updated | Any field of a task changes |
| task.completed | A task moves to a status in the Done group |
| task.deleted | A task is moved to Trash |
| comment.created | A comment is added to a task |

The body contains the event type, a delivery ID, the time of the event, and the full object after the change.

### Verifying a webhook

Every delivery is signed, so your endpoint can check that it came from us and wasn't replayed. Each request has two headers: X-Signature and X-Timestamp. To verify a delivery:

1. Read the raw request body, exactly as received, before parsing it as JSON.
2. Join the X-Timestamp value, a period, and the raw body into one string.
3. Compute an HMAC-SHA256 of that string, using your webhook secret as the key, and encode it as lowercase hexadecimal.
4. Compare the result with the X-Signature header using a constant-time comparison.
5. Check that X-Timestamp is no more than 5 minutes old. Reject the delivery if it is older, even when the signature matches.

Find the webhook secret on the webhook's settings page. Rotating the secret takes effect immediately for new deliveries.

### Responses and retries

Your endpoint must respond with a 2xx status within 10 seconds. Anything else, including a redirect, counts as a failure. A failed delivery is retried up to 5 times:

| Retry | Time after the first attempt |
|---|---|
| 1 | 1 minute |
| 2 | 10 minutes |
| 3 | 1 hour |
| 4 | 6 hours |
| 5 | 24 hours |

If the last retry fails, the webhook is paused and the Owner is notified by email. Resume it from its settings page; deliveries that failed while it was paused are not sent again. Deliveries can arrive more than once and out of order, so use the delivery ID to ignore duplicates.

## Versioning and deprecation

The version is part of the path. Changes that could break existing clients, such as removing a field or changing its type, are made only in a new version. Adding fields, endpoints, or event types isn't considered breaking, so clients should ignore fields they don't know.

When an endpoint or version is deprecated, its responses include a Deprecation header, and a Sunset header with the date it will stop working. A deprecated version keeps working for at least 6 months after the announcement.

Version 1 was deprecated on 2026-06-01 and will stop working on 2027-03-31. Version 1 used offset pagination with page and per_page parameters, and its webhooks were signed without a timestamp. Clients that still use version 1 should move to cursor pagination and the timestamp check described above.
