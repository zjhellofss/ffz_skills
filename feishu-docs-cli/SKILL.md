---
name: feishu-docs-cli
description: Use when the user wants to create, update, fetch, search, or troubleshoot Feishu documents with `lark-cli`, especially for cloud docs, Drive Markdown files, wiki pages, document media insertion, or document authorization and scope issues.
---

# Feishu Docs CLI

## Overview

Operate Feishu documents from the terminal with `lark-cli`. Use this skill when the task is about creating cloud docs, updating existing docs, fetching document content, uploading Markdown into Feishu, or diagnosing auth and scope failures around document operations.

Read [references/recipes.md](references/recipes.md) for command patterns and validated examples.

## When To Use

Use this skill when the user asks for any of the following:

- Create a Feishu cloud doc from text or Markdown
- Update an existing Feishu doc with generated content
- Fetch or inspect an existing document
- Search docs or wiki content
- Upload or overwrite a Drive-native Markdown file
- Insert images or attachments into a Feishu document
- Troubleshoot `lark-cli` auth, scope, or parameter issues for doc operations

Do not use this skill for general Feishu messaging, calendar, Base, or approval workflows unless the document step is the main task.

## Workflow

1. Check local readiness first.
   Run `lark-cli auth status` and confirm the active identity is usable. For doc creation, verify required scopes before attempting writes.

2. Pick the right document surface.
   Use `docs` for Feishu cloud docs.
   Use `markdown` for Drive-native Markdown files.
   Use `wiki` only when the target is explicitly a knowledge-base node or wiki space.

3. Prefer direct execution over explanation.
   If the user wants a document created or updated, generate the content, execute the command, and return the resulting URL.

4. Treat permission errors as an expected workflow.
   If `missing_scope` appears, request only the missing scopes with `lark-cli auth login --no-wait --json --scope "..."`, return the raw verification URL to the user, then resume later with `lark-cli auth login --device-code ...` after the user confirms authorization.

5. Keep content in local files when the document is substantial.
   Draft the Markdown locally first, then upload or push it to Feishu. This makes retries, diffs, and follow-up edits easier.

## Command Selection

### Create a Feishu cloud doc

Use `lark-cli docs +create` when the output should be a normal Feishu doc with a shareable docx URL.

Important: in this environment, `docs +create --help` may show `--markdown`, but the working invocation is:

```bash
lark-cli docs +create --api-version v2 --doc-format markdown --content "$CONTENT"
```

For larger content, compose a local `.md` file and pass its contents through the shell rather than relying on `@/absolute/path` expansion.

### Update an existing Feishu cloud doc

Use `lark-cli docs +update --api-version v2 --doc <url-or-token>`.

Choose the smallest correct update mode:

- `append` for adding a section
- `overwrite` or `replace_all` when replacing the whole document
- `insert_before` or `insert_after` when targeting a known section

If precise placement matters, use `--selection-by-title` or `--selection-with-ellipsis`.

### Fetch a Feishu cloud doc

Use `lark-cli docs +fetch --api-version v2 --doc <url-or-token>`.

Fetch before editing when the user asks to revise, extend, or surgically patch an existing document.

### Use Drive-native Markdown

Use `lark-cli markdown +create`, `+fetch`, `+overwrite`, or `+patch` when the user explicitly wants a Drive Markdown file rather than a docx document.

This is useful for:

- syncing local notes into Feishu Drive
- storing repo-like Markdown with fewer formatting transformations
- diff-friendly content workflows

### Search docs and wiki

Use `lark-cli docs +search` when the user needs to locate an existing document before updating it.

## Auth And Scope Rules

Check scopes before retries. Common scopes for document work include:

- `docx:document:create` for cloud doc creation
- `drive:file:upload` for Markdown upload or document media upload
- `drive:drive.metadata:readonly` for Drive metadata access

When auth is missing:

1. Start device auth with `--no-wait --json`
2. Return the raw `verification_url` exactly as emitted
3. Wait for the user to confirm authorization
4. Resume with `--device-code`
5. Retry the original document command

Do not rewrite or wrap the verification URL as a Markdown link.

## Output Expectations

When this skill is used for execution, the response should usually include:

- what was created or updated
- the resulting Feishu document URL
- any auth or scope change that was required
- the local source file path when a draft was written before upload

When blocked, report the exact missing scope or validation issue and the next command needed to unblock it.

## Notes

- Prefer `--api-version v2` for `docs` operations.
- If a file reference is rejected because it is absolute, change to the target directory and use a relative path.
- If the CLI help text conflicts with runtime behavior, trust validated command recipes from [references/recipes.md](references/recipes.md) and mention the discrepancy in the result.
