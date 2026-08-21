# Legal Corpus V2 PDF Preflight

Generated: 2026-08-19T12:20:16.078786+00:00

Input directory: `A:\RAG\evaluation\corpus\input`

PDFs discovered: **5**  
READY: **3**  
Excluded: **2**

No OCR was used. Text checks use native PDF extraction only.

| File | Bytes | Pages | Encrypted | Extracted chars | Text pages | Classification |
|---|---:|---:|---|---:|---:|---|
| 104.2026.TT-BQP.pdf | 337077 | 5 | False | 4 | 0 | **TEXT_TOO_SPARSE_OR_SCAN_LIKE** |
| Nghị-định-273-2026-NĐ-CP.pdf | 6885589 | 67 | False | 66 | 0 | **TEXT_TOO_SPARSE_OR_SCAN_LIKE** |
| Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf | 1469636 | 18 | False | 33196 | 18 | **READY** |
| Thông tư 40.2026.TT-NHNN.pdf | 504579 | 21 | False | 33886 | 21 | **READY** |
| VBHN 10.2026.pdf | 984068 | 66 | False | 157065 | 66 | **READY** |

## File hashes

- `104.2026.TT-BQP.pdf`: `fef9526df3f657025bc418ea82e49af0698bd1480f4e7d4b52a3ebea5ae92134`
- `Nghị-định-273-2026-NĐ-CP.pdf`: `2c1f68426dd84536917975fa2cc0e4cc502ab7791edc9a0a4e115ebc1c61c5bc`
- `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`: `1700c0adc6938fe21bbfa2be46c6dd6eeaeec3fe6ed49c88da0a598f4639c0ba`
- `Thông tư 40.2026.TT-NHNN.pdf`: `80286aaa15cdd95f3ce554ee12d5a5c9c94303953093df5057561c9fea72dfb0`
- `VBHN 10.2026.pdf`: `80855c15b8f935a271e9bdbac0e74b009d0c036d29212f391da884e9431d0e58`

## Classification rule

A readable, unlocked PDF is READY when native extraction yields at least max(500 characters, 30 characters per page) and at least half that threshold is alphabetic.
