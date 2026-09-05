# NyayaGraph ? Qwen3-8B LLM Integration

> **Qwen3-8B is used as the reasoning and response-generation component only.
> It is not the source of truth for evidence.**
>
> The source of truth remains: PostgreSQL ? pgvector ? the encrypted evidence
> store ? case metadata ? the case graph ? the timeline ? audit records.

---

## 1. Why Qwen3-8B

| Criterion | Decision |
|---|---|
| Open-source / local | No case data leaves the deployment boundary |
| 8B parameter size | Fits on a single consumer GPU (? 8 GB VRAM) or CPU with acceptable latency |
| Instruction-following quality | Reliably follows JSON output schema and `/no-think` prompt instructions |
| Apache 2.0 licence | Compatible with the SIH 2026 deliverable |
| Ollama distribution | Single `ollama pull qwen3:8b`; no Python environment changes needed |

The model is provider-agnostic in the codebase.  Replacing it with Llama,
Mistral, Gemma, or a cloud API requires adding one file and one `elif` branch
in `factory.py` ? nothing else changes.

---

## 2. Architecture

```
User question
      ?
      ?
Authentication (Keycloak / dev_jwt)
      ?
      ?
Authorization  ? policy_engine.can_view_case()
      ?
      ?
AuthorizedCorpus.for_case()          ? ACL applied HERE, before retrieval
  policy_engine.can_view_document()
  classification_level ? clearance_level
      ?
      ?
HybridRetriever.retrieve()
  ??????????????????????
  ?   ?                ?
BM25 Phrase       pgvector cosine
keyword  match    (when embedding
scoring          provider enabled)
  ??????????????????????
      ?  top-k re-ranked by score
      ?
PromptBuilder.build_structured_context()
  Numbered [Source N] blocks with:
    Document ID ? Evidence ID ? Type ? Title
    Case ID ? Page ? Source Hash ? Text (HTML-escaped)
      ?
      ?
QwenOllamaProvider.generate()
  POST http://<OLLAMA_BASE_URL>/api/chat
  System prompt: NYAYAGRAPH_SYSTEM_PROMPT (evidence-grounded rules)
  User prompt:   structured context + question
  Options:       temperature=0.1, stop=["<think>","</think>"]
      ?
      ?
_parse_llm_output()
  JSON extraction with markdown-fence stripping
  Hallucinated document IDs ? claim demoted to UNSUPPORTED
  INSUFFICIENT_EVIDENCE status ? pass through
      ?
      ?
ClaimValidator.enforce()   ? faithfulness gate
  SUPPORTED + invalid/missing citations ? UNSUPPORTED
  PARTIALLY_SUPPORTED / CONFLICTING ? valid citations kept
  UNSUPPORTED / INSUFFICIENT_EVIDENCE ? pass through
      ?
      ?
overall_trust_status()     ? single top-level trust label
      ?
      ?
API response
  { answer, claims, sources, trustStatus, generationMode, disclaimer }
```

**Wrong architecture (never used in NyayaGraph):**

```
User ? Qwen ? Answer          ?
```

---

## 3. Provider abstraction

```
apps/api/app/ai/llm/
  __init__.py          re-exports LLMProvider, LLMRequest, LLMResponse,
                       LLMProviderError, get_llm_provider
  base.py              Abstract base ? generate(LLMRequest) ? LLMResponse
                                       health() ? dict
  qwen.py              QwenOllamaProvider   (Ollama /api/chat)
  openai_compat.py     OpenAICompatProvider (any /chat/completions endpoint)
  factory.py           get_llm_provider()   (lru_cache singleton)
```

To add a new provider:

1. Create `apps/api/app/ai/llm/myprovider.py` implementing `LLMProvider`.
2. Add an `elif provider == "myprovider":` branch in `factory.py`.
3. Add `LLM_PROVIDER=myprovider` to your `.env`.

---

## 4. Ollama installation

### macOS / Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows

Download and run the installer from <https://ollama.com/download>.

### Pull the model

```bash
ollama pull qwen3:8b
```

Disk space: approximately 5 GB.

### Verify

```bash
ollama run qwen3:8b "Reply with the single word: ready"
```

---

## 5. Environment variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `demo` | `ollama` ? `openai_compatible` ? `demo` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint. Inside Docker use `http://host.docker.internal:11434` |
| `LLM_MODEL` | `qwen3:8b` | Model tag served by Ollama |
| `LLM_TEMPERATURE` | `0.1` | Generation temperature (0.0?1.0) |
| `LLM_MAX_TOKENS` | `2048` | Maximum completion tokens |
| `LLM_BASE_URL` | _(empty)_ | Only used when `LLM_PROVIDER=openai_compatible` |
| `LLM_API_KEY` | _(empty)_ | Only used when `LLM_PROVIDER=openai_compatible` |

