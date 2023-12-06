#!/usr/bin/env bash

bitrate=48

while [[ $# -gt 0 ]]; do
	case $1 in
		--bitrate)
			bitrate=$2
			shift
			;;
		*)
			echo "Unknown argument: $1"
			exit 1
			;;
	esac
	shift
done

files=()
readarray -d '' files < <(find . -type f -not -iname "*.opus" -print0)

convert() {
	file="$1"
	bitrate="$2"
	name="$(basename "$file")"
	suffix="${name##*.}"
	name="$(slugify "$(basename "$name" "$suffix")").opus"
	outputdir=""
	path="$file"
	while [ "$path" != '.' ]; do
		dir=$(dirname "$path")
		outputdir="$(slugify "$(basename "$dir")")/$outputdir"
		path="$dir"
	done
	mkdir -p ".$outputdir"
	ffmpeg -hide_banner -loglevel panic -i "$file" -c:a libopus -b:a "$bitrate"k -frame_duration 60 ".$outputdir$name" && rm "$file"

}
export -f convert

parallel -j "$(nproc)" --bar "convert {} $bitrate" ::: "${files[@]}"
