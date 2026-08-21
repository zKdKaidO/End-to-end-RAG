import uuid, urllib.request, json
doc_id = "1efc75bf-e911-4f1e-963f-14397dee69cb"

resp = urllib.request.urlopen(f'http://localhost:8000/documents/{doc_id}/indexes')
data = json.loads(resp.read())
print(json.dumps(data, indent=2))