To activate Qwen3-8B, add to your `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen3:8b
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2048
```

---

## 6. API flow

### POST `/api/v1/ai/case/{case_number}/brief`

Returns a full case brief grounded in all authorised evidence.

### POST `/api/v1/ai/case/{case_number}/ask`

Body: `{ "question": "string" }`

Returns:

```json
{
  "answer": "The vehicle was reported near Gate 3 at approximately 21:20.",
  "status": "SUPPORTED",
  "trustStatus": "SUPPORTED",
  "claims": [
    {
      "claim": "...",
      "confidence": 1.0,
      "status": "SUPPORTED",
      "sources": [
        {
          "documentId": "DOC-002",
          "documentVersionId": "...",
          "documentTitle": "Witness Statement ? Witness-01",
          "page": 2,
          "chunkId": "...",
          "sourceHash": "sha256:..."
        }
      ]
    }
  ],
  "sources": [...],
  "disclaimer": "Evidence-grounded investigative support only. Not a determination of guilt or legal conclusion.",
  "generationMode": "GROUNDED_LLM"
}
```

### GET `/api/v1/health/llm`

```json
{
  "provider": "ollama",
  "model": "qwen3:8b",
  "status": "healthy"
}
```

---

## 7. RAG flow

```
1. AuthorizedCorpus.for_case(db, actor, case)
   ? applies policy_engine.can_view_document() for every document
   ? filters chunks by classification_level ? actor.clearance_level
   ? result: list[AuthorizedChunk]

2. HybridRetriever.retrieve(db, actor, case, query, mode="semantic")
   ? keyword overlap scoring (BM25-style)
   ? phrase match bonus
   ? pgvector cosine similarity (when embedding provider enabled)
   ? semantic expansion dictionary
   ? returns top-k RetrievalResult sorted by score

3. PromptBuilder.build_structured_context(chunks)
   ? HTML-escapes all evidence text
   ? sanitises control characters
   ? caps per-chunk length at 20 000 characters
   ? produces numbered [Source N] blocks

4. QwenOllamaProvider.generate(LLMRequest)
   ? system: NYAYAGRAPH_SYSTEM_PROMPT
   ? user: context + question
   ? Qwen3 /no-think mode (stop tokens strip chain-of-thought)
   ? timeout: 120 s

5. _parse_llm_output(raw, allowed_chunks)
   ? strips markdown fences
   ? extracts JSON substring if surrounded by text
   ? validates document IDs against authorised pool
   ? demotes hallucinated citations to UNSUPPORTED

6. ClaimValidator.enforce(claims, authorised_chunks)
   ? SUPPORTED + invalid citations ? UNSUPPORTED
   ? returns final validated claim list

7. overall_trust_status(claims) ? top-level label
```

---

## 8. Evidence context format

Each source block sent to Qwen:

```
[Source 1]
Document ID: DOC-002
Evidence ID: <chunk_id>
Document Type: Witness Statement
Document Title: Witness Statement ? Witness-01
Case ID: MH-PUNE-2026-00142
Page: 2
Source Hash: <sha256>
Text:
"The vehicle was observed near Gate 3 at approximately 21:20."
```

All text is HTML-escaped before injection.  The system prompt instructs the
model that evidence is untrusted data and it must never follow instructions
found inside it.

---

## 9. Citation validation

After generation, every claim is validated:

```
Qwen claim ? supporting_sources list
    ?
For each source:
    document_id in authorised_chunk_pool?
        No  ? drop citation, demote claim to UNSUPPORTED
        Yes ? resolve best matching chunk by page proximity
    ?
ClaimValidator.enforce()
    SUPPORTED + no valid citations ? UNSUPPORTED
    PARTIALLY_SUPPORTED / CONFLICTING ? strip invalid citations, keep valid
    UNSUPPORTED ? pass through (no citations expected)
    INSUFFICIENT_EVIDENCE ? pass through, sources cleared
```

---

## 10. Faithfulness gate

The faithfulness gate is implemented in `ClaimValidator.enforce()`:

| Input status | Valid citations? | Output status |
|---|---|---|
| SUPPORTED | Yes | SUPPORTED |
| SUPPORTED | No / hallucinated | UNSUPPORTED |
| PARTIALLY_SUPPORTED | Any | PARTIALLY_SUPPORTED (valid only) |
| CONFLICTING | Any | CONFLICTING (valid only) |
| UNSUPPORTED | N/A | UNSUPPORTED |
| INSUFFICIENT_EVIDENCE | N/A | INSUFFICIENT_EVIDENCE |

