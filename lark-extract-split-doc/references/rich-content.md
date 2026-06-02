# Rich-Content Materialization

Convert the immutable `source.xml` export into readable `source.md`. Preserve document order. Use Markdown when it is faithful; use HTML blocks when Markdown cannot represent the structure without loss.

## Standard Blocks

| Source content | Materialize in `source.md` |
|---|---|
| Paragraphs, headings, lists, quotes, code | Equivalent Markdown in original order |
| Native simple table | Markdown table |
| Native complex table with merged cells, nested blocks, or multiline structure | HTML `<table>` block |
| Formula | Original formula text or supported Markdown/HTML representation |
| Unsupported block | Visible blockquote stating its type plus an HTML comment with source metadata |

Do not summarize, polish, correct, or reorder source content.

## Images, Files, and Whiteboards

Download media referenced by `<img>`, `<image>`, `<source>`, `<file>`, or `<whiteboard>` blocks.

- Use the provided media URL directly when available.
- Otherwise run:

  ```bash
  lark-cli docs +media-download --token "<token>" --output "<output-directory>/assets/<stable-name>"
  ```

- For a whiteboard thumbnail run:

  ```bash
  lark-cli docs +media-download --type whiteboard --token "<token>" --output "<output-directory>/assets/<stable-name>"
  ```

Materialize images and whiteboard thumbnails as visible Markdown images. Materialize downloadable files as links. Keep token metadata in an adjacent HTML comment.

```markdown
![文档图片](assets/image-001.png)
<!-- lark-resource: type=image token=<token> -->

![画板预览](assets/whiteboard-001.png)
<!-- lark-resource: type=whiteboard token=<token> -->

[附件：skills.zip](assets/skills.zip)
<!-- lark-resource: type=file token=<token> -->
```

When writing numbered files under `split/`, adjust these links mechanically to `../assets/...`.

## Embedded Sheets

For `<sheet>` or `<cite file-type="sheets">`, extract the spreadsheet token and sheet ID. Read `$HOME/.agents/skills/lark-sheets/SKILL.md`, then use `sheets +info` and `sheets +read`.

Write a snapshot to `embedded/sheet-<sequence>-<sheet-id>.md`. Preserve formatted cell values, row order, and columns. Add a local link and source metadata at the original block location. Inline a readable Markdown or HTML table when reasonably sized.

```markdown
### 嵌入电子表格：<name>

[查看完整快照](embedded/sheet-001-<sheet-id>.md)

| ... |
|---|
| ... |

<!-- lark-resource: type=sheet token=<token> sheet-id=<sheet-id> -->
```

If a sheet is too large for a useful inline view, keep a small labeled preview inline and write the complete paged snapshot to `embedded/`. Record the preview limit in `manifest.md`.

## Embedded Base Tables

For `<bitable>` or `<cite file-type="bitable">`, extract the Base token and table ID. Read `$HOME/.agents/skills/lark-base/SKILL.md` and its record-read guidance. Use `base +table-list`, `base +field-list`, and serial paginated `base +record-list` calls as needed.

Write `embedded/base-<sequence>-<table-id>.md`. Keep a visible local link at the original location and inline a readable preview or full table when reasonably sized. Preserve table name, field names, row order, and pagination limitations in `manifest.md`.

## Referenced Blocks

For `<synced_reference src-token="..." src-block-id="...">`, fetch the referenced block or section with `docs +fetch --api-version v2`, materialize it as a labeled quote or HTML `<details>` block, and preserve the source token and block ID.

For cited documents that cannot or should not be expanded, keep a visible link or placeholder and source metadata.

## Split Visibility

Markdown has no portable transclusion mechanism. To keep data visible after splitting:

- Keep downloaded images embedded with adjusted local paths.
- Keep native tables inline.
- Keep a compact inline preview for large Sheet or Base snapshots and a relative link to the complete local snapshot.
- Copy no resource into multiple numbered files unless the original materialized source contains multiple references to it.

