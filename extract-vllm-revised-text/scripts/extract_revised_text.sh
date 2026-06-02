#!/usr/bin/env bash
set -u

input_dir=${1:-./reviewed}
input_dir=${input_dir%/}
output_dir=${2:-"$(dirname "$input_dir")/output"}
output_dir=${output_dir%/}

if [[ ! -d "$input_dir" ]]; then
  printf 'Error: input directory does not exist: %s\n' "$input_dir" >&2
  exit 2
fi

input_path=$(realpath "$input_dir")
output_path=$(realpath -m "$output_dir")
if [[ "$input_path" == "$output_path" ]]; then
  printf 'Error: output directory must differ from input directory: %s\n' "$output_dir" >&2
  exit 2
fi

mkdir -p "$output_dir"

mapfile -t files < <(find "$input_dir" -maxdepth 1 -type f -name '*.md' -printf '%f\n' | sort)
total=${#files[@]}
if [[ $total -eq 0 ]]; then
  printf 'Error: no Markdown files found in input directory: %s\n' "$input_dir" >&2
  exit 2
fi

success=0
failed=0

for file in "${files[@]}"; do
  source_file="$input_dir/$file"
  output_file="$output_dir/$file"
  temp_file=$(mktemp "$output_dir/.extract-revised-text.XXXXXX")

  awk '
    BEGIN {
      in_section = 0
      found = 0
    }
    /^##[[:space:]]+Revised Text[[:space:]]*$/ {
      if (found) {
        exit
      }
      found = 1
      in_section = 1
      next
    }
    in_section && /^##[[:space:]]+/ {
      exit
    }
    in_section {
      lines[++count] = $0
    }
    END {
      if (!found) {
        exit 3
      }
      start = 1
      while (start <= count && lines[start] ~ /^[[:space:]]*$/) {
        start++
      }
      end = count
      while (end >= start && lines[end] ~ /^[[:space:]]*$/) {
        end--
      }
      for (i = start; i <= end; i++) {
        print lines[i]
      }
      if (start <= end) {
        print ""
      }
    }
  ' "$source_file" >"$temp_file"
  status=$?

  if [[ $status -eq 0 && -s "$temp_file" ]]; then
    mv "$temp_file" "$output_file"
    printf 'OK %s\n' "$file"
    success=$((success + 1))
  else
    rm -f "$temp_file"
    rm -f "$output_file"
    printf 'FAILED %s: missing or empty ## Revised Text section\n' "$file" >&2
    failed=$((failed + 1))
  fi
done

printf '\nTotal: %s\n' "$total"
printf 'Success: %s\n' "$success"
printf 'Failed: %s\n' "$failed"

if [[ $failed -ne 0 ]]; then
  exit 1
fi
