# BNETDocs Community Bot (BCB)
[![Build Status](https://travis-ci.org/BNETDocs/community-bot.svg?branch=develop)](https://travis-ci.org/BNETDocs/community-bot)

A WIP community-built bot written in Python (3.6) for the classic Battle.net v1 chat platform.

Join us on Discord: https://discordapp.com/invite/u87WVeu

## API Keys
The classic Battle.net chat API requires a key to use. You can obtain one by logging in to one of the classic games (StarCraft, Diablo 2, or WarCraft 3) and going to your preferred clan or op channel and using the /register-bot command. You will need to have an email registered to your account and click the activation link in the email.

Running the command again will send you a new key and invalidate the old one.

## Installing the bot (and running for the first time)
 - Download and install [Python v3.6.7](https://www.python.org/downloads/release/python-367/)
 - Clone or download the community-bot repository. If you downloaded a zip/archive, extract the contents.
 - Open a console and navigate to the directory with the downloaded files. You may want to setup a [python virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtualenv/).
 - Run the setup script with the command `python setup.py install` - this will install the required dependencies
 - Use the command `python -m bnetbot --apikey=<your api key>` to run the bot and create a new profile with your API key. If you don't want your API key in the console log you can copy the `config.example.json` file to `config.json` and insert your API key there.
 
## Running the bot normally
Once you've run the bot with the --apikey argument or manually created a profile, you can run the bot normally by using `python -m bnetbot`, which will pull your settings from the default config file.

Optional command-line arguments:
 - `--config=/path/to/config.json`: specifies an alternate path to your config file
 - `--debug`: enables printing of debug messages
 - `--apikey=abcdefg`: creates a new profile with the specified API key

## Adding users to the bot
By default the bot comes with 3 internal groups:
 - `admin`: access to all commands and can add/remove other users
 - `moderator`: access to channel moderation functions (ban, kick, etc)
 - `user`: access to other general purpose commands
 
To add a user to the bot, use the following command from the bot console: `/perms group <group> add <user>`.
For example, to add the user 'bob' to the 'admin' group you'll use: `/perms group admin add bob`.

To remove a user from the bot, use the command: `/perms user <user> remove`.

These commands can also be done by any user in the admin group. Commands can be used in the channel or through whispers, using the trigger `!` instead of the slash `/`.
