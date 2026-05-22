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

## 5. Fetch a document

```bash
lark-cli docs +fetch --api-version v2 --doc "<doc-url-or-token>"
```

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
