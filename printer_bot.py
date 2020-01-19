#!/usr/bin/env python
# -*- coding: utf-8 -*-
import random
import yaml
import logging
import requests
import datetime
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

AFFIRMATIONS = [
    "WRRR-wrrr",
    "WRRRRRRRRRRR",
    "WRRR-wr-WRRR",
    "WRRRR *beep*",
    "wrr-WRR-wrr-WRR-wrr",
    "wrrr-WRRR",
]


class PrinterBot:

    def __init__(self):
        self.config = {}

    @staticmethod
    def get_affirmation():
        return random.choice(AFFIRMATIONS)

    def get_headers(self):
        return {"X-Api-Key": self.config['octoprint']['api_key']}

    def get_request(self, path):
        resp = requests.get(self.config['octoprint']['url'] + "/api/" + path, headers=self.get_headers())
        return resp.json()

    def has_permission(self, user_id):
        if "approved_users" in self.config:
            return user_id in self.config['approved_users']
        return True

    # Conversation handlers:
    def handle_status(self, bot, update):
        if not self.has_permission(update.message.from_user.id):
            update.message.reply_text(self.get_affirmation())
            return
        status = self.get_request("job")
        state = status['state']
        if "printing" in state.lower():
            print_file = status['job']['file']['display']
            progress = status['progress']['completion']
            time_left = status['progress']['printTimeLeft']

            formatted_time = None
            if time_left:
                formatted_time = str(datetime.timedelta(seconds=time_left))

            msg = "{}\n\n<b>{}</b>\n{}\n{:.2f}% complete\n{} remaining".format(
                self.get_affirmation(),
                state.strip(),
                print_file,
                progress,
                formatted_time or "??:??"
            )

            update.message.reply_text(msg, parse_mode="html")
        else:
            msg = "*{}*\n{}".format(
                state,
                self.get_affirmation()
            )
            update.message.reply_text(msg, parse_mode="markdown")

    def handle_message(self, bot, update):
        if not self.has_permission(update.message.from_user.id):
            update.message.reply_text(self.get_affirmation())
            return
        update.message.reply_text(self.get_affirmation())

    # Help command handler
    def handle_help(self, bot, update):
        """Send a message when the command /help is issued."""
        helptext = "WRRR-wrrr-WRRR-wrrr-wrp-wrp-wrp-WRRR-wrrr-WRRR"

        update.message.reply_text(helptext, parse_mode="Markdown")

    # Error handler
    def handle_error(self, bot, update, error):
        """Log Errors caused by Updates."""
        logger.warning('Update "%s" caused error "%s"', update, error)

    def run(self, opts):
        with open(opts.config, 'r') as configfile:
            config = yaml.load(configfile)
            self.config = config

        """Start the bot."""
        # Create the EventHandler and pass it your bot's token.
        updater = Updater(config['token'])

        # Get the dispatcher to register handlers
        dp = updater.dispatcher

        dp.add_handler(CommandHandler("status", self.handle_status))
        dp.add_handler(CommandHandler("help", self.handle_help))
        dp.add_handler(CommandHandler("start", self.handle_status))

        dp.add_error_handler(self.handle_error)

        dp.add_handler(MessageHandler(None, self.handle_message))

        # Start the Bot
        updater.start_polling()

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        updater.idle()


def main(opts):
    PrinterBot().run(opts)


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-c', '--config', dest='config', default='config.yml', type='string',
                      help="Path of configuration file")
    (opts, args) = parser.parse_args()
    main(opts)