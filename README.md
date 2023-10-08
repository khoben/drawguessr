
`pybabel extract --input-dirs=. --ignore-dirs=venv -o ./locales/messages.pot`
`pybabel update -d locales -D messages -i locales/messages.pot`
`pybabel compile -d locales -D messages`

`pybabel init -i locales/messages.pot -d locales -D messages -l en`

