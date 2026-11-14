# LTSM Portal – JSON API contract (Task 3A)

All endpoints are under `/api`, send and receive JSON, and use the Flask session cookie for sign-in.
`POST` bodies must be sent with `Content-Type: application/json`.

**Errors** always look like `{"error": "Readable message", "fields": {"field_name": "message"}}` (`fields` may be empty).
Status codes: `400` invalid input, `401` not signed in (the front end redirects to `/login`), `403` wrong role, `409` conflict (duplicate, no stock, double booking), `415` body not JSON.

| Method & path | Who | Request | Success response |
| --- | --- | --- | --- |
| `POST /api/login` | anyone | `role` (teacher/learner/ltsm), `username` (email or student/staff no.), `password` | `{user:{id,name,role}, redirect}` |
| `POST /api/logout` | anyone | – | `{redirect}` |
| `POST /api/register` | anyone | `full_name, account_type (learner/teacher), school_id, email, password, confirm_password` | `201 {message}` |
| `GET /api/resources?q=&category=` | signed in | – | `{items:[{id,name,description,category,stock,unit,availability,tone}]}` |
| `POST /api/requests` | signed in | `resource_name, category, quantity (1-100), needed_by (YYYY-MM-DD, not past), purpose (10-500 chars)` | `201 {message,id}` |
| `GET /api/requests?status=` | signed in | – (own requests only) | `{items:[{id,name,category,submitted,quantity,status,update,tone}]}` |
| `GET /api/equipment` | signed in | – | `{items:[{id,name,stock}]}` |
| `POST /api/bookings` | signed in | `equipment_id, booking_date, start_time (HH:MM), end_time, room, purpose` | `201 {message}`; `409` if no unit is free in that slot |
| `GET /api/bookings` | signed in | – (own, upcoming) | `{items:[{id,equipment,date,start,end,room,status,tone}]}` |
| `GET /api/inventory?q=&category=` | ltsm | – | `{items:[{id,name,category,stock,reorder_level,status,tone}]}` |
| `POST /api/inventory` | ltsm | `item_name, category, quantity, reorder_level` | `201 {message}` |
| `GET /api/loans` | ltsm | – | `{items:[{id,borrower,item,quantity,due,status,tone}]}` |
| `POST /api/movements` | ltsm | `movement_type (issue/return), item_id, borrower_id, quantity, movement_date, due_date (issue only)` | `201 {message}`; `409` not enough stock / no matching loan |
| `GET /api/maintenance` | ltsm | – | `{items:[{id,item,issue,reported,status,priority,tone}], summary:{open,in_repair,resolved,out_of_service}}` |
| `POST /api/maintenance` | ltsm | `equipment, reported_by, priority (Low/Normal/High/Urgent), date, description (10-500 chars)` | `201 {message}` |

`tone` is one of `ok`, `warning`, `danger`, `blue` and only controls the badge colour.
