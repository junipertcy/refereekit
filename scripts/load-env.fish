# Load .env into the current fish shell.
#
#     source scripts/load-env.fish [path-to-env]
#
# Must be sourced, not executed: a child process cannot set variables in its
# parent, so running this as a script does nothing observable.
#
# fish cannot `source` a KEY=value file directly, which is why this exists at
# all rather than the one-liner bash and zsh get.

set -l _envfile .env
if set -q argv[1]
    set _envfile $argv[1]
end

if not test -f $_envfile
    echo "load-env: $_envfile not found; run: cp .env.template .env" >&2
    return 1
end

set -l _loaded
for _line in (cat $_envfile)
    set _line (string trim -- $_line)
    if test -z "$_line"; or string match -qr '^#' -- $_line
        continue
    end
    # -m1 so a password containing '=' keeps everything after the first one.
    set -l _pair (string split -m1 '=' -- $_line)
    if test (count $_pair) -lt 2
        continue
    end
    set -l _key (string trim -- $_pair[1])
    set -l _val (string trim -- $_pair[2])
    set _val (string replace -r '^"(.*)"$' '$1' -- $_val)
    set _val (string replace -r "^'(.*)'\$" '$1' -- $_val)
    # A blank value is left unset rather than exported empty. refereekit
    # rejects an empty OPENREVIEW_USERNAME exactly as it rejects a missing
    # one, and an exported empty is the harder of the two to notice.
    if test -z "$_val"
        continue
    end
    set -gx $_key $_val
    set -a _loaded $_key
end

# Names only. Printing a value here would put the password on the screen and
# into the scrollback of every session that loads it.
echo "load-env: exported "(count $_loaded)" variable(s): $_loaded"
