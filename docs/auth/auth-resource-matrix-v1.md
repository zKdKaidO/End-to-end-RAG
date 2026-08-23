# Auth Resource Matrix V1

| Resource/action | Anonymous | USER | ADMIN |
|---|---:|---:|---:|
| Login | Allow | Allow | Allow |
| Product Documents/Ask/History | 401 | Own private + Global | Own private + Global |
| Private upload | 401 | Allow | Allow |
| Global upload/access mutation | 401 | 403 | Allow |
| Another user's private document/chunk/job | 401 | 404 | 404 unless independently granted |
| Another user's chat/history | 401 | 404 | 404 |
| Debug API | 401 | 403 | Allow only when Debug flag enabled |
| Evaluation API | 401 | 403 | Allow only when Evaluation flag enabled |
| User provisioning/status | 401 | 403 | Allow |
| Own password/account lifecycle | 401 | Allow | Allow |

Frontend navigation is UX only. Backend dependencies are authoritative. Historic citation snapshots remain readable by the owning chat user after current access is revoked, while current-source document/chunk lookup is reauthorized and returns 404.