The overall response trust label is derived by `overall_trust_status()`:

| Claim set | Trust label |
|---|---|
| All SUPPORTED | `SUPPORTED` |
| Mix of SUPPORTED + UNSUPPORTED | `PARTIALLY_SUPPORTED` |
| Any CONFLICTING | `CONFLICTING` |
| All INSUFFICIENT_EVIDENCE | `INSUFFICIENT_EVIDENCE` |

---

## 11. Security considerations

- **Authorization happens before retrieval.**  The LLM never receives evidence
  it is not authorised to see.  There is no "retrieve everything, ask the LLM
  to ignore restricted parts" pattern anywhere in the codebase.
- **Evidence is untrusted data.**  All evidence text is HTML-escaped before
  being injected into the prompt.  The system prompt repeats this constraint.
- **The LLM cannot call tools or mutate state.**  It has no function-calling
  configuration; it only generates text.
- **Citations are validated post-generation.**  Hallucinated document IDs are
  detected and the claim is demoted to UNSUPPORTED before the response is
  returned.
- **No secrets in prompts.**  The system prompt and evidence context contain no
  API keys, tokens, database credentials, or KMS material.
- **No case data leaves the host.**  Ollama runs locally.  `QwenOllamaProvider`
  posts only to `OLLAMA_BASE_URL`; it never contacts external endpoints.
- **Error responses are sanitised.**  `LLMProviderError` messages are
  user-facing strings only.  Python stack traces are never propagated to API
  responses.

---

## 12. Testing

```bash
cd apps/api
pytest tests/test_llm_integration.py -v
```

No Ollama instance is required.  All T01?T10 tests run in SQLite demo mode;
Ollama-specific tests use mocks.

| Test | What it verifies |
|---|---|
| T01 | Supported question ? answer + valid citation |
| T02 | Out-of-evidence question ? INSUFFICIENT_EVIDENCE |
| T03 | Restricted witness excluded from external expert context |
| T04 | Contradictions surfaced neutrally, no truth judgment |
| T05 | Nonexistent entity ? INSUFFICIENT_EVIDENCE, no hallucination |
| T06 | Every citation in the brief points to an authorised source |
| T07 | Case A retrieval does not return Case B chunks |
| T08 | External expert clearance filters chunks before retrieval |
| T09 | Ollama unreachable ? HTTP 503, no stack trace |
| T10 | Tampered document hash detected independently of LLM |

Additional unit tests cover: `_parse_llm_output` (valid, hallucinated ID,
malformed JSON, INSUFFICIENT_EVIDENCE), `ClaimValidator`, `overall_trust_status`,
`PromptBuilder` (injection escaping, source numbering), query classifier,
`QwenOllamaProvider` (empty URL rejection, thinking-token stripping, health
check with unreachable server), and the `/health/llm` endpoint in demo mode.

Run the complete existing suite to confirm nothing regressed:

```bash
pytest tests/ -v
```

---

## 13. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `GET /health/llm` ? `"status": "unhealthy"` | Ollama not running | `ollama serve` |
| `"Model 'qwen3:8b' not found"` | Model not pulled | `ollama pull qwen3:8b` |
| 503 on `/ask` inside Docker | Container cannot reach host Ollama | Set `OLLAMA_BASE_URL=http://host.docker.internal:11434` in `.env` |
| Slow responses on CPU | 8B model is large | Reduce `LLM_MAX_TOKENS`; use `LLM_TEMPERATURE=0.1` |
| Claims all UNSUPPORTED | Document chunks not indexed | Run `make seed`; check `DocumentChunk` table is populated |
| `AIProviderError: no grounded claims` | Model returned empty JSON | Check Ollama logs: `ollama logs`; verify model is loaded |
| Frontend shows "Demo mode" badge | `LLM_PROVIDER` still `demo` | Set `LLM_PROVIDER=ollama` in `.env` and restart API |

---

## 14. How to run

```bash
# 1. Start Ollama on the host machine
ollama serve

# 2. Pull the model (once)
ollama pull qwen3:8b

# 3. Configure
cp .env.example .env
# Edit .env:
#   LLM_PROVIDER=ollama
#   OLLAMA_BASE_URL=http://localhost:11434
#   LLM_MODEL=qwen3:8b

# 4. Start the stack
make up
make migrate
make seed

# 5. Verify LLM connectivity
curl http://localhost:8000/api/v1/health/llm

# 6. Run all tests
cd apps/api && pytest tests/ -v
```

---

*Last updated: 2026-09-05 ? Qwen3-8B integration via Ollama.*
