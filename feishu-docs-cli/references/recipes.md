# Feishu Docs CLI Recipes

These command recipes are intended for `feishu-docs-cli`.

## 1. Check auth status

```bash
lark-cli auth status
```

Use this first for any write operation.

## 2. Request missing document scopes

```bash
lark-cli auth login --no-wait --json --scope "docx:document:create drive:file:upload drive:drive.metadata:readonly"
```

After the user completes browser authorization:

```bash
lark-cli auth login --device-code <device_code>
```

For existing doc cleanup or revision tasks, you often need separate docx scopes:

- fetch/read: `docx:document:readonly`
- create new doc: `docx:document:create`
- update existing doc: `docx:document:write_only`

Request only the missing scope at the point of failure. Do not assume one docx scope implies the others.

## 3. Create a Feishu cloud doc from a local Markdown file

This pattern is validated in the current environment:

```bash
CONTENT=$(cat ./example.md)
lark-cli docs +create --api-version v2 --doc-format markdown --content "$CONTENT"
```

Why this pattern:

- `docs +create --help` may advertise `--markdown`, but runtime expects `--doc-format markdown --content`
- `@/absolute/path` may fail validation

Expected result shape:

```json
{
  "ok": true,
  "data": {
    "document": {
      "document_id": "...",
      "url": "https://...feishu.cn/docx/..."
    }
  }
}
```

## 4. Update an existing Feishu cloud doc

Append:

```bash
CONTENT=$(cat ./appendix.md)
lark-cli docs +update --api-version v2 --doc "<doc-url-or-token>" --mode append --markdown "$CONTENT"
```

Replace all:

```bash
CONTENT=$(cat ./full.md)
lark-cli docs +update --api-version v2 --doc "<doc-url-or-token>" --mode replace_all --markdown "$CONTENT"
```

Important runtime caveat validated in the current environment:

- `lark-cli docs +update --help` shows `--mode` plus `--markdown`
- on `lark-cli version 1.0.38`, runtime may still fail with:

```json
{
  "ok": false,
  "error": {
    "type": "validation",
    "message": "--command is required"
  }
}
```

Treat this as a CLI behavior mismatch, not as a Markdown-content issue.

Recommended fallback for "整理现有文档":

1. Fetch the original doc
2. Draft the cleaned Markdown locally
3. Attempt `docs +update` once
4. If `--command is required` appears, create a new cleaned cloud doc instead and return the new URL

Validated fallback create flow:

```bash
CONTENT=$(cat ./cleaned.md)
lark-cli docs +create --api-version v2 --doc-format markdown --content "$CONTENT"
```

## 5. Fetch a document

```bash
lark-cli docs +fetch --api-version v2 --doc "<doc-url-or-token>"
```

If this fails with `missing_scope`, request:

- `docx:document:readonly`

## 6. Create a Drive-native Markdown file

```bash
lark-cli markdown +create --name "notes.md" --file ./notes.md
```

If this fails with missing scopes, request:

- `drive:file:upload`
- `drive:drive.metadata:readonly`

## 7. Search docs or wiki

```bash
lark-cli docs +search --query "周报"
```

Use search before update when the user only knows the title, not the URL.

## 8. Insert media into a doc

```bash
lark-cli docs +media-insert --doc "<doc-url-or-token>" --file ./image.png
```

Use this when the user wants images or attachments inserted into a cloud doc rather than linked separately.
