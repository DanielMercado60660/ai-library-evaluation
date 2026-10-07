# Circulation Service

Handles checkouts, returns, holds, and fines for Hanno Memorial Library.

## Endpoints

- `GET /patrons/{patron_id}` - Get patron details
- `GET /patrons/{patron_id}/summary` - Get patron summary (checkouts, holds, fines)
- `POST /checkouts` - Check out an item
- `POST /checkouts/{id}/renew` - Renew a checkout
- `POST /returns` - Return an item
- `POST /holds` - Place a hold
- `DELETE /holds/{id}` - Cancel a hold
- `GET /patrons/{patron_id}/fines` - List patron fines
- `POST /fines/{id}/pay` - Pay a fine

## Running

```bash
uv run uvicorn circulation.main:app --reload --port 8002
```
