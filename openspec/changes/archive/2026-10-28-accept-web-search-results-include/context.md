# Web-search include compatibility

Official reference, checked on 2026-10-28: [Responses / ResponseIncludable](https://developers.openai.com/api/reference/typescript/resources/responses). It lists `web_search_call.results` separately from `web_search_call.action.sources`; these are not aliases and must not be silently rewritten into each other.

The actual desktop request at 15:44:55 (China time), request ID `<request-id>`, was rejected by local Pydantic validation on `include`. The diagnostic did not log the enum value, so this patch addresses a verified compatibility gap without claiming that the original request contained that exact enum.

Example accepted include list after the fix:

```json
["web_search_call.results", "web_search_call.action.sources", "reasoning.encrypted_content"]
```

The patch does not drop include entries to make requests pass, accept arbitrary values, or disable validation. Existing model-source capability filtering remains authoritative if a provider cannot execute a hosted tool. All automated upstreams are stubs; production acceptance still needs a user replay. The user approved immediate activation after passing tests, keeping the complete startup database integrity check.

## Verification and activation

- Before the fix, all four new native/v1 schema cases failed specifically on `web_search_call.results` with `include/value_error`.
- After the fix, 304 tests passed across the full request-schema and OpenAI compatibility suites, private diagnostic tests, passthrough rejection tests, and selected WebSocket forwarding/rejection cases. The sole warning was an existing Starlette/AnyIO deprecation.
- Ruff formatting/lint, targeted type checks, and strict OpenSpec change validation passed. The normative requirement was synced to the main capability.
- Runtime backup: `<data>/service/backups/web-search-include-20261028-155604/requests.py`.
- The deployed file exactly matched the tested source: SHA-256 `A10D144E7AF384EB77AA3AE5BEAC78474E5B99D8AC8A9D52374D3C8096DFFF1C`.
- The approved restart stopped the old process at 15:57:36 and startup completed at 15:57:47 (China time). The existing startup logic recognized a recorded clean shutdown and automatically skipped a redundant `quick_check`; no integrity-check setting or sidecar was manually changed. `/health` returned `{"status":"ok"}`.
- At 16:00:57, two native Responses probes used only the scoped existing test key, loaded privately from the read-only token store without printing or regenerating it. Both deliberately included invalid `truncation` so no request could reach upstream or billing. With `web_search_call.results`, the error moved to `param=truncation` (request `<request-id>`), proving the running server accepted the new include. The unsupported-include control still returned `param=include` (request `<request-id>`).
- The user's 16:04:39 replay still failed `include/value_error` under request ID `<request-id>`. Thus the documented compatibility gap is fixed, but the original weather incident is not resolved. The user authorized narrowly expanded metadata diagnostics in `trace-rejected-include-options`; no further allowlist additions should be guessed.
