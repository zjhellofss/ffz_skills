#!/usr/bin/env bash
set -u

input_dir=${1:-./split}
input_dir=${input_dir%/}
output_dir=${2:-"$(dirname "$input_dir")/reviewed"}
output_dir=${output_dir%/}
log_dir="$output_dir/.logs"

if ! command -v codex >/dev/null 2>&1; then
  printf 'Error: codex is not available on PATH.\n' >&2
  exit 2
fi

if [[ ! -d "$input_dir" ]]; then
  printf 'Error: input directory does not exist: %s\n' "$input_dir" >&2
  exit 2
fi

mkdir -p "$output_dir" "$log_dir"

mapfile -t files < <(find "$input_dir" -maxdepth 1 -type f -name '*.md' -printf '%f\n' | sort)
total=${#files[@]}
success=0
failed=0

for file in "${files[@]}"; do
  source_file="$input_dir/$file"
  output_file="$output_dir/$file"
  log_file="$log_dir/$file.log"

  {
    printf '%s\n\n' \
      '使用 $review-vllm-courseware skill 优化当前这一个独立文件。严格遵循该 skill 的输出结构。不要读取或分析输入目录下的其他文档。输出仅包含最终 Markdown 结果，不要附加过程说明。' \
      '本次输入只包含当前文件名和当前文件内容。请使用本地安装的 vLLM 源码核对技术细节。若 rg 不可用，请使用 grep、find、sed 等工具。' \
      "文件名：$file" \
      '文件内容：'
    cat "$source_file"
  } | codex -a never exec - \
      --ephemeral \
      --skip-git-repo-check \
      -s danger-full-access \
      -C "$input_dir" \
      -o "$output_file" >"$log_file" 2>&1
  status=$?

  if [[ $status -eq 0 && -s "$output_file" ]]; then
    printf '✓ %s\n' "$file"
    success=$((success + 1))
  else
    printf '✗ %s\n' "$file"
    failed=$((failed + 1))
  fi
done

printf '\nTotal: %s\n' "$total"
printf 'Success: %s\n' "$success"
printf 'Failed: %s\n' "$failed"

if [[ $failed -ne 0 ]]; then
  exit 1
fi
