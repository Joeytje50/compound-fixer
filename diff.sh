git diff --no-index --word-diff "$1txt" "$1out"
#diff -W $(tput cols) "$1txt" "$1out" -U3 | colordiff
echo ""
