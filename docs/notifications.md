# Notifications

Bookarr supports push notifications through [Pushover](https://pushover.net/). Notifications are optional and disabled by default.

## Setting up Pushover

### Step 1: Create a Pushover account

Sign up at [pushover.net](https://pushover.net/). Install the Pushover app on your phone (iOS or Android) or desktop.

### Step 2: Create an application

1. Go to [pushover.net/apps/build](https://pushover.net/apps/build).
2. Enter a name (for example, "Bookarr").
3. Optionally upload an icon.
4. Click **Create Application**.
5. Copy the **API Token/Key** shown on the next page.

### Step 3: Find your user key

Your user key is shown on your [Pushover dashboard](https://pushover.net/) after logging in. It is a 30-character string.

### Step 4: Configure in Bookarr

1. Open Bookarr and navigate to **Settings**.
2. In the **Notifications (Pushover)** section, enter your **App Token** and **User Key**.
3. Click **Save**.

## When notifications are sent

Bookarr sends a Pushover notification when:

- A book release is grabbed (sent to a download client).
- A download completes successfully.

Each notification includes the book title and relevant details.

## Disabling notifications

To disable notifications, clear the **App Token** and **User Key** fields in Settings and save. If either field is empty, Bookarr skips sending notifications silently.

## Troubleshooting

| Problem | Solution |
|---|---|
| No notifications received | Verify both App Token and User Key are correct in Settings. Check `bookarr.log` for `[Pushover] Error` messages. |
| "invalid token" error in logs | The App Token is incorrect or the application was deleted on pushover.net. Create a new application. |
| "invalid user" error in logs | The User Key is incorrect. Copy it again from your Pushover dashboard. |
| Notifications delayed | Pushover delivery is typically near-instant. Delays may be on Pushover's end. Check [status.pushover.net](https://status.pushover.net/). |
